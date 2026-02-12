"""
Tests for /metrics and structured logging. No network; retrieval mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app import metrics as metrics_module
from app.models import Evidence, GraphEdge, GraphNode, Subgraph

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "graph_rag.schema.json"
)
with open(SCHEMA_PATH) as f:
    GRAPH_RAG_SCHEMA = json.load(f)


def _mock_subgraph() -> tuple[Subgraph, bool]:
    node = GraphNode(
        id="poi:metrics_test", type="poi", name="Metrics POI", aliases=[], properties={}
    )
    ev = Evidence(
        videoUrl="https://example.com/v",
        timestampUrl="https://example.com/v?t=0",
        startSec=0,
        endSec=60,
        chunkIdx=0,
    )
    edge = GraphEdge(
        source="it:1",
        type="INCLUDES_POI",
        target="poi:metrics_test",
        properties={},
        evidence=ev,
    )
    return (Subgraph(nodes=[node], edges=[edge]), False)


def test_metrics_endpoint_returns_json_with_required_keys() -> None:
    """GET /metrics returns JSON with requests_total, cache_hits_total, neo4j_fallback_total, avg_latency_ms."""
    metrics_module.reset_metrics()
    c = TestClient(app)
    r = c.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "requests_total" in body
    assert "cache_hits_total" in body
    assert "neo4j_fallback_total" in body
    assert "avg_latency_ms" in body
    assert body["requests_total"] == 0
    assert body["cache_hits_total"] == 0
    assert body["neo4j_fallback_total"] == 0
    assert body["avg_latency_ms"] == 0.0


@patch(
    "app.main.retrieval_module.get_subgraph",
    side_effect=lambda *a, **k: _mock_subgraph(),
)
def test_two_mcp_calls_increment_requests_and_second_is_cache_hit(
    mock_get_subgraph: object,
) -> None:
    """Call /mcp/retrieve_travel_graph twice with same payload; /metrics shows requests_total=2, cache_hits_total=1."""
    from app import cache as cache_module

    metrics_module.reset_metrics()
    cache_module.clear_for_tests()
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "user_query": "itinerary Barcelona",
            "destination": "Barcelona",
            "lang": "en",
        },
    }
    r1 = c.post("/mcp/retrieve_travel_graph", json=payload)
    assert r1.status_code == 200
    r2 = c.post("/mcp/retrieve_travel_graph", json=payload)
    assert r2.status_code == 200
    assert mock_get_subgraph.call_count == 1
    metrics_r = c.get("/metrics")
    assert metrics_r.status_code == 200
    m = metrics_r.json()
    assert m["requests_total"] == 2
    assert m["cache_hits_total"] == 1
    assert m["neo4j_fallback_total"] == 0
    assert m["avg_latency_ms"] >= 0


@patch(
    "app.main.retrieval_module.get_subgraph",
    side_effect=lambda *a, **k: _mock_subgraph(),
)
def test_mcp_response_still_validates_contract(mock_get_subgraph: object) -> None:
    """POST /mcp/retrieve_travel_graph response validates against graph_rag schema."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {"user_query": "itinerary Barcelona", "destination": "Barcelona"},
    }
    r = c.post("/mcp/retrieve_travel_graph", json=payload)
    assert r.status_code == 200
    jsonschema.validate(instance=r.json(), schema=GRAPH_RAG_SCHEMA)


@patch(
    "app.main.retrieval_module.get_subgraph",
    side_effect=lambda *a, **k: _mock_subgraph(),
)
def test_structured_log_has_required_fields(
    mock_get_subgraph: object, capsys: object
) -> None:
    """One JSON log line per request with ts, service, route, cache_hit, latency_ms, session_id, request_id, neo4j_fallback."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {"user_query": "log test query", "destination": "Barcelona"},
    }
    c.post(
        "/mcp/retrieve_travel_graph",
        json=payload,
        headers={"x-session-id": "s1", "x-request-id": "r1"},
    )
    out = capsys.readouterr().out
    lines = [line.strip() for line in out.strip().split("\n") if line.strip()]
    assert len(lines) >= 1
    log = json.loads(lines[-1])
    assert "ts" in log
    assert log["service"] == "mcp-travel-graph"
    assert log["route"] == "/mcp/retrieve_travel_graph"
    assert "cache_hit" in log
    assert "latency_ms" in log
    assert log.get("session_id") == "s1"
    assert log.get("request_id") == "r1"
    assert "neo4j_fallback" in log
