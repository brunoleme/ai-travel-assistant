"""Phase 6 vision MCP integration tests: config, client, routing, answer merge, eval."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.main import (
    _build_answer_and_citations,
    _get_packing_gap_query,
    _infer_vision_mode,
    run_pipeline_raw,
)
from app.mcp_client import MCPConfig, analyze_image


def test_infer_vision_mode_packing() -> None:
    """Packing keywords or default -> packing."""
    assert _infer_vision_mode("what to pack for Orlando") == "packing"
    assert _infer_vision_mode("outfit for summer trip") == "packing"
    assert _infer_vision_mode("malas para Disney") == "packing"
    assert _infer_vision_mode("") == "packing"


def test_infer_vision_mode_landmark() -> None:
    """Landmark keywords -> landmark."""
    assert _infer_vision_mode("where is this place?") == "landmark"
    assert _infer_vision_mode("que lugar é esse?") == "landmark"
    assert _infer_vision_mode("what landmark is this") == "landmark"


def test_infer_vision_mode_product_similarity() -> None:
    """Product similarity keywords -> product_similarity."""
    assert _infer_vision_mode("find one like this") == "product_similarity"
    assert _infer_vision_mode("parecido com isso") == "product_similarity"
    assert _infer_vision_mode("similar product") == "product_similarity"


def test_build_answer_and_citations_with_vision_packing() -> None:
    """Packing signals merge into answer (detected + missing)."""
    evidence = []
    vision_response = {
        "signals": {
            "mode": "packing",
            "confidence": 0.9,
            "detected_items": ["light_top", "walking_shoes"],
            "missing_categories": ["rain_jacket", "umbrella"],
        },
    }
    answer, citations = _build_answer_and_citations(
        evidence, None, vision_response, {"destination": "Orlando"}
    )
    assert "light_top" in answer or "walking_shoes" in answer
    assert "rain_jacket" in answer or "umbrella" in answer
    assert "Consider adding" in answer


def test_build_answer_and_citations_with_vision_packing_suitability() -> None:
    """Outfit suitability: suitability_ok False + suitability_issue and suggested_categories appear in answer."""
    evidence = []
    vision_response = {
        "signals": {
            "mode": "packing",
            "confidence": 0.85,
            "suitability_ok": False,
            "suitability_issue": "Too light for Disney in winter.",
            "detected_items": ["light_top", "long_pants"],
            "suggested_categories_for_products": ["warm_top", "insulated_jacket"],
        },
    }
    answer, _ = _build_answer_and_citations(
        evidence, None, vision_response, {"destination": "Orlando"}
    )
    assert "not be ideal" in answer or "suitable" in answer.lower()
    assert "Too light" in answer or "winter" in answer
    assert "warm_top" in answer or "insulated_jacket" in answer


def test_get_packing_gap_query_uses_suggested_categories_when_not_suitable() -> None:
    """Product query uses suggested_categories_for_products when suitability_ok is False."""
    ctx = {"destination": "Orlando"}
    # No critical gap in missing; suggested categories + not suitable -> use first suggested
    q = _get_packing_gap_query(
        missing_categories=[],
        trip_context=ctx,
        suggested_categories_for_products=["rain_jacket", "umbrella"],
        suitability_ok=False,
    )
    assert q == "Orlando:rain_jacket:en"


def test_build_answer_and_citations_with_vision_landmark() -> None:
    """Landmark signals -> place guess and follow-up."""
    evidence = []
    vision_response = {
        "signals": {
            "mode": "landmark",
            "confidence": 0.85,
            "scene_type": "theme_park",
            "place_candidates": [
                {"place_name": "Magic Kingdom", "confidence": 0.9, "reason": "castle"},
            ],
        },
    }
    answer, citations = _build_answer_and_citations(
        evidence, None, vision_response, None
    )
    assert "Magic Kingdom" in answer
    assert "dicas" in answer or "dicas" in answer.lower() or "Quer" in answer


def test_build_answer_and_citations_with_vision_product_similarity() -> None:
    """Product_similarity signals -> category and attributes."""
    evidence = []
    vision_response = {
        "signals": {
            "mode": "product_similarity",
            "confidence": 0.8,
            "category": "day_bag",
            "attributes": {"color": "black", "size": "medium"},
            "style_keywords": ["minimal"],
        },
    }
    answer, citations = _build_answer_and_citations(
        evidence, None, vision_response, None
    )
    assert "day_bag" in answer or "Produtos similares" in answer


def test_mcp_config_from_env_vision_url() -> None:
    """VISION_MCP_URL override is applied in from_env."""
    with patch.dict("os.environ", {"VISION_MCP_URL": "http://vision:8032"}, clear=False):
        cfg = MCPConfig.from_env()
    assert cfg.vision_base_url == "http://vision:8032"


@pytest.mark.asyncio
async def test_analyze_image_client_mock() -> None:
    """analyze_image POSTs to correct path and returns JSON (mocked HTTP)."""
    mock_response = {
        "x_contract_version": "1.0",
        "request": {"image_ref": "data:image/jpeg;base64,...", "mode": "packing"},
        "signals": {"mode": "packing", "confidence": 0.9, "detected_items": [], "missing_categories": []},
    }

    async def post(*args, **kwargs):
        assert "/mcp/analyze_image" in args[0]
        body = kwargs.get("json") or {}
        assert body.get("x_contract_version") == "1.0"
        assert "request" in body
        resp = AsyncMock()
        resp.raise_for_status = lambda: None
        resp.json = lambda: mock_response
        return resp

    client = AsyncMock()
    client.post = post
    out = await analyze_image(
        client, "http://localhost:8032",
        {"image_ref": "data:image/jpeg;base64,...", "mode": "packing"},
    )
    assert out["x_contract_version"] == "1.0"
    assert out["signals"]["mode"] == "packing"


@pytest.mark.asyncio
async def test_pipeline_calls_vision_with_image_ref_not_without() -> None:
    """With image_ref vision MCP is called; without image_ref it is not."""
    valid_evidence = {
        "x_contract_version": "1.0",
        "request": {"user_query": "x"},
        "evidence": [
            {
                "card_id": "evid_001_tips",
                "summary": "Best times to visit are early morning.",
                "signals": [], "places": [], "categories": ["tips"],
                "primary_category": "tips", "confidence": 0.9,
                "source_url": "https://example.com/tips",
            },
        ],
    }
    empty_products = {
        "x_contract_version": "1.0",
        "request": {"query_signature": "orlando:pack:en", "destination": None, "lang": None},
        "candidates": [],
    }
    valid_vision = {
        "x_contract_version": "1.0",
        "request": {"image_ref": "data:image/jpeg;base64,abc", "mode": "packing"},
        "signals": {"mode": "packing", "confidence": 0.9, "detected_items": ["light_top"], "missing_categories": []},
    }
    timing: dict = {}

    with (
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock, return_value=valid_evidence),
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock, return_value=empty_products),
        patch("app.main.analyze_image", new_callable=AsyncMock, return_value=valid_vision) as m_vision,
    ):
        await run_pipeline_raw(
            "s1", "r1", "what to pack?",
            destination="Orlando", image_ref="data:image/jpeg;base64,abc",
            timing_out=timing,
        )
    m_vision.assert_called_once()
    assert timing.get("vision_ms", 0) >= 0

    with (
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock, return_value=valid_evidence),
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock, return_value=empty_products),
        patch("app.main.analyze_image", new_callable=AsyncMock, return_value=valid_vision) as m_vision,
    ):
        await run_pipeline_raw(
            "s2", "r2", "what to pack?",
            destination="Orlando", timing_out=timing,
        )
    m_vision.assert_not_called()


@pytest.mark.asyncio
async def test_eval_row_includes_vision_fields(tmp_path) -> None:
    """Eval runner row has latency_ms_vision, vision_included, vision_mode when vision called."""
    import json

    from app.eval_runner import _load_eval_schema, _validate_row, run

    valid_evidence = {
        "x_contract_version": "1.0",
        "request": {"user_query": "x"},
        "evidence": [
            {
                "card_id": "evid_001_tips",
                "summary": "Best times to visit are early morning.",
                "signals": [], "places": [], "categories": ["tips"],
                "primary_category": "tips", "confidence": 0.9,
                "source_url": "https://example.com/tips",
            },
        ],
    }
    empty_products = {
        "x_contract_version": "1.0",
        "request": {"query_signature": "orlando:pack:en", "destination": None, "lang": None},
        "candidates": [],
    }
    valid_vision = {
        "x_contract_version": "1.0",
        "request": {"image_ref": "data:image/jpeg;base64,x", "mode": "packing"},
        "signals": {"mode": "packing", "confidence": 0.9, "detected_items": [], "missing_categories": []},
    }

    queries_file = tmp_path / "queries.json"
    queries_file.write_text(
        json.dumps([
            {
                "user_query": "what to pack for Orlando?",
                "destination": "Orlando",
                "image_ref": "data:image/jpeg;base64,abc",
            },
        ]),
        encoding="utf-8",
    )
    out_file = tmp_path / "run.jsonl"

    with (
        patch.dict("os.environ", {"TEST_QUERIES_JSON": queries_file.read_text()}),
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock, return_value=valid_evidence),
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock, return_value=empty_products),
        patch("app.main.retrieve_travel_graph", new_callable=AsyncMock),
        patch("app.main.analyze_image", new_callable=AsyncMock, return_value=valid_vision),
    ):
        await run(out_file)

    schema = _load_eval_schema()
    row = json.loads(out_file.read_text(encoding="utf-8").strip().split("\n")[0])
    _validate_row(row, schema)
    assert row["vision_included"] is True
    assert row["latency_ms_vision"] >= 0
    assert row["vision_mode"] == "packing"
