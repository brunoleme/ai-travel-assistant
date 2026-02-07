"""
Weaviate retrieval for ProductCard. Returns contract ProductCandidates via adapter.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.adapter import product_card_to_candidate
from app.models import ProductCandidate

if TYPE_CHECKING:
    import weaviate


def get_client():  # type: () -> weaviate.WeaviateClient | None
    """Connect to Weaviate from env (WEAVIATE_HOST, WEAVIATE_PORT). Returns None on failure."""
    try:
        import weaviate
        host = os.getenv("WEAVIATE_HOST", "localhost")
        port = int(os.getenv("WEAVIATE_PORT", "8080"))
        return weaviate.connect_to_local(host=host, port=port)
    except Exception:
        return None


def retrieve_product_cards(
    client: "weaviate.WeaviateClient | None",
    query_signature: str,
    limit: int = 10,
    min_confidence: float | None = None,
) -> list[ProductCandidate]:
    """
    Query Weaviate ProductCard with near_text; map to contract ProductCandidates.
    Returns 1–3 candidates when client is None or query fails (stub).
    """
    candidates, _ = retrieve_product_cards_with_fallback(
        client, query_signature, limit=limit, min_confidence=min_confidence
    )
    return candidates


def retrieve_product_cards_with_fallback(
    client: "weaviate.WeaviateClient | None",
    query_signature: str,
    limit: int = 10,
    min_confidence: float | None = None,
) -> tuple[list[ProductCandidate], bool]:
    """
    Same as retrieve_product_cards but returns (candidates, weaviate_fallback).
    weaviate_fallback is True when stub was used (client None or query failed).
    """
    if client is None:
        return (_stub_candidates(), True)

    try:
        import weaviate.classes as wvc

        coll = client.collections.get("ProductCard")
        response = coll.query.near_text(
            query=query_signature,
            limit=min(limit, 20),
            return_metadata=wvc.query.MetadataQuery(distance=True),
        )
        candidates: list[ProductCandidate] = []
        for rank, obj in enumerate(response.objects, start=1):
            props = dict(obj.properties) if obj.properties else {}
            distance = getattr(obj.metadata, "distance", None) if obj.metadata else None
            conf = props.get("confidence")
            if min_confidence is not None and conf is not None and float(conf) < min_confidence:
                continue
            cand = product_card_to_candidate(
                props,
                str(obj.uuid),
                distance=distance,
                rank=rank,
            )
            candidates.append(cand)
        if not candidates:
            return (_stub_candidates(), True)
        return (candidates[: min(limit, 3)], False)
    except Exception:
        return (_stub_candidates(), True)


def _stub_candidates() -> list[ProductCandidate]:
    """Fallback 1–3 candidates when Weaviate is unavailable."""
    from app.models import ProductScore

    return [
        ProductCandidate(
            product_id="stub-product-01",
            summary="Stub product summary for when Weaviate is unavailable (min 10 chars).",
            merchant="Stub Merchant",
            link="https://example.com/stub1",
            categories=["stub"],
            primary_category="stub",
            triggers=["stub"],
            constraints=[],
            affiliate_priority=0.5,
            user_value=0.5,
            confidence=0.5,
            score=ProductScore(distance=0.0, rank=1),
        ),
    ]
