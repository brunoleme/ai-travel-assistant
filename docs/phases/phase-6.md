Phase 6 — Deployment & Productionization
Goal:Run the system reliably outside local dev: first on EC2, later on EKS.
Scope:
* Harden MCPs for real-world dependencies
* Define EC2 deployment baseline
* Prepare migration path to Kubernetes
Tickets:
Ticket K3/P3 — MCP hardening for production
Owners: services/mcp-travel-knowledge, services/mcp-travel-products
* Enforce strict request schema validation at boundary
* Add configurable timeouts for downstream dependencies
* Ensure graceful fallback returns valid contract response
* Extend /health to optionally report dependency health (non-fatal)
Tests:
* invalid request schema → 422
* dependency timeout → valid fallback response
* logs include fallback + correlation fields

Ticket D1 — EC2 deployment baseline
Owner: infra + services
* Dockerfiles for:
    * agent-api
    * mcp-travel-knowledge
    * mcp-travel-products
* docker-compose:
    * agent
    * MCPs
    * weaviate
* Logging strategy:
    * stdout JSON logs (CloudWatch agent friendly)
Acceptance:
* full system runs on single EC2 instance
* services restart cleanly after reboot

Ticket D2 — EKS migration plan
Owner: infra
* Define Kubernetes manifests or Helm charts
* Service definitions + internal networking
* ConfigMaps and Secrets for env vars
* Document differences between EC2 and EKS setups
Acceptance:
* manifests apply successfully to a test cluster
* migration path documented

Acceptance criteria:
* system deployable on EC2 with docker-compose
* MCPs resilient to dependency failures
* clear path defined for EKS migration