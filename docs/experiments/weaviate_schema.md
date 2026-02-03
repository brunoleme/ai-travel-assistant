# Weaviate Schema Reference (Experiment → Production)

This document captures the **current experimental Weaviate classes + properties** that the ingestion + retrieval flow expects.

> Important:
> - This is reference truth for *naming* and *types*.
> - Production services must still comply with `/contracts/*.schema.json` at boundaries.
> - Prefer migrations (additive changes) over destructive changes.

---

## Collections / Classes

### 1) `Video` (metadata, vectorizer=none)
Purpose: store video-level metadata; referenced by recommendation cards.

**Properties**
- `videoId` (text)
- `videoUrl` (text)
- `title` (text)
- `channel` (text)
- `lang` (text)
- `playlistUrl` (text)
- `playlistName` (text)
- `creatorTier` (text)
- `uploadDate` (date) — RFC3339/ISO stored as date

**Notes**
- UUID strategy recommended: stable UUID v5 from `videoUrl`.

---

### 2) `RecommendationCard` (vector search, text2vec-openai)
Purpose: travel “evidence cards” derived from transcript chunks.

**Vectorizer**
- `text2vec-openai` model: `text-embedding-3-large` (as per experiment)

**Properties**
- `summary` (text)
- `text` (text) — raw chunk text
- `startSec` (number)
- `endSec` (number)
- `timestampUrl` (text) — clickable source (video URL + `t=...`)
- `lang` (text)
- `destination` (text)

- `categories` (text[])
- `primaryCategory` (text)

- `places` (text[])
- `signals` (text[])

- `confidence` (number) — 0..1
- `rationale` (text) — debug-only

- `videoUploadDate` (date) — (optional) copy from Video.uploadDate into card
- `fromVideo` (Video ref)

**Notes**
- UUID strategy recommended:
  - stable UUID v5 from `(video_uuid, startSec, endSec, md5(text))`.
- Retrieval should request `distance` metadata where possible.
- Freshness penalty can use `videoUploadDate` if present.

---

### 3) `Product` (metadata, vectorizer=none)
Purpose: store raw product entries.

**Properties**
- `question` (text) — the user-intent seed that produced this entry
- `opportunity` (text) — what this product solves
- `link` (text)
- `destination` (text)
- `lang` (text)
- `market` (text)
- `merchant` (text)
- `createdAt` (date)

**Notes**
- UUID strategy recommended: stable UUID v5 from `(link, question)`.

---

### 4) `ProductCard` (vector search, text2vec-openai)
Purpose: an enriched “candidate suggestion” derived from Product.

**Vectorizer**
- `text2vec-openai` model: `text-embedding-3-large` (as per experiment)

**Properties**
- `summary` (text)
- `question` (text)
- `opportunity` (text)
- `link` (text)
- `merchant` (text)
- `lang` (text)
- `market` (text)
- `destination` (text)

- `primaryCategory` (text)
- `categories` (text[])

- `triggers` (text[]) — “when to recommend”
- `constraints` (text[])

- `affiliatePriority` (number) — 0..1
- `userValue` (number) — 0..1
- `confidence` (number) — 0..1
- `rationale` (text) — debug-only

- `fromProduct` (Product ref)
- `createdAt` (date)

**Notes**
- UUID strategy recommended: stable UUID v5 from `(product_uuid, md5(question + opportunity))`.

---

## Production Alignment Notes

- **Agent runtime** must *not* depend directly on Weaviate schema.
  - It consumes MCP outputs that validate the `/contracts/` schemas.
- MCP services may query Weaviate internally, but must output contract-compliant data:
  - `contracts/travel_evidence.schema.json`
  - `contracts/product_candidates.schema.json`

---

## Risky / Dangerous Ops (DO NOT AUTOMATE)

The experiment notebook sometimes deletes schema classes to reset state.
Do NOT put deletion into normal scripts or automated agent flows.
If you need a reset, make a separate manual-only script with confirmations.
