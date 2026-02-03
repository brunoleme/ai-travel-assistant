# Phase 2 — Memory + Caching + Guardrails Hardening

Goal:
Reduce cost/latency and improve correctness:
- caching at MCP layer
- session memory summary
- guardrails validation before final response

Tickets:

## Ticket K2 — evidence caching
Owner: services/mcp-travel-knowledge
- Cache key: normalized(user_query, destination, lang, strategy_params_version)
- Add cache_hit in logs
Tests (TDD):
- same request returns cached response without calling retrieval adapter
- different destination busts cache
- TTL expiry refreshes

## Ticket P2 — product candidates caching
Owner: services/mcp-travel-products
- Cache key: query_signature + market + destination + lang
Tests:
- same signature returns cached candidates
- min_confidence changes must be part of key OR applied as post-filter deterministically

## Ticket A4 — session memory (LangMem-style)
Owner: services/agent-api
- Maintain session memory in runtime:
  preferences + constraints + recent plan steps
- Generate compact memory_summary per session and pass into:
  - answer generation
  - product decision
Tests:
- memory updated after message
- memory_summary included in downstream request payloads (mocked)

## Ticket A5 — guardrails validator
Owner: services/agent-api
- Add output validator:
  - no invented prices/policies
  - requires citations when claims are factual
  - block product addon if user didn’t request relevant bucket
Tests:
- answer with missing citations gets rejected or rewritten
- product suggested when not requested => removed

Acceptance criteria:
- cache hit rate observable in logs
- tests prove caching and guardrails behavior
