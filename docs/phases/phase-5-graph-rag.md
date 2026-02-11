# Phase 5 — Graph RAG MCP + Agent Runtime Routing

**Goal:** Add an MCP that queries the travel knowledge graph (Neo4j) and expose it to the agent so itinerary / routes / day-order questions can be answered from graph data. The agent runtime decides when to call which MCP (knowledge, products, graph).

**Scope:**
- New service: **mcp-travel-graph** (same structure as mcp-travel-knowledge / mcp-travel-products).
- Contract: **contracts/graph_rag.schema.json** (request/response for subgraph + paths + evidence).
- Agent runtime: MCP config for graph URL, **routing logic** (when to call graph MCP), integration of graph result into answer/citations, and eval metrics for graph latency.

**Out of scope:** Changes to ingestion (youtube_kg pipeline already writes to Neo4j). No Terraform in this phase (graph MCP runs alongside existing MCPs).

**Reference:** Phase 1 (MCP skeleton, contracts, agent calling MCPs), Phase 2 (caching), mcp-travel-knowledge and mcp-travel-products structure.

---

## 1. Contract

**File:** `contracts/graph_rag.schema.json`

- **Request:** `user_query`, optional `destination`, `lang`, `limit`, `debug`.
- **Response:** `x_contract_version`, `request` (echo), `subgraph` (nodes, edges with evidence), optional `paths` (ordered sequences for itinerary narrative), optional `debug`.
- **Nodes:** `id`, `type` (city | place | poi | itinerary | dayplan | activity_type | advice | constraint), `name`, `aliases`, `properties`.
- **Edges:** `source`, `type`, `target`, `evidence` (videoUrl, timestampUrl, startSec, endSec, chunkIdx).
- **Paths:** optional array of `{ path_id, label, nodes[], edges[], evidence[] }` for itinerary-style answers.

Consumers (mcp-travel-graph and agent-api) MUST validate responses against this schema in tests.

---

## 2. MCP: mcp-travel-graph

**Owner:** services/mcp-travel-graph (new service).

Structure aligned with mcp-travel-knowledge:
- `app/main.py` — FastAPI, `/health`, `/metrics`, `POST /mcp/retrieve_graph` (or `/mcp/retrieve_travel_graph`).
- `app/retrieval.py` — Neo4j read: run Cypher to fetch subgraph (nodes + edges + evidence) from `Entity` and `REL`; optional path expansion (e.g. itinerary → HAS_DAY → dayplan → INCLUDES_POI → poi).
- `app/adapter.py` — Map Neo4j result rows to contract shapes (GraphNode, GraphEdge, Evidence).
- `app/models.py` — Pydantic models matching graph_rag.schema.json.
- `app/cache.py` — Cache key: normalized(user_query, destination, lang); TTL cache.
- `app/metrics.py` — request_count, error_count, latency_ms, cache_hit (same pattern as other MCPs).
- `app/logging_utils.py` — Structured logs with session_id, request_id, latency_ms, cache_hit.
- Env: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, optional `NEO4J_DATABASE`.

### Ticket G1 — mcp-travel-graph repo scaffold
**Owner:** services/mcp-travel-graph
- Add pyproject.toml (fastapi, uvicorn, neo4j, pydantic, httpx for tests), uv.lock.
- Add minimal FastAPI app: `/health`, `/metrics`, `POST /mcp/retrieve_travel_graph` returning mocked response that validates against contracts/graph_rag.schema.json.
- Add Make target in root Makefile (sync-graph, run-graph, test-graph) mirroring knowledge/products.
- **Tests:** Contract validation test (response matches graph_rag.schema.json).

### Ticket G2 — Neo4j retrieval
**Owner:** services/mcp-travel-graph
- Implement retrieval: connect Neo4j (env), run Cypher to fetch Entity nodes and REL edges with evidence.
- Query strategy: e.g. text match on user_query/destination against node name/aliases, then expand to N hops; return subgraph (nodes + edges) and attach evidence from REL.evidence.
- Adapter: map Neo4j records to contract GraphNode, GraphEdge, Evidence (timestampUrl, videoUrl, startSec, endSec).
- **Tests:** Unit tests with mocked Neo4j driver; no real Neo4j in unit tests. Contract validation on adapter output.

### Ticket G3 — Paths for itinerary narrative
**Owner:** services/mcp-travel-graph
- Optional: from subgraph, compute 1–3 ordered paths (e.g. itinerary → days → POIs) and attach evidence per path.
- Populate response `paths[]` when useful (itinerary-style queries).
- **Tests:** Mocked Neo4j returning itinerary-shaped subgraph; assert paths[] shape matches contract.

### Ticket G4 — Caching and metrics
**Owner:** services/mcp-travel-graph
- Cache key: (user_query, destination, lang) normalized; TTL cache (same pattern as K2/P2).
- Metrics: request_count, error_count, latency_ms, cache_hit_rate.
- Structured logs: session_id, request_id, latency_ms, cache_hit.
- **Tests:** Same-request returns cached; cache hit in logs/metrics.

---

## 3. Agent Runtime: MCP selection and integration

**Owner:** services/agent-api.

Today the agent always calls knowledge then products. We add:
- Config for graph MCP URL (e.g. `KNOWLEDGE_MCP_URL`, `PRODUCTS_MCP_URL`, `GRAPH_MCP_URL`).
- **Routing:** Decide when to call the graph MCP (e.g. user_query indicates itinerary, routes, day order, “roteiro”, “ordem”, “dia 1”, “what to do first”).
- **Integration:** When graph is called, merge graph evidence (paths/subgraph) into answer building: use paths for narrative, cite timestampUrl from evidence.
- **Eval:** Record latency_graph_ms and optionally graph_included in eval JSONL.

### Ticket A6 — MCP config and client for graph
**Owner:** services/agent-api
- Add `graph_base_url` to MCPConfig (env `GRAPH_MCP_URL`, default e.g. http://127.0.0.1:8031).
- Add `retrieve_travel_graph(client, base_url, request)` in mcp_client.py; POST to `/mcp/retrieve_travel_graph`, validate response against graph_rag.schema.json (or contract validation helper).
- **Tests:** Unit test with mocked HTTP; response shape validated.

### Ticket A7 — Routing: when to call graph MCP
**Owner:** services/agent-api
- Implement routing heuristic (or small classifier): e.g. keywords/phrases for “itinerary”, “routes”, “order of visits”, “day 1”, “what to do first”, “roteiro”, “trajeto”. If match → call graph MCP in addition to (or instead of) knowledge for that query.
- Document routing rule (e.g. “itinerary/routes → graph + knowledge”; “general tips” → knowledge only).
- **Tests:** For query “suggest a 3-day itinerary for Barcelona” → graph MCP is called; for “best hotels in Madrid” → graph MCP not called (or called with low priority). Mock MCPs.

### Ticket A8 — Integrate graph result into answer
**Owner:** services/agent-api
- When graph MCP returns subgraph/paths: pass paths and evidence into answer builder (e.g. _build_answer_and_citations); include graph-derived narrative (e.g. “Day 1: … Day 2: …”) and cite timestampUrl from edge evidence.
- Ensure citations list includes both knowledge evidence and graph evidence (source_url / timestampUrl).
- **Tests:** With mocked graph response containing paths + evidence, assert answer contains path-based content and citations include graph evidence URLs.

### Ticket A9 — Eval and metrics for graph
**Owner:** services/agent-api
- Add `latency_ms_graph` (and optionally `graph_included: bool`) to eval runner output and eval_row schema.
- When graph MCP is called, record its latency in timing_out and in eval JSONL row.
- **Tests:** Eval runner with mocked graph call writes latency_ms_graph and graph_included in JSONL; schema validation passes.

---

## 4. Order of work (suggested)

1. **Contract** — graph_rag.schema.json (done in this phase doc).
2. **G1** — mcp-travel-graph scaffold + mock response + contract test.
3. **G2** — Neo4j retrieval + adapter; contract validation.
4. **G4** — Caching and metrics (parallel or right after G2).
5. **G3** — Paths for itinerary (optional, can follow G2).
6. **A6** — Agent: graph MCP config and client.
7. **A7** — Agent: routing (when to call graph).
8. **A8** — Agent: integrate graph into answer and citations.
9. **A9** — Agent: eval latency_graph and graph_included.

---

## 5. Acceptance criteria

- [ ] mcp-travel-graph: `/health`, `/metrics`, `POST /mcp/retrieve_travel_graph` return response validating against contracts/graph_rag.schema.json; unit tests with mocked Neo4j; cache and metrics in place.
- [ ] Agent: For itinerary/routes-style queries, graph MCP is called; answer can include path-based narrative and graph evidence citations; eval row includes latency_ms_graph and graph_included.
- [ ] make test and make lint pass for agent-api and mcp-travel-graph.
- [ ] No breaking changes to existing travel_evidence or product_candidates contracts.

---

## 6. Config summary

| Service           | Env / config              |
|-------------------|----------------------------|
| mcp-travel-graph  | NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE (optional) |
| agent-api         | GRAPH_MCP_URL (e.g. http://127.0.0.1:8031) |

Port suggestion for mcp-travel-graph: **8031** (knowledge=8010, products=8020, ingestion=8030).
