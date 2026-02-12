# Phase 8 — Observability, Logging, CI Nightly & Tracing

**Goal:** Make the system observable, debuggable, and regression-safe.

**Scope:**
- Structured logging everywhere
- Metrics parity across all services (including graph, vision, STT, TTS MCPs)
- Local tracing when LangSmith is off
- CI on push + nightly eval runs (including multimodal eval fields)

**Reference:** Phase 1–3 (skeleton, caching, eval harness), Phase 5 (graph MCP), Phase 6 (vision MCP), Phase 7 (audio MCPs).

---

## 1. Tickets

### Ticket O0 — Structured logging (Loguru, CloudWatch-ready)
**Owner:** all services (agent-api, mcp-travel-knowledge, mcp-travel-products, mcp-travel-graph, mcp-travel-vision, mcp-travel-stt, mcp-travel-tts, ingestion)
- Add loguru
- Create app/logging.py with JSON logging setup
- Replace all print() calls with structured logs
- Standard fields in every log:
  - service, route, session_id, request_id, latency_ms
  - error (if any), cache_hit, fallback (when applicable)

**Tests:**
- log line is valid JSON
- includes service + correlation fields
- no print() remains in code

---

### Ticket O3 — Agent monitoring parity (/metrics + logs)
**Owner:** services/agent-api
- Add GET /metrics (JSON counters like MCP services)
- Track:
  - ws_messages_total
  - avg_latency_ms
  - guardrails_rewrites_total
  - addons_included_total
  - downstream_failures_total
  - latency_ms_knowledge, latency_ms_products, latency_ms_graph, latency_ms_vision, latency_ms_stt, latency_ms_tts (when applicable)
  - graph_included_total, vision_included_total, audio_included_total
- Log one structured JSON line per WS message and per /feedback

**Tests:**
- /metrics returns required keys
- two WS messages → ws_messages_total == 2
- guardrails rewrite increments counter
- when graph/vision/audio used, corresponding latency and _included fields present

---

### Ticket O4 — Local tracing when LangSmith disabled
**Owner:** services/agent-api
- Implement LocalFileTracer:
  - active when TRACING_ENABLED=1 and LANGSMITH_ENABLED=0
  - writes spans to data/traces/traces.jsonl
- Ensure spans for:
  - answer_generation
  - knowledge_mcp_call
  - product_decision
  - products_mcp_call
  - graph_mcp_call (when graph MCP used)
  - vision_mcp_call (when vision MCP used)
  - stt_mcp_call (when STT used)
  - tts_mcp_call (when TTS used)
- Span fields:
  - span_name, start_ts, end_ts, latency_ms
  - session_id, request_id, user_query_hash

**Tests:**
- enabling LocalFileTracer writes span lines
- spans contain correlation fields
- spans for graph/vision/audio appear when those MCPs are called

---

### Ticket C2 — CI pipelines (push + nightly regression)
**Owner:** repo root / infra
- CI on push/PR:
  - make lint
  - make test (all services: agent-api, mcp-travel-knowledge, mcp-travel-products, mcp-travel-graph, mcp-travel-vision, mcp-travel-stt, mcp-travel-tts, ingestion)
- Nightly scheduled workflow:
  - run make test
  - run eval harness (eval_row schema includes graph_included, vision_included, latency_ms_graph, latency_ms_vision, latency_ms_stt, latency_ms_tts, audio_included)
  - upload eval JSONL as artifact

**Acceptance:**
- push triggers CI automatically
- nightly workflow runs on schedule
- eval artifacts stored per run
- eval schema validates against all multimodal fields from phases 5–7

---

## 2. Acceptance criteria

- [ ] All services emit structured logs (agent-api + all MCPs + ingestion)
- [ ] Agent has /metrics endpoint with latency and _included counters for graph, vision, audio
- [ ] LocalFileTracer writes spans for answer_generation, knowledge_mcp_call, products_mcp_call, graph_mcp_call, vision_mcp_call, stt_mcp_call, tts_mcp_call when applicable
- [ ] CI runs on push and nightly; eval harness produces JSONL with graph/vision/audio fields
- [ ] make test and make lint pass for all services
