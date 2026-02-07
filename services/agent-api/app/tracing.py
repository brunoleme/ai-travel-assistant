"""Injectable tracing abstraction (NoopTracer / LangSmithTracer)."""

from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from typing import Protocol


def user_query_hash(user_query: str) -> str:
    """Hash user_query for tags; do not log raw query."""
    return hashlib.sha256(user_query.encode()).hexdigest()[:16]


class Tracer(Protocol):
    """Tracer interface with span(name, tags) context manager."""

    @contextmanager
    def span(self, name: str, tags: dict[str, str]):
        """Enter/exit a span with given name and tags."""
        ...


class NoopTracer:
    """Default no-op tracer."""

    @contextmanager
    def span(self, name: str, tags: dict[str, str]):
        yield


def _make_langsmith_tracer() -> Tracer:
    """Create LangSmithTracer; on any failure return NoopTracer."""
    if os.environ.get("LANGSMITH_ENABLED") != "1":
        return NoopTracer()
    if not os.environ.get("LANGSMITH_API_KEY"):
        return NoopTracer()
    try:
        return _LangSmithTracer()
    except Exception:
        return NoopTracer()


class _LangSmithTracer:
    """LangSmith tracer; uses RunTree for spans."""

    def __init__(self) -> None:
        from langsmith import Client
        self._client = Client()

    @contextmanager
    def span(self, name: str, tags: dict[str, str]):
        from langsmith.run_trees import RunTree
        run = RunTree(
            name=name,
            run_type="chain",
            extra={"metadata": tags},
        )
        try:
            yield
        finally:
            run.end()
            try:
                run.patch()
            except Exception:
                pass


_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    """Return the global tracer (NoopTracer or LangSmithTracer)."""
    global _tracer
    if _tracer is None:
        _tracer = _make_langsmith_tracer()
    return _tracer


def set_tracer(t: Tracer | None) -> None:
    """Set tracer (for tests); None resets to default."""
    global _tracer
    _tracer = t
