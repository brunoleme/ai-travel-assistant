"""Metrics tests: request_count, error_count, latency_ms; response validates against contract."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app.models import SynthesizeResponse, TTSRequest

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "tts_audio.schema.json"
)
with open(SCHEMA_PATH) as f:
    TTS_AUDIO_SCHEMA = json.load(f)


def _mock_ok(req: TTSRequest) -> SynthesizeResponse:
    return SynthesizeResponse(
        x_contract_version="1.0",
        request=req,
        audio_ref="data:audio/mp3;base64,YQ==",
        format="mp3",
        error=None,
    )


def _mock_error(req: TTSRequest) -> SynthesizeResponse:
    return SynthesizeResponse(
        x_contract_version="1.0",
        request=req,
        audio_ref="data:audio/mp3;base64,YQ==",
        format="mp3",
        error="Synthesis failed",
    )


@patch(
    "app.main.synthesize_module.synthesize",
    side_effect=_mock_ok,
)
def test_metrics_endpoint_increments_request_count(mock_synthesize: object) -> None:
    """GET /metrics returns request_count after a POST."""
    from app import metrics as metrics_module

    metrics_module.reset_metrics()
    client = TestClient(app)
    assert client.get("/metrics").json().get("request_count", 0) == 0
    client.post(
        "/mcp/synthesize",
        json={
            "x_contract_version": "1.0",
            "request": {"text": "Hello."},
        },
    )
    m = client.get("/metrics").json()
    assert m.get("request_count") == 1
    assert "latency_ms_avg" in m
    assert "error_count" in m


@patch(
    "app.main.synthesize_module.synthesize",
    side_effect=_mock_error,
)
def test_error_increments_error_count(mock_synthesize: object) -> None:
    """When synthesis returns error, error_count increments."""
    from app import metrics as metrics_module

    metrics_module.reset_metrics()
    client = TestClient(app)
    client.post(
        "/mcp/synthesize",
        json={
            "x_contract_version": "1.0",
            "request": {"text": "Hello."},
        },
    )
    m = client.get("/metrics").json()
    assert m.get("error_count") == 1


@patch(
    "app.main.synthesize_module.synthesize",
    side_effect=_mock_ok,
)
def test_mcp_response_still_validates_contract(mock_synthesize: object) -> None:
    """POST /mcp/synthesize response validates against tts_audio schema."""
    client = TestClient(app)
    r = client.post(
        "/mcp/synthesize",
        json={
            "x_contract_version": "1.0",
            "request": {"text": "Hello."},
        },
    )
    assert r.status_code == 200
    jsonschema.validate(instance=r.json(), schema=TTS_AUDIO_SCHEMA)
