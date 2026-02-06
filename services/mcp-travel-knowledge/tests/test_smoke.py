from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app

# Load the contract schema
SCHEMA_PATH = Path(__file__).parent.parent.parent.parent / "contracts" / "travel_evidence.schema.json"
with open(SCHEMA_PATH) as f:
    TRAVEL_EVIDENCE_SCHEMA = json.load(f)


# Fixture raw Weaviate RecommendationCard objects (no network) for mocking retrieval
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
    {
        "uuid": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        "summary": "Use FastPass+ by booking high-demand attractions first thing in the morning.",
        "signals": ["fastpass", "planning"],
        "places": ["Orlando", "Disney World"],
        "categories": ["strategy", "fastpass"],
        "primaryCategory": "strategy",
        "confidence": 0.78,
        "timestampUrl": "https://youtube.com/watch?v=xyz&t=120",
        "videoUploadDate": "2024-02-20T14:15:00Z",
    },
]


def test_health() -> None:
    """Test GET /health endpoint."""
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@patch("app.main.retrieval_module.get_recommendation_cards", return_value=WEAVIATE_CARDS_FIXTURE)
def test_retrieve_travel_evidence_schema_validation(mock_get_cards: object) -> None:
    """Test POST /mcp/retrieve_travel_evidence validates against contract schema (no network)."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "user_query": "dicas para evitar filas na Disney",
            "destination": "Orlando",
            "lang": "pt-BR",
            "debug": True,
        },
    }
    r = c.post("/mcp/retrieve_travel_evidence", json=payload)
    assert r.status_code == 200
    body = r.json()
    
    # Validate against JSON schema
    jsonschema.validate(instance=body, schema=TRAVEL_EVIDENCE_SCHEMA)
    
    # Additional assertions
    assert "x_contract_version" in body
    assert body["x_contract_version"] == "1.0"
    assert "request" in body
    assert "evidence" in body
    assert isinstance(body["evidence"], list)
    assert len(body["evidence"]) >= 1
    assert len(body["evidence"]) <= 2
    mock_get_cards.assert_called_once()


@patch("app.main.retrieval_module.get_recommendation_cards", return_value=WEAVIATE_CARDS_FIXTURE)
def test_retrieve_travel_evidence_minimal_request(mock_get_cards: object) -> None:
    """Test POST /mcp/retrieve_travel_evidence with minimal required fields (no network)."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "user_query": "test query",
        },
    }
    r = c.post("/mcp/retrieve_travel_evidence", json=payload)
    assert r.status_code == 200
    body = r.json()
    
    # Validate against JSON schema
    jsonschema.validate(instance=body, schema=TRAVEL_EVIDENCE_SCHEMA)
    
    assert len(body["evidence"]) >= 1
    assert len(body["evidence"]) <= 2


@patch("app.main.retrieval_module.get_recommendation_cards", return_value=WEAVIATE_CARDS_FIXTURE)
def test_retrieve_travel_evidence_always_returns_contract_version_1_0(mock_get_cards: object) -> None:
    """Test that response always returns x_contract_version="1.0" regardless of request version."""
    c = TestClient(app)
    payload = {
        "x_contract_version": "2.0",
        "request": {
            "user_query": "test query",
        },
    }
    r = c.post("/mcp/retrieve_travel_evidence", json=payload)
    assert r.status_code == 200
    body = r.json()
    
    assert body["x_contract_version"] == "1.0"
    jsonschema.validate(instance=body, schema=TRAVEL_EVIDENCE_SCHEMA)
