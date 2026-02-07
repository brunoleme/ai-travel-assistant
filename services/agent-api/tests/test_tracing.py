"""Tracing tests (no LangSmith network calls)."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

from app.main import app
from app.tracing import NoopTracer, set_tracer, user_query_hash

VALID_EVIDENCE = {
    "x_contract_version": "1.0",
    "request": {"user_query": "dicas Disney"},
    "evidence": [{
        "card_id": "evid_001_tips",
        "summary": "Best times to visit are early morning.",
        "signals": [],
        "places": [],
        "categories": [],
        "primary_category": "tips",
        "confidence": 0.9,
        "source_url": "https://example.com/tips",
    }],
}
EMPTY_PRODUCTS = {
    "x_contract_version": "1.0",
    "request": {"query_signature": "any:dicas Disney:en"},
    "candidates": [],
}


def test_user_query_hash() -> None:
    """user_query_hash returns consistent short hash, not raw query."""
    h = user_query_hash("dicas para Disney")
    assert len(h) == 16
    assert h == user_query_hash("dicas para Disney")
    assert h != user_query_hash("other query")


def test_noop_tracer_span() -> None:
    """NoopTracer span is a no-op context manager."""
    tracer = NoopTracer()
    with tracer.span("test", {"k": "v"}):
        pass


def test_pipeline_spans_called_with_tags() -> None:
    """Fake tracer injected: both spans called with session_id, request_id, user_query_hash."""
    spans_called: list[tuple[str, dict]] = []

    class FakeTracer:
        @contextmanager
        def span(self, name: str, tags: dict):
            spans_called.append((name, dict(tags)))
            yield

    with (
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock, return_value=VALID_EVIDENCE),
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock, return_value=EMPTY_PRODUCTS),
    ):
        set_tracer(FakeTracer())
        try:
            client = TestClient(app)
            with client.websocket_connect("/ws") as ws:
                ws.send_json({
                    "session_id": "sess-123",
                    "request_id": "req-456",
                    "user_query": "dicas Disney",
                })
                ws.receive_json()
        finally:
            set_tracer(None)

    names = [s[0] for s in spans_called]
    assert "answer_generation" in names
    assert "product_decision" in names

    for _name, tags in spans_called:
        assert tags.get("session_id") == "sess-123"
        assert tags.get("request_id") == "req-456"
        assert "user_query_hash" in tags
        assert tags["user_query_hash"] == user_query_hash("dicas Disney")
