"""Phase 7 audio MCP integration tests: STT/TTS config, client, routing, eval."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.main import _infer_voice_mode, _build_spoken_version, run_pipeline_raw
from app.mcp_client import MCPConfig, transcribe, synthesize


def test_infer_voice_mode_normal() -> None:
    """Planning keywords → normal mode."""
    assert _infer_voice_mode("suggest a 3-day itinerary") == "normal"
    assert _infer_voice_mode("compare hotels in Orlando") == "normal"
    assert _infer_voice_mode("") == "normal"


def test_infer_voice_mode_quick() -> None:
    """Urgency keywords → quick mode."""
    assert _infer_voice_mode("urgent, quick answer") == "quick"
    assert _infer_voice_mode("fast response now") == "quick"


def test_build_spoken_version_truncates() -> None:
    """Long text is truncated by word count."""
    long_text = " ".join(["word"] * 100)
    out = _build_spoken_version(long_text, "quick")
    assert len(out.split()) <= 26  # 25 + potential final word
    out_normal = _build_spoken_version(long_text, "normal")
    assert len(out_normal.split()) <= 61


def test_build_spoken_version_short_passthrough() -> None:
    """Short text passes through unchanged."""
    short = "Best time is November."
    assert _build_spoken_version(short, "normal") == short


def test_mcp_config_from_env_stt_tts_urls() -> None:
    """STT_MCP_URL and TTS_MCP_URL overrides are applied."""
    with patch.dict(
        "os.environ",
        {"STT_MCP_URL": "http://stt:8033", "TTS_MCP_URL": "http://tts:8034"},
        clear=False,
    ):
        cfg = MCPConfig.from_env()
    assert cfg.stt_base_url == "http://stt:8033"
    assert cfg.tts_base_url == "http://tts:8034"


@pytest.mark.asyncio
async def test_transcribe_client_mock() -> None:
    """transcribe POSTs to correct path and returns JSON (mocked HTTP)."""
    mock_response = {
        "x_contract_version": "1.0",
        "request": {"audio_ref": "data:audio/mp3;base64,x", "language": "en"},
        "transcript": "What to pack for Orlando?",
        "language": "en",
        "confidence": 0.95,
    }

    async def post(*args, **kwargs):
        assert "/mcp/transcribe" in args[0]
        body = kwargs.get("json") or {}
        assert body.get("x_contract_version") == "1.0"
        assert "request" in body
        assert body["request"].get("audio_ref")
        resp = AsyncMock()
        resp.raise_for_status = lambda: None
        resp.json = lambda: mock_response
        return resp

    client = AsyncMock()
    client.post = post
    out = await transcribe(
        client,
        "http://localhost:8033",
        {"audio_ref": "data:audio/mp3;base64,x", "language": "en"},
    )
    assert out["x_contract_version"] == "1.0"
    assert out["transcript"] == "What to pack for Orlando?"


@pytest.mark.asyncio
async def test_synthesize_client_mock() -> None:
    """synthesize POSTs to correct path and returns JSON (mocked HTTP)."""
    mock_response = {
        "x_contract_version": "1.0",
        "request": {"text": "Hello", "language": "en"},
        "audio_ref": "data:audio/mp3;base64,abc123",
        "format": "mp3",
    }

    async def post(*args, **kwargs):
        assert "/mcp/synthesize" in args[0]
        body = kwargs.get("json") or {}
        assert body.get("x_contract_version") == "1.0"
        assert body.get("request", {}).get("text")
        resp = AsyncMock()
        resp.raise_for_status = lambda: None
        resp.json = lambda: mock_response
        return resp

    client = AsyncMock()
    client.post = post
    out = await synthesize(
        client,
        "http://localhost:8034",
        {"text": "Hello", "language": "en"},
    )
    assert out["x_contract_version"] == "1.0"
    assert out["audio_ref"].startswith("data:audio/")


@pytest.mark.asyncio
async def test_pipeline_calls_stt_when_audio_ref() -> None:
    """With audio_ref, STT is called and transcript used as user_query."""
    valid_evidence = {
        "x_contract_version": "1.0",
        "request": {"user_query": "x"},
        "evidence": [
            {
                "card_id": "evid_001",
                "summary": "Best time is November.",
                "signals": [],
                "places": [],
                "categories": ["tips"],
                "primary_category": "tips",
                "confidence": 0.9,
                "source_url": "https://example.com/tips",
            },
        ],
    }
    empty_products = {
        "x_contract_version": "1.0",
        "request": {"query_signature": "orlando:pack:en", "destination": None, "lang": None},
        "candidates": [],
    }
    stt_response = {
        "x_contract_version": "1.0",
        "request": {"audio_ref": "data:audio/mp3;base64,x", "language": "en"},
        "transcript": "what is the best time to visit Orlando?",
        "language": "en",
    }

    with (
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock, return_value=valid_evidence),
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock, return_value=empty_products),
        patch("app.main.retrieve_travel_graph", new_callable=AsyncMock),
        patch("app.main.analyze_image", new_callable=AsyncMock),
        patch("app.main.transcribe", new_callable=AsyncMock, return_value=stt_response) as m_stt,
    ):
        raw = await run_pipeline_raw(
            "s1",
            "r1",
            "fallback",
            destination="Orlando",
            audio_ref="data:audio/mp3;base64,x",
            lang="en",
        )
    m_stt.assert_called_once()
    assert "November" in raw["answer_text"]  # Answer reflects transcript query
    assert "best time" in raw["answer_text"].lower() or "November" in raw["answer_text"]


@pytest.mark.asyncio
async def test_pipeline_no_stt_without_audio_ref() -> None:
    """Without audio_ref, STT is not called."""
    valid_evidence = {
        "x_contract_version": "1.0",
        "request": {"user_query": "x"},
        "evidence": [
            {
                "card_id": "evid_001",
                "summary": "Best time is November.",
                "signals": [],
                "places": [],
                "categories": ["tips"],
                "primary_category": "tips",
                "confidence": 0.9,
                "source_url": "https://example.com/tips",
            },
        ],
    }
    empty_products = {
        "x_contract_version": "1.0",
        "request": {"query_signature": "orlando:pack:en", "destination": None, "lang": None},
        "candidates": [],
    }

    with (
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock, return_value=valid_evidence),
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock, return_value=empty_products),
        patch("app.main.retrieve_travel_graph", new_callable=AsyncMock),
        patch("app.main.analyze_image", new_callable=AsyncMock),
        patch("app.main.transcribe", new_callable=AsyncMock) as m_stt,
    ):
        await run_pipeline_raw(
            "s2",
            "r2",
            "what to pack?",
            destination="Orlando",
        )
    m_stt.assert_not_called()


@pytest.mark.asyncio
async def test_voice_mode_includes_audio_ref_from_tts() -> None:
    """When voice_mode=True, TTS is called and response includes audio_ref."""
    valid_evidence = {
        "x_contract_version": "1.0",
        "request": {"user_query": "x"},
        "evidence": [
            {
                "card_id": "evid_001",
                "summary": "Best time is November.",
                "signals": [],
                "places": [],
                "categories": ["tips"],
                "primary_category": "tips",
                "confidence": 0.9,
                "source_url": "https://example.com/tips",
            },
        ],
    }
    empty_products = {
        "x_contract_version": "1.0",
        "request": {"query_signature": "orlando:pack:en", "destination": None, "lang": None},
        "candidates": [],
    }
    tts_response = {
        "x_contract_version": "1.0",
        "request": {"text": "Best time is November.", "language": "en"},
        "audio_ref": "data:audio/mp3;base64,xyz789",
        "format": "mp3",
    }

    with (
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock, return_value=valid_evidence),
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock, return_value=empty_products),
        patch("app.main.retrieve_travel_graph", new_callable=AsyncMock),
        patch("app.main.analyze_image", new_callable=AsyncMock),
        patch("app.main.synthesize", new_callable=AsyncMock, return_value=tts_response) as m_tts,
    ):
        raw = await run_pipeline_raw(
            "s3",
            "r3",
            "best time to visit?",
            destination="Orlando",
            voice_mode=True,
        )
    m_tts.assert_called_once()
    assert raw.get("audio_ref") == "data:audio/mp3;base64,xyz789"
    assert "spoken_version" in raw
    assert "screen_summary" in raw


@pytest.mark.asyncio
async def test_text_only_mode_no_tts_call() -> None:
    """Without voice_mode, TTS is not called."""
    valid_evidence = {
        "x_contract_version": "1.0",
        "request": {"user_query": "x"},
        "evidence": [
            {
                "card_id": "evid_001",
                "summary": "Best time is November.",
                "signals": [],
                "places": [],
                "categories": ["tips"],
                "primary_category": "tips",
                "confidence": 0.9,
                "source_url": "https://example.com/tips",
            },
        ],
    }
    empty_products = {
        "x_contract_version": "1.0",
        "request": {"query_signature": "orlando:pack:en", "destination": None, "lang": None},
        "candidates": [],
    }

    with (
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock, return_value=valid_evidence),
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock, return_value=empty_products),
        patch("app.main.retrieve_travel_graph", new_callable=AsyncMock),
        patch("app.main.analyze_image", new_callable=AsyncMock),
        patch("app.main.synthesize", new_callable=AsyncMock) as m_tts,
    ):
        raw = await run_pipeline_raw(
            "s4",
            "r4",
            "best time?",
            destination="Orlando",
            voice_mode=False,
        )
    m_tts.assert_not_called()
    assert "audio_ref" not in raw


@pytest.mark.asyncio
async def test_eval_row_includes_audio_fields(tmp_path: Path) -> None:
    """Eval runner row has latency_ms_stt, latency_ms_tts, audio_included when voice mode used."""
    from app.eval_runner import _load_eval_schema, _validate_row, run

    valid_evidence = {
        "x_contract_version": "1.0",
        "request": {"user_query": "x"},
        "evidence": [
            {
                "card_id": "evid_001",
                "summary": "Best time is November.",
                "signals": [],
                "places": [],
                "categories": ["tips"],
                "primary_category": "tips",
                "confidence": 0.9,
                "source_url": "https://example.com/tips",
            },
        ],
    }
    empty_products = {
        "x_contract_version": "1.0",
        "request": {"query_signature": "orlando:pack:en", "destination": None, "lang": None},
        "candidates": [],
    }
    tts_response = {
        "x_contract_version": "1.0",
        "request": {"text": "x", "language": "en"},
        "audio_ref": "data:audio/mp3;base64,abc",
        "format": "mp3",
    }

    queries_file = tmp_path / "queries_voice.json"
    queries_file.write_text(
        json.dumps([
            {
                "user_query": "best time to visit Orlando?",
                "destination": "Orlando",
                "voice_mode": True,
            },
        ]),
        encoding="utf-8",
    )
    out_file = tmp_path / "run_voice.jsonl"

    with (
        patch.dict("os.environ", {"TEST_QUERIES_FILE": str(queries_file)}),
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock, return_value=valid_evidence),
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock, return_value=empty_products),
        patch("app.main.retrieve_travel_graph", new_callable=AsyncMock),
        patch("app.main.analyze_image", new_callable=AsyncMock),
        patch("app.main.synthesize", new_callable=AsyncMock, return_value=tts_response),
    ):
        await run(out_file)

    schema = _load_eval_schema()
    row = json.loads(out_file.read_text(encoding="utf-8").strip().split("\n")[0])
    _validate_row(row, schema)
    assert "latency_ms_stt" in row
    assert "latency_ms_tts" in row
    assert row["audio_included"] is True
