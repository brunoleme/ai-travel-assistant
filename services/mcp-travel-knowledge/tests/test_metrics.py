"""
Tests for /metrics and structured logging (O2).
No network; mocks for retrieval.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app import metrics as metrics_module

# Load contract schema
SCHEMA_PATH = Path(__file__).parent.parent.parent.parent / "contracts" / "travel_evidence.schema.json"
with open(SCHEMA_PATH) as f:
    TRAVEL_EVIDENCE_SCHEMA = json.load(f)

WEAVIATE_CARDS_FIXTURE = [
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "summary": "Best times to visit are early morning or late evening.",
        "signals": ["crowd_avoidance"],
        "places": ["Orlando"],
        "categories": ["tips"],
        "primaryCategory": "tips",
        "confidence": 0.85,
        "timestampUrl": "https://example.com/watch?v=abc123",
    },
]


def test_metrics_endpoint_returns_json_with_required_keys() -> None:
    """GET /metrics returns JSON with requests_total, cache_hits_total, weaviate_fallback_total, avg_latency_ms."""
    metrics_module.reset_metrics()
    c = TestClient(app)
    r = c.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "requests_total" in body
    assert "cache_hits_total" in body
    assert "weaviate_fallback_total" in body
    assert "avg_latency_ms" in body
    assert body["requests_total"] == 0
    assert body["cache_hits_total"] == 0
    assert body["weaviate_fallback_total"] == 0
    assert body["avg_latency_ms"] == 0.0


@patch("app.main.retrieval_module.get_recommendation_cards", return_value=WEAVIATE_CARDS_FIXTURE)
def test_two_mcp_calls_increment_requests_and_second_is_cache_hit(mock_get_cards: object) -> None:
    """Call /mcp/retrieve_travel_evidence twice with same payload; /metrics shows requests_total=2, cache_hits_total=1."""
    metrics_module.reset_metrics()
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {"user_query": "dicas Disney", "destination": "Orlando", "lang": "pt-BR"},
    }
    r1 = c.post("/mcp/retrieve_travel_evidence", json=payload)
    assert r1.status_code == 200
    r2 = c.post("/mcp/retrieve_travel_evidence", json=payload)
    assert r2.status_code == 200
    mock_get_cards.assert_called_once()
    metrics_r = c.get("/metrics")
    assert metrics_r.status_code == 200
    m = metrics_r.json()
    assert m["requests_total"] == 2
    assert m["cache_hits_total"] == 1
    assert m["weaviate_fallback_total"] == 0
    assert m["avg_latency_ms"] >= 0


@patch("app.main.retrieval_module.get_recommendation_cards", return_value=WEAVIATE_CARDS_FIXTURE)
def test_mcp_response_still_validates_contract(mock_get_cards: object) -> None:
    """POST /mcp/retrieve_travel_evidence response still validates against travel_evidence schema."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {"user_query": "dicas Disney", "destination": "Orlando"},
    }
    r = c.post("/mcp/retrieve_travel_evidence", json=payload)
    assert r.status_code == 200
    jsonschema.validate(instance=r.json(), schema=TRAVEL_EVIDENCE_SCHEMA)


@patch("app.main.retrieval_module.get_recommendation_cards", return_value=WEAVIATE_CARDS_FIXTURE)
def test_structured_log_has_required_fields(mock_get_cards: object, capsys: object) -> None:
    """One JSON log line per request with ts, service, route, cache_hit, latency_ms, session_id, request_id, weaviate_fallback."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {"user_query": "log test query", "destination": "Orlando"},
    }
    c.post("/mcp/retrieve_travel_evidence", json=payload, headers={"x-session-id": "s1", "x-request-id": "r1"})
    out = capsys.readouterr().out
    lines = [line.strip() for line in out.strip().split("\n") if line.strip()]
    assert len(lines) >= 1
    log = json.loads(lines[-1])
    assert "ts" in log
    assert log["service"] == "mcp-travel-knowledge"
    assert log["route"] == "/mcp/retrieve_travel_evidence"
    assert "cache_hit" in log
    assert "latency_ms" in log
    assert log.get("session_id") == "s1"
    assert log.get("request_id") == "r1"
    assert "weaviate_fallback" in log
