"""
Product candidates cache tests (TDD). No network; retrieval is mocked.
- Same request twice -> second is cache hit, retrieval not called again.
- Different destination/lang bust cache.
- min_confidence applied as post-filter (approach B): same key, different min_confidence still hits cache.
- TTL expiry -> after expiry same request calls retrieval again.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app.models import ProductCandidate, ProductScore

SCHEMA_PATH = Path(__file__).parent.parent.parent.parent / "contracts" / "product_candidates.schema.json"
with open(SCHEMA_PATH) as f:
    PRODUCT_CANDIDATES_SCHEMA = json.load(f)


def _candidate(pid: str, confidence: float) -> ProductCandidate:
    return ProductCandidate(
        product_id=pid,
        summary="A product summary with at least ten characters for tests.",
        merchant="Merchant",
        link="https://example.com/link",
        categories=["cat"],
        primary_category="cat",
        triggers=None,
        constraints=None,
        affiliate_priority=0.5,
        user_value=0.5,
        confidence=confidence,
        score=ProductScore(distance=0.1, rank=1),
    )


MOCK_CANDIDATES = [
    _candidate("mock-product-01", 0.85),
]


@patch("app.main.retrieval_module.retrieve_product_cards_with_fallback", return_value=(MOCK_CANDIDATES, False))
def test_same_request_twice_second_hit_retrieval_not_called_again(mock_retrieve: object) -> None:
    """Same request twice: second response is from cache; retrieval is not called on second request."""
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "query_signature": "orlando:disney:pt-BR",
            "destination": "Orlando",
            "market": "BR",
            "lang": "pt-BR",
        },
    }
    r1 = client.post("/mcp/retrieve_product_candidates", json=payload)
    assert r1.status_code == 200
    jsonschema.validate(instance=r1.json(), schema=PRODUCT_CANDIDATES_SCHEMA)

    r2 = client.post("/mcp/retrieve_product_candidates", json=payload)
    assert r2.status_code == 200
    jsonschema.validate(instance=r2.json(), schema=PRODUCT_CANDIDATES_SCHEMA)

    assert mock_retrieve.call_count == 1


@patch("app.main.retrieval_module.retrieve_product_cards_with_fallback", return_value=(MOCK_CANDIDATES, False))
def test_different_destination_busts_cache(mock_retrieve: object) -> None:
    """Different destination yields different cache key; retrieval called for each."""
    client = TestClient(app)
    r1 = client.post(
        "/mcp/retrieve_product_candidates",
        json={
            "x_contract_version": "1.0",
            "request": {"query_signature": "orlando:disney", "destination": "Orlando"},
        },
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/mcp/retrieve_product_candidates",
        json={
            "x_contract_version": "1.0",
            "request": {"query_signature": "orlando:disney", "destination": "Paris"},
        },
    )
    assert r2.status_code == 200
    jsonschema.validate(instance=r2.json(), schema=PRODUCT_CANDIDATES_SCHEMA)
    assert mock_retrieve.call_count == 2


@patch("app.main.retrieval_module.retrieve_product_cards_with_fallback", return_value=(MOCK_CANDIDATES, False))
def test_different_lang_busts_cache(mock_retrieve: object) -> None:
    """Different lang yields different cache key; retrieval called for each."""
    client = TestClient(app)
    r1 = client.post(
        "/mcp/retrieve_product_candidates",
        json={
            "x_contract_version": "1.0",
            "request": {"query_signature": "orlando:disney", "lang": "pt-BR"},
        },
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/mcp/retrieve_product_candidates",
        json={
            "x_contract_version": "1.0",
            "request": {"query_signature": "orlando:disney", "lang": "en"},
        },
    )
    assert r2.status_code == 200
    assert mock_retrieve.call_count == 2


# Three candidates with confidence 0.4, 0.7, 0.95 for min_confidence post-filter test
CANDIDATES_VARYING_CONF = [
    _candidate("prod-low-12345678", 0.4),
    _candidate("prod-mid-12345678", 0.7),
    _candidate("prod-high12345678", 0.95),
]


@patch("app.main.retrieval_module.retrieve_product_cards_with_fallback", return_value=(CANDIDATES_VARYING_CONF, False))
def test_min_confidence_post_filter_same_cache_key(mock_retrieve: object) -> None:
    """Approach B: min_confidence excluded from key; same key with different min_confidence hits cache, results filtered."""
    client = TestClient(app)
    payload1 = {
        "x_contract_version": "1.0",
        "request": {"query_signature": "orlando:disney", "market": "BR", "min_confidence": 0.5},
    }
    payload2 = {
        "x_contract_version": "1.0",
        "request": {"query_signature": "orlando:disney", "market": "BR", "min_confidence": 0.9},
    }

    r1 = client.post("/mcp/retrieve_product_candidates", json=payload1)
    assert r1.status_code == 200
    body1 = r1.json()
    jsonschema.validate(instance=body1, schema=PRODUCT_CANDIDATES_SCHEMA)
    # confidence >= 0.5 -> 2 candidates (0.7, 0.95)
    assert len(body1["candidates"]) == 2

    r2 = client.post("/mcp/retrieve_product_candidates", json=payload2)
    assert r2.status_code == 200
    body2 = r2.json()
    jsonschema.validate(instance=body2, schema=PRODUCT_CANDIDATES_SCHEMA)
    # confidence >= 0.9 -> 1 candidate (0.95)
    assert len(body2["candidates"]) == 1

    # Same cache key (query_signature, market, destination, lang); retrieval called once
    assert mock_retrieve.call_count == 1


@patch("app.main.retrieval_module.retrieve_product_cards_with_fallback", return_value=(MOCK_CANDIDATES, False))
@patch("app.cache.get_ttl_seconds", return_value=1)
@patch("app.cache.time")
def test_ttl_expiry_refreshes(mock_time: object, mock_ttl: object, mock_retrieve: object) -> None:
    """After TTL expires, same request calls retrieval again (simulate time advance)."""
    mock_time.time.side_effect = [0.0, 2.0, 2.0]
    client = TestClient(app)
    payload = {"x_contract_version": "1.0", "request": {"query_signature": "orlando:disney"}}

    r1 = client.post("/mcp/retrieve_product_candidates", json=payload)
    assert r1.status_code == 200
    r2 = client.post("/mcp/retrieve_product_candidates", json=payload)
    assert r2.status_code == 200
    jsonschema.validate(instance=r2.json(), schema=PRODUCT_CANDIDATES_SCHEMA)
    assert mock_retrieve.call_count == 2
