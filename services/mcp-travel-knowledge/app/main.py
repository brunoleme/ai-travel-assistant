from __future__ import annotations

import time

from fastapi import FastAPI, Request

from app import adapter as adapter_module
from app import cache as cache_module
from app import logging_utils as logging_utils_module
from app import metrics as metrics_module
from app import retrieval as retrieval_module
from app.models import (
    RetrieveTravelEvidencePayload,
    RetrieveTravelEvidenceResponse,
    TravelEvidenceCard,
)


app = FastAPI(title="mcp-travel-knowledge", version="0.1.0")


def _session_request_ids(request: Request) -> tuple[str | None, str | None]:
    """Read x-session-id and x-request-id from headers; default None."""
    session_id = request.headers.get("x-session-id") or None
    request_id = request.headers.get("x-request-id") or None
    return session_id, request_id


@app.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> dict:
    """Lightweight JSON metrics (in-memory since process start)."""
    return metrics_module.get_metrics()


def _strategy_params_version(payload: RetrieveTravelEvidencePayload) -> str:
    """Version string for cache key: strategy_params.version or 'v0'."""
    if payload.request.strategy_params is None:
        return "v0"
    return str(payload.request.strategy_params.get("version", "v0"))


def _fetch_evidence_cards(query: str, limit: int = 5) -> list[TravelEvidenceCard]:
    """Fetch raw cards from Weaviate and map to contract evidence (uses retrieval + adapter)."""
    raw_list = retrieval_module.get_recommendation_cards(query=query, limit=limit)
    evidence_items: list[TravelEvidenceCard] = []
    for raw in raw_list:
        try:
            mapped = adapter_module.weaviate_card_to_evidence(raw)
            evidence_items.append(TravelEvidenceCard(**mapped))
        except (ValueError, TypeError):
            continue
    return evidence_items


@app.post("/mcp/retrieve_travel_evidence", response_model=RetrieveTravelEvidenceResponse)
def retrieve_travel_evidence(request: Request, payload: RetrieveTravelEvidencePayload) -> RetrieveTravelEvidenceResponse:
    """Retrieve travel evidence from Weaviate RecommendationCard; map to contract schema. Uses in-memory TTL cache."""
    route = "/mcp/retrieve_travel_evidence"
    session_id, request_id = _session_request_ids(request)
    t0 = time.perf_counter()

    key = cache_module.build_cache_key(
        payload.request.user_query,
        payload.request.destination,
        payload.request.lang,
        _strategy_params_version(payload),
    )
    cached = cache_module.get(key)
    if cached is not None:
        evidence = [TravelEvidenceCard(**e) for e in cached["evidence"]]
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
        return RetrieveTravelEvidenceResponse(
            x_contract_version="1.0",
            request=payload.request,
            expanded_queries=cached.get("expanded_queries"),
            evidence=evidence,
            debug=cached.get("debug"),
        )
    try:
        evidence_items = _fetch_evidence_cards(payload.request.user_query, limit=5)
        dbg = {"evidence_count": len(evidence_items)} if payload.request.debug else None
        cache_module.set_(key, {
            "evidence": [c.model_dump() for c in evidence_items],
            "expanded_queries": None,
            "debug": dbg,
        })
        latency_ms = (time.perf_counter() - t0) * 1000
        metrics_module.record_request(cache_hit=False, latency_ms=latency_ms, weaviate_fallback=False)
        logging_utils_module.log_request(
            route=route,
            cache_hit=False,
            latency_ms=latency_ms,
            session_id=session_id,
            request_id=request_id,
            weaviate_fallback=False,
        )
        return RetrieveTravelEvidenceResponse(
            x_contract_version="1.0",
            request=payload.request,
            expanded_queries=None,
            evidence=evidence_items,
            debug=dbg,
        )
    except Exception:
        latency_ms = (time.perf_counter() - t0) * 1000
        metrics_module.record_request(cache_hit=False, latency_ms=latency_ms, weaviate_fallback=True)
        logging_utils_module.log_request(
            route=route,
            cache_hit=False,
            latency_ms=latency_ms,
            session_id=session_id,
            request_id=request_id,
            weaviate_fallback=True,
        )
        return RetrieveTravelEvidenceResponse(
            x_contract_version="1.0",
            request=payload.request,
            expanded_queries=None,
            evidence=[],
            debug={"evidence_count": 0} if payload.request.debug else None,
        )


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8010, reload=True)


if __name__ == "__main__":
    main()
