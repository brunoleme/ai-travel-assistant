Phase 4 — Event-Driven Ingestion (Data Pipeline Foundation)
Goal:Turn ingestion into a reliable, idempotent, event-driven pipeline using AWS primitives.
Scope:
* Internal ingestion contracts (not user-facing)
* Idempotent processing stages
* Queue + DLQ infrastructure
* No heavy optimization yet — correctness first

Tickets:
Ticket I1 — ingestion service boundaries + events
Owner: services/ingestion
* Define internal event types:
    * IngestionRequested
    * TranscriptReady
    * ChunksReady
    * EnrichmentReady
    * EmbeddingsReady
    * WriteComplete
* Define idempotency key strategy:
    * content_source_id + stage_name
* Implement pipeline stages:
    * fetch → transcript → chunk → enrich → embed → write
* Each stage:
    * consumes one event type
    * emits the next event type
    * is safe to run twice (idempotent writes)
Tests:
* same event processed twice does not duplicate DB/vector writes
* stage failure emits error metadata and does not advance pipeline

Ticket I2 — DLQ handling and retry policy
Owner: services/ingestion
* Add retry counter in event metadata
* After N retries:
    * move event to DLQ
    * store failure reason
* Add simple DLQ reprocessor script (manual replay tool)
Tests:
* failing stage retries N times
* after N failures, event is routed to DLQ
* DLQ replay re-enqueues event correctly

Ticket T1 — Terraform EDA resources
Owner: infra/terraform
* S3 buckets:
    * raw ingestion artifacts
    * processed artifacts
* SQS:
    * main ingestion queue
    * dead-letter queue (DLQ)
* IAM roles/policies:
    * least privilege for ingestion workers
* Terraform outputs:
    * bucket names
    * queue URLs / ARNs
Acceptance:
* terraform validate passes
* outputs can be injected into services via env vars

Acceptance criteria:
* ingestion pipeline runs end-to-end locally with mocked AWS
* idempotency guaranteed by tests
* DLQ behavior verified by tests
* infrastructure defined and validated via Terraform
