"""In-memory metrics since process start (request_count, error_count, latency_ms)."""

from __future__ import annotations

_metrics: dict[str, int | float] = {
    "request_count": 0,
    "error_count": 0,
    "sum_latency_ms": 0.0,
}


def record_request(latency_ms: float, error: bool = False) -> None:
    """Record one MCP request for metrics."""
    _metrics["request_count"] = _metrics.get("request_count", 0) + 1
    _metrics["sum_latency_ms"] = _metrics.get("sum_latency_ms", 0.0) + latency_ms
    if error:
        _metrics["error_count"] = _metrics.get("error_count", 0) + 1


def get_metrics() -> dict[str, int | float]:
    """Return current metrics as dict (for /metrics endpoint)."""
    total = _metrics.get("request_count", 0)
    sum_ms = _metrics.get("sum_latency_ms", 0.0)
    avg = sum_ms / total if total else 0.0
    return {
        "request_count": total,
        "error_count": _metrics.get("error_count", 0),
        "latency_ms_avg": round(avg, 2),
    }


def reset_metrics() -> None:
    """Reset in-memory counters (for tests only)."""
    _metrics["request_count"] = 0
    _metrics["error_count"] = 0
    _metrics["sum_latency_ms"] = 0.0
