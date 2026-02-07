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
from app import cache as cache_module
from app import metrics as metrics_module
from app.models import ProductCandidate, ProductScore

# Load contract schema
SCHEMA_PATH = Path(__file__).parent.parent.parent.parent / "contracts" / "product_candidates.schema.json"
with open(SCHEMA_PATH) as f:
    PRODUCT_CANDIDATES_SCHEMA = json.load(f)


def _mock_candidates():
    """Return 1–3 contract ProductCandidates (no Weaviate)."""
    return [
        ProductCandidate(
            product_id="mock-product-01",
            summary="Mock product summary for contract validation (min 10 chars).",
            merchant="Mock Merchant",
            link="https://example.com/mock1",
            categories=["mock"],
            primary_category="mock",
            triggers=["mock"],
            constraints=[],
            affiliate_priority=0.8,
            user_value=0.9,
            confidence=0.85,
            score=ProductScore(distance=0.1, rank=1),
        ),
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


@patch("app.main.retrieval_module.retrieve_product_cards_with_fallback", side_effect=lambda *a, **k: (_mock_candidates(), False))
def test_two_mcp_calls_increment_requests_and_second_is_cache_hit(_mock_retrieve) -> None:
    """Call /mcp/retrieve_product_candidates twice with same payload; /metrics shows requests_total=2, cache_hits_total=1."""
    metrics_module.reset_metrics()
    cache_module.clear_for_tests()
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "query_signature": "orlando:disney:pt-BR",
            "destination": "Orlando",
            "market": "BR",
            "lang": "pt-BR",
        },
    }
    r1 = c.post("/mcp/retrieve_product_candidates", json=payload)
    assert r1.status_code == 200
    r2 = c.post("/mcp/retrieve_product_candidates", json=payload)
    assert r2.status_code == 200
    assert _mock_retrieve.call_count == 1
    metrics_r = c.get("/metrics")
    assert metrics_r.status_code == 200
    m = metrics_r.json()
    assert m["requests_total"] == 2
    assert m["cache_hits_total"] == 1
    assert m["weaviate_fallback_total"] == 0
    assert m["avg_latency_ms"] >= 0


@patch("app.main.retrieval_module.retrieve_product_cards_with_fallback", side_effect=lambda *a, **k: (_mock_candidates(), False))
def test_mcp_response_still_validates_contract(_mock_retrieve) -> None:
    """POST /mcp/retrieve_product_candidates response still validates against product_candidates schema."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {"query_signature": "test_query"},
    }
    r = c.post("/mcp/retrieve_product_candidates", json=payload)
    assert r.status_code == 200
    jsonschema.validate(instance=r.json(), schema=PRODUCT_CANDIDATES_SCHEMA)


@patch("app.main.retrieval_module.retrieve_product_cards_with_fallback", side_effect=lambda *a, **k: (_mock_candidates(), False))
def test_structured_log_has_required_fields(_mock_retrieve, capsys: object) -> None:
    """One JSON log line per request with ts, service, route, cache_hit, latency_ms, session_id, request_id, weaviate_fallback."""
    cache_module.clear_for_tests()
    c = TestClient(app)
    payload = {"x_contract_version": "1.0", "request": {"query_signature": "log_test_query"}}
    c.post("/mcp/retrieve_product_candidates", json=payload, headers={"x-session-id": "s2", "x-request-id": "r2"})
    out = capsys.readouterr().out
    lines = [line.strip() for line in out.strip().split("\n") if line.strip()]
    assert len(lines) >= 1
    log = json.loads(lines[-1])
    assert "ts" in log
    assert log["service"] == "mcp-travel-products"
    assert log["route"] == "/mcp/retrieve_product_candidates"
    assert "cache_hit" in log
    assert "latency_ms" in log
    assert log.get("session_id") == "s2"
    assert log.get("request_id") == "r2"
    assert "weaviate_fallback" in log
