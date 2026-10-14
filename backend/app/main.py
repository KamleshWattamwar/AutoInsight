import re
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.services.analyzer import analyze_csv
from app.services.loader import load_csv

app = FastAPI(title="AutoInsight API", version="0.1.0")

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

# In-memory job store: {dataset_id: {"status", "result"?, "error"?}}.

JOBS: dict[str, dict] = {}


def _dataset_path(dataset_id: str) -> Path:
    if not UUID_RE.match(dataset_id):
        raise HTTPException(status_code=400, detail="Invalid dataset id")
    path = UPLOAD_DIR / f"{dataset_id}.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dataset not found")
    return path


def _run_analysis(dataset_id: str, path: Path) -> None:
    JOBS[dataset_id] = {"status": "running"}
    try:
        JOBS[dataset_id] = {"status": "done", "result": analyze_csv(path)}
    except Exception as e:
        JOBS[dataset_id] = {"status": "failed", "error": str(e)}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)):
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

    return {"dataset_id": dataset_id, "rows": len(df), "columns": len(df.columns)}


@app.post("/datasets/{dataset_id}/analyze", status_code=202)
def analyze_dataset(dataset_id: str, background_tasks: BackgroundTasks):
    path = _dataset_path(dataset_id)
    if JOBS.get(dataset_id, {}).get("status") not in ("pending", "running"):
        JOBS[dataset_id] = {"status": "pending"}
        background_tasks.add_task(_run_analysis, dataset_id, path)
    return {"dataset_id": dataset_id, "status": JOBS[dataset_id]["status"]}


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