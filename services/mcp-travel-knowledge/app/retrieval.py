"""Weaviate retrieval from RecommendationCard collection."""

from __future__ import annotations

import os
from typing import Any

import weaviate


def _get_client() -> weaviate.WeaviateClient:
    """Connect to Weaviate using env WEAVIATE_HOST, WEAVIATE_PORT."""
    host = os.environ.get("WEAVIATE_HOST", "localhost")
    port = int(os.environ.get("WEAVIATE_PORT", "8080"))
    return weaviate.connect_to_local(host=host, port=port)


def _object_to_raw(obj: Any) -> dict[str, Any]:
    """Turn a Weaviate collection object into a flat dict (uuid + properties) for the adapter."""
    raw: dict[str, Any] = {"uuid": str(obj.uuid)}
    props = obj.properties
    if hasattr(props, "items"):
        for k, v in props.items():
            raw[k] = v
    return raw


def get_recommendation_cards(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """
    Query Weaviate RecommendationCard with near_text; return list of raw dicts (uuid + properties).
    Each dict is suitable for app.adapter.weaviate_card_to_evidence().
    """
    client = _get_client()
    try:
        coll = client.collections.get("RecommendationCard")
        result = coll.query.near_text(query=query, limit=limit)
        return [_object_to_raw(obj) for obj in result.objects]
    finally:
        client.close()
