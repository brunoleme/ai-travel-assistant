# Phase 6 — Vision MCP + Multimodal Agent

**Goal:** Add an MCP that analyzes images via a vision model (gpt-4.1-mini) and produces structured signals for three use cases: (4) outfit + weather packing, (5) landmark / place recognition, (7) product similarity via attribute extraction. The agent runtime routes image-bearing messages to the vision MCP, then uses signals for advice and optional product search.

**Scope:**
- New service: **mcp-travel-vision** (same structure as mcp-travel-knowledge / mcp-travel-products).
- Contract: **contracts/vision_signals.schema.json** (request/response for packing, landmark, product_similarity modes).
- Agent runtime: MCP config for vision URL, **routing logic** (when user sends image → call vision MCP), integration of vision signals into answer + optional product recommendation, and eval metrics for vision latency.

**Out of scope:** Image embeddings / vector search (Feature 7 uses attribute → search query, not embeddings). No changes to ingestion. No Terraform.

**Reference:** Phase 1 (MCP skeleton, contracts), Phase 5 (graph MCP structure), phase docs 1–3.

---

## 1. Contract

**File:** `contracts/vision_signals.schema.json`

- **Request:** `image_ref` (data URL or HTTP URL), `mode` (`packing` | `landmark` | `product_similarity`), optional `trip_context`, optional `user_query`, optional `lang`, `debug`.
- **Response:** `x_contract_version`, `request` (echo), `signals` (VisionSignals), optional `debug`.
- **VisionSignals:** `mode`, `confidence`, optional `error`.
  - **Packing mode:** `detected_items` (array of category strings from 18-item set), `missing_categories`.
  - **Landmark mode:** `scene_type`, `ocr_text`, `distinctive_features`, `language_hint`, `place_candidates` (array of `{place_name, confidence, reason}`).
  - **Product_similarity mode:** `category`, `attributes`, `style_keywords`, `search_queries` (2–3 marketplace query strings).

**18-item travel category set (reference):** `light_top`, `warm_top`, `insulated_jacket`, `rain_jacket`, `long_pants`, `shorts_or_skirt`, `walking_shoes`, `sandals`, `weather_proof_shoes`, `sun_protection`, `cold_accessory`, `umbrella`, `day_bag`, `travel_bag_organizer`, `power_adapter`, `portable_charger`, `water_bottle`, `travel_comfort_item`.

**Scene types (landmark mode):** `landmark`, `street`, `beach`, `mountain`, `museum`, `airport`, `restaurant`, `hotel`, `transit`, `urban`, `nature`.

Consumers (mcp-travel-vision and agent-api) MUST validate responses against this schema in tests.

---

## 2. MCP: mcp-travel-vision

**Owner:** services/mcp-travel-vision (new service).

Structure aligned with mcp-travel-knowledge / mcp-travel-products:
- `app/main.py` — FastAPI, `/health`, `/metrics`, `POST /mcp/analyze_image`.
- `app/vision.py` — Call OpenAI vision API (gpt-4.1-mini) with image + mode-specific prompts; parse structured JSON from model output.
- `app/prompts.py` — Prompt templates per mode (packing, landmark, product_similarity) returning strict JSON.
- `app/models.py` — Pydantic models matching vision_signals.schema.json.
- `app/cache.py` — Cache key: hash(image_ref) + mode + trip_context_snapshot; TTL cache (vision calls are costly).
- `app/metrics.py` — request_count, error_count, latency_ms, cache_hit.
- `app/logging_utils.py` — Structured logs with session_id, request_id, latency_ms, cache_hit.
- Env: `OPENAI_API_KEY`, optional `VISION_MODEL` (default `gpt-4.1-mini`).

### Ticket V1 — mcp-travel-vision repo scaffold
**Owner:** services/mcp-travel-vision
- Add pyproject.toml (fastapi, uvicorn, openai, httpx, pydantic), uv.lock.
- Add minimal FastAPI app: `/health`, `/metrics`, `POST /mcp/analyze_image` returning mocked response that validates against contracts/vision_signals.schema.json.
- Add Make target in root Makefile (sync-vision, run-vision, test-vision) mirroring knowledge/products/graph.
- **Tests:** Contract validation test (response matches vision_signals.schema.json).

### Ticket V2 — Vision analysis (packing mode)
**Owner:** services/mcp-travel-vision
- Implement packing mode: send image + trip_context to gpt-4.1-mini with structured prompt; output `detected_items` (from 18-item set), `missing_categories`.
- Prompt: "List detected clothing/item categories from the 18-item travel set. Infer missing categories for the given trip context. Output JSON only."
- Adapter: map model output to VisionSignals; validate against schema; on parse failure set `error` and `confidence=0`.
- **Tests:** Unit test with mocked OpenAI client; response validates; parse failure returns valid schema with error.

### Ticket V3 — Vision analysis (landmark mode)
**Owner:** services/mcp-travel-vision
- Implement landmark mode: prompt for `scene_type`, `ocr_text`, `distinctive_features`, `place_candidates` (top 3).
- Prompt: "Describe scene, extract text, list distinctive features, propose up to 3 place candidates with confidence."
- **Tests:** Mocked OpenAI; response validates for landmark mode.

### Ticket V4 — Vision analysis (product_similarity mode)
**Owner:** services/mcp-travel-vision
- Implement product_similarity mode: prompt for `category` (18-item set), `attributes`, `style_keywords`, `search_queries` (2–3 strings).
- Prompt: "Extract product category and attributes; produce 2–3 marketplace search query strings."
- **Tests:** Mocked OpenAI; response validates for product_similarity mode.

### Ticket V5 — Caching and metrics
**Owner:** services/mcp-travel-vision
- Cache key: hash(image_ref) + mode + JSON-stringified trip_context; TTL (e.g. 1h).
- Metrics: request_count, error_count, latency_ms, cache_hit_rate.
- Structured logs: session_id, request_id, latency_ms, cache_hit.
- **Tests:** Same request returns cached; cache hit in logs/metrics.

---

## 3. Agent Runtime: image routing and integration

**Owner:** services/agent-api.

- Config for vision MCP URL (e.g. `VISION_MCP_URL`, default http://127.0.0.1:8032).
- **Routing:** When WS message includes `image_ref` (or `image` field), call vision MCP with appropriate `mode` (infer from user_query or default to `packing`).
- **Integration:**
  - Packing: pass vision signals + trip_context to answer builder; apply gap-detection policy; optionally recommend 1 product when critical gap exists (Feature 7 extension).
  - Landmark: use signals for place candidates; retrieve POIs/guides from knowledge or graph; answer + optional actions (transit, opening hours).
  - Product_similarity: use `search_queries` to call products MCP (or external search); return 3–6 options with "why this matches."
- **Eval:** Record `latency_ms_vision` and `vision_included` in eval JSONL when vision is used.

### Ticket AV1 — MCP config and client for vision
**Owner:** services/agent-api
- Add `vision_base_url` to MCPConfig (env `VISION_MCP_URL`, default http://127.0.0.1:8032).
- Add `analyze_image(client, base_url, request)` in mcp_client.py; POST to `/mcp/analyze_image`; validate response against vision_signals.schema.json.
- **Tests:** Unit test with mocked HTTP; response shape validated.

### Ticket AV2 — Routing: when to call vision MCP
**Owner:** services/agent-api
- When WS message has `image_ref` (or `image`), call vision MCP.
- Infer `mode` from user_query: "packing"/"outfit"/"clothes"/"suitcase" → packing; "where is this"/"landmark"/"place" → landmark; "like this"/"similar"/"find one like" → product_similarity. Default: packing.
- **Tests:** Message with image_ref → vision MCP called; message without image → vision not called. Mock MCPs.

### Ticket AV3 — Integrate vision signals into answer (packing)
**Owner:** services/agent-api
- When vision returns packing signals: build answer from detected_items + missing_categories + trip context.
- Apply simple gap-detection policy (from Phase 6 design): recommend only when critical gap (rain_jacket + rain_risk, etc.).
- Frame advice as comfort/weather, never appearance/body.
- **Tests:** Mocked vision packing response; answer contains packing advice; no recommendation when no critical gap.

### Ticket AV4 — Integrate vision signals (landmark)
**Owner:** services/agent-api
- When vision returns landmark signals: use place_candidates + scene_type; optionally call knowledge/graph for POI info.
- Answer template: "Parece ser X. Quer dicas do que fazer por perto?" (or ask clarifying question if confidence low).
- Recommend actions (transit, hours), not products, unless user signals need (e.g. "phone dying" → portable charger).
- **Tests:** Mocked landmark response; answer includes place guess and/or follow-up question.

### Ticket AV5 — Integrate vision signals (product_similarity)
**Owner:** services/agent-api
- When vision returns product_similarity signals: use `search_queries` to call products MCP (query_signature built from first query) or external product search.
- Return 3–6 options; include "why this matches" from attributes.
- Only trigger when user asked ("find one like this") or accepted prior suggestion.
- **Tests:** Mocked product_similarity response; products MCP called with query from search_queries; answer includes product options.

### Ticket AV6 — Eval and metrics for vision
**Owner:** services/agent-api
- Add `latency_ms_vision`, `vision_included`, `vision_mode` to eval runner output and eval_row schema.
- When vision MCP is called, record latency and mode in eval JSONL.
- **Tests:** Eval runner with mocked vision call writes latency_ms_vision and vision_included; schema validation passes.

---

## 4. Order of work (suggested)

1. **Contract** — vision_signals.schema.json (done).
2. **V1** — mcp-travel-vision scaffold + mock response + contract test.
3. **V2** — Packing mode vision analysis.
4. **V3** — Landmark mode vision analysis.
5. **V4** — Product_similarity mode vision analysis.
6. **V5** — Caching and metrics.
7. **AV1** — Agent: vision MCP config and client.
8. **AV2** — Agent: routing (when to call vision).
9. **AV3** — Agent: integrate packing signals.
10. **AV4** — Agent: integrate landmark signals.
11. **AV5** — Agent: integrate product_similarity signals.
12. **AV6** — Agent: eval latency_vision and vision_included.

---

## 5. Acceptance criteria

- [ ] mcp-travel-vision: `/health`, `/metrics`, `POST /mcp/analyze_image` return response validating against contracts/vision_signals.schema.json; unit tests with mocked OpenAI; cache and metrics in place.
- [ ] Agent: For messages with image_ref, vision MCP is called; packing/landmark/product_similarity answers integrate signals correctly; eval row includes latency_ms_vision and vision_included.
- [ ] make test and make lint pass for agent-api and mcp-travel-vision.
- [ ] No breaking changes to existing travel_evidence, product_candidates, or graph_rag contracts.

---

## 6. Config summary

| Service            | Env / config                                |
|--------------------|---------------------------------------------|
| mcp-travel-vision  | OPENAI_API_KEY, VISION_MODEL (default gpt-4.1-mini) |
| agent-api          | VISION_MCP_URL (e.g. http://127.0.0.1:8032) |

Port suggestion for mcp-travel-vision: **8032** (knowledge=8010, products=8020, ingestion=8030, graph=8031).

---

## 7. UX rules (from design)

- **Packing:** Frame as comfort + weather; never appearance/body. Recommend product only when critical gap; ask "Want me to suggest one?" before showing options.
- **Landmark:** High confidence → answer directly; medium/low → ask 1 clarifying question. Recommend actions (transit, hours), not products, unless user signals need.
- **Product similarity:** Only trigger when user asked or accepted suggestion. Max 3–6 options; include "why this matches."
