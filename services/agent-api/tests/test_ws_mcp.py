"""WebSocket MCP integration tests (mocked, no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


VALID_EVIDENCE_RESPONSE = {
    "x_contract_version": "1.0",
    "request": {"user_query": "dicas Disney"},
    "evidence": [
        {
            "card_id": "evid_001_tips",
            "summary": "Best times to visit are early morning.",
            "signals": ["timing"],
            "places": ["Orlando"],
            "categories": ["tips"],
            "primary_category": "tips",
            "confidence": 0.9,
            "source_url": "https://example.com/tips",
        },
    ],
}

EMPTY_PRODUCTS_RESPONSE = {
    "x_contract_version": "1.0",
    "request": {"query_signature": "orlando:disney:pt-BR"},
    "candidates": [],
}


@pytest.fixture
def mock_mcp():
    """Patch MCP client to avoid network calls."""
    with (
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock) as m_ev,
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock) as m_prod,
    ):
        m_ev.return_value = VALID_EVIDENCE_RESPONSE
        m_prod.return_value = EMPTY_PRODUCTS_RESPONSE
        yield m_ev, m_prod


def test_ws_builds_answer_from_evidence(mock_mcp) -> None:
    """answer_text built from evidence summaries; citations from source_url; addon None."""
    m_ev, m_prod = mock_mcp
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json(
            {
                "session_id": "s1",
                "request_id": "r1",
                "user_query": "dicas para evitar filas no Magic Kingdom",
            }
        )
        resp = ws.receive_json()

    assert resp["session_id"] == "s1"
    assert resp["request_id"] == "r1"
    assert "answer_text" in resp
    assert "Best times to visit are early morning." in resp["answer_text"]
    assert resp["citations"] == ["https://example.com/tips"]
    assert resp["addon"] is None
    m_ev.assert_called_once()
    m_prod.assert_called_once()


def test_ws_products_failure_still_returns_answer(mock_mcp) -> None:
    """Works even if products MCP fails; addon is None."""
    m_ev, m_prod = mock_mcp
    m_prod.side_effect = Exception("network error")
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json(
            {"session_id": "s2", "request_id": "r2", "user_query": "dicas Disney"}
        )
        resp = ws.receive_json()

    assert resp["session_id"] == "s2"
    assert resp["request_id"] == "r2"
    assert "answer_text" in resp
    assert "Best times to visit" in resp["answer_text"]
    assert resp["addon"] is None
