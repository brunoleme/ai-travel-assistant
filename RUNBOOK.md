# Runbook – Local Development & Eval

Quick reference for running the agent stack locally and running evals.

## Prerequisites

- `uv` installed
- Copy `configs/.env` and ensure `WEAVIATE_*` and optional `OPENAI_API_KEY` are set

## Running the Three Services Locally

Load env from `configs/.env` (run from repo root):

```bash
make run-knowledge   # MCP travel-knowledge @ http://127.0.0.1:8010
make run-products    # MCP travel-products @ http://127.0.0.1:8020
make run-agent       # Agent API @ http://127.0.0.1:8000
```

Start them in separate terminals. Order: knowledge and products first, then agent.

Example output:

```
INFO:     Uvicorn running on http://127.0.0.1:8010 (Press CTRL+C to quit)
INFO:     Started reloader process
```

## Running the Eval Runner

From repo root:

```bash
make eval
```

This runs:

```bash
cd services/agent-api && set -a && . ../../configs/.env && set +a && \
  uv run python -m app.eval_runner --out ../../data/eval/run.jsonl
```

**Output location:** `data/eval/run.jsonl` (JSONL, one eval row per line).

**Queries:** Set `TEST_QUERIES_JSON` (JSON array of `{user_query, destination?, lang?, market?}`) or create `data/eval/test_queries.json`:

```json
[
  {"user_query": "best hotels in Paris", "destination": "Paris"},
  {"user_query": "dicas para evitar filas no Magic Kingdom", "destination": "Orlando", "lang": "pt-BR"}
]
```

Example output snippet:

```
# run.jsonl (one line per eval row)
{"ts":"2026-02-06T17:52:27+00:00","run_id":"...","latency_ms_total":1667.28,...}
```

## Enabling the Judge (LLM Scoring)

Set `JUDGE_ENABLED=1` and `OPENAI_API_KEY` before running the eval:

```bash
export JUDGE_ENABLED=1
export OPENAI_API_KEY="sk-..."
make eval
```

With judge enabled, each eval row includes `judge_groundedness_score`, `judge_product_relevance_score`, and `judge_model`.

## MCP `/metrics` Endpoint

Both MCP services expose a JSON metrics endpoint:

| Service | URL |
|---------|-----|
| mcp-travel-knowledge | http://127.0.0.1:8010/metrics |
| mcp-travel-products  | http://127.0.0.1:8020/metrics |

Example response:

```json
{
  "requests_total": 42,
  "cache_hits_total": 28,
  "weaviate_fallback_total": 0,
  "avg_latency_ms": 45.12
}
```

**Interpretation:**

- **cache_hits_total** – Number of requests served from in-memory cache (no Weaviate call). Higher = less load on Weaviate.
- **avg_latency_ms** – Mean latency per request since process start. Cache hits are fast (~5–20 ms); misses are slower (Weaviate + rerank).
- **Cache hit rate** = `cache_hits_total / requests_total` when `requests_total > 0`.

## Neo4j (youtube_kg / Graph ingestion)

The ingestion worker writes the **youtube_kg** pipeline (graph extraction) to Neo4j. If Neo4j runs on another host (e.g. Neo4j Aura or a separate server), do the following.

**1. Get this host’s public IP** (to allowlist on Neo4j):

```bash
curl -s https://checkip.amazonaws.com
```

**2. Open the door on the Neo4j side**

- **Neo4j Aura:** In the Aura console, add this IP to the IP allowlist for your database (or allow 0.0.0.0/0 for dev only).
- **Self‑hosted / firewall:** Allow inbound TCP **7687** (Bolt) from the IP above (e.g. security group or iptables).

**3. Point config at the Neo4j server**

In `configs/.env`, set `NEO4J_URI` to the Neo4j host (not `localhost` if Neo4j is remote):

```bash
NEO4J_URI=bolt://YOUR_NEO4J_HOST:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

Restart the ingestion worker after changing `.env`.

## LangSmith Tracing

`LANGSMITH_ENABLED=0` disables trace upload; the system works normally. When set to `1`, traces are sent to LangSmith (requires valid `LANGSMITH_API_KEY`). A 403 from LangSmith upload does not affect eval or agent behavior.
