# How to run a real test (integration, no mocks)

Real tests hit the live MCP services (knowledge, products, graph) and backends (Weaviate, Neo4j). Use this when you want to validate the full stack.

## Prerequisites

- **Weaviate** running (for knowledge + products MCPs). Default: `localhost:8080` (see `configs/.env`: `WEAVIATE_HOST`, `WEAVIATE_PORT`).
- **Neo4j** running (for graph MCP). Default: `bolt://localhost:7687` (see `configs/.env`: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`).
- **OpenAI API key** in `configs/.env` as `OPENAI_API_KEY` (used by knowledge, graph, and vision MCPs).

## 1. Start the MCP servers

From the repo root, in **separate terminals** (or background):

```bash
# Terminal 1 – Knowledge (port 8010)
make run-knowledge

# Terminal 2 – Products (port 8020)
make run-products

# Terminal 3 – Graph (port 8031)
make run-graph

# Terminal 4 – Vision (port 8032) – for image-bearing queries
make run-vision

# Terminal 5 – STT (port 8033) – for voice input (audio → transcript)
make run-stt

# Terminal 6 – TTS (port 8034) – for voice output (text → audio)
make run-tts
```

Load `configs/.env` before each run (the Makefile does this). Ensure nothing else is using ports 8010, 8020, 8031, 8032, 8033, 8034.

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

Each row includes `latency_ms_knowledge`, `latency_ms_products`, `latency_ms_graph`, `graph_included`, `latency_ms_vision`, `vision_included`, `vision_mode`, `response_snapshot.answer_text`, and `response_snapshot.citations`.

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

You should get a response with `answer_text`, `citations`, and optionally `addon`. For itinerary-style queries the agent calls the graph MCP and includes path-based content. For messages with `image_ref` (data URL or HTTP URL), the vision MCP is called with mode inferred from `user_query` (packing / landmark / product_similarity).

**Voice mode:** Include `audio_ref` (data URL or HTTP URL) for speech input → STT transcribes and the transcript is used as the query. Set `voice_mode: true` to receive `audio_ref` (synthesized speech) and `spoken_version` / `screen_summary` in the response.

## 4. Custom query set (eval)

To run the eval harness with your own queries without editing the file:

```bash
cd services/agent-api
export TEST_QUERIES_JSON='[{"user_query": "what to do first in Disney?", "destination": "Orlando", "lang": "en"}]'
uv run python -m app.eval_runner --out ../../data/eval/run.jsonl
```

## 5. Eval with vision (image-bearing queries)

Run vision eval (prepare 15 queries, run eval, write `data/eval/run_vision.jsonl`):

```bash
make eval-vision
```

Or manually:

```bash
cd services/agent-api
uv run python ../../scripts/prepare_vision_eval_queries.py --out data/eval/vision_queries.json
TEST_QUERIES_FILE=data/eval/vision_queries.json uv run python -m app.eval_runner --out ../../data/eval/run_vision.jsonl
```

**Query set:** The script generates 15 queries covering all images in `docs/images_vision_test_cases/`:

| Prefix | Mode | Use cases |
|--------|------|-----------|
| `outfit_*` | packing | Outfit suitability for Disney/Orlando, seasonal packing |
| `landmark_*` | landmark | Where is this place?, which park/restaurant/attraction |
| `outfit_social.jpg` | product_similarity | Find something like this outfit on Amazon |

Each image has at least one query. Regenerate with `scripts/prepare_vision_eval_queries.py --out ...` whenever adding images.

## 6. Quick sanity check (no Neo4j/Weaviate)

If only the agent and MCPs are running and Weaviate/Neo4j are down or empty:

- **Knowledge MCP** may return empty evidence or fallback; agent still returns an answer.
- **Graph MCP** may return an empty subgraph when Neo4j is unavailable (or mock, depending on implementation).
- **Vision MCP** requires `OPENAI_API_KEY` for image analysis.
- **Products MCP** may return no candidates.

So you can still run `make eval` or the WebSocket to confirm the agent and MCP wiring; answers will be weaker without real data.

## 7. Interpreting eval results

### run.jsonl / run_vision.jsonl schema

Each JSONL row contains:

| Field | Meaning |
|-------|---------|
| `user_query` | Input query |
| `latency_ms_total` | End-to-end response time (ms) |
| `latency_ms_knowledge` | Knowledge MCP call time |
| `latency_ms_products` | Products MCP call time |
| `latency_ms_graph` | Graph MCP call time |
| `latency_ms_vision` | Vision MCP call time |
| `vision_included` | Whether vision was invoked |
| `vision_mode` | packing \| landmark \| product_similarity (if vision used) |
| `latency_ms_stt` | STT MCP call latency (0 if not called) |
| `latency_ms_tts` | TTS MCP call latency (0 if not called) |
| `audio_included` | True when voice reply included audio_ref |
| `graph_included` | Whether graph was invoked |
| `citations_count` | Number of evidence citations |
| `product_included` | Whether product addon was returned |
| `groundedness_proxy` | min(1.0, citations_count / 3) |
| `response_snapshot.answer_text` | Full answer text |
| `response_snapshot.citations` | List of citation URLs |

### What to look for

- **Vision success:** `vision_included: true` and `vision_mode` set → vision MCP was called.
- **Latency:** Vision calls are typically 2–5 s (OpenAI); total latency often dominated by vision when used.
- **Groundedness:** `citations_count` ≥ 3 gives `groundedness_proxy` = 1; answers with citations are better supported.
- **Errors:** Check `response_snapshot.answer_text` for fallbacks or error messages if MCPs fail.

### Example: inspect vision results

```bash
# Count vision vs non-vision rows
jq -s '[.[] | select(.vision_included == true)] | length' data/eval/run_vision.jsonl

# Per-row: query, vision mode, latency
jq -r '"\(.user_query[:50])... | vision=\(.vision_included) mode=\(.vision_mode // "n/a") latency=\(.latency_ms_total | floor)ms"' data/eval/run_vision.jsonl

# Summary stats
jq -s 'length as $n | (map(select(.vision_included)) | length) as $v | (map(.latency_ms_total) | add / $n | floor) as $avg | {queries: $n, vision_invoked: $v, avg_latency_ms: $avg}' data/eval/run_vision.jsonl
```

### Latest run interpretation (15 queries)

| Metric | Value |
|--------|-------|
| Total queries | 15 |
| Vision invoked | 15 (100%) |
| Mode distribution | packing 11, landmark 3, product_similarity 1 |
| Avg latency | ~3.2 s |

**What worked well**

- **Packing mode:** All outfit queries returned correct item detection (e.g. light_top, shorts_or_skirt, walking_shoes) and suitability judgments.
- **Landmark mode (when routed):** Correct identifications for Pandora (Avatar), Tree of Life, Galaxy's Edge when the right mode was used.
- **Product_similarity:** Returned structured product attributes (e.g. long_pants, color, fit).
- **Cache:** Same-image queries showed low vision latency (~8–30 ms) from cache; cold calls ~2–5 s.
- **Groundedness:** All rows had 5 citations and groundedness_proxy = 1.

**Mode routing gap**

Several landmark-style queries were routed to packing because they lack `LANDMARK_KEYWORDS` ("where is this", "place", "landmark", etc.):

- "Which park is this attraction from?" → packing (wrong)
- "What is this tree? Where is it located?" → packing (wrong)
- "What restaurant is this?" → packing (wrong)
- "Where can I eat this in Orlando?" → packing (wrong)
- "Which Star Wars attraction is this in Orlando?" → packing (wrong)

These returned "This outfit looks suitable for your trip" instead of place identification. Consider expanding `LANDMARK_KEYWORDS` in `agent-api/app/main.py` (e.g. add "restaurant", "attraction", "which park", "what is this") to improve landmark routing.

## Summary

| Goal                         | Command / step                                                         |
|-----------------------------|-------------------------------------------------------------------------|
| Eval over real MCPs         | Start knowledge, products, graph (and vision if needed) → `make eval`   |
| Eval with vision            | Start vision MCP → `make eval-vision` (or prepare script + eval)        |
| Interpret vision results    | `jq` on `data/eval/run_vision.jsonl` (see §7)                           |
| Manual chat                 | Start all MCPs + `make run-agent` → WS client                          |
| Custom queries for eval     | `TEST_QUERIES_JSON='[...]'` + `app.eval_runner`                         |

Test queries in `services/agent-api/data/eval/test_queries.json` are aligned with Orlando/Disney demo data and include one itinerary query so the graph MCP is exercised.
