Vision

Build a production-ready AI Travel Assistant platform that combines:

- Conversational planning
- Retrieval-augmented travel knowledge
- Contextual product recommendations
- Continuous evaluation and feedback

The system should behave like a real-world AI product, not a demo:

It must be:

- Grounded in trusted travel sources
- Context-aware across a conversation
- Careful with monetization (helpful, not spammy)
- Measurable and improvable through feedback and evaluation
- Modular and scalable, so new capabilities can be added without breaking the system

This project demonstrates how to design and operate an agentic RAG system with clear separation between:

- Agent runtime (reasoning layer)
- Retrieval & recommendation services (capability layer via MCP)
- Data ingestion and knowledge pipelines (data layer)

The end goal is not just answering travel questions, but showing how to build an AI product architecture that is testable, extensible, and production-oriented.

Problem Statement

Travel planning involves many decisions:

- When to go
- Where to stay
- How to move
- What to book in advance
- How to save money
- What to avoid

Users often search across blogs, videos, forums, and booking sites. Information is:

- Fragmented
- Sometimes outdated
- Hard to personalize

At the same time, travel marketplaces struggle to present relevant offers at the right moment in the user journey.

This system solves both sides by:

1. Using retrieval-augmented generation (RAG) to provide grounded, practical travel guidance
2. Detecting user intent and context to offer only highly relevant travel-related products or services
3. Ensuring monetization is controlled and evaluated, not intrusive

Scope
In Scope
1️⃣ Conversational Travel Assistant (Agent Runtime)

A FastAPI + WebSocket based chat service that:

- Receives user questions
- Maintains conversational context
- Calls external capabilities (MCP servers)
- Produces grounded answers with citations
- Optionally includes a relevant product suggestion

2️⃣ Travel Knowledge Retrieval (MCP Server)

A capability service responsible for:

- Query expansion
- Vector retrieval from Weaviate
- Deduplication and scoring
- Freshness adjustments
- Optional lightweight reranking

Returning a structured evidence pack with traceability and sources

This service abstracts all retrieval complexity away from the agent.

3️⃣ Travel Product Recommendation (MCP Server)

A capability service that:

- Retrieves candidate travel-related products
- Applies intent-based filtering
- Ranks candidates by usefulness
- Supports a conservative decision policy to avoid over-recommending

The agent remains in control of whether to show a product.

4️⃣ RAG Ingestion Pipeline (Event-Driven)

A separate pipeline that:

- Processes raw travel content (e.g., transcripts, articles)
- Cleans and structures it into “recommendation cards”
- Generates embeddings
- Stores them in Weaviate
- Runs asynchronously via an event-driven architecture

This keeps data processing separate from runtime reasoning.

5️⃣ Feedback Loop

The system will include a feedback mechanism that captures:

- User question
- Assistant answer
- Sources used
- Product shown (if any)
- User rating and link clicks

This enables future:

- Model and retrieval tuning
- Monetization quality control
- Evaluation of answer usefulness

6️⃣ Evaluation Harness

An automated evaluation pipeline that:

- Replays predefined travel queries
- Measures answer groundedness
- Validates citation correctness
- Tracks product recommendation rate and relevance
- Detects regressions over time

This treats the AI assistant as a continuously tested system, not a static demo.

7️⃣ Observability and Guardrails

The system will include:

- Structured logs
- Tracing of MCP calls
- Guardrails that prevent hallucinated policies, prices, or rules
- Validation that answers are grounded in retrieved evidence

Out of Scope (for now)

To keep the project focused, the following are not included in early phases:

- Real-time booking integrations (payments, reservations)
- Personal user accounts and authentication
- Full UI polish (React app can be basic)
- Large-scale multi-region infrastructure
- Advanced personalization models beyond simple memory summaries

These can be added later once the core architecture is stable.

Success Criteria

- The system is considered successful when:
- The assistant answers travel questions using retrieved evidence with citations
- Product suggestions appear only when clearly relevant
- Feedback and evaluation data are being collected
- The system can be deployed as separate services (agent + MCP servers)
- Changes to retrieval or prompts can be tested using the evaluation harness

🧠 PROJECT STRUCTURE

You are building four parallel tracks:

Track	Purpose	Repo / Folder
Agent Runtime	WebSocket chat + orchestration	agentic-chatbot/
MCP Capability Servers	Retrieval & product intelligence	mcp-servers/
RAG Ingestion Platform	Event-driven pipeline → Weaviate	rag-ingestion-pipeline/
Infra & DevOps	AWS, CI/CD, EKS, Observability	infra/

Each phase activates work across these tracks.

🚀 PHASE 1 — Core RAG + Chat + Feedback (MVP)
🎯 Goal

Working AI travel assistant:

- retrieves evidence
- answers with citations
- optionally suggests product
- captures user feedback

1️⃣ Agent Runtime (agentic-chatbot)

Agents to assign in Cursor

- chat-backend-engineer
- protocol-designer
- feedback-engineer

Deliverables

- FastAPI + WebSocket server
- Session + turn IDs
- Chat pipeline orchestration
- Final answer generation
- /feedback endpoint (or WS event)
- Logs for each turn

Tests

- WebSocket connection lifecycle
- One user message → one response
- Answer always contains citations when claims made
- Feedback request stored correctly

2️⃣ MCP Servers (mcp-servers)

Agents

- mcp-travel-knowledge-engineer
- mcp-product-engineer

Deliverables

mcp-travel-knowledge
Tool: retrieve_travel_evidence

- Query expansion
- Weaviate retrieval
- Quota merge
- Freshness scoring
- Light rerank
- Returns evidence pack

mcp-travel-products
Tool: retrieve_product_candidates

- Vector search in ProductCard
- Basic rerank
- Returns candidates

Tests

- Tool schema validation
- Deterministic ranking with fixed seed
- Evidence always includes source URL
- Product candidates include required fields

3️⃣ Feedback Loop

Agent: feedback-engineer

Deliverables

- Feedback schema
- Storage (S3 JSONL or DB)
- Logging per turn

Tests

- Feedback payload validation
- One call → one stored record

✅ Phase 1 Done When

You can demo:

- Chat → answer with citations
- Product suggestion appears only when relevant
- Feedback stored and linked to turn

🧠 PHASE 2 — Memory + Caching + Guardrails
🎯 Goal
Cheaper, safer, consistent behavior across turns.

1️⃣ Memory (Agent Runtime)

Agent: memory-engineer

Deliverables

- Session memory store
- Memory summarizer
- Inject memory into answer + need hint prompts

Tests

- Memory updates per turn
- Summary bounded in size
- Memory influences future answers

2️⃣ Caching (MCP Layer)

Agent: mcp-performance-engineer

Deliverables

- Cache layer in mcp-travel-knowledge
- Cache layer in mcp-travel-products
- Cache key versioning

Tests

- Repeated query hits cache
- Version bump invalidates cache

3️⃣ Guardrails

Agent: safety-engineer

Deliverables

- Final answer validator (no hallucinated policies)
- Product insertion validator
- Tool output schema validation

Tests

- Invalid answer blocked
- Irrelevant product blocked
- Missing citation blocked

✅ Phase 2 Done When

- Memory influences responses
- Cost per turn reduced via cache
- Guardrail interventions logged

☁️ PHASE 3 — Infra + Event-Driven Ingestion + Observability
🎯 Goal

Production-ready data pipeline + deployment + tracing.

1️⃣ RAG Ingestion Platform (rag-ingestion-pipeline)

Agents

- data-pipeline-engineer
- llm-enrichment-engineer
- weaviate-loader-engineer

Deliverables

- Event-driven ingestion workflow
- Chunking service
- Card enrichment service
- Product ingestion pipeline
- S3 artifact storage

Tests

- Each stage produces artifact
- Retry logic works
- Failed events go to DLQ

2️⃣ Infra (infra)

Agent: cloud-infra-engineer

Deliverables

- S3 buckets
- EventBridge / SQS / Step Functions
- IAM roles
- EC2 deployment stack
- EKS deployment manifests

Tests

- Infra plan applies without error
- Services reachable
- Secrets not hardcoded

3️⃣ Observability (with LangSmith)

Agent: observability-engineer

Deliverables

- LangSmith tracing in agent runtime
- MCP tool run traces
- Ingestion pipeline traces
- Structured logs + metrics

Tests

- Each turn creates LangSmith trace
- Tool calls visible
- Dataset version tagged

✅ Phase 3 Done When

- Ingestion runs fully via events
- System deployable on EC2
- Traces visible in LangSmith

🔁 PHASE 4 — CI/CD + Eval Harness + Safe Releases
🎯 Goal

Prevent regressions. Operate system continuously.

1️⃣ CI/CD

Agent: devops-engineer

- Deliverables
- GitHub Actions pipelines
- Build + test + docker publish
- Staging + prod workflows

2️⃣ Eval Harness

Agent: eval-engineer

Deliverables

- Nightly test run on TEST_QUERIES
- Groundedness scoring (LLM judge)
- Citation validation
- Product relevance scoring
- Latency + cost metrics
- Regression thresholds

3️⃣ Release Engineering

Agent: release-engineer

Deliverables

- Canary deployment support
- Rollback mechanism
- Version tagging

✅ Phase 4 Done When

- Nightly eval runs automatically
- Regression triggers alerts/fails
- Deployments reproducible and safe


Who edits what (the exact mapping)


| Agent name (you create in Cursor) | Owns folder                             | Can edit                           | Must not edit                          |
| --------------------------------- | --------------------------------------- | ---------------------------------- | -------------------------------------- |
| `contracts-agent`                 | `contracts/`                            | schemas + shared interfaces        | anything outside `contracts/`          |
| `agent-runtime-agent`             | `agentic-chatbot/`                      | FastAPI + websockets orchestration | MCP server code, ingestion, infra      |
| `mcp-knowledge-agent`             | `mcp-servers/travel-knowledge/`         | travel evidence tool               | chatbot, products MCP, infra           |
| `mcp-products-agent`              | `mcp-servers/travel-products/`          | product retrieval tool             | chatbot, knowledge MCP, infra          |
| `feedback-agent`                  | `agentic-chatbot/feedback/` (subfolder) | feedback endpoints + storage       | other chatbot modules unless requested |
| `eval-agent`                      | `eval/`                                 | eval harness                       | everything else                        |
| `infra-agent`                     | `infra/`                                | Terraform/CDK, deploy scripts      | application code                       |
| `ingestion-agent`                 | `rag-ingestion-pipeline/`               | event-driven ingestion             | chatbot + MCP servers                  |




