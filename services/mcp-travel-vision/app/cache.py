"""In-memory TTL cache for vision responses. Key = hash(image_ref) + mode + trip_context snapshot."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any


def build_cache_key(
    image_ref: str, mode: str, trip_context: dict[str, Any] | None
) -> str:
    """Build cache key from image_ref hash, mode, and JSON-stringified trip_context."""
    h = hashlib.sha256(image_ref.encode("utf-8", errors="replace")).hexdigest()[:32]
    ctx_snapshot = json.dumps(trip_context or {}, sort_keys=True)
    return f"{h}|{mode}|{ctx_snapshot}"


def get_ttl_seconds() -> int:
    """TTL in seconds from env VISION_CACHE_TTL_SECONDS (default 3600 = 1h)."""
    return int(os.environ.get("VISION_CACHE_TTL_SECONDS", "3600"))


_store: dict[str, tuple[Any, float]] = {}


def get(key: str) -> dict[str, Any] | None:
    """Return cached value if present and not expired, else None."""
    if key not in _store:
        return None
    value, expires_at = _store[key]
    if time.time() >= expires_at:
        del _store[key]
        return None
    return value


def set_(key: str, value: dict[str, Any]) -> None:
    """Store value with TTL from env."""
    ttl = get_ttl_seconds()
    _store[key] = (value, time.time() + ttl)


def clear_for_tests() -> None:
    """Clear in-memory cache (for tests only)."""
    _store.clear()
