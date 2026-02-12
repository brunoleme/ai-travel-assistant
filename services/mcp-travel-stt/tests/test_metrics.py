"""Metrics tests: request_count, error_count, latency_ms; response validates against contract."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app.models import TranscribeResponse, STTRequest

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "stt_transcript.schema.json"
)
with open(SCHEMA_PATH) as f:
    STT_TRANSCRIPT_SCHEMA = json.load(f)


def _mock_ok(req: STTRequest) -> TranscribeResponse:
    return TranscribeResponse(
        x_contract_version="1.0",
        request=req,
        transcript="OK",
        language="en",
        confidence=0.9,
        error=None,
    )


def _mock_error(req: STTRequest) -> TranscribeResponse:
    return TranscribeResponse(
        x_contract_version="1.0",
        request=req,
        transcript="",
        error="Transcription failed",
    )


@patch(
    "app.main.transcribe_module.transcribe",
    side_effect=_mock_ok,
)
def test_metrics_endpoint_increments_request_count(mock_transcribe: object) -> None:
    """GET /metrics returns request_count after a POST."""
    from app import metrics as metrics_module

    metrics_module.reset_metrics()
    client = TestClient(app)
    assert client.get("/metrics").json().get("request_count", 0) == 0
    client.post(
        "/mcp/transcribe",
        json={
            "x_contract_version": "1.0",
            "request": {"audio_ref": "data:audio/mp3;base64,//uQx"},
        },
    )
    m = client.get("/metrics").json()
    assert m.get("request_count") == 1
    assert "latency_ms_avg" in m
    assert "error_count" in m


@patch(
    "app.main.transcribe_module.transcribe",
    side_effect=_mock_error,
)
def test_error_increments_error_count(mock_transcribe: object) -> None:
    """When transcription returns error, error_count increments."""
    from app import metrics as metrics_module

    metrics_module.reset_metrics()
    client = TestClient(app)
    client.post(
        "/mcp/transcribe",
        json={
            "x_contract_version": "1.0",
            "request": {"audio_ref": "data:audio/mp3;base64,//uQx"},
        },
    )
    m = client.get("/metrics").json()
    assert m.get("error_count") == 1


@patch(
    "app.main.transcribe_module.transcribe",
    side_effect=_mock_ok,
)
def test_mcp_response_still_validates_contract(mock_transcribe: object) -> None:
    """POST /mcp/transcribe response validates against stt_transcript schema."""
    client = TestClient(app)
    r = client.post(
        "/mcp/transcribe",
        json={
            "x_contract_version": "1.0",
            "request": {"audio_ref": "data:audio/mp3;base64,//uQx"},
        },
    )
    assert r.status_code == 200
    jsonschema.validate(instance=r.json(), schema=STT_TRANSCRIPT_SCHEMA)
