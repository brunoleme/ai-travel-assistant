"""
Adapter: Weaviate ProductCard → Contract ProductCandidate.
Mapping: uuid→product_id, primaryCategory→primary_category,
affiliatePriority→affiliate_priority, userValue→user_value;
triggers/constraints/categories map directly; metadata.distance/rank→score.
"""
from __future__ import annotations

from typing import Any

from app.models import ProductCandidate, ProductScore


def _get(obj: dict[str, Any], key: str, default: Any = None) -> Any:
    return obj.get(key, default)


def product_card_to_candidate(
    properties: dict[str, Any],
    uuid: str,
    *,
    distance: float | None = None,
    rank: int | None = None,
) -> ProductCandidate:
    """
    Map a Weaviate ProductCard (properties dict + uuid) to contract ProductCandidate.
    Weaviate keys: summary, merchant, link, categories, primaryCategory,
    triggers, constraints, affiliatePriority, userValue, confidence.
    """
    product_id = str(uuid)
    summary = _get(properties, "summary") or ""
    merchant = _get(properties, "merchant") or ""
    link = _get(properties, "link") or ""
    categories = _get(properties, "categories")
    if categories is None:
        categories = []
    if not isinstance(categories, list):
        categories = list(categories) if categories else []
    categories = [str(c) for c in categories]

    primary_category = _get(properties, "primaryCategory")
    primary_category = str(primary_category) if primary_category is not None else None

    triggers = _get(properties, "triggers")
    if triggers is not None and not isinstance(triggers, list):
        triggers = list(triggers) if triggers else []
    triggers = [str(t) for t in triggers] if triggers else None

    constraints = _get(properties, "constraints")
    if constraints is not None and not isinstance(constraints, list):
        constraints = list(constraints) if constraints else []
    constraints = [str(c) for c in constraints] if constraints else None

    ap = _get(properties, "affiliatePriority")
    affiliate_priority = float(ap) if ap is not None else None
    uv = _get(properties, "userValue")
    user_value = float(uv) if uv is not None else None
    conf = _get(properties, "confidence")
    confidence = float(conf) if conf is not None else 0.0

    score = None
    if distance is not None or rank is not None:
        score = ProductScore(distance=distance, rank=rank)

    return ProductCandidate(
        product_id=product_id,
        summary=summary,
        merchant=merchant,
        link=link,
        categories=categories,
        primary_category=primary_category,
        triggers=triggers,
        constraints=constraints,
        affiliate_priority=affiliate_priority,
        user_value=user_value,
        confidence=confidence,
        score=score,
    )
