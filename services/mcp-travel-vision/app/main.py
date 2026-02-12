from __future__ import annotations

import time

from fastapi import FastAPI, Request

from app import cache as cache_module
from app import logging_utils as logging_utils_module
from app import metrics as metrics_module
from app import vision as vision_module
from app.models import (
    AnalyzeImagePayload,
    AnalyzeImageResponse,
    VisionSignals,
)


app = FastAPI(title="mcp-travel-vision", version="0.1.0")


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


@app.post("/mcp/analyze_image", response_model=AnalyzeImageResponse)
def analyze_image(
    request: Request, payload: AnalyzeImagePayload
) -> AnalyzeImageResponse:
    """Analyze image for packing, landmark, or product_similarity; uses in-memory TTL cache."""
    route = "/mcp/analyze_image"
    session_id, request_id = _session_request_ids(request)
    t0 = time.perf_counter()
    req = payload.request

    key = cache_module.build_cache_key(req.image_ref, req.mode, req.trip_context)
    cached = cache_module.get(key)
    if cached is not None:
        signals = VisionSignals(**cached["signals"])
        latency_ms = (time.perf_counter() - t0) * 1000
        metrics_module.record_request(
            cache_hit=True, latency_ms=latency_ms, error=False
        )
        logging_utils_module.log_request(
            route=route,
            cache_hit=True,
            latency_ms=latency_ms,
            session_id=session_id,
            request_id=request_id,
        )
        return AnalyzeImageResponse(
            x_contract_version="1.0",
            request=req,
            signals=signals,
            debug=cached.get("debug"),
        )

    try:
        signals = vision_module.analyze_image(req)
        cache_module.set_(key, {"signals": signals.model_dump(), "debug": None})
        latency_ms = (time.perf_counter() - t0) * 1000
        metrics_module.record_request(
            cache_hit=False, latency_ms=latency_ms, error=bool(signals.error)
        )
        logging_utils_module.log_request(
            route=route,
            cache_hit=False,
            latency_ms=latency_ms,
            session_id=session_id,
            request_id=request_id,
        )
        return AnalyzeImageResponse(
            x_contract_version="1.0",
            request=req,
            signals=signals,
            debug={"mode": req.mode} if req.debug else None,
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        metrics_module.record_request(
            cache_hit=False, latency_ms=latency_ms, error=True
        )
        logging_utils_module.log_request(
            route=route,
            cache_hit=False,
            latency_ms=latency_ms,
            session_id=session_id,
            request_id=request_id,
        )
        signals = VisionSignals(mode=req.mode, confidence=0.0, error=str(e))
        return AnalyzeImageResponse(
            x_contract_version="1.0",
            request=req,
            signals=signals,
            debug={"error": str(e)} if req.debug else None,
        )


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8032, reload=True)


if __name__ == "__main__":
    main()
