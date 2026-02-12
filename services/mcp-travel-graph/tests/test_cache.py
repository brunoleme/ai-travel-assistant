# Graph cache tests: same request -> cache hit; different destination/lang -> miss; TTL expiry.
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app.models import Evidence, GraphEdge, GraphNode, Subgraph

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "graph_rag.schema.json"
)
with open(SCHEMA_PATH) as f:
    GRAPH_RAG_SCHEMA = json.load(f)


def _mock_subgraph() -> tuple[Subgraph, bool]:
    node = GraphNode(
        id="poi:cache_test",
        type="poi",
        name="Cache Test POI",
        aliases=[],
        properties={},
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
        target="poi:cache_test",
        properties={},
        evidence=ev,
    )
    return (Subgraph(nodes=[node], edges=[edge]), False)


@patch(
    "app.main.retrieval_module.get_subgraph",
    side_effect=lambda *a, **k: _mock_subgraph(),
)
def test_same_request_twice_second_hit_retrieval_not_called_again(
    mock_get_subgraph: object,
) -> None:
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "user_query": "itinerary Barcelona",
            "destination": "Barcelona",
            "lang": "en",
        },
    }
    r1 = client.post("/mcp/retrieve_travel_graph", json=payload)
    assert r1.status_code == 200
    jsonschema.validate(instance=r1.json(), schema=GRAPH_RAG_SCHEMA)
    r2 = client.post("/mcp/retrieve_travel_graph", json=payload)
    assert r2.status_code == 200
    jsonschema.validate(instance=r2.json(), schema=GRAPH_RAG_SCHEMA)
    assert mock_get_subgraph.call_count == 1


@patch(
    "app.main.retrieval_module.get_subgraph",
    side_effect=lambda *a, **k: _mock_subgraph(),
)
def test_different_destination_busts_cache(mock_get_subgraph: object) -> None:
    client = TestClient(app)
    r1 = client.post(
        "/mcp/retrieve_travel_graph",
        json={
            "x_contract_version": "1.0",
            "request": {"user_query": "itinerary", "destination": "Barcelona"},
        },
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/mcp/retrieve_travel_graph",
        json={
            "x_contract_version": "1.0",
            "request": {"user_query": "itinerary", "destination": "Rome"},
        },
    )
    assert r2.status_code == 200
    jsonschema.validate(instance=r2.json(), schema=GRAPH_RAG_SCHEMA)
    assert mock_get_subgraph.call_count == 2


@patch(
    "app.main.retrieval_module.get_subgraph",
    side_effect=lambda *a, **k: _mock_subgraph(),
)
@patch("app.cache.get_ttl_seconds", return_value=1)
@patch("app.cache.time")
def test_ttl_expiry_refreshes(
    mock_time: object, mock_ttl: object, mock_get_subgraph: object
) -> None:
    mock_time.time.side_effect = [0.0, 2.0, 2.0]
    client = TestClient(app)
    payload = {"x_contract_version": "1.0", "request": {"user_query": "itinerary"}}
    r1 = client.post("/mcp/retrieve_travel_graph", json=payload)
    assert r1.status_code == 200
    r2 = client.post("/mcp/retrieve_travel_graph", json=payload)
    assert r2.status_code == 200
    jsonschema.validate(instance=r2.json(), schema=GRAPH_RAG_SCHEMA)
    assert mock_get_subgraph.call_count == 2
