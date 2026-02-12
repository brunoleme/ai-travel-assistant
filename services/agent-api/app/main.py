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
    analyze_image,
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


# Routing: infer vision mode from user_query (packing | landmark | product_similarity).
PACKING_KEYWORDS = ("packing", "outfit", "clothes", "suitcase", "malas", "roupas", "levar", "levar o que")
LANDMARK_KEYWORDS = ("where is this", "landmark", "place", "onde é", "que lugar", "qual lugar", "o que é isso")
PRODUCT_SIMILARITY_KEYWORDS = ("like this", "similar", "find one like", "parecido", "igual a", "encontre um como")

# Critical packing gaps: recommend product when missing + context matches.
CRITICAL_GAP_RULES = (
    ({"rain_jacket"}, {"rain_risk": ["medium", "high"]}),
    ({"umbrella"}, {"rain_risk": ["high"]}),
    ({"sun_protection"}, {"uv_risk": ["high"]}),
)


def _get_packing_gap_query(
    missing_categories: list[str],
    trip_context: dict | None,
    suggested_categories_for_products: list[str] | None = None,
    suitability_ok: bool | None = None,
) -> str | None:
    """Return query_signature for products when outfit suggests recommendations (suggested categories or critical gap)."""
    ctx = trip_context or {}
    dest = ctx.get("destination") or "any"
    # Prefer suggested categories from vision (outfit not suitable or user wants recommendations)
    if suggested_categories_for_products and (suitability_ok is False or suitability_ok is None):
        first = next((c for c in suggested_categories_for_products if c), None)
        if first:
            return f"{dest}:{first}:en"
    # Fall back to critical gap rules (missing + context)
    missing_set = set(missing_categories or [])
    for gap_items, ctx_reqs in CRITICAL_GAP_RULES:
        if not gap_items & missing_set:
            continue
        for key, valid in ctx_reqs.items():
            if ctx.get(key) in valid:
                item = next(iter(gap_items & missing_set))
                return f"{dest}:{item}:en"
    return None


def _infer_vision_mode(user_query: str) -> str:
    """Infer vision mode from user_query; default packing."""
    q = user_query.lower().strip()
    if any(kw in q for kw in PRODUCT_SIMILARITY_KEYWORDS):
        return "product_similarity"
    if any(kw in q for kw in LANDMARK_KEYWORDS):
        return "landmark"
    return "packing"


def _build_answer_and_citations(
    evidence: list[dict],
    graph_response: dict[str, Any] | None = None,
    vision_response: dict[str, Any] | None = None,
    trip_context: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    citations: list[str] = []
    parts: list[str] = []

    if vision_response:
        sig = vision_response.get("signals") or {}
        mode = sig.get("mode", "packing")
        if mode == "packing":
            detected = sig.get("detected_items") or []
            missing = sig.get("missing_categories") or []
            suitability_ok = sig.get("suitability_ok")
            suitability_issue = sig.get("suitability_issue") or ""
            suggested = sig.get("suggested_categories_for_products") or []
            if suitability_ok is True:
                parts.append("This outfit looks suitable for your trip.")
            elif suitability_ok is False and suitability_issue:
                parts.append(f"This outfit may not be ideal: {suitability_issue}")
            if detected:
                parts.append("Detected: " + ", ".join(detected[:8]) + ".")
            if suggested:
                parts.append("Consider adding: " + ", ".join(suggested[:5]) + ".")
            elif missing:
                parts.append("Consider adding for your trip: " + ", ".join(missing[:5]) + ".")
            if not detected and not missing and suitability_ok is None:
                parts.append("Could not clearly detect travel items. Pack according to your trip context.")
        elif mode == "landmark":
            candidates = sig.get("place_candidates") or []
            scene = sig.get("scene_type") or "place"
            if candidates:
                top = candidates[0]
                name = top.get("place_name", "") if isinstance(top, dict) else getattr(top, "place_name", "")
                conf = top.get("confidence") if isinstance(top, dict) else getattr(top, "confidence", None)
                if conf and conf >= 0.6:
                    parts.append(f"Parece ser {name}. Quer dicas do que fazer por perto?")
                else:
                    parts.append(f"Possívelmente {name} ou local similar ({scene}). Quer que eu sugira o que fazer por perto?")
            else:
                parts.append(f"Parece um local do tipo {scene}. Quer dicas do que fazer por perto?")
        elif mode == "product_similarity":
            cat = sig.get("category") or "item"
            attrs = sig.get("attributes") or {}
            kw = sig.get("style_keywords") or []
            desc_parts = [cat]
            if attrs:
                desc_parts.append(", ".join(f"{k}: {v}" for k, v in list(attrs.items())[:3]))
            if kw:
                desc_parts.append("style: " + ", ".join(kw[:3]))
            parts.append("Produtos similares: " + "; ".join(desc_parts) + ".")

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
    image_ref: str | None = None,
    trip_context: dict[str, Any] | None = None,
    timing_out: dict[str, float] | None = None,
    tracer: Tracer | None = None,
) -> dict[str, Any]:
    """Run the agent pipeline (knowledge + products + graph + vision) and return response before guardrails."""
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
    t_vision = 0.0
    graph_resp: dict[str, Any] | None = None
    vision_resp: dict[str, Any] | None = None
    vision_mode: str | None = None

    ctx = trip_context or {}
    if destination:
        ctx.setdefault("destination", destination)

    async with httpx.AsyncClient(timeout=config.timeout_s) as client:
        if image_ref:
            mode = _infer_vision_mode(user_query)
            vision_mode = mode
            with tracer.span("vision_mcp_call", tags):
                vision_req = {
                    "image_ref": image_ref,
                    "mode": mode,
                    "trip_context": ctx if ctx else None,
                    "user_query": user_query,
                    "lang": lang,
                }
                t0 = time.perf_counter()
                try:
                    vision_resp = await analyze_image(
                        client, config.vision_base_url, vision_req
                    )
                except Exception:
                    vision_resp = None
                t_vision = (time.perf_counter() - t0) * 1000
            if vision_resp is not None:
                validate_or_raise(vision_resp, "vision_signals.schema.json")

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

        answer_text, citations = _build_answer_and_citations(
            evidence, graph_resp, vision_resp, ctx
        )

        with tracer.span("product_decision", tags):
            query_sig = _build_query_signature(user_query, destination, lang, session_id)
            if vision_resp and vision_mode == "product_similarity":
                sig = (vision_resp.get("signals") or {}).get("search_queries") or []
                if sig:
                    query_sig = f"{destination or 'any'}:{sig[0][:80]}:{lang or 'en'}"
            elif vision_resp and vision_mode == "packing":
                sig = vision_resp.get("signals") or {}
                missing = sig.get("missing_categories") or []
                suggested = sig.get("suggested_categories_for_products") or []
                suitability_ok = sig.get("suitability_ok")
                gap_query = _get_packing_gap_query(missing, ctx, suggested, suitability_ok)
                if gap_query:
                    query_sig = gap_query

            prod_req = {
                "query_signature": query_sig,
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
        want_addon = _is_commercial_query(user_query)
        if not want_addon and vision_resp and vision_mode == "product_similarity":
            want_addon = bool(candidates)
        if not want_addon and vision_resp and vision_mode == "packing":
            sig = vision_resp.get("signals") or {}
            missing = sig.get("missing_categories") or []
            suggested = sig.get("suggested_categories_for_products") or []
            suitability_ok = sig.get("suitability_ok")
            want_addon = (
                _get_packing_gap_query(missing, ctx, suggested, suitability_ok) is not None
                and bool(candidates)
            )
        if candidates and want_addon:
            top = candidates[0]
            addon = {"product_id": top["product_id"], "summary": top["summary"], "link": top["link"], "merchant": top["merchant"]}

        if vision_mode == "product_similarity" and candidates:
            opts = [f"{c.get('summary', '')[:80]}..." for c in candidates[:6]]
            if opts:
                answer_text = answer_text.rstrip() + " Opções: " + " | ".join(opts)

    if timing_out is not None:
        timing_out["knowledge_ms"] = t_knowledge
        timing_out["products_ms"] = t_products
        timing_out["graph_ms"] = t_graph
        timing_out["vision_ms"] = t_vision
        timing_out["vision_mode"] = vision_mode
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
            image_ref = msg.get("image_ref") or msg.get("image")
            trip_context = msg.get("trip_context")

            response = await run_pipeline_raw(
                session_id, request_id, user_query,
                destination=destination, lang=lang,
                image_ref=image_ref, trip_context=trip_context,
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
