# How to run a real test (integration, no mocks)

Real tests hit the live MCP services (knowledge, products, graph) and backends (Weaviate, Neo4j). Use this when you want to validate the full stack.

## Prerequisites

- **Weaviate** running (for knowledge + products MCPs). Default: `localhost:8080` (see `configs/.env`: `WEAVIATE_HOST`, `WEAVIATE_PORT`).
- **Neo4j** running (for graph MCP). Default: `bolt://localhost:7687` (see `configs/.env`: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`).
- **OpenAI API key** in `configs/.env` as `OPENAI_API_KEY` (used by knowledge and graph MCPs).

## 1. Start the MCP servers

From the repo root, in **separate terminals** (or background):

```bash
# Terminal 1 – Knowledge (port 8010)
make run-knowledge

# Terminal 2 – Products (port 8020)
make run-products

# Terminal 3 – Graph (port 8031)
make run-graph
```

Load `configs/.env` before each run (the Makefile does this). Ensure nothing else is using ports 8010, 8020, 8031.

## 2. Run the eval harness (recommended)

The eval runner sends a list of queries through the agent pipeline and writes one JSONL row per query. It uses **real** MCP calls (no test mocks).

From repo root:

```bash
make eval
```

This:

- Uses test queries from `services/agent-api/data/eval/test_queries.json` (or `TEST_QUERIES_JSON` if set).
- Runs from `services/agent-api` with `configs/.env` loaded.
- Writes results to `data/eval/run.jsonl`.

Inspect results:

```bash
cat data/eval/run.jsonl
# or
jq -s '.' data/eval/run.jsonl
```

Each row includes `latency_ms_knowledge`, `latency_ms_products`, `latency_ms_graph`, `graph_included`, `response_snapshot.answer_text`, and `response_snapshot.citations`.

## 3. Run the agent and hit the WebSocket (manual)

Start the agent API:

```bash
make run-agent
```

Agent listens on port 8000. Use a WebSocket client (e.g. `websocat`, browser devtools, or a small script) and send:

```json
{
  "session_id": "manual-1",
  "request_id": "req-1",
  "user_query": "suggest a 3-day itinerary for Orlando",
  "destination": "Orlando",
  "lang": "en"
}
```

You should get a response with `answer_text`, `citations`, and optionally `addon`. For itinerary-style queries the agent will call the graph MCP and include path-based content and graph evidence URLs in citations.

## 4. Custom query set (eval)

To run the eval harness with your own queries without editing the file:

```bash
cd services/agent-api
export TEST_QUERIES_JSON='[{"user_query": "what to do first in Disney?", "destination": "Orlando", "lang": "en"}]'
uv run python -m app.eval_runner --out ../../data/eval/run.jsonl
```

## 5. Quick sanity check (no Neo4j/Weaviate)

If only the agent and MCPs are running and Weaviate/Neo4j are down or empty:

- **Knowledge MCP** may return empty evidence or fallback; agent still returns an answer.
- **Graph MCP** may return an empty subgraph when Neo4j is unavailable (or mock, depending on implementation).
- **Products MCP** may return no candidates.

So you can still run `make eval` or the WebSocket to confirm the agent and MCP wiring; answers will be weaker without real data.

## Summary

| Goal                         | Command / step                                      |
|-----------------------------|-----------------------------------------------------|
| Eval over real MCPs         | Start knowledge, products, graph → `make eval`      |
| Manual chat                 | Start all three MCPs + `make run-agent` → WS client |
| Custom queries for eval     | `TEST_QUERIES_JSON='[...]'` + `app.eval_runner`     |

Test queries in `services/agent-api/data/eval/test_queries.json` are aligned with Orlando/Disney demo data and include one itinerary query so the graph MCP is exercised.
