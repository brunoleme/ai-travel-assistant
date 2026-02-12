"""Smoke and contract validation tests for mcp-travel-vision. No network; vision mocked."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app.models import PlaceCandidate, VisionSignals

# Load the contract schema (repo root: services/mcp-travel-vision/tests -> parents[3])
SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "vision_signals.schema.json"
)
with open(SCHEMA_PATH) as f:
    VISION_SIGNALS_SCHEMA = json.load(f)


def _mock_packing_signals() -> VisionSignals:
    """Return minimal packing signals that validate against vision_signals.schema.json."""
    return VisionSignals(
        mode="packing",
        confidence=0.9,
        detected_items=["light_top", "walking_shoes"],
        missing_categories=["rain_jacket"],
    )


def test_health() -> None:
    """Test GET /health endpoint."""
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@patch(
    "app.main.vision_module.analyze_image",
    side_effect=lambda req: _mock_packing_signals(),
)
def test_analyze_image_schema_validation(mock_analyze: object) -> None:
    """Test POST /mcp/analyze_image validates against contract schema (no network)."""
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "image_ref": "https://example.com/photo.jpg",
            "mode": "packing",
            "trip_context": {"destination": "London", "rain_risk": "high"},
            "debug": True,
        },
    }
    r = client.post("/mcp/analyze_image", json=payload)
    assert r.status_code == 200
    body = r.json()
    jsonschema.validate(instance=body, schema=VISION_SIGNALS_SCHEMA)
    assert body["x_contract_version"] == "1.0"
    assert body["request"]["image_ref"] == "https://example.com/photo.jpg"
    assert body["request"]["mode"] == "packing"
    assert body["signals"]["mode"] == "packing"
    assert "detected_items" in body["signals"]
    mock_analyze.assert_called_once()


@patch(
    "app.main.vision_module.analyze_image",
    side_effect=lambda req: _mock_packing_signals(),
)
def test_analyze_image_minimal_request(mock_analyze: object) -> None:
    """Test POST /mcp/analyze_image with minimal required fields (image_ref, mode)."""
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {"image_ref": "data:image/jpeg;base64,/9j/4AAQ", "mode": "packing"},
    }
    r = client.post("/mcp/analyze_image", json=payload)
    assert r.status_code == 200
    body = r.json()
    jsonschema.validate(instance=body, schema=VISION_SIGNALS_SCHEMA)
    assert len(body["signals"].get("detected_items") or []) >= 1


def _mock_landmark_signals() -> VisionSignals:
    """Return landmark signals for schema validation."""
    return VisionSignals(
        mode="landmark",
        confidence=0.85,
        scene_type="landmark",
        ocr_text=[],
        distinctive_features=["tower"],
        place_candidates=[
            PlaceCandidate(place_name="Eiffel Tower", confidence=0.9, reason="Shape"),
        ],
    )


@patch(
    "app.main.vision_module.analyze_image",
    side_effect=lambda req: _mock_landmark_signals(),
)
def test_analyze_image_landmark_mode_validates(mock_analyze: object) -> None:
    """POST /mcp/analyze_image with mode=landmark returns response validating against schema."""
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {"image_ref": "https://example.com/place.jpg", "mode": "landmark"},
    }
    r = client.post("/mcp/analyze_image", json=payload)
    assert r.status_code == 200
    body = r.json()
    jsonschema.validate(instance=body, schema=VISION_SIGNALS_SCHEMA)
    assert body["signals"]["mode"] == "landmark"
    assert body["signals"]["scene_type"] == "landmark"
    assert len(body["signals"].get("place_candidates") or []) >= 1
