"""Contract and request/response models for travel_evidence.schema.json."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class TravelEvidenceRequest(BaseModel):
    """Request payload nested inside the main request."""
    user_query: str = Field(min_length=1)
    destination: Optional[str] = None
    lang: Optional[str] = None
    debug: bool = False
    strategy_params: Optional[dict[str, Any]] = None


class RetrieveTravelEvidencePayload(BaseModel):
    """Top-level request payload matching contract schema."""
    x_contract_version: str = Field(default="1.0")
    request: TravelEvidenceRequest


class EvidenceScore(BaseModel):
    """Score object for evidence items."""
    distance: Optional[float] = None
    freshness_penalty: Optional[float] = None
    adjusted: Optional[float] = None


class EvidenceRerank(BaseModel):
    """Rerank object for evidence items."""
    rank: int = Field(ge=1)
    reason: str


class TravelEvidenceCard(BaseModel):
    """Evidence item matching contract schema."""
    card_id: str = Field(min_length=8)
    summary: str = Field(min_length=10)
    signals: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    primary_category: str = "other"
    confidence: float = Field(ge=0.0, le=1.0)
    source_url: str = Field(min_length=8)
    video_upload_date: Optional[str] = None
    score: Optional[EvidenceScore] = None
    seen_in_queries: Optional[list[str]] = None
    rerank: Optional[EvidenceRerank] = None


class RetrieveTravelEvidenceResponse(BaseModel):
    """Response matching contract schema."""
    x_contract_version: str = "1.0"
    request: TravelEvidenceRequest
    expanded_queries: Optional[list[str]] = None
    evidence: list[TravelEvidenceCard] = Field(default_factory=list)
    debug: Optional[dict[str, Any]] = None
