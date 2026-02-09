# Phase 4 (Real Ingestion) — YouTube & Products in the Event Pipeline

**Goal:** Replace mock pipeline stages with real logic: YouTube (yt-dlp → subtitles → chunk → enrich → Weaviate) and Products (JSON → enrich → Weaviate), using the existing Phase 4 events, idempotency, and SQS/DLQ.

**Scope:**
- Same event types and stage order as Phase 4 (IngestionRequested → … → WriteComplete).
- Payload contracts so each event carries the data your manual pipelines need.
- Real fetch (yt-dlp), chunking, OpenAI enrich, and Weaviate write inside `services/ingestion`.
- Two content types: **youtube** (one video per event or batch) and **products** (batch of product inputs).
- Phase 5 (observability) and Phase 6 (deployment) unchanged; this phase only touches `services/ingestion` and optional shared Weaviate schema helpers.

**Out of scope:** Agent API, MCP services, Terraform. No change to Phase 5/6 docs.

---

## 1. Payload contracts (event payloads)

All events already have `event_id`, `content_source_id`, `stage`, `payload`, `retry_count`, `max_retries`, `error`. Below defines what goes inside `payload` for each stage and content type.

### 1.1 YouTube

| Stage            | Who produces it | Payload shape (add to existing) |
|------------------|------------------|----------------------------------|
| **requested**    | Producer (API/script) | `source_type: "youtube"`, `video_url: str`, `destination: str`, `language_hint: "pt"\|"en"\|"es"\|"auto"`, optional: `playlist_url`, `playlist_name`, `creator_tier`, `chunk_max_chars`, `chunk_min_chars`, `chunk_max_duration_s`, `chunk_min_duration_s`, `gap_split_s`, `enrich_model` |
| **transcript**   | handle_fetch     | `segments: [{start, duration, text}]`, `lang: str`, `video_metadata: {id, title, channel, upload_date, webpage_url}` (for Video upsert and later stages) |
| **chunks**       | handle_transcript | `chunks: [{startSec, endSec, text}]`, same `video_metadata`, `lang` |
| **enrichment**   | handle_chunk     | `cards: [RecommendationCard-like dicts]` per chunk, plus `chunks`, `video_metadata`, `lang`, `destination` |
| **embeddings**   | handle_enrich    | For Weaviate with vectorizer: can be same as enrichment payload; no separate embed call. Optional: store precomputed vectors if not using Weaviate vectorizer. |
| **write_complete** | handle_embed  | Same; handle_write consumes this and writes to Weaviate. |

- **content_source_id** for YouTube: stable id per video, e.g. `youtube:<video_id>` or UUID from `video_url`.

### 1.2 Products

| Stage            | Who produces it | Payload shape |
|------------------|------------------|---------------|
| **requested**    | Producer         | `source_type: "products"`, `products: [{question, opportunity, link, destination?, lang?, market?}]`, optional `enrich_model` |
| **transcript**   | handle_fetch     | No-op for products: pass through `products` list (or treat as “already transcribed”). Emit TranscriptReady with same payload. |
| **chunks**       | handle_transcript | Same; each “chunk” = one product input for enrichment. |
| **enrichment**   | handle_chunk     | `cards: [ProductCard-like dicts]`, `products` (original inputs). |
| **embeddings**   | handle_enrich    | Same as enrichment (Weaviate vectorizer). |
| **write_complete** | handle_embed   | Same; handle_write inserts Product + ProductCard. |

- **content_source_id** for products: e.g. `products:<batch_id>` (one event = one batch).

---

## 2. Stage implementation plan

Implement inside `services/ingestion` only. Keep existing events and idempotency keys; replace mock logic with real calls.

### Ticket R1 — YouTube fetch (handle_fetch for youtube)

**Owner:** `services/ingestion`

- **Input:** `IngestionRequested` with `payload.source_type == "youtube"`, `payload.video_url`, `payload.destination`, `payload.language_hint`, optional chunk/enrich params.
- **Logic:**
  - Use **yt-dlp** (subprocess) to get video metadata (`get_video_metadata`) and subtitles (`fetch_subtitles_via_ytdlp` → VTT → `vtt_to_segments`).
  - Output: segments + chosen lang + video metadata (id, title, channel, upload_date, webpage_url).
- **Output:** `TranscriptReady` with `payload.segments`, `payload.lang`, `payload.video_metadata`.
- **Idempotency:** key `content_source_id:transcript` (already in Phase 4); same video twice → skip or overwrite with same result.
- **Dependencies:** yt-dlp on PATH or installable; certifi/SSL if needed (reuse your notebook pattern).
- **Tests:** unit test with mocked subprocess (fixed VTT + metadata); no real YouTube in tests.

### Ticket R2 — YouTube chunking (handle_transcript for youtube)

**Owner:** `services/ingestion`

- **Input:** `TranscriptReady` with `payload.segments`, `payload.video_metadata`, `payload.lang`, and chunk params (from original request or defaults).
- **Logic:** `chunk_timestamped_segments(segments, max_chars=..., min_chars=..., max_duration_s=..., min_duration_s=..., gap_split_s=...)` → list of `{startSec, endSec, text}`.
- **Output:** `ChunksReady` with `payload.chunks`, `payload.video_metadata`, `payload.lang`, `payload.destination`.
- **Idempotency:** key `content_source_id:chunks`.
- **Tests:** unit test with fixed segments; assert chunk count and boundaries.

### Ticket R3 — YouTube enrich (handle_chunk for youtube)

**Owner:** `services/ingestion`

- **Input:** `ChunksReady` with chunks, video_metadata, lang, destination.
- **Logic:** For each chunk, call `enrich_chunk_to_card(chunk_text=chunk["text"], destination=..., source_lang=..., model=...)` (OpenAI) → RecommendationCard-like dict; collect list.
- **Output:** `EnrichmentReady` with `payload.cards`, `payload.chunks`, `payload.video_metadata`, `payload.lang`, `payload.destination`.
- **Idempotency:** key `content_source_id:enrichment`.
- **Tests:** mock OpenAI; assert card count and that fallback is used when LLM fails.

### Ticket R4 — YouTube write (handle_embed + handle_write for youtube)

**Owner:** `services/ingestion`

- **handle_embed:** For Weaviate-backed RecommendationCard (vectorizer = text2vec-openai), no separate embed step; pass through `EnrichmentReady` payload as `WriteComplete` payload.
- **handle_write:**
  - Connect Weaviate (reuse your `connect_weaviate()` pattern; env: WEAVIATE_HOST, WEAVIATE_PORT, WEAVIATE_GRPC_PORT).
  - Ensure schema: Video + RecommendationCard (reuse your `ensure_collections()` / REST schema or equivalent).
  - `upsert_video(client, meta=video_metadata, cfg)` → video_uuid.
  - For each card: `stable_uuid_for_card(video_uuid, start_sec, end_sec, text)`; insert RecommendationCard with ref to Video, properties from card (summary, categories, places, signals, confidence, rationale, timestampUrl, etc.).
- **Idempotency:** key `content_source_id:write`; if already processed, skip (no duplicate inserts).
- **Tests:** mock Weaviate client; assert insert/upsert called with expected shapes; no real Weaviate in unit tests.

### Ticket R5 — Products “fetch” and chunk (handle_fetch + handle_transcript for products)

**Owner:** `services/ingestion`

- **handle_fetch:** When `payload.source_type == "products"`, no external fetch; emit `TranscriptReady` with same `payload.products` (and optional metadata).
- **handle_transcript:** Pass through; emit `ChunksReady` with `payload.products` (each item is one “chunk” for enrich).
- **Idempotency:** same keys; idempotent by content_source_id.

### Ticket R6 — Products enrich (handle_chunk for products)

**Owner:** `services/ingestion`

- **Input:** `ChunksReady` with `payload.products` (list of ProductInput-like dicts).
- **Logic:** For each product, call `enrich_product_to_card(pi=ProductInput(**p), model=...)` → ProductCard-like dict.
- **Output:** `EnrichmentReady` with `payload.cards`, `payload.products`.
- **Tests:** mock OpenAI; assert card count.

### Ticket R7 — Products write (handle_embed + handle_write for products)

**Owner:** `services/ingestion`

- **handle_embed:** Pass through (Weaviate vectorizer).
- **handle_write:** Ensure Product + ProductCard schema; for each product: `upsert_product(client, pi)`; for each card: insert ProductCard with ref to Product (reuse your `stable_uuid_for_product`, `stable_uuid_for_card`, and insert_cards logic).
- **Tests:** mock Weaviate; assert Product and ProductCard inserts.

---

## 3. Routing by source_type

- In **pipeline** (or aws_worker): from `IngestionRequested.payload.source_type` decide:
  - `"youtube"` → run YouTube fetch (R1); subsequent stages use YouTube payload shapes.
  - `"products"` → run products “fetch” (R5); subsequent stages use products payload shapes.
- If `source_type` missing or unknown, emit error and send to DLQ (or requeue with error metadata).

---

## 4. Weaviate schema and config

- **Schema:** Reuse your existing classes: **Video**, **RecommendationCard**, **Product**, **ProductCard** (same properties as in your manual pipelines).
- **Ensure schema:** Call your `ensure_collections()` (or equivalent) at worker startup or once per write (idempotent).
- **Config:** WEAVIATE_HOST, WEAVIATE_PORT, WEAVIATE_GRPC_PORT, OPENAI_API_KEY from env (or .env); no change to Phase 4 env vars for SQS.

---

## 5. Dependencies and layout

- **services/ingestion:** Add deps: `openai`, `weaviate-client`, `certifi`; optional `python-dotenv`. yt-dlp remains external (subprocess).
- **Layout suggestion:**
  - `app/pipeline.py` — keep stage entrypoints; delegate to real implementations.
  - `app/sources/youtube.py` — fetch (yt-dlp), segments, chunking, enrich_chunk_to_card, upsert_video, insert_cards (or split into fetch/chunk/enrich/write modules).
  - `app/sources/products.py` — enrich_product_to_card, upsert_product, insert_product_cards.
  - `app/weaviate_schema.py` — ensure_collections (Video, RecommendationCard, Product, ProductCard) via REST or client.
- **Event payload:** Keep generic `payload: dict`; document the shapes above in code (e.g. TypedDict or a small docs string) so producers (API or scripts) know what to send.

---

## 6. Producer: who sends IngestionRequested

- **YouTube:** Script or future API that sends one SQS message per video (or per playlist, then worker expands and emits one event per video). Example payload:
  - `content_source_id`: `youtube:<video_id>`
  - `payload`: `{ "source_type": "youtube", "video_url": "https://www.youtube.com/watch?v=...", "destination": "Orlando", "language_hint": "pt" }`
- **Products:** Script or API that sends one message per batch. Example:
  - `content_source_id`: `products:<batch_id>`
  - `payload`: `{ "source_type": "products", "products": [{ "question": "...", "opportunity": "...", "link": "..." }] }`

---

## 7. Acceptance criteria (Phase 4 Real Ingestion)

- [ ] YouTube: one IngestionRequested (video_url) → worker runs fetch → transcript → chunk → enrich → write → Video + RecommendationCards in Weaviate; idempotent (same content_source_id twice = no duplicate cards).
- [ ] Products: one IngestionRequested (products list) → worker runs fetch (pass-through) → chunk (pass-through) → enrich → write → Product + ProductCards in Weaviate; idempotent.
- [ ] Unknown or missing `source_type` → error metadata and DLQ after retries.
- [ ] Unit tests mock yt-dlp, OpenAI, Weaviate; no real external calls in tests.
- [ ] Existing Phase 4 tests (idempotency, DLQ, replay) still pass; optional “integration” test with mock pipeline run for one YouTube and one products event.

---

## 8. Order of work (suggested)

1. **R4 + Weaviate schema** — ensure_collections + write path for YouTube (so you can “write” from existing data in tests).
2. **R1** — YouTube fetch (yt-dlp + segments).
3. **R2** — YouTube chunking.
4. **R3** — YouTube enrich (OpenAI RecommendationCard).
5. Wire **R1→R2→R3→R4** in pipeline for `source_type == "youtube"`; run E2E with one video.
6. **R5, R6, R7** — Products fetch/chunk/enrich/write; wire for `source_type == "products"`.
7. **Routing** — source_type dispatch and DLQ on unknown type.

Phase 5 (observability) and Phase 6 (deployment) remain as-is; this phase only implements real ingestion inside the existing Phase 4 pipeline.
