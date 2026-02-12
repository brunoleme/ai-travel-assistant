"""In-memory metrics since process start (requests_total, cache_hits_total, neo4j_fallback_total, avg_latency_ms)."""

from __future__ import annotations

_metrics: dict[str, int | float] = {
    "requests_total": 0,
    "cache_hits_total": 0,
    "neo4j_fallback_total": 0,
    "sum_latency_ms": 0.0,
}


def record_request(
    cache_hit: bool,
    latency_ms: float,
    neo4j_fallback: bool = False,
) -> None:
    """Record one MCP request for metrics."""
    _metrics["requests_total"] = _metrics.get("requests_total", 0) + 1
    _metrics["sum_latency_ms"] = _metrics.get("sum_latency_ms", 0.0) + latency_ms
    if cache_hit:
        _metrics["cache_hits_total"] = _metrics.get("cache_hits_total", 0) + 1
    if neo4j_fallback:
        _metrics["neo4j_fallback_total"] = _metrics.get("neo4j_fallback_total", 0) + 1


def get_metrics() -> dict[str, int | float]:
    """Return current metrics as dict (for /metrics endpoint)."""
    total = _metrics.get("requests_total", 0)
    sum_ms = _metrics.get("sum_latency_ms", 0.0)
    avg = sum_ms / total if total else 0.0
    return {
        "requests_total": total,
        "cache_hits_total": _metrics.get("cache_hits_total", 0),
        "neo4j_fallback_total": _metrics.get("neo4j_fallback_total", 0),
        "avg_latency_ms": round(avg, 2),
    }


def reset_metrics() -> None:
    """Reset in-memory counters (for tests only)."""
    _metrics["requests_total"] = 0
    _metrics["cache_hits_total"] = 0
    _metrics["neo4j_fallback_total"] = 0
    _metrics["sum_latency_ms"] = 0.0
