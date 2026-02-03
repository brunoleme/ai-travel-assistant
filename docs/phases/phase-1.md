# Phase 1 — Skeleton + Contracts + Minimal Vertical Slice (with Feedback)

Goal:
Ship a minimal end-to-end system that:
- accepts a WebSocket chat message
- retrieves travel evidence (stub or simple retrieval)
- optionally returns a product suggestion (stub allowed)
- emits a FeedbackEvent

Scope boundaries:
- Focus on structure, contracts, tests, and a working happy path.
- Real ingestion/EDA is NOT required yet.

Tickets (Cursor-ready):

## Ticket A1 — Repo scaffold per service (uv)
Owner: services/agent-api
- Add pyproject.toml, uv.lock (generated), ruff, pytest
- Add minimal FastAPI app with /ws endpoint
- Add Make targets already present in root Makefile
Tests:
- test_websocket_connects
- test_message_roundtrip_schema (basic response shape)

## Ticket K1 — travel-knowledge MCP server skeleton
Owner: services/mcp-travel-knowledge
- Implement a minimal MCP server exposing tool:
  retrieve_travel_evidence(user_query, destination?, lang?, debug?)
- For now: return mocked evidence list (hardcoded) that validates contracts
Tests:
- validates output against contracts/travel_evidence.schema.json

## Ticket P1 — travel-products MCP server skeleton
Owner: services/mcp-travel-products
- Implement tool:
  retrieve_product_candidates(query_signature, market?, destination?, lang?, limit?, min_confidence?)
- Return mocked candidates that validate contracts
Tests:
- validates output against contracts/product_candidates.schema.json

## Ticket A2 — agent runtime calls MCP services
Owner: services/agent-api
- Add MCP client adapters (HTTP/local) with timeouts
- Implement message flow:
  user_query -> knowledge evidence -> answer text -> product candidates -> optional addon
- Must include request_id/session_id in response
Tests:
- unit test: if products empty => no addon
- unit test: if products present => addon included only when requested buckets exist (simple heuristic allowed)

## Ticket A3 — feedback endpoint + event emission
Owner: services/agent-api
- Add POST /feedback accepting contracts/feedback_event.schema.json
- Store events locally in JSONL under data/feedback/ (phase 1 only)
Tests:
- validates incoming feedback payload against schema
- writes JSONL line

Acceptance criteria:
- make test passes
- make lint passes
- WebSocket demo works locally
- FeedbackEvent is stored
