"""
Schema bootstrap via REST API (dev/bootstrap only).
Ensures Video (vectorizer none) and RecommendationCard (text2vec-openai, text-embedding-3-large).
"""
from __future__ import annotations

import os

import requests


def ensure_collections() -> None:
    """
    Create Weaviate collections if they do not exist:
      - Video (vectorizer none)
      - RecommendationCard (text2vec-openai, model text-embedding-3-large)
    """
    host = os.getenv("WEAVIATE_HOST", "localhost")
    port = int(os.getenv("WEAVIATE_PORT", "8080"))
    base = f"http://{host}:{port}"

    def class_exists(class_name: str) -> bool:
        r = requests.get(f"{base}/v1/schema", timeout=30)
        r.raise_for_status()
        schema = r.json()
        return any(c.get("class") == class_name for c in schema.get("classes", []))

    if not class_exists("Video"):
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
        requests.post(f"{base}/v1/schema", json=payload, timeout=30).raise_for_status()
        print("Created class: Video")

    if not class_exists("RecommendationCard"):
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
        requests.post(f"{base}/v1/schema", json=payload, timeout=30).raise_for_status()
        print("Created class: RecommendationCard")


if __name__ == "__main__":
    ensure_collections()
