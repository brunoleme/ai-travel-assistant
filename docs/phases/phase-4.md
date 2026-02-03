# Phase 4 — Event-Driven Ingestion + MCP Productionization + Deployment Path (EC2 -> EKS)

Goal:
Formalize ingestion as a subproject using AWS EDA, then deploy services first to EC2 and later EKS.

Tickets:

## Ticket I1 — ingestion service boundaries + events
Owner: services/ingestion
- Define ingestion event types (internal) and idempotency keys
- Pipeline stages:
  fetch -> transcript -> chunk -> enrich -> embed -> write
Tests:
- idempotency: same event processed twice does not duplicate writes
- DLQ routing on failure

## Ticket T1 — Terraform EDA resources
Owner: infra/terraform
- S3 for raw artifacts
- SQS for ingestion queue + DLQ
- IAM roles/policies
- (Optional) Lambda for lightweight steps, or ECS task pattern
Acceptance:
- terraform validate passes
- outputs expose queue URLs + bucket names

## Ticket K3/P3 — MCP servers hardened for prod
Owners: mcp-travel-knowledge / mcp-travel-products
- Strict contract validation at boundaries
- Caching + metrics + timeouts
- Config via env vars
Tests:
- schema validation enforced
- timeouts handled gracefully

## Ticket D1 — deployment path
Owner: infra/terraform + services
- EC2: docker compose or systemd services (minimal)
- Later: EKS manifests/Helm (phase 4 end)
Acceptance:
- can run on a single EC2 instance reliably
- migration plan to EKS documented
