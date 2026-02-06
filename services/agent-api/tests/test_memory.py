"""Session memory tests (TDD)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

from app.main import app
from app.memory_store import summary, update


def test_memory_updated_after_ws_messages() -> None:
    """After two messages in same session, summary changes predictably."""
    valid_evidence = {
        "card_id": "evid_001_tip",
        "summary": "Best times to visit are early morning.",
        "signals": [],
        "places": [],
        "categories": [],
        "primary_category": "tips",
        "confidence": 0.9,
        "source_url": "https://example.com/tip",
    }
    with (
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock) as m_ev,
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock) as m_prod,
    ):
        m_ev.return_value = {
            "x_contract_version": "1.0",
            "request": {"user_query": "dicas Disney"},
            "evidence": [valid_evidence],
        }
        m_prod.return_value = {
            "x_contract_version": "1.0",
            "request": {"query_signature": "any:dicas Disney:en"},
            "candidates": [],
        }

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"session_id": "sess01", "request_id": "r1", "user_query": "dicas Disney"}
            )
            ws.receive_json()

            ws.send_json(
                {
                    "session_id": "sess01",
                    "request_id": "r2",
                    "user_query": "we need wheelchair access and travel with 2 kids",
                }
            )
            ws.receive_json()

        s = summary("sess01")
        assert len(s) <= 500
        assert "kids" in s.lower() or "2" in s or "wheelchair" in s.lower()


def test_memory_summary_in_mcp_requests() -> None:
    """memory_summary included in outbound MCP requests (mock MCP, inspect call args)."""
    m_ev = AsyncMock(
        return_value={
            "x_contract_version": "1.0",
            "request": {"user_query": "budget trip to Orlando with kids"},
            "evidence": [],
        }
    )
    m_prod = AsyncMock(
        return_value={
            "x_contract_version": "1.0",
            "request": {"query_signature": "orlando:budget trip:en"},
            "candidates": [],
        }
    )

    with (
        patch("app.main.retrieve_travel_evidence", m_ev),
        patch("app.main.retrieve_product_candidates", m_prod),
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {
                    "session_id": "session123",
                    "request_id": "r1",
                    "user_query": "budget trip to Orlando with kids",
                }
            )
            ws.receive_json()

    ev_request = m_ev.call_args[0][2]
    strategy = ev_request.get("strategy_params") or {}
    assert "memory_summary" in strategy
    assert strategy.get("version") == "v1"

    prod_request = m_prod.call_args[0][2]
    qs = prod_request.get("query_signature", "")
    assert "|mem:" in qs
    assert len(qs.split("|mem:")[-1]) >= 8


def test_memory_isolates_sessions() -> None:
    """Memory store isolates sessions: s1 != s2."""
    update("sess_a", "luxury hotels in Paris", None)
    update("sess_b", "cheap hostels in Tokyo", None)

    sa = summary("sess_a")
    sb = summary("sess_b")

    assert sa != sb
