"""Adapter: Weaviate RecommendationCard → Contract EvidenceItem."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def weaviate_card_to_evidence(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Map a single Weaviate RecommendationCard object to contract EvidenceItem.

    Mapping:
      uuid (object uuid) → card_id
      timestampUrl → source_url
      primaryCategory → primary_category
      videoUploadDate → video_upload_date (string ISO/RFC3339; formatted if needed)
      summary, signals, places, categories, confidence → direct
    """
    uuid_val = raw.get("uuid")
    if uuid_val is None:
        raise ValueError("Weaviate card must have 'uuid'")
    card_id = str(uuid_val)

    timestamp_url = raw.get("timestampUrl")
    if timestamp_url is None:
        raise ValueError("Weaviate card must have 'timestampUrl' for source_url")
    source_url = str(timestamp_url)

    video_upload = raw.get("videoUploadDate")
    video_upload_date: str | None = None
    if video_upload is not None:
        if isinstance(video_upload, datetime):
            video_upload_date = video_upload.isoformat()
        else:
            video_upload_date = str(video_upload)

    return {
        "card_id": card_id,
        "summary": raw.get("summary", ""),
        "signals": raw.get("signals") or [],
        "places": raw.get("places") or [],
        "categories": raw.get("categories") or [],
        "primary_category": raw.get("primaryCategory", "other"),
        "confidence": float(raw.get("confidence", 0.0)),
        "source_url": source_url,
        "video_upload_date": video_upload_date,
    }
