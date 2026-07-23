from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "data" / "database_bloom_5_questions.jsonl"


def test_dry_run_validates_sample_file() -> None:
    with TestClient(app) as client, SAMPLE_PATH.open("rb") as sample:
        response = client.post(
            "/api/v1/questions/import-jsonl?dry_run=true",
            files={"file": (SAMPLE_PATH.name, sample, "application/x-ndjson")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed_lines"] == 5
    assert payload["succeeded"] == 5
    assert payload["failed"] == 0
    assert {result["status"] for result in payload["results"]} == {"validated"}


def test_rejects_non_jsonl_extension() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/questions/import-jsonl?dry_run=true",
            files={"file": ("questions.json", b"{}", "application/json")},
        )

    assert response.status_code == 400
