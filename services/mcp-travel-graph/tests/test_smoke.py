"""Smoke and contract validation tests for mcp-travel-graph. No network; retrieval mocked."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app.models import Evidence, GraphEdge, GraphNode, Subgraph

# Load the contract schema
SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "graph_rag.schema.json"
)
with open(SCHEMA_PATH) as f:
    GRAPH_RAG_SCHEMA = json.load(f)


def _mock_subgraph() -> tuple[Subgraph, bool]:
    """Return a minimal subgraph that validates against graph_rag.schema.json."""
    node = GraphNode(
        id="poi:mock_poi",
        type="poi",
        name="Mock POI",
        aliases=[],
        properties={},
    )
    ev = Evidence(
        videoUrl="https://example.com/watch?v=mock",
        timestampUrl="https://example.com/watch?v=mock&t=0",
        startSec=0,
        endSec=60,
        chunkIdx=0,
    )
    edge = GraphEdge(
        source="itinerary:mock",
        type="INCLUDES_POI",
        target="poi:mock_poi",
        properties={},
        evidence=ev,
    )
    return (Subgraph(nodes=[node], edges=[edge]), False)


def test_health() -> None:
    """Test GET /health endpoint."""
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@patch(
    "app.main.retrieval_module.get_subgraph",
    side_effect=lambda *a, **k: _mock_subgraph(),
)
def test_retrieve_travel_graph_schema_validation(mock_get_subgraph: object) -> None:
    """Test POST /mcp/retrieve_travel_graph validates against contract schema (no network)."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "user_query": "3-day itinerary for Barcelona",
            "destination": "Barcelona",
            "lang": "en",
            "limit": 20,
            "debug": True,
        },
    }
    r = c.post("/mcp/retrieve_travel_graph", json=payload)
    assert r.status_code == 200
    body = r.json()

    jsonschema.validate(instance=body, schema=GRAPH_RAG_SCHEMA)

    assert body["x_contract_version"] == "1.0"
    assert "request" in body
    assert body["request"]["user_query"] == "3-day itinerary for Barcelona"
    assert "subgraph" in body
    assert "nodes" in body["subgraph"]
    assert "edges" in body["subgraph"]
    assert len(body["subgraph"]["nodes"]) >= 1
    assert len(body["subgraph"]["edges"]) >= 1
    mock_get_subgraph.assert_called()


@patch(
    "app.main.retrieval_module.get_subgraph",
    side_effect=lambda *a, **k: _mock_subgraph(),
)
def test_retrieve_travel_graph_minimal_request(mock_get_subgraph: object) -> None:
    """Test POST /mcp/retrieve_travel_graph with minimal required fields."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "user_query": "what to do first in Rome",
        },
    }
    r = c.post("/mcp/retrieve_travel_graph", json=payload)
    assert r.status_code == 200
    body = r.json()
    jsonschema.validate(instance=body, schema=GRAPH_RAG_SCHEMA)
    assert len(body["subgraph"]["nodes"]) >= 1


@patch(
    "app.main.retrieval_module.get_subgraph",
    side_effect=lambda *a, **k: _mock_subgraph(),
)
def test_retrieve_travel_graph_always_returns_contract_version_1_0(
    mock_get_subgraph: object,
) -> None:
    """Response always returns x_contract_version=1.0 regardless of request version."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "2.0",
        "request": {"user_query": "test query"},
    }
    r = c.post("/mcp/retrieve_travel_graph", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["x_contract_version"] == "1.0"
    jsonschema.validate(instance=body, schema=GRAPH_RAG_SCHEMA)
