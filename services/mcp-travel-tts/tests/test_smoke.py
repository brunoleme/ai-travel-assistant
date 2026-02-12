"""Smoke and contract validation tests for mcp-travel-tts. No network; synthesize mocked."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app.models import SynthesizeResponse, TTSRequest

# Load the contract schema (repo root: services/mcp-travel-tts/tests -> parents[3])
SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "tts_audio.schema.json"
)
with open(SCHEMA_PATH) as f:
    TTS_AUDIO_SCHEMA = json.load(f)


def _mock_synthesize_response(req: TTSRequest) -> SynthesizeResponse:
    """Return minimal audio_ref that validates against tts_audio.schema.json."""
    return SynthesizeResponse(
        x_contract_version="1.0",
        request=req,
        audio_ref="data:audio/mp3;base64,//uQx",
        format=req.format or "mp3",
        duration_seconds=2.1,
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
    "app.main.synthesize_module.synthesize",
    side_effect=lambda req: _mock_synthesize_response(req),
)
def test_synthesize_schema_validation(mock_synthesize: object) -> None:
    """Test POST /mcp/synthesize validates against contract schema (no network)."""
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "text": "The best time to visit Tokyo is spring.",
            "voice": "nova",
            "speed": 1.0,
            "format": "mp3",
            "debug": True,
        },
    }
    r = client.post("/mcp/synthesize", json=payload)
    assert r.status_code == 200
    body = r.json()
    jsonschema.validate(instance=body, schema=TTS_AUDIO_SCHEMA)
    assert body["x_contract_version"] == "1.0"
    assert body["request"]["text"] == "The best time to visit Tokyo is spring."
    assert body["audio_ref"].startswith("data:audio/")
    mock_synthesize.assert_called_once()


@patch(
    "app.main.synthesize_module.synthesize",
    side_effect=lambda req: _mock_synthesize_response(req),
)
def test_synthesize_minimal_request(mock_synthesize: object) -> None:
    """Test POST /mcp/synthesize with minimal required fields (text only)."""
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {"text": "Hello, world."},
    }
    r = client.post("/mcp/synthesize", json=payload)
    assert r.status_code == 200
    body = r.json()
    jsonschema.validate(instance=body, schema=TTS_AUDIO_SCHEMA)
    assert "audio_ref" in body
    assert body["audio_ref"].startswith("data:audio/")
