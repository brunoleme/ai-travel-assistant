"""
Tests for real ingestion (YouTube / Products) with mocked external calls.

No real yt-dlp, OpenAI, or Weaviate in tests.
"""

from __future__ import annotations

from unittest.mock import patch

from app.events import ChunksReady, IngestionRequested, TranscriptReady
from app.idempotency import reset_processed
from app.pipeline import handle_fetch, handle_transcript, handle_chunk


def test_unknown_source_type_returns_none() -> None:
    """Unknown source_type does not advance; caller can send to DLQ."""
    reset_processed()
    event = IngestionRequested(
        event_id="e1",
        content_source_id="x",
        stage="requested",
        payload={"source_type": "unknown"},
    )
    out = handle_fetch(event)
    assert out is None


def test_youtube_fetch_mocked_returns_transcript() -> None:
    """With fetch_youtube_transcript mocked, handle_fetch emits TranscriptReady."""
    reset_processed()
    fake_segments = [{"start": 0, "duration": 5, "text": "Hello world"}]
    fake_meta = {"id": "vid1", "title": "T", "channel": "C", "upload_date": None, "webpage_url": "https://youtube.com/watch?v=vid1"}
    with patch("app.sources.youtube.fetch_youtube_transcript") as m_fetch:
        m_fetch.return_value = (fake_segments, "en", fake_meta)
        event = IngestionRequested(
            event_id="e1",
            content_source_id="youtube:vid1",
            stage="requested",
            payload={"source_type": "youtube", "video_url": "https://www.youtube.com/watch?v=vid1", "destination": "Orlando"},
        )
        out = handle_fetch(event)
    assert out is not None
    assert out.stage == "transcript"
    assert out.payload.get("source_type") == "youtube"
    assert out.payload.get("segments") == fake_segments
    assert out.payload.get("lang") == "en"
    assert out.payload.get("video_metadata") == fake_meta


def test_youtube_chunk_mocked_returns_chunks() -> None:
    """With segments in payload, handle_transcript emits ChunksReady with chunks."""
    reset_processed()
    segments = [{"start": 0, "duration": 10, "text": "First segment."}, {"start": 10, "duration": 10, "text": "Second segment."}]
    meta = {"id": "v1", "title": "T", "channel": "C", "upload_date": None, "webpage_url": "https://youtube.com/watch?v=v1"}
    event = TranscriptReady(
        event_id="e1",
        content_source_id="youtube:v1",
        stage="transcript",
        payload={
            "source_type": "youtube",
            "segments": segments,
            "lang": "en",
            "video_metadata": meta,
            "destination": "Orlando",
        },
    )
    out = handle_transcript(event)
    assert out is not None
    assert out.stage == "chunks"
    assert out.payload.get("source_type") == "youtube"
    chunks = out.payload.get("chunks") or []
    assert len(chunks) >= 1
    assert "text" in chunks[0] and "startSec" in chunks[0]


def test_youtube_enrich_mocked_returns_cards() -> None:
    """With OpenAI mocked, handle_chunk emits EnrichmentReady with cards."""
    reset_processed()
    chunks = [{"startSec": 0, "endSec": 30, "text": "Buy tickets early for Disney."}]
    meta = {"id": "v1", "title": "T", "channel": "C", "upload_date": None, "webpage_url": "https://youtube.com/watch?v=v1"}
    with patch("app.sources.youtube.enrich_chunk_to_card") as m_enrich:
        from app.sources.youtube import RecommendationCard
        m_enrich.return_value = RecommendationCard(
            summary="Buy tickets early.",
            primaryCategory="tip",
            categories=["tip", "itinerary"],
            places=[],
            signals=["Buy tickets in advance"],
            confidence=0.8,
            rationale="Clear advice.",
        )
        event = ChunksReady(
            event_id="e1",
            content_source_id="youtube:v1",
            stage="chunks",
            payload={
                "source_type": "youtube",
                "chunks": chunks,
                "video_metadata": meta,
                "lang": "en",
                "destination": "Orlando",
            },
        )
        out = handle_chunk(event)
    assert out is not None
    assert out.stage == "enrichment"
    assert out.payload.get("source_type") == "youtube"
    cards = out.payload.get("cards") or []
    assert len(cards) == 1
    assert cards[0].get("summary") == "Buy tickets early."


def test_products_fetch_pass_through() -> None:
    """Products handle_fetch emits TranscriptReady with products."""
    reset_processed()
    products = [
        {"question": "Seguro para Orlando?", "opportunity": "Seguro viagem cobre cancelamento.", "link": "https://example.com/s"},
    ]
    event = IngestionRequested(
        event_id="e1",
        content_source_id="products:batch1",
        stage="requested",
        payload={"source_type": "products", "products": products},
    )
    out = handle_fetch(event)
    assert out is not None
    assert out.stage == "transcript"
    assert out.payload.get("source_type") == "products"
    assert out.payload.get("products") == products


def test_products_enrich_mocked_returns_cards() -> None:
    """With OpenAI mocked, products handle_chunk emits EnrichmentReady."""
    reset_processed()
    products = [
        {"question": "Chip internacional?", "opportunity": "eSIM para usar app da Disney.", "link": "https://example.com/esim"},
    ]
    with patch("app.sources.products.enrich_product_to_card") as m_enrich:
        from app.sources.products import ProductCardModel
        m_enrich.return_value = ProductCardModel(
            summary="eSIM for mobile data at Disney.",
            primaryCategory="esim",
            categories=["esim"],
            triggers=[],
            constraints=[],
            affiliatePriority=0.5,
            userValue=0.8,
            confidence=0.85,
            rationale="Relevant.",
        )
        event = ChunksReady(
            event_id="e1",
            content_source_id="products:batch1",
            stage="chunks",
            payload={"source_type": "products", "products": products},
        )
        out = handle_chunk(event)
    assert out is not None
    assert out.stage == "enrichment"
    assert out.payload.get("source_type") == "products"
    cards = out.payload.get("cards") or []
    assert len(cards) == 1
    assert cards[0].get("primaryCategory") == "esim"
