# Ownership & Boundaries

This project uses explicit ownership to enable safe multi-agent development in Cursor.

## Why ownership exists
- Prevents parallel agents from editing the same code.
- Forces cross-service coordination through contracts, not ad-hoc edits.
- Makes CI/Make targets the source of truth for "done".

## Folder ownership (source of truth)

### contracts/
Owner: Human (you)
- Only changed intentionally (schema versioning).
- Any change here may be breaking.

### services/agent-api/
Owner: Agent: Agent Runtime
- FastAPI + WebSocket API
- Session handling, memory wiring, response formatting
- Calls MCP servers via client adapters (knowledge, products, graph, vision, stt, tts)
- Routing logic for when to call each MCP
- NEVER implements retrieval logic itself

### services/mcp-travel-knowledge/
Owner: Agent: Travel Knowledge MCP
- Retrieval pipeline for travel evidence
- Query expansions, merge/dedupe, freshness scoring, rerank (optional)
- Caching of evidence packs
- Output MUST validate `contracts/travel_evidence.schema.json`

### services/mcp-travel-products/
Owner: Agent: Travel Products MCP
- Product retrieval + ranking + conservative selection policy
- Caching of product candidates
- Output MUST validate `contracts/product_candidates.schema.json`

### services/mcp-travel-graph/
Owner: Agent: Travel Graph MCP
- Neo4j queries for itinerary / routes / day-order
- Subgraph + paths + evidence for answer building
- Output MUST validate `contracts/graph_rag.schema.json`

### services/mcp-travel-vision/
Owner: Agent: Travel Vision MCP
- Image analysis (packing, landmark, product_similarity modes)
- Output MUST validate `contracts/vision_signals.schema.json`

### services/mcp-travel-stt/
Owner: Agent: Travel STT MCP
- Speech-to-text (audio → transcript)
- Output MUST validate `contracts/stt_transcript.schema.json`

### services/mcp-travel-tts/
Owner: Agent: Travel TTS MCP
- Text-to-speech (text → audio)
- Output MUST validate `contracts/tts_audio.schema.json`

### services/ingestion/
Owner: Agent: Ingestion Pipeline
- Event-driven ingestion (EDA): fetch -> chunk -> enrich -> embed -> write to Weaviate or Neo4j
- YouTube, products, and youtube_kg (graph) source types
- Produces ingestion metrics and DLQ handling
- MUST NOT contain agent runtime code

### infra/terraform/
Owner: Agent: Infra
- Terraform only
- Provides AWS resources for EDA ingestion + deployment (ECR/EC2/EKS/etc.)

### webapp/ui/
Owner: Agent: Frontend (later)
- React UI
- WebSocket client + feedback UI
- No backend logic

## Definition of done (global)
A change is "done" only if:
- Contract outputs still validate (where applicable)
- Unit tests exist (TDD) and pass
- `make lint` and `make test` pass for the touched service
- No edits outside the agent's owned folders
