from __future__ import annotations

import json

from fastapi import FastAPI

from app import cache as cache_module
from app import retrieval as retrieval_module
from app.models import (
    ProductCandidate,
    ProductCandidatesRequest,
    ProductCandidatesResponse,
)


app = FastAPI(title="mcp-travel-products", version="0.1.0")


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


@app.post("/mcp/retrieve_product_candidates", response_model=ProductCandidatesResponse)
def retrieve_product_candidates(req: ProductCandidatesRequest) -> ProductCandidatesResponse:
    """Retrieve product candidates from Weaviate ProductCard; uses in-memory TTL cache. min_confidence applied as post-filter."""
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
        log_line = json.dumps({"cache_hit": True})
        print(log_line)
        return ProductCandidatesResponse(
            x_contract_version="1.0",
            request=req.request,
            candidates=filtered,
        )
    client = retrieval_module.get_client()
    limit = req.request.limit or 10
    raw = retrieval_module.retrieve_product_cards(
        client,
        query_signature=req.request.query_signature,
        limit=limit,
        min_confidence=None,
    )
    cache_module.set_(key, {"candidates": [c.model_dump() for c in raw]})
    filtered = _filter_by_min_confidence(raw, req.request.min_confidence)
    log_line = json.dumps({"cache_hit": False})
    print(log_line)
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
