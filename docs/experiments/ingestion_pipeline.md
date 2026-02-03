# Ingestion Pipeline (Experiment → Production Reference)

This document summarizes the ingestion logic used in experiments.
Production ingestion should be event-driven (Phase 4), but this is a correct “shape” reference.

---

## Goal
Convert YouTube content into:
- Video metadata objects
- RecommendationCard objects (chunk-level evidence)
and store them in Weaviate.

---

## Inputs
- playlist_url OR youtube_urls (mutually exclusive)
- destination: optional
- language_hint: pt/en/es/auto
- max_videos: optional limit

Chunking params:
- chunk_max_chars (e.g., 1200)
- chunk_min_chars (e.g., 350)
- chunk_max_duration_s (e.g., 75)
- chunk_min_duration_s (e.g., 25)
- gap_split_s (e.g., 2.5)

Enrichment:
- enrich_model (e.g., gpt-4.1-mini)

---

## Stages (high-level)

### Stage 0) Expand sources
- If playlist_url:
  - use yt-dlp `--flat-playlist` to list video ids
  - build canonical video URLs
- Else:
  - validate and normalize video URLs

### Stage 1) Video metadata
- yt-dlp `--dump-single-json`
- parse upload date:
  - prefer `upload_date` (YYYYMMDD)
  - fallback to `timestamp`

Insert Video:
- stable UUID v5 from video_url
- only insert if not exists (idempotent)

### Stage 2) Subtitles
- yt-dlp:
  - `--write-auto-subs` and `--write-subs`
  - choose language by preference list (hint → fallback)
- parse VTT into timestamped segments

### Stage 3) Chunking
- chunk timestamped segments with:
  - max_chars and max_duration gates
  - flush on long pauses (`gap_split_s`)
  - optional boundary cues heuristic

Output chunks:
- startSec, endSec, text

### Stage 4) Enrichment (RecommendationCard fields)
- Use LLM to extract:
  - summary, categories, places, signals, confidence, rationale
- Must be strict JSON-only output.
- Apply guardrails:
  - if signals empty: confidence <= 0.40 and category “other”
- Fallback:
  - if parse fails or model fails: create safe minimal card

### Stage 5) Insert RecommendationCard (idempotent)
- stable UUID v5 from (video_uuid, startSec, endSec, md5(text))
- insert if not exists

Optional:
- record QA JSONL logs for debugging enrichment quality

---

## Idempotency Keys (must keep)
- Video UUID = uuid5(NAMESPACE_URL, video_url)
- Card UUID = uuid5(NAMESPACE_URL, f"{video_uuid}:{start}:{end}:{md5(text)[:10]}")

---

## Production Notes
- This logic should move into an event-driven ingestion service (Phase 4):
  - fetch → transcript → chunk → enrich → embed → write
- Any destructive schema operations must be manual-only and never used by agents.
