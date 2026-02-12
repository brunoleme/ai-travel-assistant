# Phase 9 — Deployment & Productionization

**Goal:** Run the system reliably outside local dev: first on EC2, later on EKS.

**Scope:**
- Harden all MCPs for real-world dependencies
- Define EC2 deployment baseline (all services + Weaviate + Neo4j)
- Prepare migration path to Kubernetes

**Reference:** Phase 1–3 (skeleton, caching, eval), Phase 4 (ingestion), Phase 5 (graph MCP), Phase 6 (vision MCP), Phase 7 (audio MCPs).

---

## 1. Tickets

### Ticket K3/P3 — MCP hardening for production
**Owners:** services/mcp-travel-knowledge, services/mcp-travel-products, services/mcp-travel-graph, services/mcp-travel-vision, services/mcp-travel-stt, services/mcp-travel-tts
- Enforce strict request schema validation at boundary
- Add configurable timeouts for downstream dependencies (OpenAI, Weaviate, Neo4j as applicable)
- Ensure graceful fallback returns valid contract response
- Extend /health to optionally report dependency health (non-fatal)

**Tests:**
- invalid request schema → 422
- dependency timeout → valid fallback response
- logs include fallback + correlation fields

---

### Ticket D1 — EC2 deployment baseline
**Owner:** infra + services
- Dockerfiles for:
  - agent-api
  - mcp-travel-knowledge
  - mcp-travel-products
  - mcp-travel-graph
  - mcp-travel-vision
  - mcp-travel-stt
  - mcp-travel-tts
  - ingestion (optional; can run as separate worker)
- docker-compose:
  - agent
  - all MCPs (knowledge, products, graph, vision, stt, tts)
  - weaviate
  - neo4j
  - ingestion worker (optional)
- Logging strategy:
  - stdout JSON logs (CloudWatch agent friendly)
- Port allocation:
  - knowledge=8010, products=8020, ingestion=8030, graph=8031, vision=8032, stt=8033, tts=8034

**Acceptance:**
- full system runs on single EC2 instance (or multi-node if desired)
- services restart cleanly after reboot
- all MCP URLs correctly wired in agent config

---

### Ticket D2 — EKS migration plan
**Owner:** infra
- Define Kubernetes manifests or Helm charts
- Service definitions for:
  - agent-api
  - mcp-travel-knowledge
  - mcp-travel-products
  - mcp-travel-graph
  - mcp-travel-vision
  - mcp-travel-stt
  - mcp-travel-tts
  - ingestion worker
- Internal networking (cluster IPs, service discovery)
- ConfigMaps and Secrets for env vars (OPENAI_API_KEY, NEO4J_*, WEAVIATE_*, MCP URLs, etc.)
- Document differences between EC2 and EKS setups

**Acceptance:**
- manifests apply successfully to a test cluster
- migration path documented
- all services discoverable and routable

---

## 2. Acceptance criteria

- [ ] All MCPs (knowledge, products, graph, vision, stt, tts) resilient to dependency failures; invalid request → 422; timeout → valid fallback
- [ ] System deployable on EC2 with docker-compose (agent + all MCPs + Weaviate + Neo4j)
- [ ] Dockerfiles exist for agent-api and all seven MCPs (plus ingestion if used)
- [ ] Clear path defined for EKS migration with manifests for all services
- [ ] make test and make lint pass for all services after deployment validation
