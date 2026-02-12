from __future__ import annotations

import time

from fastapi import FastAPI, Request

from app import cache as cache_module
from app import logging_utils as logging_utils_module
from app import metrics as metrics_module
from app import retrieval as retrieval_module
from app.models import (
    GraphNode,
    GraphEdge,
    Subgraph,
    RetrieveTravelGraphPayload,
    RetrieveTravelGraphResponse,
)


app = FastAPI(title="mcp-travel-graph", version="0.1.0")


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


def _from_cache_value(cached: dict) -> tuple[Subgraph, list | None]:
    """Rebuild Subgraph and paths from cached dict."""
    nodes = [GraphNode(**n) for n in cached.get("nodes", [])]
    edges = [GraphEdge(**e) for e in cached.get("edges", [])]
    subgraph = Subgraph(nodes=nodes, edges=edges)
    paths_raw = cached.get("paths")
    if not paths_raw:
        return subgraph, None
    from app.models import PathItem

    paths = [PathItem(**p) for p in paths_raw]
    return subgraph, paths


@app.post("/mcp/retrieve_travel_graph", response_model=RetrieveTravelGraphResponse)
def retrieve_travel_graph(
    request: Request, payload: RetrieveTravelGraphPayload
) -> RetrieveTravelGraphResponse:
    """Retrieve travel graph (subgraph + optional paths) from Neo4j; uses in-memory TTL cache."""
    route = "/mcp/retrieve_travel_graph"
    session_id, request_id = _session_request_ids(request)
    t0 = time.perf_counter()

    req = payload.request
    key = cache_module.build_cache_key(req.user_query, req.destination, req.lang)
    cached = cache_module.get(key)
    if cached is not None:
        subgraph, paths = _from_cache_value(cached)
        latency_ms = (time.perf_counter() - t0) * 1000
        metrics_module.record_request(
            cache_hit=True, latency_ms=latency_ms, neo4j_fallback=False
        )
        logging_utils_module.log_request(
            route=route,
            cache_hit=True,
            latency_ms=latency_ms,
            session_id=session_id,
            request_id=request_id,
            neo4j_fallback=False,
        )
        return RetrieveTravelGraphResponse(
            x_contract_version="1.0",
            request=req,
            subgraph=subgraph,
            paths=paths,
            debug=cached.get("debug"),
        )

    limit = req.limit or 20
    subgraph, neo4j_fallback = retrieval_module.get_subgraph(
        user_query=req.user_query,
        destination=req.destination,
        limit=limit,
    )
    paths = retrieval_module.compute_paths(subgraph)
    cache_value = {
        "nodes": [n.model_dump() for n in subgraph.nodes],
        "edges": [e.model_dump() for e in subgraph.edges],
        "paths": [p.model_dump() for p in paths] if paths else None,
        "debug": {"node_count": len(subgraph.nodes), "edge_count": len(subgraph.edges)}
        if req.debug
        else None,
    }
    cache_module.set_(key, cache_value)
    latency_ms = (time.perf_counter() - t0) * 1000
    metrics_module.record_request(
        cache_hit=False, latency_ms=latency_ms, neo4j_fallback=neo4j_fallback
    )
    logging_utils_module.log_request(
        route=route,
        cache_hit=False,
        latency_ms=latency_ms,
        session_id=session_id,
        request_id=request_id,
        neo4j_fallback=neo4j_fallback,
    )
    return RetrieveTravelGraphResponse(
        x_contract_version="1.0",
        request=req,
        subgraph=subgraph,
        paths=paths,
        debug=cache_value.get("debug"),
    )


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8031, reload=True)


if __name__ == "__main__":
    main()
