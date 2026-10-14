import pytest
from fastapi.testclient import TestClient

from app import main

CSV = b"age,city\n25,Pune\n30,Mumbai\n35,Pune\n40,Delhi\n"
UNKNOWN_ID = "123e4567-e89b-42d3-a456-426614174000"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path)
    return TestClient(main.app)


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
    assert status["status"] == "failed" and "boom" in status["error"]

@pytest.mark.parametrize("dataset_id, status", [("not-a-uuid", 400), (UNKNOWN_ID, 404)])
def test_analyze_errors(client, dataset_id, status):
    assert client.post(f"/datasets/{dataset_id}/analyze").status_code == status

def test_cors_allows_frontend_origin(client):
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_blocks_unknown_origin(client):
    r = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers