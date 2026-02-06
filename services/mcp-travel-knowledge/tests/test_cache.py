"""
Evidence cache tests (TDD). No network; retrieval is mocked.
- Same request twice -> second is cache hit, retrieval not called again.
- Different destination -> cache miss, retrieval called for each.
- TTL expiry -> after expiry same request calls retrieval again.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app

SCHEMA_PATH = Path(__file__).parent.parent.parent.parent / "contracts" / "travel_evidence.schema.json"
with open(SCHEMA_PATH) as f:
    TRAVEL_EVIDENCE_SCHEMA = json.load(f)

WEAVIATE_CARDS_FIXTURE = [
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "summary": "Best times to visit are early morning or late evening to avoid crowds.",
        "signals": ["crowd_avoidance", "timing_tips"],
        "places": ["Orlando", "Magic Kingdom"],
        "categories": ["tips", "crowd_management"],
        "primaryCategory": "tips",
        "confidence": 0.85,
        "timestampUrl": "https://example.com/watch?v=abc123",
    },
]


@patch("app.main.retrieval_module.get_recommendation_cards", return_value=WEAVIATE_CARDS_FIXTURE)
def test_same_request_twice_second_hit_retrieval_not_called_again(mock_get_cards: object) -> None:
    """Same request twice: second response is from cache; retrieval is not called on second request."""
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {"user_query": "disney tips", "destination": "Orlando", "lang": "en"},
    }
    r1 = client.post("/mcp/retrieve_travel_evidence", json=payload)
    assert r1.status_code == 200
    jsonschema.validate(instance=r1.json(), schema=TRAVEL_EVIDENCE_SCHEMA)

    r2 = client.post("/mcp/retrieve_travel_evidence", json=payload)
    assert r2.status_code == 200
    jsonschema.validate(instance=r2.json(), schema=TRAVEL_EVIDENCE_SCHEMA)

    # Retrieval must have been called only once (second request served from cache)
    assert mock_get_cards.call_count == 1


@patch("app.main.retrieval_module.get_recommendation_cards", return_value=WEAVIATE_CARDS_FIXTURE)
def test_different_destination_busts_cache(mock_get_cards: object) -> None:
    """Different destination yields different cache key; retrieval called for each."""
    client = TestClient(app)
    r1 = client.post(
        "/mcp/retrieve_travel_evidence",
        json={"x_contract_version": "1.0", "request": {"user_query": "disney tips", "destination": "Orlando"}},
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/mcp/retrieve_travel_evidence",
        json={"x_contract_version": "1.0", "request": {"user_query": "disney tips", "destination": "Paris"}},
    )
    assert r2.status_code == 200
    jsonschema.validate(instance=r2.json(), schema=TRAVEL_EVIDENCE_SCHEMA)
    # Two different keys -> retrieval called twice
    assert mock_get_cards.call_count == 2


@patch("app.main.retrieval_module.get_recommendation_cards", return_value=WEAVIATE_CARDS_FIXTURE)
@patch("app.cache.get_ttl_seconds", return_value=1)
@patch("app.cache.time")
def test_ttl_expiry_refreshes(mock_time: object, mock_ttl: object, mock_get_cards: object) -> None:
    """After TTL expires, same request calls retrieval again (simulate time advance)."""
    # TTL=1: set_() uses time.time() once (t=0 -> expires_at=1). Second request get() uses time.time()=2 -> expired.
    mock_time.time.side_effect = [0.0, 2.0, 2.0]
    client = TestClient(app)
    payload = {"x_contract_version": "1.0", "request": {"user_query": "disney tips"}}

    r1 = client.post("/mcp/retrieve_travel_evidence", json=payload)
    assert r1.status_code == 200
    r2 = client.post("/mcp/retrieve_travel_evidence", json=payload)
    assert r2.status_code == 200
    jsonschema.validate(instance=r2.json(), schema=TRAVEL_EVIDENCE_SCHEMA)
    # First request: miss, fetch. Second request: expired, fetch again.
    assert mock_get_cards.call_count == 2
