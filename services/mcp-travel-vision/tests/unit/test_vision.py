"""Unit tests for vision analysis. Mocked OpenAI; no network."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.models import VisionAnalyzeRequest
from app.vision import (
    _extract_json_from_text,
    _mock_signals,
    _parse_landmark,
    _parse_packing,
    _parse_product_similarity,
    analyze_image,
)


def test_extract_json_from_text_raw_object() -> None:
    """Extract JSON from raw {...} text."""
    out = _extract_json_from_text('{"a": 1, "b": 2}')
    assert out == {"a": 1, "b": 2}


def test_extract_json_from_text_markdown_code_block() -> None:
    """Extract JSON from ```json ... ``` block."""
    text = 'Here is the result:\n```json\n{"mode": "packing", "confidence": 0.9}\n```'
    out = _extract_json_from_text(text)
    assert out == {"mode": "packing", "confidence": 0.9}


def test_extract_json_from_text_invalid_returns_none() -> None:
    """Invalid JSON returns None."""
    assert _extract_json_from_text("not json at all") is None
    assert _extract_json_from_text("") is None


def test_mock_signals_packing() -> None:
    """Mock packing signals have required fields and validate."""
    s = _mock_signals("packing")
    assert s.mode == "packing"
    assert 0 <= s.confidence <= 1
    assert isinstance(s.detected_items, list)
    assert isinstance(s.missing_categories, list)


def test_mock_signals_landmark() -> None:
    """Mock landmark signals have place_candidates."""
    s = _mock_signals("landmark")
    assert s.mode == "landmark"
    assert s.place_candidates is not None
    assert len(s.place_candidates) >= 1


def test_mock_signals_product_similarity() -> None:
    """Mock product_similarity signals have search_queries."""
    s = _mock_signals("product_similarity")
    assert s.mode == "product_similarity"
    assert s.search_queries is not None
    assert len(s.search_queries) >= 2


def test_parse_packing_filters_to_18_item_set() -> None:
    """Packing parser only keeps categories from the 18-item set."""
    raw = {
        "confidence": 0.8,
        "detected_items": ["light_top", "walking_shoes", "invalid_item"],
        "missing_categories": ["rain_jacket"],
    }
    s = _parse_packing(raw, "packing")
    assert s.mode == "packing"
    assert s.confidence == 0.8
    assert set(s.detected_items or []) == {"light_top", "walking_shoes"}
    assert (s.missing_categories or []) == ["rain_jacket"]


def test_parse_packing_suitability_and_suggested_categories() -> None:
    """Outfit mode: suitability_ok, suitability_issue, suggested_categories_for_products parsed and filtered."""
    raw = {
        "confidence": 0.85,
        "detected_items": ["light_top", "long_pants"],
        "missing_categories": [],
        "suitability_ok": False,
        "suitability_issue": "Too light for winter.",
        "suggested_categories_for_products": ["warm_top", "insulated_jacket", "invalid_cat"],
    }
    s = _parse_packing(raw, "packing")
    assert s.mode == "packing"
    assert s.suitability_ok is False
    assert s.suitability_issue == "Too light for winter."
    assert set(s.suggested_categories_for_products or []) == {"warm_top", "insulated_jacket"}


def test_parse_landmark_builds_place_candidates() -> None:
    """Landmark parser builds PlaceCandidate list."""
    raw = {
        "confidence": 0.9,
        "scene_type": "landmark",
        "ocr_text": ["Tour Eiffel"],
        "distinctive_features": ["iron tower"],
        "place_candidates": [
            {"place_name": "Eiffel Tower", "confidence": 0.95, "reason": "Shape"},
        ],
    }
    s = _parse_landmark(raw, "landmark")
    assert s.mode == "landmark"
    assert s.scene_type == "landmark"
    assert len(s.place_candidates or []) == 1
    assert (s.place_candidates or [])[0].place_name == "Eiffel Tower"


def test_parse_product_similarity_filters_category() -> None:
    """Product_similarity parser only accepts category from 18-item set."""
    raw = {
        "confidence": 0.85,
        "category": "day_bag",
        "attributes": {"color": "black"},
        "style_keywords": ["minimal"],
        "search_queries": ["black day bag", "minimal backpack"],
    }
    s = _parse_product_similarity(raw, "product_similarity")
    assert s.mode == "product_similarity"
    assert s.category == "day_bag"
    assert (s.search_queries or [])[:2] == ["black day bag", "minimal backpack"]


@patch("app.vision._get_client", return_value=None)
def test_analyze_image_no_client_returns_mock(get_client: MagicMock) -> None:
    """When OpenAI client is None (no API key), analyze_image returns mock signals."""
    req = VisionAnalyzeRequest(image_ref="https://example.com/img.jpg", mode="packing")
    s = analyze_image(req)
    get_client.assert_called_once()
    assert s.mode == "packing"
    assert s.detected_items is not None


@patch("app.vision._get_client")
def test_analyze_image_parse_failure_returns_error(mock_get_client: MagicMock) -> None:
    """When model returns non-JSON, analyze_image returns valid schema with error and confidence=0."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="not valid json"))]
    )
    mock_get_client.return_value = mock_client

    req = VisionAnalyzeRequest(image_ref="https://example.com/img.jpg", mode="packing")
    s = analyze_image(req)
    assert s.mode == "packing"
    assert s.confidence == 0.0
    assert s.error is not None
    assert "parse" in (s.error or "").lower() or "JSON" in (s.error or "")


@patch("app.vision._get_client")
def test_analyze_image_packing_calls_openai(mock_get_client: MagicMock) -> None:
    """Packing mode with valid JSON response returns VisionSignals."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"detected_items":["light_top","walking_shoes"],"missing_categories":["rain_jacket"],"confidence":0.9}'
                )
            )
        ]
    )
    mock_get_client.return_value = mock_client

    req = VisionAnalyzeRequest(
        image_ref="https://example.com/img.jpg",
        mode="packing",
        trip_context={"rain_risk": "high"},
    )
    s = analyze_image(req)
    assert s.mode == "packing"
    assert s.confidence == 0.9
    assert s.error is None
    assert "light_top" in (s.detected_items or [])
    mock_client.chat.completions.create.assert_called_once()
