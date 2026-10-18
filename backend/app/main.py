import logging
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db, models
from app.services.analyzer import analyze_csv
from app.services.llm import gemini_generate
from app.services.loader import load_csv
from app.services.narrative import generate_narrative

from app.services import charts
from app.services.loader import infer_types, load_csv

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.Base.metadata.create_all(db.engine)  # creates missing tables at startup
    yield


app = FastAPI(title="AutoInsight API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _check_uuid(value: str, what: str) -> None:
    if not UUID_RE.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {what} id")


def _dataset_path(dataset_id: str) -> Path:
    _check_uuid(dataset_id, "dataset")
    path = UPLOAD_DIR / f"{dataset_id}.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dataset not found")
    return path


def _latest_report(session: Session, dataset_id: str) -> models.Report | None:
    return session.scalars(
        select(models.Report)
        .where(models.Report.dataset_id == dataset_id)
        .order_by(models.Report.created_at.desc())
        .limit(1)
    ).first()


def _run_analysis(report_id: str, path: Path) -> None:
    # Own session: the request's session is closed once the response is sent.
    session = db.SessionLocal()
    try:
        report = session.get(models.Report, report_id)
        report.status = "running"
        session.commit()

        report.result = analyze_csv(path)  # whole new dict, never edited in place
        report.status = "done"
        report.finished_at = datetime.now(timezone.utc)
        session.commit()
    except Exception:
        logger.exception("Analysis failed for report %s", report_id)
        session.rollback()
        report = session.get(models.Report, report_id)
        report.status = "failed"
        report.error = "Analysis failed"
        report.finished_at = datetime.now(timezone.utc)
        session.commit()
    finally:
        session.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/datasets/upload")
async def upload_dataset(
    file: UploadFile = File(...), session: Session = Depends(db.get_db)
):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are allowed")

    dataset_id = str(uuid.uuid4())
    path = UPLOAD_DIR / f"{dataset_id}.csv"

    size = 0
    too_big = False
    with path.open("wb") as out:
        while chunk := await file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                too_big = True
                break
            out.write(chunk)

    if too_big:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    try:
        df = load_csv(path)
    except ValueError as e:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))

    session.add(
        models.Dataset(
            id=dataset_id,
            original_filename=(file.filename or "")[:255],
            stored_path=str(path),
            rows=len(df),
            columns=len(df.columns),
        )
    )
    session.commit()

    return {"dataset_id": dataset_id, "rows": len(df), "columns": len(df.columns)}


@app.post("/datasets/{dataset_id}/analyze", status_code=202)
def analyze_dataset(
    dataset_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(db.get_db),
):
    path = _dataset_path(dataset_id)

    active = session.scalars(
        select(models.Report).where(
            models.Report.dataset_id == dataset_id,
            models.Report.status.in_(("pending", "running")),
        )
    ).first()
    if active:
        return {"dataset_id": dataset_id, "report_id": active.id, "status": active.status}

    report = models.Report(id=str(uuid.uuid4()), dataset_id=dataset_id, status="pending")
    session.add(report)
    session.commit()

    background_tasks.add_task(_run_analysis, report.id, path)
    return {"dataset_id": dataset_id, "report_id": report.id, "status": "pending"}


@app.get("/datasets/{dataset_id}/status")
def analysis_status(dataset_id: str, session: Session = Depends(db.get_db)):
    _dataset_path(dataset_id)
    report = _latest_report(session, dataset_id)
    if report is None:
        return {"dataset_id": dataset_id, "status": "not_started", "error": None}
    return {"dataset_id": dataset_id, "status": report.status, "error": report.error}


@app.get("/datasets/{dataset_id}/result")
def analysis_result(dataset_id: str, session: Session = Depends(db.get_db)):
    _dataset_path(dataset_id)
    report = _latest_report(session, dataset_id)
    status = report.status if report else "not_started"
    if status != "done":
        raise HTTPException(status_code=409, detail=f"Analysis is {status}")
    return report.result


@app.get("/reports/{report_id}")
def get_report(report_id: str, session: Session = Depends(db.get_db)):
    _check_uuid(report_id, "report")
    report = session.get(models.Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "report_id": report.id,
        "dataset_id": report.dataset_id,
        "status": report.status,
        "error": report.error,
        "created_at": report.created_at,
        "finished_at": report.finished_at,
        "result": report.result if report.status == "done" else None,
        "narrative": report.narrative,
    }


@app.post("/reports/{report_id}/narrative")
def create_narrative(report_id: str, session: Session = Depends(db.get_db)):
    """Generate (or regenerate) the plain-English narrative for a finished report.
    Never fails because of the LLM: bad output or an outage gives the rule-based text."""
    _check_uuid(report_id, "report")
    report = session.get(models.Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != "done":
        raise HTTPException(status_code=409, detail=f"Analysis is {report.status}")

    # gemini_generate is looked up here at call time, so tests can patch main.gemini_generate
    report.narrative = generate_narrative(report.result, gemini_generate)
    session.commit()
    return {"report_id": report.id, "narrative": report.narrative}


@app.get("/datasets")
def list_datasets(
    limit: int = Query(50, ge=1, le=200), session: Session = Depends(db.get_db)
):
    rows = session.scalars(
        select(models.Dataset).order_by(models.Dataset.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "dataset_id": d.id,
            "original_filename": d.original_filename,
            "rows": d.rows,
            "columns": d.columns,
            "created_at": d.created_at,
        }
        for d in rows
    ]


@app.get("/reports")
def list_reports(
    dataset_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(db.get_db),
):
    query = select(models.Report).order_by(models.Report.created_at.desc()).limit(limit)
    if dataset_id is not None:
        _check_uuid(dataset_id, "dataset")
        query = query.where(models.Report.dataset_id == dataset_id)
    return [
        {
            "report_id": r.id,
            "dataset_id": r.dataset_id,
            "status": r.status,
            "error": r.error,
            "created_at": r.created_at,
            "finished_at": r.finished_at,
        }
        for r in session.scalars(query).all()
    ]

@app.get("/datasets/{dataset_id}/charts")
def get_chart(
    dataset_id: str,
    chart_type: str = Query(..., alias="type"),
    columns: list[str] = Query(default=[]),  # repeat the param: ?columns=a&columns=b
    bins: int = Query(20, ge=1, le=charts.MAX_BINS),
    top: int = Query(10, ge=1, le=charts.MAX_TOP),
    session: Session = Depends(db.get_db),
):
    """Aggregated chart data for one dataset. Never returns raw rows."""
    path = _dataset_path(dataset_id)

    if chart_type == "heatmap":  # read from the stored analysis, no CSV needed
        report = _latest_report(session, dataset_id)
        if report is None or report.status != "done":
            status = report.status if report else "not_started"
            raise HTTPException(status_code=409, detail=f"Analysis is {status}")
        return charts.heatmap(report.result["correlations"]["matrix"])

    df, types = infer_types(load_csv(path))  # reloaded per request, no cache
    try:
        return charts.build_chart(df, types, chart_type, columns, bins=bins, top=top)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))