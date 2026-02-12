"""Contract and request/response models for vision_signals.schema.json."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

VisionMode = Literal["packing", "landmark", "product_similarity"]

# 18-item travel category set (reference from phase-6)
TRAVEL_ITEM_CATEGORIES = frozenset({
    "light_top", "warm_top", "insulated_jacket", "rain_jacket",
    "long_pants", "shorts_or_skirt", "walking_shoes", "sandals",
    "weather_proof_shoes", "sun_protection", "cold_accessory",
    "umbrella", "day_bag", "travel_bag_organizer", "power_adapter",
    "portable_charger", "water_bottle", "travel_comfort_item",
})

# Scene types for landmark mode
SCENE_TYPES = frozenset({
    "landmark", "street", "beach", "mountain", "museum",
    "airport", "restaurant", "hotel", "transit", "urban", "nature",
})


class VisionAnalyzeRequest(BaseModel):
    """Request payload nested inside the main request (matches contract)."""
    image_ref: str = Field(min_length=1, description="Image as data URL or HTTP(S) URL")
    mode: VisionMode = Field(..., description="packing | landmark | product_similarity")
    trip_context: Optional[dict[str, Any]] = None
    user_query: Optional[str] = None
    lang: Optional[str] = None
    debug: bool = False


class AnalyzeImagePayload(BaseModel):
    """Top-level request payload matching contract schema."""
    x_contract_version: str = Field(default="1.0")
    request: VisionAnalyzeRequest


class PlaceCandidate(BaseModel):
    """Landmark mode: one place candidate."""
    place_name: str = Field(min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    reason: Optional[str] = None


class VisionSignals(BaseModel):
    """Structured signals from vision analysis; mode-specific fields optional."""
    mode: VisionMode = Field(..., description="packing | landmark | product_similarity")
    confidence: float = Field(ge=0.0, le=1.0)
    error: Optional[str] = None
    # Packing / outfit
    detected_items: Optional[list[str]] = None
    missing_categories: Optional[list[str]] = None
    suitability_ok: Optional[bool] = None
    suitability_issue: Optional[str] = None
    suggested_categories_for_products: Optional[list[str]] = None
    # Landmark
    scene_type: Optional[str] = None
    ocr_text: Optional[list[str]] = None
    distinctive_features: Optional[list[str]] = None
    language_hint: Optional[str] = None
    place_candidates: Optional[list[PlaceCandidate]] = None
    # Product_similarity
    category: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None
    style_keywords: Optional[list[str]] = None
    search_queries: Optional[list[str]] = None


class AnalyzeImageResponse(BaseModel):
    """Response matching contract schema."""
    x_contract_version: str = "1.0"
    request: VisionAnalyzeRequest
    signals: VisionSignals
    debug: Optional[dict[str, Any]] = None
