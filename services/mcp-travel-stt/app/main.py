from __future__ import annotations

import time

from fastapi import FastAPI, Request

from app import logging_utils as logging_utils_module
from app import metrics as metrics_module
from app import transcribe as transcribe_module
from app.models import TranscribePayload, TranscribeResponse


app = FastAPI(title="mcp-travel-stt", version="0.1.0")


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


@app.post("/mcp/transcribe", response_model=TranscribeResponse)
def transcribe_endpoint(
    request: Request, payload: TranscribePayload
) -> TranscribeResponse:
    """Transcribe audio to text via OpenAI STT API."""
    route = "/mcp/transcribe"
    session_id, request_id = _session_request_ids(request)
    t0 = time.perf_counter()

    req = payload.request

    try:
        result = transcribe_module.transcribe(req)
        latency_ms = (time.perf_counter() - t0) * 1000
        has_error = bool(result.error)
        metrics_module.record_request(latency_ms=latency_ms, error=has_error)
        logging_utils_module.log_request(
            route=route,
            latency_ms=latency_ms,
            session_id=session_id,
            request_id=request_id,
            error=has_error,
        )
        return result
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        metrics_module.record_request(latency_ms=latency_ms, error=True)
        logging_utils_module.log_request(
            route=route,
            latency_ms=latency_ms,
            session_id=session_id,
            request_id=request_id,
            error=True,
        )
        return TranscribeResponse(
            x_contract_version="1.0",
            request=req,
            transcript="",
            language=None,
            confidence=None,
            duration_seconds=None,
            error=str(e),
            debug={"error": str(e)} if req.debug else None,
        )


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8033, reload=True)


if __name__ == "__main__":
    main()
