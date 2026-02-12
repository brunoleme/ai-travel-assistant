# Contracts

This folder contains versioned, service-agnostic schemas that define the data exchanged between:
- Agent runtime (FastAPI/WebSockets)
- MCP servers (travel-knowledge, travel-products, travel-vision, travel-graph)
- Ingestion pipeline
- Feedback pipeline
- Evaluation harness

Rules:
1) Services MUST NOT change payload shapes without updating schemas here.
2) Service responses MUST validate against these schemas (at least in tests).
3) Breaking changes require bumping `x-contract-version` in the schema and updating all consumers.

Recommended:
- Keep schemas JSON Schema Draft 2020-12.
- Validate at boundaries: API input/output, MCP tool input/output, ingestion events.