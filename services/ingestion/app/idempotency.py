"""
Idempotency for ingestion pipeline stages.

Key strategy: {content_source_id}:{stage}. Same key processed twice must not
produce duplicate writes.
"""

from __future__ import annotations

_processed: set[str] = set()


def build_idempotency_key(content_source_id: str, stage: str) -> str:
    """Build a unique idempotency key for a content source and stage."""
    return f"{content_source_id}:{stage}"


def already_processed(key: str) -> bool:
    """Return True if this key has already been successfully processed."""
    return key in _processed


def mark_processed(key: str) -> None:
    """Mark a key as processed (call after successful stage completion)."""
    _processed.add(key)


def reset_processed() -> None:
    """Clear the in-memory store. For tests only."""
    _processed.clear()
