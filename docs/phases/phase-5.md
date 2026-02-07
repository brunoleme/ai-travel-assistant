Phase 5 — Observability, Logging, CI Nightly & Tracing
Goal:Make the system observable, debuggable, and regression-safe.
Scope:
* Structured logging everywhere
* Metrics parity across services
* Local tracing when LangSmith is off
* CI on push + nightly eval runs
Tickets:
Ticket O0 — structured logging (Loguru, CloudWatch-ready)
Owner: all services
* Add loguru
* Create app/logging.py with JSON logging setup
* Replace all print() calls with structured logs
* Standard fields in every log:
    * service, route, session_id, request_id, latency_ms
    * error (if any), cache_hit, fallback (when applicable)
Tests:
* log line is valid JSON
* includes service + correlation fields
* no print() remains in code

Ticket O3 — agent monitoring parity (/metrics + logs)
Owner: services/agent-api
* Add GET /metrics (JSON counters like MCP services)
* Track:
    * ws_messages_total
    * avg_latency_ms
    * guardrails_rewrites_total
    * addons_included_total
    * downstream_failures_total
* Log one structured JSON line per WS message and per /feedback
Tests:
* /metrics returns required keys
* two WS messages → ws_messages_total == 2
* guardrails rewrite increments counter

Ticket O4 — local tracing when LangSmith disabled
Owner: services/agent-api
* Implement LocalFileTracer:
    * active when TRACING_ENABLED=1 and LANGSMITH_ENABLED=0
    * writes spans to data/traces/traces.jsonl
* Ensure spans for:
    * answer_generation
    * knowledge_mcp_call
    * product_decision
    * products_mcp_call
* Span fields:
    * span_name, start_ts, end_ts, latency_ms
    * session_id, request_id, user_query_hash
Tests:
* enabling LocalFileTracer writes span lines
* spans contain correlation fields

Ticket C2 — CI pipelines (push + nightly regression)
Owner: repo root / infra
* CI on push/PR:
    * make lint
    * make test
* Nightly scheduled workflow:
    * run make test
    * run eval harness
    * upload eval JSONL as artifact
Acceptance:
* push triggers CI automatically
* nightly workflow runs on schedule
* eval artifacts stored per run

Acceptance criteria:
* all services emit structured logs
* agent has /metrics endpoint
* traces exist locally when LangSmith is disabled
* CI runs on push and nightly