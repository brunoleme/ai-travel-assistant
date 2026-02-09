"""
Weaviate schema: ensure Video, RecommendationCard, Product, ProductCard exist.

Uses REST /v1/schema so it works regardless of client version.
"""

from __future__ import annotations

import os

import httpx


def get_weaviate_base() -> str:
    """Base URL for Weaviate REST API from env."""
    host = os.environ.get("WEAVIATE_HOST", "localhost")
    port = int(os.environ.get("WEAVIATE_PORT", "8080"))
    return f"http://{host}:{port}"


def _class_exists(base: str, class_name: str, timeout: float = 30.0) -> bool:
    """Return True if the class exists in the schema."""
    with httpx.Client(timeout=timeout) as client:
        r = client.get(f"{base}/v1/schema")
        r.raise_for_status()
        schema = r.json()
    classes = schema.get("classes") or []
    return any(c.get("class") == class_name for c in classes)


def ensure_collections(timeout: float = 30.0) -> None:
    """
    Create Video, RecommendationCard, Product, ProductCard if they do not exist.
    Idempotent; safe to call at startup or before each write.
    """
    base = get_weaviate_base()
    with httpx.Client(timeout=timeout) as client:
        if not _class_exists(base, "Video", timeout):
            payload = {
                "class": "Video",
                "vectorizer": "none",
                "properties": [
                    {"name": "videoId", "dataType": ["text"]},
                    {"name": "videoUrl", "dataType": ["text"]},
                    {"name": "title", "dataType": ["text"]},
                    {"name": "channel", "dataType": ["text"]},
                    {"name": "lang", "dataType": ["text"]},
                    {"name": "playlistUrl", "dataType": ["text"]},
                    {"name": "playlistName", "dataType": ["text"]},
                    {"name": "creatorTier", "dataType": ["text"]},
                    {"name": "uploadDate", "dataType": ["date"]},
                ],
            }
            client.post(f"{base}/v1/schema", json=payload).raise_for_status()

        if not _class_exists(base, "RecommendationCard", timeout):
            payload = {
                "class": "RecommendationCard",
                "vectorizer": "text2vec-openai",
                "moduleConfig": {"text2vec-openai": {"model": "text-embedding-3-large"}},
                "properties": [
                    {"name": "summary", "dataType": ["text"]},
                    {"name": "text", "dataType": ["text"]},
                    {"name": "startSec", "dataType": ["number"]},
                    {"name": "endSec", "dataType": ["number"]},
                    {"name": "timestampUrl", "dataType": ["text"]},
                    {"name": "lang", "dataType": ["text"]},
                    {"name": "destination", "dataType": ["text"]},
                    {"name": "categories", "dataType": ["text[]"]},
                    {"name": "primaryCategory", "dataType": ["text"]},
                    {"name": "places", "dataType": ["text[]"]},
                    {"name": "signals", "dataType": ["text[]"]},
                    {"name": "confidence", "dataType": ["number"]},
                    {"name": "rationale", "dataType": ["text"]},
                    {"name": "videoUploadDate", "dataType": ["date"]},
                    {"name": "fromVideo", "dataType": ["Video"]},
                ],
            }
            client.post(f"{base}/v1/schema", json=payload).raise_for_status()

        if not _class_exists(base, "Product", timeout):
            payload = {
                "class": "Product",
                "vectorizer": "none",
                "properties": [
                    {"name": "question", "dataType": ["text"]},
                    {"name": "opportunity", "dataType": ["text"]},
                    {"name": "link", "dataType": ["text"]},
                    {"name": "destination", "dataType": ["text"]},
                    {"name": "lang", "dataType": ["text"]},
                    {"name": "market", "dataType": ["text"]},
                    {"name": "merchant", "dataType": ["text"]},
                    {"name": "createdAt", "dataType": ["date"]},
                ],
            }
            client.post(f"{base}/v1/schema", json=payload).raise_for_status()

        if not _class_exists(base, "ProductCard", timeout):
            payload = {
                "class": "ProductCard",
                "vectorizer": "text2vec-openai",
                "moduleConfig": {"text2vec-openai": {"model": "text-embedding-3-large"}},
                "properties": [
                    {"name": "summary", "dataType": ["text"]},
                    {"name": "question", "dataType": ["text"]},
                    {"name": "opportunity", "dataType": ["text"]},
                    {"name": "link", "dataType": ["text"]},
                    {"name": "merchant", "dataType": ["text"]},
                    {"name": "lang", "dataType": ["text"]},
                    {"name": "market", "dataType": ["text"]},
                    {"name": "destination", "dataType": ["text"]},
                    {"name": "primaryCategory", "dataType": ["text"]},
                    {"name": "categories", "dataType": ["text[]"]},
                    {"name": "triggers", "dataType": ["text[]"]},
                    {"name": "affiliatePriority", "dataType": ["number"]},
                    {"name": "userValue", "dataType": ["number"]},
                    {"name": "constraints", "dataType": ["text[]"]},
                    {"name": "confidence", "dataType": ["number"]},
                    {"name": "rationale", "dataType": ["text"]},
                    {"name": "fromProduct", "dataType": ["Product"]},
                    {"name": "createdAt", "dataType": ["date"]},
                ],
            }
            client.post(f"{base}/v1/schema", json=payload).raise_for_status()
