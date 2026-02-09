"""
Tests for DLQ handling and retry policy.

- Failing stage retries N times.
- After N failures, event is stored in DLQ.
- Replay moves event back to active pipeline.
"""

from __future__ import annotations

from app.dlq import (
    clear_dlq,
    clear_requeue,
    get_dlq,
    get_requeue,
    handle_failure,
    replay_dlq_to_requeue,
)
from app.events import IngestionRequested


def test_failing_stage_retries_n_times() -> None:
    """Failure with retry_count < max_retries results in requeue, not DLQ."""
    clear_dlq()
    clear_requeue()

    event = IngestionRequested(
        event_id="e1",
        content_source_id="cs1",
        stage="requested",
        payload={},
        retry_count=0,
        max_retries=3,
    )
    handle_failure(event, "simulated error")

    assert len(get_dlq()) == 0
    requeue = get_requeue()
    assert len(requeue) == 1
    assert requeue[0]["retry_count"] == 1
    assert requeue[0]["error"] == "simulated error"


def test_after_n_failures_event_stored_in_dlq() -> None:
    """After max_retries failures, event is stored in DLQ and not requeued."""
    clear_dlq()
    clear_requeue()

    event = IngestionRequested(
        event_id="e2",
        content_source_id="cs2",
        stage="requested",
        payload={},
        retry_count=2,  # one more will make it 3 >= max_retries=3
        max_retries=3,
    )
    handle_failure(event, "final error")

    assert len(get_requeue()) == 0
    dlq = get_dlq()
    assert len(dlq) == 1
    assert dlq[0]["content_source_id"] == "cs2"
    assert dlq[0]["retry_count"] == 3
    assert dlq[0]["error"] == "final error"


def test_replay_moves_event_back_to_active_pipeline() -> None:
    """Replay moves events from DLQ to requeue (active pipeline)."""
    clear_dlq()
    clear_requeue()

    event = IngestionRequested(
        event_id="e3",
        content_source_id="cs3",
        stage="requested",
        payload={},
        retry_count=3,
        max_retries=3,
    )
    handle_failure(event, "exhausted")
    assert len(get_dlq()) == 1
    assert len(get_requeue()) == 0

    n = replay_dlq_to_requeue()
    assert n == 1
    assert len(get_dlq()) == 0
    requeue = get_requeue()
    assert len(requeue) == 1
    assert requeue[0]["event_id"] == "e3"
    assert requeue[0]["content_source_id"] == "cs3"
