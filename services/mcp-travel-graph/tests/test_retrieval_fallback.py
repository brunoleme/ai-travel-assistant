"""Neo4j fallback: when driver is unavailable, endpoint returns 200 with valid contract (mock subgraph)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "graph_rag.schema.json"
)
with open(SCHEMA_PATH) as f:
    GRAPH_RAG_SCHEMA = json.load(f)


@patch("app.retrieval._get_driver", return_value=None)
def test_neo4j_unavailable_returns_200_valid_contract(mock_driver: object) -> None:
    """When Neo4j driver is None, POST returns 200 and response validates against graph_rag schema."""
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {"user_query": "itinerary Barcelona", "destination": "Barcelona"},
    }
    r = client.post("/mcp/retrieve_travel_graph", json=payload)
    assert r.status_code == 200
    body = r.json()
    jsonschema.validate(instance=body, schema=GRAPH_RAG_SCHEMA)
    assert "subgraph" in body
    assert "nodes" in body["subgraph"]
    assert "edges" in body["subgraph"]
