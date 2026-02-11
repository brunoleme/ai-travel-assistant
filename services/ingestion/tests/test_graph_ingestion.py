"""
Tests for youtube_kg (graph / Neo4j) ingestion with mocked OpenAI and Neo4j.

No real yt-dlp, OpenAI, or Neo4j in tests.
"""

from __future__ import annotations

from unittest.mock import patch

from app.events import (
    ChunksReady,
    EnrichmentReady,
    IngestionRequested,
    TranscriptReady,
    WriteComplete,
)
from app.idempotency import reset_processed
from app.pipeline import (
    handle_chunk,
    handle_enrich,
    handle_fetch,
    handle_transcript,
    handle_write,
)
from app.sources.graph import (
    Evidence,
    GraphEdge,
    GraphExtraction,
    GraphNode,
    merge_graph,
)


def test_youtube_kg_fetch_mocked_returns_transcript() -> None:
    """With fetch mocked, handle_fetch for youtube_kg emits TranscriptReady with destination_hint and extract_model."""
    reset_processed()
    fake_segments = [{"start": 0, "duration": 5, "text": "Hello world"}]
    fake_meta = {"id": "v1", "title": "T", "channel": "C", "upload_date": None, "webpage_url": "https://youtube.com/watch?v=v1"}
    with patch("app.sources.youtube.fetch_youtube_transcript") as m_fetch:
        m_fetch.return_value = (fake_segments, "pt", fake_meta)
        event = IngestionRequested(
            event_id="e1",
            content_source_id="youtube_kg:v1",
            stage="requested",
            payload={
                "source_type": "youtube_kg",
                "video_url": "https://www.youtube.com/watch?v=v1",
                "destination_hint": "Playa del Carmen",
                "extract_model": "gpt-4.1",
            },
        )
        out = handle_fetch(event)
    assert out is not None
    assert out.stage == "transcript"
    assert out.payload.get("source_type") == "youtube_kg"
    assert out.payload.get("destination_hint") == "Playa del Carmen"
    assert out.payload.get("extract_model") == "gpt-4.1"
    assert out.payload.get("segments") == fake_segments


def test_youtube_kg_transcript_chunks() -> None:
    """handle_transcript for youtube_kg emits ChunksReady with chunks and extract_model."""
    reset_processed()
    segments = [{"start": 0, "duration": 10, "text": "First."}, {"start": 10, "duration": 10, "text": "Second."}]
    meta = {"id": "v1", "title": "T", "channel": "C", "upload_date": None, "webpage_url": "https://youtube.com/watch?v=v1"}
    event = TranscriptReady(
        event_id="e1",
        content_source_id="youtube_kg:v1",
        stage="transcript",
        payload={
            "source_type": "youtube_kg",
            "segments": segments,
            "lang": "pt",
            "video_metadata": meta,
            "destination_hint": "Barcelona",
            "extract_model": "gpt-4.1",
        },
    )
    out = handle_transcript(event)
    assert out is not None
    assert out.stage == "chunks"
    assert out.payload.get("source_type") == "youtube_kg"
    assert out.payload.get("destination_hint") == "Barcelona"
    assert out.payload.get("extract_model") == "gpt-4.1"
    assert len(out.payload.get("chunks", [])) >= 1


def test_youtube_kg_chunk_extraction_mocked() -> None:
    """handle_chunk for youtube_kg calls extract_graph_from_chunk and emits EnrichmentReady with graph_extractions."""
    reset_processed()
    chunks = [
        {"startSec": 0, "endSec": 60, "text": "a" * 200},
    ]
    meta = {"id": "v1", "title": "T", "channel": "C", "upload_date": None, "webpage_url": "https://youtube.com/watch?v=v1"}
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
        with patch("app.sources.graph.extract_graph_from_chunk") as m_extract:
            m_extract.return_value = GraphExtraction(
                nodes=[GraphNode(id="poi:sagrada", type="poi", name="Sagrada Família")],
                edges=[
                    GraphEdge(
                        source="poi:sagrada",
                        type="IN_AREA",
                        target="place:eixample",
                        evidence=Evidence(
                            videoUrl="https://youtube.com/watch?v=v1",
                            startSec=0,
                            endSec=60,
                            chunkIdx=1,
                            timestampUrl="https://youtube.com/watch?v=v1?t=0s",
                        ),
                    ),
                ],
            )
            event = ChunksReady(
                event_id="e1",
                content_source_id="youtube_kg:v1",
                stage="chunks",
                payload={
                    "source_type": "youtube_kg",
                    "chunks": chunks,
                    "video_metadata": meta,
                    "destination_hint": "Barcelona",
                    "extract_model": "gpt-4.1",
                },
            )
            out = handle_chunk(event)
    assert out is not None
    assert out.stage == "enrichment"
    assert out.payload.get("source_type") == "youtube_kg"
    extractions = out.payload.get("graph_extractions") or []
    assert len(extractions) == 1
    assert extractions[0]["nodes"][0]["id"] == "poi:sagrada"
    assert len(extractions[0]["edges"]) == 1


def test_youtube_kg_enrich_merge_emits_embeddings() -> None:
    """handle_enrich for youtube_kg merges graph_extractions and emits EmbeddingsReady with graph."""
    reset_processed()
    extractions = [
        GraphExtraction(
            nodes=[GraphNode(id="poi:a", type="poi", name="A")],
            edges=[
                GraphEdge(
                    source="poi:a",
                    type="IN_AREA",
                    target="city:b",
                    evidence=Evidence(
                        videoUrl="https://youtube.com/watch?v=v1",
                        startSec=0,
                        endSec=30,
                        chunkIdx=1,
                        timestampUrl="https://youtube.com/watch?v=v1?t=0s",
                    ),
                ),
            ],
        ).model_dump(),
    ]
    event = EnrichmentReady(
        event_id="e1",
        content_source_id="youtube_kg:v1",
        stage="enrichment",
        payload={
            "source_type": "youtube_kg",
            "graph_extractions": extractions,
            "video_metadata": {"id": "v1", "title": "T", "channel": "C", "webpage_url": "https://youtube.com/watch?v=v1"},
            "lang": "pt",
            "destination_hint": "Barcelona",
            "extract_model": "gpt-4.1",
        },
    )
    out = handle_enrich(event)
    assert out is not None
    assert out.stage == "embeddings"
    assert out.payload.get("source_type") == "youtube_kg"
    graph = out.payload.get("graph") or {}
    assert "nodes" in graph
    assert "edges" in graph
    assert "meta" in graph
    assert graph["meta"]["videoUrl"] == "https://youtube.com/watch?v=v1"
    assert len(graph["nodes"]) == 1
    assert len(graph["edges"]) == 1


def test_youtube_kg_write_mocked() -> None:
    """handle_write for youtube_kg calls ingest_into_neo4j with graph."""
    reset_processed()
    graph = {
        "nodes": [{"id": "poi:a", "type": "poi", "name": "A", "aliases": [], "properties": {}}],
        "edges": [
            {
                "source": "poi:a",
                "type": "IN_AREA",
                "target": "city:b",
                "properties": {},
                "evidence": {"videoUrl": "u", "startSec": 0, "endSec": 30, "chunkIdx": 1, "timestampUrl": "u?t=0s"},
            },
        ],
    }
    event = WriteComplete(
        event_id="e1",
        content_source_id="youtube_kg:v1",
        stage="write_complete",
        payload={"source_type": "youtube_kg", "graph": graph},
    )
    with patch("app.sources.graph.ingest_into_neo4j") as m_ingest:
        handle_write(event)
        m_ingest.assert_called_once()
        call_arg = m_ingest.call_args[0][0]
        assert call_arg["nodes"] == graph["nodes"]
        assert call_arg["edges"] == graph["edges"]


def test_merge_graph_dedup_nodes_and_edges() -> None:
    """merge_graph deduplicates nodes by id and edges by (type, source, target, startSec, endSec)."""
    ev1 = Evidence(videoUrl="u", startSec=0, endSec=30, chunkIdx=1, timestampUrl="u?t=0s")
    ev2 = Evidence(videoUrl="u", startSec=30, endSec=60, chunkIdx=2, timestampUrl="u?t=30s")
    ex1 = GraphExtraction(
        nodes=[GraphNode(id="poi:a", type="poi", name="A", aliases=["A1"])],
        edges=[GraphEdge(source="poi:a", type="IN_AREA", target="city:b", evidence=ev1)],
    )
    ex2 = GraphExtraction(
        nodes=[GraphNode(id="poi:a", type="poi", name="A", aliases=["A2"])],
        edges=[
            GraphEdge(source="poi:a", type="IN_AREA", target="city:b", evidence=ev1),
            GraphEdge(source="poi:a", type="IN_AREA", target="city:b", evidence=ev2),
        ],
    )
    merged = merge_graph([ex1, ex2])
    assert len(merged["nodes"]) == 1
    assert set(merged["nodes"][0]["aliases"]) == {"A1", "A2"}
    assert len(merged["edges"]) == 2
