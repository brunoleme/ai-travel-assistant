"""
Schema via REST para evitar nuances de versão do client.
Cria: Product (vectorizer none), ProductCard (text2vec-openai).
"""
from __future__ import annotations

import os

import requests


def ensure_collections() -> None:
    """
    Cria coleções Weaviate se não existirem:
      - Product (vectorizer none)
      - ProductCard (text2vec-openai)
    """
    host = os.getenv("WEAVIATE_HOST", "localhost")
    port = int(os.getenv("WEAVIATE_PORT", "8080"))
    base = f"http://{host}:{port}"

    def class_exists(class_name: str) -> bool:
        r = requests.get(f"{base}/v1/schema", timeout=30)
        r.raise_for_status()
        schema = r.json()
        return any(c.get("class") == class_name for c in schema.get("classes", []))

    if not class_exists("Product"):
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
        requests.post(f"{base}/v1/schema", json=payload, timeout=30).raise_for_status()
        print("Created class: Product")

    if not class_exists("ProductCard"):
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
        requests.post(f"{base}/v1/schema", json=payload, timeout=30).raise_for_status()
        print("Created class: ProductCard")


if __name__ == "__main__":
    ensure_collections()
