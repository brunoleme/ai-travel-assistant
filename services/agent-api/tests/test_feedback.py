"""Feedback endpoint tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from app.main import app

VALID_FEEDBACK = {
    "x_contract_version": "1.0",
    "event_id": "evt_abc12345",
    "timestamp": "2025-02-05T12:00:00Z",
    "session_id": "s01",
    "user_query": "dicas Disney",
    "answer_text": "Visit early morning.",
    "rating": 5,
}


def test_feedback_valid_stores_jsonl(tmp_path: Path) -> None:
    """POST valid payload -> 200, JSONL file written."""
    written: list[dict] = []

    def capture(event: dict) -> None:
        written.append(event)
        (tmp_path / "data" / "feedback").mkdir(parents=True, exist_ok=True)
        (tmp_path / "data" / "feedback" / "events.jsonl").open("a").write(
            __import__("json").dumps(event, ensure_ascii=False) + "\n"
        )

    with patch("app.main.append_jsonl", side_effect=capture):
        client = TestClient(app)
        r = client.post("/feedback", json=VALID_FEEDBACK)

    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert len(written) == 1
    assert written[0]["event_id"] == "evt_abc12345"
    assert written[0]["rating"] == 5


def test_feedback_invalid_schema_returns_error() -> None:
    """Invalid payload fails schema validation."""
    invalid = {**VALID_FEEDBACK, "rating": 99}  # rating must be 1-5
    client = TestClient(app)
    r = client.post("/feedback", json=invalid)
    assert r.status_code == 422
