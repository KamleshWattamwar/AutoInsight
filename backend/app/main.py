import logging
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db, models
from app.services.analyzer import analyze_csv
from app.services.loader import load_csv

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

# Temporary: status and result still read this until step 5.
JOBS: dict[str, dict] = {}


def _dataset_path(dataset_id: str) -> Path:
    if not UUID_RE.match(dataset_id):
        raise HTTPException(status_code=400, detail="Invalid dataset id")
    path = UPLOAD_DIR / f"{dataset_id}.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dataset not found")
    return path


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
        logger.exception("Analysis failed for report %s", report_id)  # full traceback in server log only
        session.rollback()
        report = session.get(models.Report, report_id)
        report.status = "failed"
        report.error = "Analysis failed"  # generic message, no internals leaked (fixes N3)
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

    # Row is added only after validation, so rejected files leave no DB record.
    session.add(
        models.Dataset(
            id=dataset_id,
            original_filename=(file.filename or "")[:255],  # metadata only, never a path
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

    # Duplicate-run guard, now a DB query instead of the JOBS dict.
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

    # Pass the id, never the session.
    background_tasks.add_task(_run_analysis, report.id, path)
    return {"dataset_id": dataset_id, "report_id": report.id, "status": "pending"}


@app.get("/datasets/{dataset_id}/status")
def analysis_status(dataset_id: str):
    _dataset_path(dataset_id)
    job = JOBS.get(dataset_id, {"status": "not_started"})
    return {"dataset_id": dataset_id, "status": job["status"], "error": job.get("error")}


@app.get("/datasets/{dataset_id}/result")
def analysis_result(dataset_id: str):
    _dataset_path(dataset_id)
    job = JOBS.get(dataset_id, {"status": "not_started"})
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail=f"Analysis is {job['status']}")
    return job["result"]