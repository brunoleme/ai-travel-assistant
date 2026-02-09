"""
Ingestion pipeline stages: fetch -> transcript -> chunk -> enrich -> embed -> write.

Routes by payload.source_type: "youtube" | "products" for real ingestion;
otherwise mock (for tests).
"""

from __future__ import annotations

from uuid import uuid4

from app.events import (
    ChunksReady,
    EmbeddingsReady,
    EnrichmentReady,
    IngestionRequested,
    TranscriptReady,
    WriteComplete,
)
from app.idempotency import already_processed, build_idempotency_key, mark_processed

# Test hook: records when an actual write is performed (for idempotency tests).
_write_events: list[dict] = []


def _default_chunk_params(p: dict) -> dict:
    return {
        "chunk_max_chars": p.get("chunk_max_chars", 1200),
        "chunk_min_chars": p.get("chunk_min_chars", 350),
        "chunk_max_duration_s": p.get("chunk_max_duration_s", 75),
        "chunk_min_duration_s": p.get("chunk_min_duration_s", 25),
        "gap_split_s": p.get("gap_split_s", 2.5),
    }


def handle_fetch(event: IngestionRequested) -> TranscriptReady | None:
    """Fetch content; emit TranscriptReady. Idempotent. Routes by source_type."""
    if event.payload.get("__fail__") is True:
        return None
    key = build_idempotency_key(event.content_source_id, "transcript")
    if already_processed(key):
        return None
    source_type = event.payload.get("source_type")

    if source_type == "youtube":
        video_url = event.payload.get("video_url")
        if not video_url:
            return None
        from app.sources.youtube import fetch_youtube_transcript
        lang_hint = event.payload.get("language_hint", "auto")
        segments, lang, video_metadata = fetch_youtube_transcript(video_url, lang_hint)
        payload = {
            "source_type": "youtube",
            "segments": segments,
            "lang": lang,
            "video_metadata": video_metadata,
            "destination": event.payload.get("destination", ""),
            "playlist_url": event.payload.get("playlist_url", ""),
            "playlist_name": event.payload.get("playlist_name", ""),
            "creator_tier": event.payload.get("creator_tier", ""),
            "enrich_model": event.payload.get("enrich_model", "gpt-4.1-mini"),
            **_default_chunk_params(event.payload),
        }
        mark_processed(key)
        return TranscriptReady(
            event_id=str(uuid4()),
            content_source_id=event.content_source_id,
            stage="transcript",
            payload=payload,
            retry_count=event.retry_count,
            max_retries=event.max_retries,
            error=event.error,
        )

    if source_type == "products":
        products = event.payload.get("products") or []
        if not products:
            return None
        payload = {
            "source_type": "products",
            "products": products,
            "enrich_model": event.payload.get("enrich_model", "gpt-4.1-mini"),
        }
        mark_processed(key)
        return TranscriptReady(
            event_id=str(uuid4()),
            content_source_id=event.content_source_id,
            stage="transcript",
            payload=payload,
            retry_count=event.retry_count,
            max_retries=event.max_retries,
            error=event.error,
        )

    if source_type is not None and source_type not in ("youtube", "products"):
        return None  # Unknown source_type -> DLQ after retries

    # Mock for tests (no source_type)
    mark_processed(key)
    return TranscriptReady(
        event_id=str(uuid4()),
        content_source_id=event.content_source_id,
        stage="transcript",
        payload={"text": "mock transcript"},
        retry_count=event.retry_count,
        max_retries=event.max_retries,
        error=event.error,
    )


def handle_transcript(event: TranscriptReady) -> ChunksReady | None:
    """Chunk transcript; emit ChunksReady. Idempotent."""
    key = build_idempotency_key(event.content_source_id, "chunks")
    if already_processed(key):
        return None
    source_type = event.payload.get("source_type")

    if source_type == "youtube":
        from app.sources.youtube import chunk_timestamped_segments
        segments = event.payload.get("segments") or []
        chunks = chunk_timestamped_segments(
            segments,
            max_chars=event.payload.get("chunk_max_chars", 1200),
            min_chars=event.payload.get("chunk_min_chars", 350),
            max_duration_s=event.payload.get("chunk_max_duration_s", 75),
            min_duration_s=event.payload.get("chunk_min_duration_s", 25),
            gap_split_s=event.payload.get("gap_split_s", 2.5),
        )
        payload = {
            "source_type": "youtube",
            "chunks": chunks,
            "video_metadata": event.payload.get("video_metadata", {}),
            "lang": event.payload.get("lang", "pt"),
            "destination": event.payload.get("destination", ""),
            "playlist_url": event.payload.get("playlist_url", ""),
            "playlist_name": event.payload.get("playlist_name", ""),
            "creator_tier": event.payload.get("creator_tier", ""),
            "enrich_model": event.payload.get("enrich_model", "gpt-4.1-mini"),
        }
        mark_processed(key)
        return ChunksReady(
            event_id=str(uuid4()),
            content_source_id=event.content_source_id,
            stage="chunks",
            payload=payload,
            retry_count=event.retry_count,
            max_retries=event.max_retries,
            error=event.error,
        )

    if source_type == "products":
        payload = {
            "source_type": "products",
            "products": event.payload.get("products", []),
            "enrich_model": event.payload.get("enrich_model", "gpt-4.1-mini"),
        }
        mark_processed(key)
        return ChunksReady(
            event_id=str(uuid4()),
            content_source_id=event.content_source_id,
            stage="chunks",
            payload=payload,
            retry_count=event.retry_count,
            max_retries=event.max_retries,
            error=event.error,
        )

    mark_processed(key)
    return ChunksReady(
        event_id=str(uuid4()),
        content_source_id=event.content_source_id,
        stage="chunks",
        payload={"chunks": ["mock chunk 1", "mock chunk 2"]},
        retry_count=event.retry_count,
        max_retries=event.max_retries,
        error=event.error,
    )


def handle_chunk(event: ChunksReady) -> EnrichmentReady | None:
    """Enrich chunks; emit EnrichmentReady. Idempotent."""
    key = build_idempotency_key(event.content_source_id, "enrichment")
    if already_processed(key):
        return None
    source_type = event.payload.get("source_type")

    if source_type == "youtube":
        from app.sources.youtube import enrich_chunk_to_card
        chunks = event.payload.get("chunks") or []
        destination = event.payload.get("destination", "")
        lang = event.payload.get("lang", "pt")
        model = event.payload.get("enrich_model", "gpt-4.1-mini")
        cards = []
        for ch in chunks:
            card = enrich_chunk_to_card(
                chunk_text=ch.get("text", ""),
                destination=destination,
                source_lang=lang,
                model=model,
            )
            cards.append(card)
        payload = {
            "source_type": "youtube",
            "cards": [c.model_dump() for c in cards],
            "chunks": chunks,
            "video_metadata": event.payload.get("video_metadata", {}),
            "lang": lang,
            "destination": destination,
            "playlist_url": event.payload.get("playlist_url", ""),
            "playlist_name": event.payload.get("playlist_name", ""),
            "creator_tier": event.payload.get("creator_tier", ""),
        }
        mark_processed(key)
        return EnrichmentReady(
            event_id=str(uuid4()),
            content_source_id=event.content_source_id,
            stage="enrichment",
            payload=payload,
            retry_count=event.retry_count,
            max_retries=event.max_retries,
            error=event.error,
        )

    if source_type == "products":
        from app.sources.products import enrich_product_to_card, ProductInput
        products = event.payload.get("products") or []
        model = event.payload.get("enrich_model", "gpt-4.1-mini")
        cards = []
        for p in products:
            pi = ProductInput(**(p if isinstance(p, dict) else p))
            card = enrich_product_to_card(pi=pi, model=model)
            cards.append(card)
        payload = {
            "source_type": "products",
            "cards": [c.model_dump() for c in cards],
            "products": products,
        }
        mark_processed(key)
        return EnrichmentReady(
            event_id=str(uuid4()),
            content_source_id=event.content_source_id,
            stage="enrichment",
            payload=payload,
            retry_count=event.retry_count,
            max_retries=event.max_retries,
            error=event.error,
        )

    mark_processed(key)
    return EnrichmentReady(
        event_id=str(uuid4()),
        content_source_id=event.content_source_id,
        stage="enrichment",
        payload={"enriched": event.payload.get("chunks", [])},
        retry_count=event.retry_count,
        max_retries=event.max_retries,
        error=event.error,
    )


def handle_enrich(event: EnrichmentReady) -> EmbeddingsReady | None:
    """Pass through (Weaviate vectorizer). Idempotent."""
    key = build_idempotency_key(event.content_source_id, "embeddings")
    if already_processed(key):
        return None
    mark_processed(key)
    return EmbeddingsReady(
        event_id=str(uuid4()),
        content_source_id=event.content_source_id,
        stage="embeddings",
        payload=event.payload,
        retry_count=event.retry_count,
        max_retries=event.max_retries,
        error=event.error,
    )


def handle_embed(event: EmbeddingsReady) -> WriteComplete | None:
    """Pass through to WriteComplete. Idempotent."""
    key = build_idempotency_key(event.content_source_id, "write_complete")
    if already_processed(key):
        return None
    mark_processed(key)
    return WriteComplete(
        event_id=str(uuid4()),
        content_source_id=event.content_source_id,
        stage="write_complete",
        payload=event.payload,
        retry_count=event.retry_count,
        max_retries=event.max_retries,
        error=event.error,
    )


def handle_write(event: WriteComplete) -> None:
    """Persist to Weaviate (youtube/products) or mock. Idempotent."""
    key = build_idempotency_key(event.content_source_id, "write")
    if already_processed(key):
        return
    source_type = event.payload.get("source_type")

    if source_type == "youtube":
        from app.sources.youtube import write_youtube_to_weaviate, RecommendationCard
        video_metadata = event.payload.get("video_metadata", {})
        chunks = event.payload.get("chunks", [])
        cards_data = event.payload.get("cards", [])
        cards = [RecommendationCard(**c) for c in cards_data]
        write_youtube_to_weaviate(
            video_metadata=video_metadata,
            chunks=chunks,
            cards=cards,
            destination=event.payload.get("destination", ""),
            playlist_url=event.payload.get("playlist_url", ""),
            playlist_name=event.payload.get("playlist_name", ""),
            creator_tier=event.payload.get("creator_tier", ""),
            lang=event.payload.get("lang", "pt"),
        )
        mark_processed(key)
        _write_events.append({"content_source_id": event.content_source_id, "event_id": event.event_id})
        return

    if source_type == "products":
        from app.sources.products import write_products_to_weaviate, ProductCardModel
        products = event.payload.get("products", [])
        cards_data = event.payload.get("cards", [])
        cards = [ProductCardModel(**c) for c in cards_data]
        write_products_to_weaviate(products=products, cards=cards)
        mark_processed(key)
        _write_events.append({"content_source_id": event.content_source_id, "event_id": event.event_id})
        return

    mark_processed(key)
    _write_events.append(
        {"content_source_id": event.content_source_id, "event_id": event.event_id}
    )


def get_write_events() -> list[dict]:
    """Return recorded write events (for tests)."""
    return list(_write_events)


def clear_write_events() -> None:
    """Clear recorded write events (for tests)."""
    _write_events.clear()
