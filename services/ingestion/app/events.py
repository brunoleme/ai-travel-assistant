"""
Internal event contracts for the ingestion pipeline.

All events are immutable; each stage consumes one type and emits the next.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestionEventBase(BaseModel):
    """Base fields for every pipeline event."""

    event_id: str
    content_source_id: str
    stage: str
    payload: dict = Field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    error: str | None = None


class IngestionRequested(IngestionEventBase):
    """Trigger: ingestion requested for a content source."""

    stage: str = "requested"


class TranscriptReady(IngestionEventBase):
    """Fetched transcript is ready for chunking."""

    stage: str = "transcript"


class ChunksReady(IngestionEventBase):
    """Text has been chunked; ready for enrichment."""

    stage: str = "chunks"


class EnrichmentReady(IngestionEventBase):
    """Chunks enriched; ready for embedding."""

    stage: str = "enrichment"


class EmbeddingsReady(IngestionEventBase):
    """Embeddings computed; ready to write to vector store."""

    stage: str = "embeddings"


class WriteComplete(IngestionEventBase):
    """Write to vector store completed; pipeline done for this source."""

    stage: str = "write_complete"


_STAGE_MODEL: dict[str, type[IngestionEventBase]] = {
    "requested": IngestionRequested,
    "transcript": TranscriptReady,
    "chunks": ChunksReady,
    "enrichment": EnrichmentReady,
    "embeddings": EmbeddingsReady,
    "write_complete": WriteComplete,
}


def event_from_dict(d: dict) -> IngestionEventBase:
    """Build the correct event model from a dict (e.g. SQS message body)."""
    stage = d.get("stage", "requested")
    model = _STAGE_MODEL.get(stage, IngestionRequested)
    return model.model_validate(d)
