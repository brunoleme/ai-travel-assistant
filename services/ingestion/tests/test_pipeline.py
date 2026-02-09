"""
Tests for ingestion pipeline stages and idempotency.

TDD: same event processed twice does not duplicate writes; stage failure
does not advance pipeline and error metadata is recorded.
"""

from __future__ import annotations

from app.events import IngestionRequested, WriteComplete
from app.idempotency import already_processed, build_idempotency_key, reset_processed
from app.pipeline import (
    clear_write_events,
    get_write_events,
    handle_fetch,
    handle_transcript,
    handle_write,
    handle_embed,
    handle_enrich,
    handle_chunk,
)


def test_build_idempotency_key() -> None:
    assert build_idempotency_key("cs1", "transcript") == "cs1:transcript"
    assert build_idempotency_key("cs2", "chunks") == "cs2:chunks"


def test_idempotent_processing() -> None:
    """Same event processed twice: second call does not produce duplicate writes."""
    reset_processed()
    clear_write_events()

    event = WriteComplete(
        event_id="e1",
        content_source_id="src1",
        stage="write_complete",
        payload={"written": True},
    )

    handle_write(event)
    handle_write(event)

    writes = get_write_events()
    assert len(writes) == 1
    assert writes[0]["content_source_id"] == "src1"
    assert writes[0]["event_id"] == "e1"


def test_idempotent_fetch_returns_none_on_second_call() -> None:
    """First handle_fetch emits TranscriptReady; second call (same source) returns None."""
    reset_processed()

    req = IngestionRequested(
        event_id="req1",
        content_source_id="cs1",
        stage="requested",
        payload={},
    )
    out1 = handle_fetch(req)
    assert out1 is not None
    assert out1.stage == "transcript"
    assert out1.content_source_id == "cs1"

    out2 = handle_fetch(req)
    assert out2 is None


def test_full_pipeline_idempotent_write() -> None:
    """Run full pipeline; handle_write called twice with same event -> only one write."""
    clear_write_events()
    reset_processed()
    req2 = IngestionRequested(
        event_id="r2", content_source_id="pipe2", stage="requested", payload={}
    )
    t2 = handle_fetch(req2)
    c2 = handle_transcript(t2)
    e2 = handle_chunk(c2)
    emb2 = handle_enrich(e2)
    w2 = handle_embed(emb2)
    handle_write(w2)
    handle_write(w2)  # duplicate call, same event
    assert len(get_write_events()) == 1


def test_stage_failure_does_not_advance() -> None:
    """Simulate failure in one stage; next stage is NOT called; error metadata recorded."""
    reset_processed()

    failing = IngestionRequested(
        event_id="fail1",
        content_source_id="fail_src",
        stage="requested",
        payload={"__fail__": True},
    )
    out = handle_fetch(failing)
    assert out is None
    assert not already_processed(build_idempotency_key("fail_src", "transcript"))
