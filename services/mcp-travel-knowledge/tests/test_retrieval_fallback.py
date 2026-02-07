"""
Tests for Weaviate fallback: retrieval never raises, endpoint returns 200 with valid contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
from fastapi.testclient import TestClient

from app.main import app
from app import cache as cache_module
from app import retrieval as retrieval_module

SCHEMA_PATH = Path(__file__).parent.parent.parent.parent / "contracts" / "travel_evidence.schema.json"
with open(SCHEMA_PATH) as f:
    TRAVEL_EVIDENCE_SCHEMA = json.load(f)


def test_connection_failure_returns_empty_list() -> None:
    """Mock weaviate.connect_to_local to raise; get_recommendation_cards() returns [] and does not raise."""
    with patch("app.retrieval.weaviate") as mock_weaviate:
        mock_weaviate.connect_to_local.side_effect = Exception("connection refused")
        result = retrieval_module.get_recommendation_cards("test query", limit=5)
    assert result == []


def test_query_failure_returns_empty_list() -> None:
    """Mock client exists but query raises; get_recommendation_cards() returns []."""
    with patch.object(retrieval_module, "_get_client") as mock_get_client:
        mock_client = mock_get_client.return_value
        mock_client.collections.get.return_value.query.near_text.side_effect = Exception("query failed")
        result = retrieval_module.get_recommendation_cards("test", limit=5)
    assert result == []


def test_endpoint_returns_200_when_retrieval_raises() -> None:
    """Patch retrieval to raise; POST to endpoint. Assert 200, evidence==[], response validates against schema."""
    payload = {
        "x_contract_version": "1.0",
        "request": {"user_query": "disney tips", "destination": "Orlando"},
    }
    with patch.object(cache_module, "get", return_value=None), patch.object(
        retrieval_module, "get_recommendation_cards", side_effect=Exception("weaviate down")
    ):
        client = TestClient(app)
        r = client.post("/mcp/retrieve_travel_evidence", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body.get("evidence") == []
    jsonschema.validate(instance=body, schema=TRAVEL_EVIDENCE_SCHEMA)
