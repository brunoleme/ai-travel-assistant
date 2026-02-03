# Phase 3 — Evaluation Harness + LangSmith + Operational Metrics

Goal:
Make it production-like:
- nightly regression tests
- traceability of LLM calls
- basic cost/latency tracking

Tickets:

## Ticket E1 — eval harness runner
Owner: services/agent-api (or a new /eval package inside it)
- Load TEST_QUERIES
- Run pipeline
- Save JSONL results with:
  groundedness proxy, citations count, product_inclusion, latency_ms
Tests:
- determinism when using mocks
- JSONL schema validated

## Ticket E2 — LLM-as-judge (optional but recommended)
Owner: services/agent-api
- Add judge prompts for:
  groundedness_score
  product_relevance_score
- Store judge outputs in eval JSONL
Tests:
- judge output parsing robust
- fallback if judge fails

## Ticket O1 — LangSmith integration
Owner: services/agent-api
- Add LangSmith tracing for:
  - answer generation
  - product decision
- Include session_id/request_id tags
Tests:
- tracing client is injectable/mocked in unit tests

## Ticket O2 — metrics surfaces
Owner: services/agent-api + MCP servers
- Standardized structured logs
- Add simple /health endpoints
Acceptance:
- can compare eval runs and flag regressions
