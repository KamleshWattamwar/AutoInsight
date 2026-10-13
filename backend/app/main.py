import re
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.services.analyzer import analyze_csv
from app.services.loader import load_csv

app = FastAPI(title="AutoInsight API", version="0.1.0")

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


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


@app.post("/datasets/{dataset_id}/analyze")
def analyze_dataset(dataset_id: str):
    if not UUID_RE.match(dataset_id):
        raise HTTPException(status_code=400, detail="Invalid dataset id")

    path = UPLOAD_DIR / f"{dataset_id}.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dataset not found")

    try:
        return analyze_csv(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))