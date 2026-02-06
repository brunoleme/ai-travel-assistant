"""Agent API: WebSocket chat + MCP integration + feedback."""

from __future__ import annotations

from typing import Any

import httpx
import jsonschema
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect

from app.contracts import validate_or_raise
from app.feedback_store import append_jsonl
from app.guardrails import validate_and_fix
from app.mcp_client import (
    MCPConfig,
    retrieve_product_candidates,
    retrieve_travel_evidence,
)
from app.memory_store import memory_hash, summary, update

app = FastAPI(title="ai-travel-assistant agent-api", version="0.1.0")
config = MCPConfig()


def _build_query_signature(
    user_query: str,
    destination: str | None,
    lang: str | None,
    session_id: str | None = None,
) -> str:
    parts = [destination or "any", user_query[:100], lang or "en"]
    base = ":".join(parts)[:200]
    if session_id:
        mem = memory_hash(session_id, 8)
        if mem:
            base = f"{base}|mem:{mem}"
    return base


def _is_commercial_query(user_query: str) -> bool:
    q = user_query.lower()
    commercial = ("comprar", "buy", "reservar", "book", "hotel", "ingresso", "ticket", "tour")
    return any(k in q for k in commercial)


def _build_answer_and_citations(evidence: list[dict]) -> tuple[str, list[str]]:
    if not evidence:
        return "No travel evidence found for your query.", []
    summaries = [e["summary"] for e in evidence]
    answer = " ".join(summaries)
    citations = [e["source_url"] for e in evidence if e.get("source_url")]
    return answer, citations


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            session_id = msg.get("session_id") or "local-session"
            request_id = msg.get("request_id") or "local-request"
            user_query = msg.get("user_query", "")
            destination = msg.get("destination")
            lang = msg.get("lang")

            update(session_id, user_query, None)
            mem_summary = summary(session_id)

            strategy_params = {"memory_summary": mem_summary, "version": "v1"} if mem_summary else None
            request = {
                "user_query": user_query,
                "destination": destination,
                "lang": lang,
                "strategy_params": strategy_params,
            }

            async with httpx.AsyncClient(timeout=config.timeout_s) as client:
                try:
                    ev_resp = await retrieve_travel_evidence(
                        client, config.knowledge_base_url, request
                    )
                except Exception:
                    ev_resp = {
                        "x_contract_version": "1.0",
                        "request": request,
                        "evidence": [],
                    }

                addon = None
                prod_req = {
                    "query_signature": _build_query_signature(
                        user_query, destination, lang, session_id
                    ),
                    "destination": destination,
                    "lang": lang,
                }
                try:
                    prod_resp = await retrieve_product_candidates(
                        client, config.products_base_url, prod_req
                    )
                except Exception:
                    prod_resp = {
                        "x_contract_version": "1.0",
                        "request": prod_req,
                        "candidates": [],
                    }

            validate_or_raise(ev_resp, "travel_evidence.schema.json")
            evidence = ev_resp.get("evidence", [])
            answer_text, citations = _build_answer_and_citations(evidence)

            validate_or_raise(prod_resp, "product_candidates.schema.json")
            candidates = prod_resp.get("candidates", [])
            if candidates and _is_commercial_query(user_query):
                top = candidates[0]
                addon = {
                    "product_id": top["product_id"],
                    "summary": top["summary"],
                    "link": top["link"],
                    "merchant": top["merchant"],
                }

            response = {
                "session_id": session_id,
                "request_id": request_id,
                "answer_text": answer_text,
                "citations": citations,
                "addon": addon,
            }
            response = validate_and_fix(response, user_query)
            await ws.send_json(response)
    except WebSocketDisconnect:
        return


@app.post("/feedback")
async def feedback(request: Request) -> dict:
    event: dict[str, Any] = await request.json()
    try:
        validate_or_raise(event, "feedback_event.schema.json")
    except jsonschema.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    append_jsonl(event)
    return {"status": "ok"}
