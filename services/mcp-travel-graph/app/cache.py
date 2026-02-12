"""In-memory TTL cache for graph responses. Key = normalized(user_query, destination, lang)."""

from __future__ import annotations

import os
import re
import time
from typing import Any


def _normalize_string(s: str | None) -> str:
    """Trim, collapse whitespace, lowercase. None -> ''."""
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def build_cache_key(
    user_query: str,
    destination: str | None,
    lang: str | None,
) -> str:
    """Build cache key from normalized request parts."""
    return "|".join(
        [
            _normalize_string(user_query),
            _normalize_string(destination),
            _normalize_string(lang),
        ]
    )


def get_ttl_seconds() -> int:
    """TTL in seconds from env GRAPH_CACHE_TTL_SECONDS (default 300)."""
    return int(os.environ.get("GRAPH_CACHE_TTL_SECONDS", "300"))


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
