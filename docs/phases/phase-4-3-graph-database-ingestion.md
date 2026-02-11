# Phase 4.3 — Graph Database Ingestion (Neo4j)

**Goal:** From a **single** YouTube video (no playlist expansion), extract a travel knowledge graph (nodes + edges with evidence) and ingest it into Neo4j, reusing the same event-driven patterns and service layout as Phase 4.1 and Phase 4.2.

**Plan references:** [phase-4-1.md](phase-4-1.md) (events, idempotency, DLQ), [phase-4-2-real-ingestion.md](phase-4-2-real-ingestion.md) (real YouTube/Products pipeline, routing by `source_type`).

**Scope:**
- **Single video per event** — one `IngestionRequested` = one `video_url`; no playlist expansion.
- Same event types and stage flow as Phase 4: `requested → transcript → chunks → enrichment → embeddings → write_complete`.
- Reuse existing YouTube **fetch** (yt-dlp metadata + subtitles) and **chunking** (timestamp-aware segments).
- New logic: **graph extraction** (GPT per chunk → nodes/edges with evidence) and **merge** (dedup nodes/edges), then **write to Neo4j**.
- Implement inside **same service:** `services/ingestion` (one pipeline, one worker; graph is a new `source_type` and sink).

**Out of scope:** Playlist expansion for graph pipeline; agent API; MCP; Terraform (no new infra for Neo4j in this phase — Neo4j is assumed existing).

---

## 1. Where to implement: same service (recommended)

**Recommendation: add to the same monolith, `services/ingestion`.**

| Option | Pros | Cons |
|--------|------|------|
| **Same service** | Reuse events, idempotency, SQS worker, YouTube fetch/chunk; one queue, one deploy; consistent patterns | Slightly larger codebase; shared dependency set (add Neo4j driver) |
| **New service** (e.g. `services/ingestion-graph`) | Strict separation; could scale or deploy independently | Duplicate events/worker/chunking; two queues or shared queue with two consumers |

**Decision:** Extend `services/ingestion` with a new **source_type** (e.g. `youtube_kg` or `youtube_graph`). Same pipeline stages; for this source_type the “enrich” stage does graph extraction and the “write” stage writes to Neo4j instead of Weaviate.

---

## 2. Pipeline stages for graph ingestion

Flow for `source_type: "youtube_kg"` (single video only):

| Stage | Handler | Input | Output | Notes |
|-------|---------|--------|--------|------|
| **requested** | handle_fetch | `video_url`, `destination_hint?`, `language_hint?`, chunk params | TranscriptReady | **Reuse** YouTube fetch (yt-dlp metadata + subtitles); same idempotency key `content_source_id:transcript`. |
| **transcript** | handle_transcript | segments, video_metadata, lang | ChunksReady | **Reuse** YouTube chunking (timestamp-aware); key `content_source_id:chunks`. |
| **chunks** | handle_chunk | chunks, video_metadata, destination_hint | EnrichmentReady | **New:** For each chunk, `extract_graph_from_chunk(...)` → list of `GraphExtraction`; payload carries `graph_extractions: List[GraphExtraction]`, plus chunks/video_metadata. Key `content_source_id:enrichment`. |
| **enrichment** | handle_enrich | graph_extractions, video_metadata | EmbeddingsReady | **New:** `merge_graph(graph_extractions)` → single merged graph (nodes deduped by id, edges by (type, source, target, evidence)); no embeddings. Payload carries `graph: { nodes, edges, meta }`. |
| **embeddings** | handle_embed | graph | WriteComplete | Pass-through (no vector step for graph). |
| **write_complete** | handle_write | graph | — | **New:** `ingest_into_neo4j(graph, uri, user, password)` — MERGE nodes (Entity), MERGE relationships with evidence. Key `content_source_id:write`. |

**content_source_id** for graph: same as YouTube — e.g. `youtube_kg:<video_id>` or `youtube:<video_id>` with source_type distinguishing behavior. Recommendation: `youtube_kg:<video_id>` so idempotency is per-video and separate from Weaviate YouTube writes.

---

## 3. Payload contracts (event payloads for youtube_kg)

| Stage | Payload shape (add to existing) |
|-------|---------------------------------|
| **requested** | `source_type: "youtube_kg"`, `video_url: str`, `destination_hint?: str`, `language_hint?: "pt"\|"en"\|"es"\|"auto"`, optional chunk params (`chunk_max_chars`, etc.), optional `extract_model` (default e.g. `gpt-4.1`) |
| **transcript** | Same as YouTube: `segments`, `lang`, `video_metadata`; plus `destination_hint`, `extract_model`. |
| **chunks** | Same as YouTube: `chunks`, `video_metadata`, `lang`, `destination_hint`, `extract_model`. |
| **enrichment** | `source_type: "youtube_kg"`, `graph_extractions: List[GraphExtraction]` (each: nodes, edges), `chunks`, `video_metadata`, `destination_hint`. |
| **embeddings** | `source_type: "youtube_kg"`, `graph: { nodes, edges, meta }` (merged). |
| **write_complete** | Same; handle_write reads `graph` and writes to Neo4j. |

**Graph data model** (internal; no new contract file unless we version it later):

- **GraphNode:** `id`, `type`, `name`, `aliases`, `properties` (allowed types: city, place, poi, itinerary, dayplan, activity_type, advice, constraint).
- **GraphEdge:** `source`, `type`, `target`, `properties`, `evidence` (videoUrl, startSec, endSec, chunkIdx, timestampUrl).
- **Evidence:** `videoUrl`, `startSec`, `endSec`, `chunkIdx`, `timestampUrl`.
- **Allowed edge types:** ITINERARY_FOR, HAS_DAY, INCLUDES_POI, IN_AREA, ORDER_BEFORE, CLUSTERED_BY, SUGGESTED_DAYS, HAS_ACTIVITY_TYPE, HAS_ADVICE, HAS_CONSTRAINT.

(Matches the pipeline you validated in the notebook.)

---

## 4. Implementation tickets

### Ticket G1 — Graph extraction (handle_chunk for youtube_kg)

**Owner:** `services/ingestion`

- **Input:** ChunksReady with `payload.source_type == "youtube_kg"`, chunks, video_metadata, destination_hint, extract_model.
- **Logic:** For each chunk (e.g. skip if `len(text) < 150`):
  - Call `extract_graph_from_chunk(client, model, video_url, chunk_idx, start_sec, end_sec, chunk_text, destination_hint)` (OpenAI) → `GraphExtraction` (nodes + edges with evidence).
  - Filter nodes/edges to allowed types; validate Evidence on each edge.
- **Output:** EnrichmentReady with `payload.graph_extractions`, chunks, video_metadata.
- **Idempotency:** key `content_source_id:enrichment`.
- **Tests:** Mock OpenAI; assert extraction count and that invalid/empty extractions are skipped.

### Ticket G2 — Merge graph (handle_enrich for youtube_kg)

**Owner:** `services/ingestion`

- **Input:** EnrichmentReady with graph_extractions, video_metadata.
- **Logic:** `merge_graph(graph_extractions)` — merge nodes by id (merge aliases/properties); unique edges by (type, source, target, startSec, endSec). Attach `meta: { videoUrl, title, channel, lang, destination_hint, extract_model }`.
- **Output:** EmbeddingsReady with `payload.graph` (merged).
- **Tests:** Unit test merge (dedup nodes, edge uniqueness).

### Ticket G3 — Neo4j write (handle_write for youtube_kg)

**Owner:** `services/ingestion`

- **Input:** WriteComplete (from handle_embed pass-through) with `payload.graph`.
- **Logic:** `ingest_into_neo4j(graph, uri, user, password)`:
  - MERGE nodes: `(x:Entity {id: $id}) SET x.type = $type, x.name = $name, x.aliases = $aliases, x += $properties`.
  - For each edge: MATCH source and target Entity by id; MERGE relationship with type and evidence (e.g. `key = type|source|target|startSec|endSec` for idempotency).
- **Config:** NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (and optionally NEO4J_DATABASE) from env.
- **Idempotency:** key `content_source_id:write`; already-processed skip (same as Weaviate write).
- **Tests:** Mock Neo4j driver; assert MERGE/MATCH calls with expected node/edge shapes.

### Ticket G4 — Pipeline routing (fetch, transcript, embed, write)

**Owner:** `services/ingestion`

- **handle_fetch:** If `source_type == "youtube_kg"`, same as YouTube: require `video_url`; call existing YouTube fetch (yt-dlp); emit TranscriptReady with segments, lang, video_metadata, plus destination_hint, extract_model. content_source_id suggestion: `youtube_kg:<video_id>`.
- **handle_transcript:** If `source_type == "youtube_kg"`, same as YouTube chunking; emit ChunksReady with chunks, video_metadata, destination_hint, extract_model.
- **handle_embed:** If `source_type == "youtube_kg"`, pass-through (no embedding step).
- **handle_write:** If `source_type == "youtube_kg"`, call Neo4j ingest; else existing youtube/products logic.
- **Tests:** Existing idempotency/DLQ tests unchanged; add unit tests for youtube_kg path with mocks (fetch, chunk, extract, merge, Neo4j).

### Ticket G5 — Graph models and extraction module

**Owner:** `services/ingestion`

- Add Pydantic models: `GraphNode`, `GraphEdge`, `Evidence`, `GraphExtraction` (and allowed NODE_TYPES / EDGE_TYPES constants).
- Add `app/sources/graph.py` (or `app/sources/kg.py`): `extract_graph_from_chunk`, `merge_graph`, `ingest_into_neo4j`, helpers (`slugify`, `make_node_id`, `make_timestamp_url`). Reuse or share `make_timestamp_url` with youtube if desired.
- System prompt and JSON parsing from your notebook (grounding rules, language, place vs POI, edge direction, ORDER_BEFORE strict, evidence required).
- **Dependencies:** `openai` (existing), `neo4j` driver in `pyproject.toml`.

---

## 5. Environment variables (.env)

Add to `configs/.env` (and do **not** commit; already in `.gitignore`):

```bash
# ---- Neo4j (Phase 4.3 graph ingestion) ----
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
# Optional: database name (Neo4j 4.x+); default "neo4j"
# NEO4J_DATABASE=neo4j
```

**Already used by this pipeline (no change):**

- `OPENAI_API_KEY` — for graph extraction (and existing YouTube/Products enrich).
- `YTDLP_COOKIES_FILE` — (optional) for yt-dlp when YouTube blocks; same as Phase 4.2.

**Not needed for graph pipeline:** WEAVIATE_* (only used for youtube/products write). SQS/queue URLs if you run the worker in AWS mode (same as today).

---

## 6. Producer: who sends IngestionRequested for graph

- **Single video:** One SQS message (or local event) per video.
- **Example payload:**
  - `content_source_id`: `youtube_kg:<video_id>`
  - `payload`: `{ "source_type": "youtube_kg", "video_url": "https://www.youtube.com/watch?v=...", "destination_hint": "Playa del Carmen", "language_hint": "pt" }`
- No playlist expansion in this phase; a separate script (e.g. `scripts/send_graph_ingestion.py`) could send one message per URL without listing playlist entries.

---

## 7. Order of work (suggested)

1. **G5** — Graph models + `app/sources/graph.py` (extract_graph_from_chunk, merge_graph, ingest_into_neo4j); add `neo4j` dependency.
2. **G3** — handle_write for `source_type == "youtube_kg"` (Neo4j); idempotency key `content_source_id:write`.
3. **G1** — handle_chunk for youtube_kg (graph extraction per chunk).
4. **G2** — handle_enrich for youtube_kg (merge_graph).
5. **G4** — handle_fetch / handle_transcript / handle_embed routing for youtube_kg; wire end-to-end.
6. **Tests** — Unit tests with mocked OpenAI and Neo4j; ensure existing Phase 4 tests still pass.

---

## 8. Acceptance criteria (Phase 4.3)

- [ ] One IngestionRequested with `source_type: "youtube_kg"` and one `video_url` → worker runs fetch (yt-dlp) → transcript → chunks → graph extraction → merge → write → nodes and relationships in Neo4j; idempotent (same content_source_id twice = no duplicate writes).
- [ ] Graph contains only allowed node and edge types; every edge has evidence (videoUrl, startSec, endSec, chunkIdx, timestampUrl).
- [ ] Unit tests mock yt-dlp, OpenAI, Neo4j; no real external calls in tests.
- [ ] Existing Phase 4 tests (idempotency, DLQ, youtube/products) still pass.
- [ ] Documented .env: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (and optional NEO4J_DATABASE).

---

## 9. Summary: what to add in .env

| Variable | Required | Description |
|---------|----------|-------------|
| `NEO4J_URI` | Yes | Neo4j bolt URI, e.g. `bolt://localhost:7687` |
| `NEO4J_USER` | Yes | Neo4j user (e.g. `neo4j`) |
| `NEO4J_PASSWORD` | Yes | Neo4j password |
| `NEO4J_DATABASE` | No | Database name (Neo4j 4.x+; default `neo4j`) |

Existing: `OPENAI_API_KEY`, optional `YTDLP_COOKIES_FILE`; for AWS mode: `INGESTION_QUEUE_URL`, `INGESTION_DLQ_URL`.
