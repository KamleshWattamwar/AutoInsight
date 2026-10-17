import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import db, main, models

CSV = b"age,city\n25,Pune\n30,Mumbai\n35,Pune\n40,Delhi\n"
UNKNOWN_ID = "123e4567-e89b-42d3-a456-426614174000"
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://autoinsight:autoinsight@localhost:5432/autoinsight_test",
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path)

    engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
    # Safety: this fixture drops all tables, so it must never touch the real database.
    assert engine.url.database.endswith("_test"), "Tests must use a *_test database"

    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", sessionmaker(bind=engine, autoflush=False))

    db.Base.metadata.drop_all(engine)  # clean start, even if a past run crashed
    db.Base.metadata.create_all(engine)

    with TestClient(main.app) as c:
        yield c

    db.Base.metadata.drop_all(engine)
    engine.dispose()


def upload(client, name="data.csv", content=CSV):
    return client.post("/datasets/upload", files={"file": (name, content)})


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("name, content", [("notes.txt", CSV), ("data.csv", b"")])
def test_upload_rejects_bad_files(client, name, content):
    assert upload(client, name, content).status_code == 400


def test_upload_then_analyze(client):
    body = upload(client).json()
    assert (body["rows"], body["columns"]) == (4, 2)
    dataset_id = body["dataset_id"]

    assert client.post(f"/datasets/{dataset_id}/analyze").status_code == 202
    assert client.get(f"/datasets/{dataset_id}/status").json()["status"] == "done"

    r = client.get(f"/datasets/{dataset_id}/result")
    assert r.status_code == 200
    assert set(r.json()) == {
        "overview", "columns", "correlations", "findings", "quality_score", "warnings"
    }


def test_status_and_result_before_analyze(client):
    dataset_id = upload(client).json()["dataset_id"]
    assert client.get(f"/datasets/{dataset_id}/status").json()["status"] == "not_started"
    assert client.get(f"/datasets/{dataset_id}/result").status_code == 409


def test_failed_job(client, monkeypatch):
    def boom(path):
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "analyze_csv", boom)
    dataset_id = upload(client).json()["dataset_id"]
    client.post(f"/datasets/{dataset_id}/analyze")

    status = client.get(f"/datasets/{dataset_id}/status").json()
    assert status["status"] == "failed"
    assert status["error"] == "Analysis failed"  # generic message, internals not leaked


@pytest.mark.parametrize("dataset_id, status", [("not-a-uuid", 400), (UNKNOWN_ID, 404)])
def test_analyze_errors(client, dataset_id, status):
    assert client.post(f"/datasets/{dataset_id}/analyze").status_code == status


def test_cors_allows_frontend_origin(client):
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_blocks_unknown_origin(client):
    r = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_upload_too_large(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 10)
    r = upload(client)
    assert r.status_code == 413
    assert list(main.UPLOAD_DIR.glob("*.csv")) == []  # partial file deleted
    assert client.get("/datasets").json() == []  # no DB row either


def test_analyze_returns_report_id_and_report_is_readable(client):
    dataset_id = upload(client).json()["dataset_id"]
    r = client.post(f"/datasets/{dataset_id}/analyze")
    assert r.status_code == 202
    report_id = r.json()["report_id"]

    rep = client.get(f"/reports/{report_id}").json()
    assert rep["status"] == "done"
    assert rep["dataset_id"] == dataset_id
    assert "quality_score" in rep["result"]


def test_analyze_skips_when_job_active(client):
    dataset_id = upload(client).json()["dataset_id"]
    with db.SessionLocal() as s:
        s.add(models.Report(id=UNKNOWN_ID, dataset_id=dataset_id, status="running"))
        s.commit()

    r = client.post(f"/datasets/{dataset_id}/analyze")
    assert r.status_code == 202
    assert r.json()["report_id"] == UNKNOWN_ID  # existing job returned
    assert r.json()["status"] == "running"
    assert len(client.get("/reports").json()) == 1  # no second report created


def test_reanalyze_keeps_history(client):
    dataset_id = upload(client).json()["dataset_id"]
    first = client.post(f"/datasets/{dataset_id}/analyze").json()["report_id"]
    second = client.post(f"/datasets/{dataset_id}/analyze").json()["report_id"]
    assert first != second

    reports = client.get(f"/reports?dataset_id={dataset_id}").json()
    assert len(reports) == 2
    assert reports[0]["report_id"] == second  # newest first
    assert "result" not in reports[0]  # list stays small


def test_list_datasets(client):
    upload(client)
    items = client.get("/datasets").json()
    assert len(items) == 1
    assert items[0]["original_filename"] == "data.csv"
    assert (items[0]["rows"], items[0]["columns"]) == (4, 2)


def test_report_errors(client):
    assert client.get("/reports/not-a-uuid").status_code == 400
    assert client.get(f"/reports/{UNKNOWN_ID}").status_code == 404
    assert client.get("/reports?dataset_id=bad").status_code == 400
    assert client.get("/datasets?limit=0").status_code == 422