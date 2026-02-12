"""Structured request logging (one JSON line per request)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


SERVICE_NAME = "mcp-travel-tts"


def log_request(
    route: str,
    latency_ms: float,
    session_id: str | None = None,
    request_id: str | None = None,
    error: bool = False,
) -> None:
    """Emit one JSON line with required fields."""
    payload: dict[str, Any] = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "service": SERVICE_NAME,
        "route": route,
        "latency_ms": round(latency_ms, 2),
        "session_id": session_id,
        "request_id": request_id,
        "error": error,
    }
    print(json.dumps(payload))
