"""Agent API: WebSocket chat + MCP integration + feedback."""

from __future__ import annotations

import time
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
    retrieve_travel_graph,
)
from app.memory_store import memory_hash, summary, update
from app.tracing import Tracer, get_tracer, user_query_hash

app = FastAPI(title="ai-travel-assistant agent-api", version="0.1.0")
config = MCPConfig.from_env()


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


# Routing: itinerary/routes/day-order → call graph MCP in addition to knowledge.
GRAPH_QUERY_KEYWORDS = (
    "itinerary", "itinerário", "roteiro", "routes", "rotas", "trajeto", "trajetos",
    "day 1", "dia 1", "day 2", "dia 2", "order of visits", "ordem das visitas",
    "what to do first", "o que fazer primeiro", "suggest a", "sugira um", "sugira uma",
    "3-day", "3 day", "5-day", "5 day", "week itinerary", "semana",
)


def _should_call_graph(user_query: str) -> bool:
    """True if query suggests itinerary, routes, or day-order (graph MCP)."""
    q = user_query.lower().strip()
    return any(kw in q for kw in GRAPH_QUERY_KEYWORDS)


def _build_answer_and_citations(
    evidence: list[dict],
    graph_response: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    citations: list[str] = []
    parts: list[str] = []

    if evidence:
        summaries = [e["summary"] for e in evidence]
        parts.append(" ".join(summaries))
        citations.extend(e["source_url"] for e in evidence if e.get("source_url"))

    if graph_response:
        subgraph = graph_response.get("subgraph") or {}
        paths = graph_response.get("paths") or []
        nodes_by_id = {n["id"]: n.get("name", n["id"]) for n in (subgraph.get("nodes") or [])}
        path_lines = []
        for p in paths[:3]:
            label = p.get("label") or p.get("path_id") or "Itinerary"
            node_ids = p.get("nodes") or []
            names = [nodes_by_id.get(nid, nid) for nid in node_ids if isinstance(nid, str)]
            path_lines.append(f"{label}: {', '.join(names)}" if names else label)
        if path_lines:
            parts.append(" ".join(path_lines))
        for p in paths:
            for ev in p.get("evidence") or []:
                if ev.get("timestampUrl"):
                    citations.append(ev["timestampUrl"])
        for edge in subgraph.get("edges") or []:
            ev = edge.get("evidence") or {}
            if ev.get("timestampUrl"):
                citations.append(ev["timestampUrl"])

    answer = " ".join(parts) if parts else "No travel evidence found for your query."
    return answer, citations


async def run_pipeline_raw(
    session_id: str,
    request_id: str,
    user_query: str,
    destination: str | None = None,
    lang: str | None = None,
    timing_out: dict[str, float] | None = None,
    tracer: Tracer | None = None,
) -> dict[str, Any]:
    """Run the agent pipeline (knowledge + products + addon) and return response before guardrails."""
    if tracer is None:
        tracer = get_tracer()
    tags = {
        "session_id": session_id,
        "request_id": request_id,
        "user_query_hash": user_query_hash(user_query),
    }

    t_start = time.perf_counter()
    update(session_id, user_query, None)
    mem_summary = summary(session_id)
    strategy_params = {"memory_summary": mem_summary, "version": "v1"} if mem_summary else None
    request = {
        "user_query": user_query,
        "destination": destination,
        "lang": lang,
        "strategy_params": strategy_params,
    }

    t_knowledge = 0.0
    t_products = 0.0
    t_graph = 0.0
    graph_resp: dict[str, Any] | None = None

    async with httpx.AsyncClient(timeout=config.timeout_s) as client:
        with tracer.span("answer_generation", tags):
            t0 = time.perf_counter()
            try:
                ev_resp = await retrieve_travel_evidence(
                    client, config.knowledge_base_url, request
                )
            except Exception:
                ev_resp = {"x_contract_version": "1.0", "request": request, "evidence": []}
            t_knowledge = (time.perf_counter() - t0) * 1000

        validate_or_raise(ev_resp, "travel_evidence.schema.json")
        evidence = ev_resp.get("evidence", [])

        if _should_call_graph(user_query):
            with tracer.span("graph_mcp_call", tags):
                graph_req = {
                    "user_query": user_query,
                    "destination": destination,
                    "lang": lang,
                }
                t0 = time.perf_counter()
                try:
                    graph_resp = await retrieve_travel_graph(
                        client, config.graph_base_url, graph_req
                    )
                except Exception:
                    graph_resp = None
                t_graph = (time.perf_counter() - t0) * 1000
            if graph_resp is not None:
                validate_or_raise(graph_resp, "graph_rag.schema.json")

        answer_text, citations = _build_answer_and_citations(evidence, graph_resp)

        with tracer.span("product_decision", tags):
            prod_req = {
                "query_signature": _build_query_signature(user_query, destination, lang, session_id),
                "destination": destination,
                "lang": lang,
            }
            t0 = time.perf_counter()
            try:
                prod_resp = await retrieve_product_candidates(
                    client, config.products_base_url, prod_req
                )
            except Exception:
                prod_resp = {"x_contract_version": "1.0", "request": prod_req, "candidates": []}
            t_products = (time.perf_counter() - t0) * 1000

        validate_or_raise(prod_resp, "product_candidates.schema.json")
        candidates = prod_resp.get("candidates", [])
        addon = None
        if candidates and _is_commercial_query(user_query):
            top = candidates[0]
            addon = {"product_id": top["product_id"], "summary": top["summary"], "link": top["link"], "merchant": top["merchant"]}

    if timing_out is not None:
        timing_out["knowledge_ms"] = t_knowledge
        timing_out["products_ms"] = t_products
        timing_out["graph_ms"] = t_graph
        timing_out["total_ms"] = (time.perf_counter() - t_start) * 1000

    return {
        "session_id": session_id,
        "request_id": request_id,
        "answer_text": answer_text,
        "citations": citations,
        "addon": addon,
    }


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

            response = await run_pipeline_raw(
                session_id, request_id, user_query, destination, lang
            )
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
