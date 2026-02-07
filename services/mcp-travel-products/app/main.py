from __future__ import annotations

import time

from fastapi import FastAPI, Request

from app import cache as cache_module
from app import logging_utils as logging_utils_module
from app import metrics as metrics_module
from app import retrieval as retrieval_module
from app.models import (
    ProductCandidate,
    ProductCandidatesRequest,
    ProductCandidatesResponse,
)


app = FastAPI(title="mcp-travel-products", version="0.1.0")


def _session_request_ids(request: Request) -> tuple[str | None, str | None]:
    """Read x-session-id and x-request-id from headers; default None."""
    session_id = request.headers.get("x-session-id") or None
    request_id = request.headers.get("x-request-id") or None
    return session_id, request_id


def _filter_by_min_confidence(
    candidates: list[ProductCandidate],
    min_confidence: float | None,
) -> list[ProductCandidate]:
    """Apply min_confidence as deterministic post-filter (approach B)."""
    if min_confidence is None:
        return candidates
    return [c for c in candidates if c.confidence >= min_confidence]


@app.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> dict:
    """Lightweight JSON metrics (in-memory since process start)."""
    return metrics_module.get_metrics()


@app.post("/mcp/retrieve_product_candidates", response_model=ProductCandidatesResponse)
def retrieve_product_candidates(request: Request, req: ProductCandidatesRequest) -> ProductCandidatesResponse:
    """Retrieve product candidates from Weaviate ProductCard; uses in-memory TTL cache. min_confidence applied as post-filter."""
    route = "/mcp/retrieve_product_candidates"
    session_id, request_id = _session_request_ids(request)
    t0 = time.perf_counter()

    key = cache_module.build_cache_key(
        req.request.query_signature,
        req.request.market,
        req.request.destination,
        req.request.lang,
    )
    cached = cache_module.get(key)
    if cached is not None:
        raw = [ProductCandidate(**d) for d in cached["candidates"]]
        filtered = _filter_by_min_confidence(raw, req.request.min_confidence)
        latency_ms = (time.perf_counter() - t0) * 1000
        metrics_module.record_request(cache_hit=True, latency_ms=latency_ms, weaviate_fallback=False)
        logging_utils_module.log_request(
            route=route,
            cache_hit=True,
            latency_ms=latency_ms,
            session_id=session_id,
            request_id=request_id,
            weaviate_fallback=False,
        )
        return ProductCandidatesResponse(
            x_contract_version="1.0",
            request=req.request,
            candidates=filtered,
        )
    client = retrieval_module.get_client()
    limit = req.request.limit or 10
    raw, weaviate_fallback = retrieval_module.retrieve_product_cards_with_fallback(
        client,
        query_signature=req.request.query_signature,
        limit=limit,
        min_confidence=None,
    )
    cache_module.set_(key, {"candidates": [c.model_dump() for c in raw]})
    filtered = _filter_by_min_confidence(raw, req.request.min_confidence)
    latency_ms = (time.perf_counter() - t0) * 1000
    metrics_module.record_request(cache_hit=False, latency_ms=latency_ms, weaviate_fallback=weaviate_fallback)
    logging_utils_module.log_request(
        route=route,
        cache_hit=False,
        latency_ms=latency_ms,
        session_id=session_id,
        request_id=request_id,
        weaviate_fallback=weaviate_fallback,
    )
    return ProductCandidatesResponse(
        x_contract_version="1.0",
        request=req.request,
        candidates=filtered,
    )


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8020, reload=True)


if __name__ == "__main__":
    main()
