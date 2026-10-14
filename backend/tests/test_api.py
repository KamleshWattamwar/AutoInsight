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

    r = client.post(f"/datasets/{body['dataset_id']}/analyze")
    assert r.status_code == 200
    assert set(r.json()) == {
        "overview", "columns", "correlations", "findings", "quality_score" ,"warnings"
    }


@pytest.mark.parametrize("dataset_id, status", [("not-a-uuid", 400), (UNKNOWN_ID, 404)])
def test_analyze_errors(client, dataset_id, status):
    assert client.post(f"/datasets/{dataset_id}/analyze").status_code == status