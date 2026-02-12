"""Smoke and contract validation tests for mcp-travel-stt. No network; transcribe mocked."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app.models import TranscribeResponse, STTRequest

# Load the contract schema (repo root: services/mcp-travel-stt/tests -> parents[3])
SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "stt_transcript.schema.json"
)
with open(SCHEMA_PATH) as f:
    STT_TRANSCRIPT_SCHEMA = json.load(f)


def _mock_transcribe_response(req: STTRequest) -> TranscribeResponse:
    """Return minimal transcript that validates against stt_transcript.schema.json."""
    return TranscribeResponse(
        x_contract_version="1.0",
        request=req,
        transcript="What is the best time to visit Tokyo?",
        language=req.language or "en",
        confidence=0.92,
        duration_seconds=2.5,
        error=None,
        debug={"mock": True} if req.debug else None,
    )


def test_health() -> None:
    """Test GET /health endpoint."""
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@patch(
    "app.main.transcribe_module.transcribe",
    side_effect=lambda req: _mock_transcribe_response(req),
)
def test_transcribe_schema_validation(mock_transcribe: object) -> None:
    """Test POST /mcp/transcribe validates against contract schema (no network)."""
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "audio_ref": "data:audio/mp3;base64,//uQx",
            "language": "en",
            "debug": True,
        },
    }
    r = client.post("/mcp/transcribe", json=payload)
    assert r.status_code == 200
    body = r.json()
    jsonschema.validate(instance=body, schema=STT_TRANSCRIPT_SCHEMA)
    assert body["x_contract_version"] == "1.0"
    assert body["request"]["audio_ref"] == "data:audio/mp3;base64,//uQx"
    assert body["transcript"] == "What is the best time to visit Tokyo?"
    mock_transcribe.assert_called_once()


@patch(
    "app.main.transcribe_module.transcribe",
    side_effect=lambda req: _mock_transcribe_response(req),
)
def test_transcribe_minimal_request(mock_transcribe: object) -> None:
    """Test POST /mcp/transcribe with minimal required fields (audio_ref only)."""
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {"audio_ref": "https://example.com/audio.mp3"},
    }
    r = client.post("/mcp/transcribe", json=payload)
    assert r.status_code == 200
    body = r.json()
    jsonschema.validate(instance=body, schema=STT_TRANSCRIPT_SCHEMA)
    assert "transcript" in body
    assert body["transcript"] == "What is the best time to visit Tokyo?"
