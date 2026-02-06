"""Unit tests for Weaviate RecommendationCard → Contract EvidenceItem adapter (no network)."""

from __future__ import annotations

import pytest

from app.adapter import weaviate_card_to_evidence


# Fixture: raw Weaviate RecommendationCard object (uuid + properties as flat dict)
@pytest.fixture
def weaviate_card_minimal() -> dict:
    """Minimal card with only required fields for EvidenceItem."""
    return {
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "summary": "Best times to visit are early morning or late evening to avoid crowds.",
        "signals": ["crowd_avoidance", "timing_tips"],
        "places": ["Orlando", "Magic Kingdom"],
        "categories": ["tips", "crowd_management"],
        "primaryCategory": "tips",
        "confidence": 0.85,
        "timestampUrl": "https://example.com/watch?v=abc123",
    }


@pytest.fixture
def weaviate_card_full() -> dict:
    """Full card including videoUploadDate (ISO string)."""
    return {
        "uuid": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        "summary": "Use FastPass+ by booking high-demand attractions first thing in the morning.",
        "signals": ["fastpass", "planning"],
        "places": ["Orlando", "Disney World"],
        "categories": ["strategy", "fastpass"],
        "primaryCategory": "strategy",
        "confidence": 0.78,
        "timestampUrl": "https://youtube.com/watch?v=xyz&t=120",
        "videoUploadDate": "2024-02-20T14:15:00Z",
    }


def test_adapter_maps_uuid_to_card_id(weaviate_card_minimal: dict) -> None:
    """Weaviate uuid (object uuid) maps to contract card_id."""
    out = weaviate_card_to_evidence(weaviate_card_minimal)
    assert out["card_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert len(out["card_id"]) >= 8


def test_adapter_maps_timestamp_url_to_source_url(weaviate_card_minimal: dict) -> None:
    """Weaviate timestampUrl maps to contract source_url."""
    out = weaviate_card_to_evidence(weaviate_card_minimal)
    assert out["source_url"] == "https://example.com/watch?v=abc123"
    assert len(out["source_url"]) >= 8


def test_adapter_maps_primary_category_to_snake(weaviate_card_minimal: dict) -> None:
    """Weaviate primaryCategory maps to contract primary_category."""
    out = weaviate_card_to_evidence(weaviate_card_minimal)
    assert out["primary_category"] == "tips"
    assert "primaryCategory" not in out


def test_adapter_maps_video_upload_date(weaviate_card_full: dict) -> None:
    """Weaviate videoUploadDate maps to contract video_upload_date (string ISO/RFC3339)."""
    out = weaviate_card_to_evidence(weaviate_card_full)
    assert out["video_upload_date"] == "2024-02-20T14:15:00Z"
    assert "videoUploadDate" not in out


def test_adapter_direct_fields_unchanged(weaviate_card_minimal: dict) -> None:
    """summary, signals, places, categories, confidence map directly."""
    out = weaviate_card_to_evidence(weaviate_card_minimal)
    assert out["summary"] == weaviate_card_minimal["summary"]
    assert out["signals"] == weaviate_card_minimal["signals"]
    assert out["places"] == weaviate_card_minimal["places"]
    assert out["categories"] == weaviate_card_minimal["categories"]
    assert out["confidence"] == weaviate_card_minimal["confidence"]


def test_adapter_minimal_has_no_video_upload_date(weaviate_card_minimal: dict) -> None:
    """When videoUploadDate is absent, contract video_upload_date is None."""
    out = weaviate_card_to_evidence(weaviate_card_minimal)
    assert out.get("video_upload_date") is None


def test_adapter_output_has_required_contract_fields(weaviate_card_minimal: dict) -> None:
    """Output includes all required EvidenceItem fields: card_id, summary, signals, places, categories, primary_category, confidence, source_url."""
    out = weaviate_card_to_evidence(weaviate_card_minimal)
    required = ["card_id", "summary", "signals", "places", "categories", "primary_category", "confidence", "source_url"]
    for key in required:
        assert key in out, f"missing required field {key}"
    assert len(out["card_id"]) >= 8
    assert len(out["summary"]) >= 10
    assert len(out["source_url"]) >= 8
    assert 0 <= out["confidence"] <= 1
