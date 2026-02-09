"""
Dead-letter queue and retry handling for the ingestion pipeline.

On stage failure: increment retry_count; requeue if under max_retries,
otherwise append to DLQ with error reason.
"""

from __future__ import annotations

from typing import Any

# In-memory queues for local/mock use. Production would use SQS.
_requeue: list[dict[str, Any]] = []
DLQ: list[dict[str, Any]] = []


def handle_failure(event: Any, error_msg: str) -> None:
    """
    Record failure and either requeue (retry) or send to DLQ.

    Increment retry_count. If retry_count < max_retries, requeue the event.
    Otherwise append to DLQ with error reason and do not requeue.
    """
    if hasattr(event, "model_dump"):
        doc = event.model_dump()
    else:
        doc = dict(event)
    retry_count = doc.get("retry_count", 0) + 1
    doc["retry_count"] = retry_count
    doc["error"] = error_msg
    max_retries = doc.get("max_retries", 3)
    if retry_count < max_retries:
        _requeue.append(doc)
    else:
        DLQ.append(doc)


def get_requeue() -> list[dict[str, Any]]:
    """Return the current requeue list (for tests / worker)."""
    return list(_requeue)


def pop_requeued() -> dict[str, Any] | None:
    """Pop one event from the requeue list, or None if empty."""
    if not _requeue:
        return None
    return _requeue.pop(0)


def get_dlq() -> list[dict[str, Any]]:
    """Return the current DLQ contents (for tests / replay)."""
    return list(DLQ)


def clear_dlq() -> None:
    """Clear the DLQ (for tests)."""
    DLQ.clear()


def clear_requeue() -> None:
    """Clear the requeue list (for tests)."""
    _requeue.clear()


def replay_dlq_to_requeue() -> int:
    """
    Move all events from DLQ back to the requeue (active pipeline).
    Returns the number of events replayed.
    """
    n = len(DLQ)
    while DLQ:
        _requeue.append(DLQ.pop(0))
    return n
