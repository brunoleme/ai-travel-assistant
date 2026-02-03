🧭 AI Travel Assistant Platform

A production-oriented Agentic RAG system that combines:

- Conversational travel planning
- Retrieval-augmented knowledge
- Context-aware product recommendations
- Continuous evaluation and feedback

This project is designed as a real AI system architecture, not just a demo notebook. It demonstrates how to build modular, testable, and scalable AI applications using an agent runtime plus capability services.

✨ What This System Does

The AI Travel Assistant can:

- Answer travel planning questions using retrieved evidence
- Cite sources to reduce hallucinations
- Understand context within a conversation
- Offer relevant travel products only when appropriate
- Learn from feedback and evaluation loops

Example topics:

- Best time to visit a destination
- How to avoid long lines at theme parks
- Where to stay on a budget
- Whether to rent a car or use ride-sharing
- What to book in advance

🧠 Architecture Overview

The system is divided into three layers:

1️⃣ Agent Runtime (Reasoning Layer)

Located in agentic-chatbot/
- FastAPI + WebSockets conversational service
- Orchestrates calls to MCP capability servers
- Generates grounded answers
- Applies guardrails
- Decides whether to include a product suggestion

2️⃣ MCP Capability Servers (Retrieval Layer)

Located in mcp-servers/

These are independent services that the agent calls via tool-like interfaces.

Travel Knowledge MCP

- Query expansion
- Vector retrieval (Weaviate)
- Deduplication + scoring
- Freshness adjustments
- Evidence pack output

Travel Products MCP

- Product candidate retrieval
- Intent-based filtering
- Lightweight ranking
- Supports conservative monetization logic

3️⃣ Data Layer (Ingestion + Storage)

Located in rag-ingestion-pipeline/

- Event-driven ingestion pipeline
- Processes travel content into structured “recommendation cards”
- Generates embeddings
- Stores data in Weaviate

This pipeline is separate from the runtime, keeping data processing decoupled from live user requests.

Supporting Systems
| Component     | Purpose                                     |
| ------------- | ------------------------------------------- |
| `contracts/`  | Shared schemas between services             |
| `eval/`       | Evaluation harness for regression testing   |
| `infra/`      | Infrastructure as code (AWS)                |
| Feedback loop | Captures ratings, clicks, and usage signals |
| Observability | Logs, tracing, guardrails                   |

🛠 Tech Stack

- Python
- FastAPI (WebSockets for chat)
- Weaviate (vector database)
- OpenAI models (reasoning + reranking)
- uv (Python package manager)
- Make (task automation)
- AWS (EC2 → EKS)
- Event-Driven Architecture for ingestion

📦 Repository Structure
```
contracts/                Shared API + MCP schemas
agentic-chatbot/          FastAPI WebSocket agent runtime
mcp-servers/
  travel-knowledge/       Travel retrieval MCP server
  travel-products/        Product recommendation MCP server
rag-ingestion-pipeline/   Event-driven RAG ingestion
eval/                     Evaluation harness
infra/                    AWS infrastructure
docs/                     Architecture & implementation plans
```
Each service is independently testable and deployable.

🧪 Engineering Principles

This project follows:

✅ Test-Driven Development (TDD)

- Tests are written before implementation
- External services (OpenAI, Weaviate) are mocked in unit tests

✅ Clear Service Boundaries

Each folder represents a logical service with its own dependencies.

✅ Make as the Single Interface

All common commands are run through make:
```
make bootstrap
make test
make run-chatbot
make run-mcp-knowledge
make run-mcp-products
```

✅ uv for Dependency Management

Each service has its own pyproject.toml managed with uv.

📊 Evaluation & Feedback

The system includes:

- Eval harness to replay test queries and detect regressions
- Groundedness checks (answers must match retrieved sources)
- Citation validation
- Product recommendation rate tracking
- Feedback loop capturing ratings and link clicks

This ensures the assistant improves over time and monetization stays user-friendly.

🚀 Deployment Plan
| Phase  | Environment            |
| ------ | ---------------------- |
| Early  | Local + EC2            |
| Later  | Kubernetes (EKS)       |
| Future | Scalable microservices |


🎯 Goal of This Project

To demonstrate how to design and operate an Agentic RAG system with:

- Clear separation of reasoning and retrieval
-  Controlled monetization
- Continuous evaluation
- Production-style modular architecture

This repository serves as both:

- A functional travel assistant prototype
- A reference architecture for AI product systems

If you're contributing, start by reading: