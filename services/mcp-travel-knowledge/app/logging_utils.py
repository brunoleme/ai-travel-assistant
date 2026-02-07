"""Structured request logging (one JSON line per request)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


SERVICE_NAME = "mcp-travel-knowledge"


def log_request(
    route: str,
    cache_hit: bool,
    latency_ms: float,
    session_id: str | None = None,
    request_id: str | None = None,
    weaviate_fallback: bool = False,
) -> None:
    """Emit one JSON line with required fields."""
    payload: dict[str, Any] = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "service": SERVICE_NAME,
        "route": route,
        "cache_hit": cache_hit,
        "latency_ms": round(latency_ms, 2),
        "session_id": session_id,
        "request_id": request_id,
        "weaviate_fallback": weaviate_fallback,
    }
    print(json.dumps(payload))
