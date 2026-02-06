"""
Unit tests for Weaviate ProductCard → Contract ProductCandidate adapter (no network).
"""
from __future__ import annotations

from app.adapter import product_card_to_candidate


def test_adapter_uuid_to_product_id():
    """uuid maps to product_id."""
    props = {
        "summary": "A summary with at least ten characters here.",
        "merchant": "Merchant",
        "link": "https://example.com/product",
        "categories": ["a", "b"],
    }
    out = product_card_to_candidate(props, "550e8400-e29b-41d4-a716-446655440000")
    assert out.product_id == "550e8400-e29b-41d4-a716-446655440000"


def test_adapter_primary_category():
    """primaryCategory maps to primary_category."""
    props = {
        "summary": "A summary with at least ten characters here.",
        "merchant": "M",
        "link": "https://example.com/link",
        "categories": [],
        "primaryCategory": "attractions",
    }
    out = product_card_to_candidate(props, "prod-id-12345678")
    assert out.primary_category == "attractions"


def test_adapter_affiliate_priority_and_user_value():
    """affiliatePriority → affiliate_priority, userValue → user_value."""
    props = {
        "summary": "A summary with at least ten characters here.",
        "merchant": "M",
        "link": "https://example.com/link",
        "categories": [],
        "affiliatePriority": 0.8,
        "userValue": 0.9,
        "confidence": 0.7,
    }
    out = product_card_to_candidate(props, "prod-id-12345678")
    assert out.affiliate_priority == 0.8
    assert out.user_value == 0.9
    assert out.confidence == 0.7


def test_adapter_triggers_constraints_categories_direct():
    """triggers, constraints, categories map directly."""
    props = {
        "summary": "A summary with at least ten characters here.",
        "merchant": "M",
        "link": "https://example.com/link",
        "categories": ["cat1", "cat2"],
        "triggers": ["t1", "t2"],
        "constraints": ["c1"],
    }
    out = product_card_to_candidate(props, "prod-id-12345678")
    assert out.categories == ["cat1", "cat2"]
    assert out.triggers == ["t1", "t2"]
    assert out.constraints == ["c1"]


def test_adapter_score_distance_rank():
    """metadata.distance and rank map to score.distance and score.rank."""
    props = {
        "summary": "A summary with at least ten characters here.",
        "merchant": "M",
        "link": "https://example.com/link",
        "categories": [],
    }
    out = product_card_to_candidate(
        props, "prod-id-12345678", distance=0.15, rank=2
    )
    assert out.score is not None
    assert out.score.distance == 0.15
    assert out.score.rank == 2


def test_adapter_score_optional():
    """score is None when distance and rank not provided."""
    props = {
        "summary": "A summary with at least ten characters here.",
        "merchant": "M",
        "link": "https://example.com/link",
        "categories": [],
    }
    out = product_card_to_candidate(props, "prod-id-12345678")
    assert out.score is None


def test_adapter_min_length_product_id():
    """product_id from uuid must satisfy min length 8 (contract)."""
    props = {
        "summary": "A summary with at least ten characters here.",
        "merchant": "M",
        "link": "https://example.com/link",
        "categories": [],
    }
    out = product_card_to_candidate(props, "12345678")
    assert len(out.product_id) >= 8
