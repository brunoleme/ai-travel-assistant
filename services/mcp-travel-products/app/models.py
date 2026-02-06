"""Contract and request/response models for product_candidates.schema.json."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProductRequest(BaseModel):
    """Request parameters for product retrieval."""
    query_signature: str = Field(min_length=1)
    destination: Optional[str] = None
    market: Optional[str] = None
    lang: Optional[str] = None
    limit: Optional[int] = Field(default=None, ge=1)
    min_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ProductScore(BaseModel):
    """Score object for product candidate."""
    distance: Optional[float] = None
    rank: Optional[int] = None


class ProductCandidate(BaseModel):
    """Product candidate matching contracts/product_candidates.schema.json."""
    product_id: str = Field(min_length=8)
    summary: str = Field(min_length=10)
    merchant: str
    link: str = Field(min_length=8)
    categories: list[str]
    primary_category: Optional[str] = None
    triggers: Optional[list[str]] = None
    constraints: Optional[list[str]] = None
    affiliate_priority: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    user_value: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    score: Optional[ProductScore] = None


class ProductCandidatesRequest(BaseModel):
    """Request payload matching contracts/product_candidates.schema.json."""
    x_contract_version: str = Field(default="1.0")
    request: ProductRequest


class ProductCandidatesResponse(BaseModel):
    """Response matching contracts/product_candidates.schema.json."""
    x_contract_version: str = Field(default="1.0")
    request: ProductRequest
    candidates: list[ProductCandidate] = Field(default_factory=list)
