"""Cache tests: same request -> cache hit; different mode/context -> miss."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.cache import clear_for_tests
from app.main import app
from app.models import VisionSignals

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "vision_signals.schema.json"
)
with open(SCHEMA_PATH) as f:
    VISION_SIGNALS_SCHEMA = json.load(f)


def _mock_signals(request: object) -> VisionSignals:
    """Return signals matching request mode."""
    req = request
    mode = getattr(req, "mode", "packing")
    return VisionSignals(
        mode=mode, confidence=0.9, detected_items=[], missing_categories=[]
    )


@patch("app.main.vision_module.analyze_image", side_effect=_mock_signals)
def test_same_request_twice_second_hit(mock_analyze: object) -> None:
    """Same image_ref + mode + trip_context -> second request is cache hit; vision not called again."""
    clear_for_tests()
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "image_ref": "https://example.com/photo.jpg",
            "mode": "packing",
            "trip_context": {"destination": "London"},
        },
    }
    r1 = client.post("/mcp/analyze_image", json=payload)
    assert r1.status_code == 200
    jsonschema.validate(instance=r1.json(), schema=VISION_SIGNALS_SCHEMA)
    r2 = client.post("/mcp/analyze_image", json=payload)
    assert r2.status_code == 200
    jsonschema.validate(instance=r2.json(), schema=VISION_SIGNALS_SCHEMA)
    assert mock_analyze.call_count == 1


@patch("app.main.vision_module.analyze_image", side_effect=_mock_signals)
def test_different_mode_busts_cache(mock_analyze: object) -> None:
    """Different mode -> cache miss."""
    clear_for_tests()
    client = TestClient(app)
    r1 = client.post(
        "/mcp/analyze_image",
        json={
            "x_contract_version": "1.0",
            "request": {
                "image_ref": "https://example.com/photo.jpg",
                "mode": "packing",
            },
        },
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/mcp/analyze_image",
        json={
            "x_contract_version": "1.0",
            "request": {
                "image_ref": "https://example.com/photo.jpg",
                "mode": "landmark",
            },
        },
    )
    assert r2.status_code == 200
    assert mock_analyze.call_count == 2
