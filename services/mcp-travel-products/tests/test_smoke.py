from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app.models import ProductCandidate, ProductScore

# Load the contract schema
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


def test_health():
    """Test GET /health endpoint."""
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@patch("app.main.retrieval_module.retrieve_product_cards_with_fallback", side_effect=lambda *a, **k: (_mock_candidates(), False))
def test_retrieve_product_candidates_schema_validation(_mock_retrieve):
    """Test POST /mcp/retrieve_product_candidates validates against contract schema."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "query_signature": "orlando:disney:pt-BR",
            "destination": "Orlando",
            "market": "BR",
            "lang": "pt-BR",
            "limit": 5,
            "min_confidence": 0.5,
        },
    }
    r = c.post("/mcp/retrieve_product_candidates", json=payload)
    assert r.status_code == 200
    body = r.json()
    
    # Validate against JSON schema
    jsonschema.validate(instance=body, schema=PRODUCT_CANDIDATES_SCHEMA)
    
    # Additional assertions
    assert "x_contract_version" in body
    assert body["x_contract_version"] == "1.0"
    assert "request" in body
    assert "candidates" in body
    assert isinstance(body["candidates"], list)
    assert len(body["candidates"]) >= 1  # Should return 1-3 candidates
    assert len(body["candidates"]) <= 3


@patch("app.main.retrieval_module.retrieve_product_cards_with_fallback", side_effect=lambda *a, **k: (_mock_candidates(), False))
def test_retrieve_product_candidates_minimal_request(_mock_retrieve):
    """Test POST /mcp/retrieve_product_candidates with minimal required fields."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "query_signature": "test_query",
        },
    }
    r = c.post("/mcp/retrieve_product_candidates", json=payload)
    assert r.status_code == 200
    body = r.json()
    
    # Validate against JSON schema
    jsonschema.validate(instance=body, schema=PRODUCT_CANDIDATES_SCHEMA)
    
    assert len(body["candidates"]) >= 1
    assert len(body["candidates"]) <= 3
