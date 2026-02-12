"""Metrics tests: request_count, cache_hit, latency, response validates against contract."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app.models import VisionSignals

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "vision_signals.schema.json"
)
with open(SCHEMA_PATH) as f:
    VISION_SIGNALS_SCHEMA = json.load(f)


@patch(
    "app.main.vision_module.analyze_image",
    return_value=VisionSignals(mode="packing", confidence=0.9),
)
def test_metrics_endpoint_increments_request_count(mock_analyze: object) -> None:
    """GET /metrics returns request_count after a POST."""
    from app import metrics as metrics_module

    metrics_module.reset_metrics()
    client = TestClient(app)
    assert client.get("/metrics").json().get("request_count", 0) == 0
    client.post(
        "/mcp/analyze_image",
        json={
            "x_contract_version": "1.0",
            "request": {"image_ref": "https://a.com/1.jpg", "mode": "packing"},
        },
    )
    m = client.get("/metrics").json()
    assert m.get("request_count") == 1
    assert "latency_ms_avg" in m
    assert "cache_hit_rate" in m


@patch(
    "app.main.vision_module.analyze_image",
    return_value=VisionSignals(mode="packing", confidence=0.9),
)
def test_mcp_response_still_validates_contract(mock_analyze: object) -> None:
    """POST /mcp/analyze_image response validates against vision_signals schema."""
    client = TestClient(app)
    r = client.post(
        "/mcp/analyze_image",
        json={
            "x_contract_version": "1.0",
            "request": {"image_ref": "https://a.com/1.jpg", "mode": "packing"},
        },
    )
    assert r.status_code == 200
    jsonschema.validate(instance=r.json(), schema=VISION_SIGNALS_SCHEMA)
