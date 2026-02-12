# Phase 7 — Audio MCPs (STT + TTS) + Voice Agent

**Goal:** Add two MCPs for speech-to-text (STT) and text-to-speech (TTS) to enable push-to-talk voice interaction. Audio is treated as modal adapters: they convert between audio and structured text; the existing pipeline (RAG, graph, recommender) stays unchanged. The agent supports voice mode with mode switching (Normal vs Quick) and a confidence-gated voice recommendation policy.

**Scope:**
- New services: **mcp-travel-stt** and **mcp-travel-tts**.
- Contracts: **contracts/stt_transcript.schema.json**, **contracts/tts_audio.schema.json**.
- Agent runtime: MCP config for STT/TTS URLs, **routing logic** (when user sends audio → call STT; when voice reply requested → call TTS), voice-safe answer generation (spoken_version + screen_summary), mode switching policy, and eval metrics for audio latency.

**Out of scope:** Diarization, speaker turns, custom voices. No Terraform in this phase.

**Reference:** Phase 1 (MCP skeleton, contracts), Phase 5/6 (graph, vision MCP structure), voice style guide and mode switching policy from design.

---

## 1. Contracts

### 1.1 STT — `contracts/stt_transcript.schema.json`

- **Request:** `audio_ref` (data URL or HTTP URL), optional `language` (IETF hint), optional `debug`.
- **Response:** `x_contract_version`, `request` (echo), `transcript` (string), optional `language`, optional `confidence` [0–1], optional `duration_seconds`, optional `error`, optional `debug`.

Consumers MUST validate STT responses against this schema.

### 1.2 TTS — `contracts/tts_audio.schema.json`

- **Request:** `text` (required), optional `voice`, optional `language`, optional `speed` [0.25–4.0], optional `format` (mp3 | opus | aac | wav | pcm), optional `debug`.
- **Response:** `x_contract_version`, `request` (echo), `audio_ref` (data URL or HTTP URL), optional `format`, optional `duration_seconds`, optional `error`, optional `debug`.

Consumers MUST validate TTS responses against this schema.

---

## 2. MCP: mcp-travel-stt

**Owner:** services/mcp-travel-stt (new service).

Structure aligned with mcp-travel-vision:
- `app/main.py` — FastAPI, `/health`, `/metrics`, `POST /mcp/transcribe`.
- `app/transcribe.py` — Call OpenAI STT (gpt-4o-mini-transcribe) with audio; map to contract.
- `app/models.py` — Pydantic models matching stt_transcript.schema.json.
- `app/metrics.py` — request_count, error_count, latency_ms.
- `app/logging_utils.py` — Structured logs with session_id, request_id, latency_ms.
- Env: `OPENAI_API_KEY`, optional `STT_MODEL` (default `gpt-4o-mini-transcribe`).

Note: STT is synchronous; no caching (audio varies per request).

### Ticket S1 — mcp-travel-stt repo scaffold
**Owner:** services/mcp-travel-stt
- Add pyproject.toml (fastapi, uvicorn, openai, httpx, pydantic), uv.lock.
- Add minimal FastAPI app: `/health`, `/metrics`, `POST /mcp/transcribe` returning mocked response that validates against contracts/stt_transcript.schema.json.
- Add Make target in root Makefile (sync-stt, run-stt, test-stt).
- **Tests:** Contract validation test (response matches stt_transcript.schema.json).

### Ticket S2 — Transcription implementation
**Owner:** services/mcp-travel-stt
- Implement transcription: decode audio_ref (base64 from data URL or fetch from HTTP URL); call OpenAI STT API (gpt-4o-mini-transcribe).
- Map response to contract: transcript, language, confidence; on failure set error and empty transcript.
- Support optional language hint; validate audio format (mp3, wav, webm, etc.).
- **Tests:** Unit test with mocked OpenAI client; response validates; parse/API failure returns valid schema with error.

### Ticket S3 — Metrics and logging
**Owner:** services/mcp-travel-stt
- Metrics: request_count, error_count, latency_ms.
- Structured logs: session_id, request_id, latency_ms.
- **Tests:** Metrics and logs asserted in integration tests.

---

## 3. MCP: mcp-travel-tts

**Owner:** services/mcp-travel-tts (new service).

Structure aligned with mcp-travel-stt:
- `app/main.py` — FastAPI, `/health`, `/metrics`, `POST /mcp/synthesize`.
- `app/synthesize.py` — Call OpenAI TTS (gpt-4o-mini-tts) with text + voice settings; return audio_ref (data URL).
- `app/models.py` — Pydantic models matching tts_audio.schema.json.
- `app/metrics.py` — request_count, error_count, latency_ms.
- `app/logging_utils.py` — Structured logs with session_id, request_id, latency_ms.
- Env: `OPENAI_API_KEY`, optional `TTS_MODEL` (default `gpt-4o-mini-tts`), optional `TTS_VOICE` (default `alloy`).

### Ticket T1 — mcp-travel-tts repo scaffold
**Owner:** services/mcp-travel-tts
- Add pyproject.toml (fastapi, uvicorn, openai, httpx, pydantic), uv.lock.
- Add minimal FastAPI app: `/health`, `/metrics`, `POST /mcp/synthesize` returning mocked response that validates against contracts/tts_audio.schema.json.
- Add Make target in root Makefile (sync-tts, run-tts, test-tts).
- **Tests:** Contract validation test (response matches tts_audio.schema.json).

### Ticket T2 — Synthesis implementation
**Owner:** services/mcp-travel-tts
- Implement synthesis: call OpenAI TTS API (gpt-4o-mini-tts) with text, voice, speed, format.
- Map response to contract: audio_ref (data:audio/mp3;base64,...), format, optional duration_seconds; on failure set error.
- Support voices: alloy, echo, fable, onyx, nova, shimmer.
- **Tests:** Unit test with mocked OpenAI client; response validates; API failure returns valid schema with error.

### Ticket T3 — Metrics and logging
**Owner:** services/mcp-travel-tts
- Metrics: request_count, error_count, latency_ms.
- Structured logs: session_id, request_id, latency_ms.
- **Tests:** Metrics and logs asserted in integration tests.

---

## 4. Agent Runtime: voice routing and integration

**Owner:** services/agent-api.

- Config for STT/TTS MCP URLs (e.g. `STT_MCP_URL`, `TTS_MCP_URL`).
- **Routing:** When WS message includes `audio_ref` or `voice_mode: true`, call STT first to get transcript; then run existing pipeline (knowledge/graph/products); when voice reply requested, call TTS with spoken_version.
- **Voice-safe generation:** GPT generates two outputs: `spoken_version` (short, 10–20s) and `screen_summary` (bullets for UI).
- **Mode switching:** Normal vs Quick (Quick for urgency, brevity request, environment keywords); Quick Mode uses stricter recommendation threshold (≥ 0.8).
- **Voice recommendation policy:** confidence-gated (≥ 0.75 speak; 0.55–0.74 category only; < 0.55 silent). One product max per voice answer; always ask permission before sharing link.
- **Eval:** Record `latency_ms_stt`, `latency_ms_tts`, `audio_included` in eval JSONL.

### Ticket A7-STT — MCP config and client for STT
**Owner:** services/agent-api
- Add `stt_base_url` to MCPConfig (env `STT_MCP_URL`, default http://127.0.0.1:8033).
- Add `transcribe(client, base_url, request)` in mcp_client.py; POST to `/mcp/transcribe`; validate response against stt_transcript.schema.json.
- **Tests:** Unit test with mocked HTTP; response shape validated.

### Ticket A7-TTS — MCP config and client for TTS
**Owner:** services/agent-api
- Add `tts_base_url` to MCPConfig (env `TTS_MCP_URL`, default http://127.0.0.1:8034).
- Add `synthesize(client, base_url, request)` in mcp_client.py; POST to `/mcp/synthesize`; validate response against tts_audio.schema.json.
- **Tests:** Unit test with mocked HTTP; response shape validated.

### Ticket A7-V1 — Routing: when to call STT
**Owner:** services/agent-api
- When WS message has `audio_ref` (or `audio`), call STT MCP first; use transcript as user query for rest of pipeline.
- **Tests:** Message with audio_ref → STT called; transcript passed to pipeline; message without audio → STT not called.

### Ticket A7-V2 — Voice-safe answer generation (spoken_version + screen_summary)
**Owner:** services/agent-api
- When voice reply requested: instruct GPT to output `spoken_version` (10–20s, conversational) and `screen_summary` (bullets).
- Use voice mode system prompt (direct answer first, optional suggestion, permission ask before links).
- **Tests:** Mocked pipeline; output contains spoken_version and screen_summary; spoken_version under ~30s equivalent.

### Ticket A7-V3 — Mode switching (Normal vs Quick)
**Owner:** services/agent-api
- Implement mode switching policy: explicit brevity request, urgency keywords, environment keywords, or push-to-talk default → Quick Mode.
- Planning keywords (itinerary, compare, explain) → Normal Mode.
- Quick Mode: stricter threshold (≥ 0.8 for product mention); 8–12s spoken; Normal Mode: ≥ 0.75; 15–30s spoken.
- **Tests:** Urgency query → Quick Mode; planning query → Normal Mode.

### Ticket A7-V4 — Voice recommendation policy
**Owner:** services/agent-api
- Apply confidence-gated policy: Tier 1 (≥ 0.75) → mention 1 product + permission ask; Tier 2 (0.55–0.74) → category hint only; Tier 3 (< 0.55) → no recommendation.
- In Quick Mode, use ≥ 0.8 threshold.
- One product max per voice answer; repetition control (no same product in last 2 turns).
- **Tests:** High confidence → product mentioned + permission ask; low confidence → no product; Quick Mode → stricter gate.

### Ticket A7-V5 — Routing: when to call TTS
**Owner:** services/agent-api
- When voice reply requested and answer built: call TTS with spoken_version; attach audio_ref to response.
- **Tests:** Voice mode response includes audio_ref from TTS; text-only mode does not call TTS.

### Ticket A7-V6 — Eval and metrics for audio
**Owner:** services/agent-api
- Add `latency_ms_stt`, `latency_ms_tts`, `audio_included` to eval runner output and eval_row schema.
- When STT/TTS called, record latencies in eval JSONL.
- **Tests:** Eval runner with mocked STT/TTS writes latency_ms_stt, latency_ms_tts, audio_included; schema validation passes.

---

## 5. Order of work (suggested)

1. **Contracts** — stt_transcript.schema.json, tts_audio.schema.json (done).
2. **S1** — mcp-travel-stt scaffold + mock + contract test.
3. **S2** — STT transcription implementation.
4. **S3** — STT metrics and logging.
5. **T1** — mcp-travel-tts scaffold + mock + contract test.
6. **T2** — TTS synthesis implementation.
7. **T3** — TTS metrics and logging.
8. **A7-STT** — Agent: STT config and client.
9. **A7-TTS** — Agent: TTS config and client.
10. **A7-V1** — Agent: routing (when to call STT).
11. **A7-V2** — Agent: voice-safe generation (spoken_version + screen_summary).
12. **A7-V3** — Agent: mode switching.
13. **A7-V4** — Agent: voice recommendation policy.
14. **A7-V5** — Agent: routing (when to call TTS).
15. **A7-V6** — Agent: eval latency_stt, latency_tts, audio_included.

---

## 6. Acceptance criteria

- [ ] mcp-travel-stt: `/health`, `/metrics`, `POST /mcp/transcribe` return response validating against stt_transcript.schema.json; unit tests with mocked OpenAI.
- [ ] mcp-travel-tts: `/health`, `/metrics`, `POST /mcp/synthesize` return response validating against tts_audio.schema.json; unit tests with mocked OpenAI.
- [ ] Agent: For messages with audio_ref, STT is called; transcript flows to pipeline; when voice reply requested, TTS returns audio_ref; mode switching and voice recommendation policy applied; eval row includes latency_ms_stt, latency_ms_tts, audio_included.
- [ ] make test and make lint pass for agent-api, mcp-travel-stt, mcp-travel-tts.
- [ ] No breaking changes to existing contracts.

---

## 7. Config summary

| Service          | Env / config                                                                 |
|------------------|-------------------------------------------------------------------------------|
| mcp-travel-stt   | OPENAI_API_KEY, STT_MODEL (default gpt-4o-mini-transcribe)                    |
| mcp-travel-tts   | OPENAI_API_KEY, TTS_MODEL (default gpt-4o-mini-tts), TTS_VOICE (default alloy)|
| agent-api        | STT_MCP_URL (e.g. http://127.0.0.1:8033), TTS_MCP_URL (e.g. http://127.0.0.1:8034) |

Port suggestion: **8033** (STT), **8034** (TTS). (knowledge=8010, products=8020, ingestion=8030, graph=8031, vision=8032)

---

## 8. UX rules (from design)

- **Voice personality:** Calm, practical, friendly; never salesy or enthusiastic. Archetype: "smart travel friend who has done this trip before."
- **Structure:** Direct answer first → brief context → optional suggestion → permission ask before links.
- **Recommendations:** One product max per voice answer; use soft suggestion language ("It might help to bring…"); always ask "Want a link?" before sharing.
- **Quick Mode:** 8–12s; direct instruction; no permission ask unless critical; stricter recommendation threshold.
- **Normal Mode:** 15–30s; short explanation; optional suggestion; permission ask.
- **Privacy:** "Audio is processed to text for intent detection; no audio is stored." (README / demo trust signal)
