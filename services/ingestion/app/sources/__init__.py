"""Real ingestion sources: YouTube and Products."""

from app.sources.youtube import (
    fetch_youtube_transcript,
    chunk_timestamped_segments as chunk_youtube_segments,
    enrich_chunk_to_card,
    write_youtube_to_weaviate,
)
from app.sources.products import (
    enrich_product_to_card,
    write_products_to_weaviate,
)

__all__ = [
    "fetch_youtube_transcript",
    "chunk_youtube_segments",
    "enrich_chunk_to_card",
    "write_youtube_to_weaviate",
    "enrich_product_to_card",
    "write_products_to_weaviate",
]
