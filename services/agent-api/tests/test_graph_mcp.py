"""Phase 5 graph MCP integration tests: config, client, routing, answer merge, eval."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.main import (
    _build_answer_and_citations,
    _should_call_graph,
    run_pipeline_raw,
)
from app.mcp_client import MCPConfig, retrieve_travel_graph


def test_should_call_graph_itinerary_queries() -> None:
    """Itinerary/route keywords trigger graph MCP."""
    assert _should_call_graph("suggest a 3-day itinerary for Orlando") is True
    assert _should_call_graph("roteiro de 5 dias em Orlando") is True
    assert _should_call_graph("what to do first in Disney?") is True
    assert _should_call_graph("order of visits for Magic Kingdom") is True
    assert _should_call_graph("day 1 and day 2 in Orlando") is True


def test_should_call_graph_non_itinerary_queries() -> None:
    """General/hotel queries do not trigger graph MCP."""
    assert _should_call_graph("best hotels in Orlando") is False
    assert _should_call_graph("dicas para Disney") is False
    assert _should_call_graph("what's the weather in Orlando?") is False


def test_build_answer_and_citations_with_graph_paths() -> None:
    """Graph paths and evidence merge into answer text and citations (timestampUrl)."""
    evidence = [
        {"summary": "Morning is best.", "source_url": "https://example.com/v1"},
    ]
    graph_response = {
        "subgraph": {
            "nodes": [
                {"id": "day1", "type": "dayplan", "name": "Day 1"},
                {"id": "poi_a", "type": "poi", "name": "Magic Kingdom"},
            ],
            "edges": [
                {
                    "source": "day1",
                    "type": "INCLUDES_POI",
                    "target": "poi_a",
                    "evidence": {
                        "videoUrl": "https://youtube.com/watch?v=x",
                        "timestampUrl": "https://youtube.com/watch?v=x&t=120",
                        "startSec": 120,
                        "endSec": 180,
                    },
                },
            ],
        },
        "paths": [
            {
                "path_id": "p1",
                "label": "Day 1",
                "nodes": ["day1", "poi_a"],
                "edges": [],
                "evidence": [
                    {
                        "videoUrl": "https://youtube.com/watch?v=x",
                        "timestampUrl": "https://youtube.com/watch?v=x&t=120",
                        "startSec": 120,
                        "endSec": 180,
                    },
                ],
            },
        ],
    }
    answer, citations = _build_answer_and_citations(evidence, graph_response)
    assert "Morning is best." in answer
    assert "Day 1" in answer
    assert "Magic Kingdom" in answer
    assert "https://example.com/v1" in citations
    assert "https://youtube.com/watch?v=x&t=120" in citations


def test_mcp_config_from_env_graph_url() -> None:
    """GRAPH_MCP_URL override is applied in from_env."""
    with patch.dict("os.environ", {"GRAPH_MCP_URL": "http://graph:8031"}, clear=False):
        cfg = MCPConfig.from_env()
    assert cfg.graph_base_url == "http://graph:8031"


@pytest.mark.asyncio
async def test_retrieve_travel_graph_client_mock() -> None:
    """retrieve_travel_graph POSTs to correct path and returns JSON (mocked HTTP)."""
    mock_response = {
        "x_contract_version": "1.0",
        "request": {"user_query": "itinerary Orlando"},
        "subgraph": {"nodes": [], "edges": []},
        "paths": None,
    }

    async def post(*args, **kwargs):
        assert "/mcp/retrieve_travel_graph" in args[0]
        body = kwargs.get("json") or {}
        assert body.get("x_contract_version") == "1.0"
        assert "request" in body
        resp = AsyncMock()
        resp.raise_for_status = lambda: None
        resp.json = lambda: mock_response
        return resp

    client = AsyncMock()
    client.post = post
    out = await retrieve_travel_graph(client, "http://localhost:8031", {"user_query": "itinerary Orlando"})
    assert out["x_contract_version"] == "1.0"
    assert "subgraph" in out
    assert out["subgraph"]["nodes"] == []


@pytest.mark.asyncio
async def test_pipeline_calls_graph_for_itinerary_not_for_hotels() -> None:
    """Itinerary query calls graph MCP; hotels query does not."""
    valid_evidence = {
        "x_contract_version": "1.0",
        "request": {"user_query": "x"},
        "evidence": [
            {
                "card_id": "evid_001_tips",
                "summary": "Best times to visit are early morning.",
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
        "request": {"query_signature": "orlando:itinerary:en", "destination": None, "lang": None},
        "candidates": [],
    }
    valid_graph = {
        "x_contract_version": "1.0",
        "request": {"user_query": "suggest a 3-day itinerary for Orlando"},
        "subgraph": {"nodes": [{"id": "n1", "type": "city", "name": "Orlando"}], "edges": []},
        "paths": [],
    }
    timing: dict = {}

    with (
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock, return_value=valid_evidence),
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock, return_value=empty_products),
        patch("app.main.retrieve_travel_graph", new_callable=AsyncMock, return_value=valid_graph) as m_graph,
    ):
        await run_pipeline_raw(
            "s1", "r1", "suggest a 3-day itinerary for Orlando",
            destination="Orlando", timing_out=timing,
        )
    m_graph.assert_called_once()
    assert timing.get("graph_ms", 0) >= 0

    with (
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock, return_value=valid_evidence),
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock, return_value=empty_products),
        patch("app.main.retrieve_travel_graph", new_callable=AsyncMock, return_value=valid_graph) as m_graph,
    ):
        await run_pipeline_raw(
            "s2", "r2", "best hotels in Orlando",
            destination="Orlando", timing_out=timing,
        )
    m_graph.assert_not_called()


@pytest.mark.asyncio
async def test_eval_row_includes_latency_graph_and_graph_included(tmp_path) -> None:
    """Eval runner row has latency_ms_graph and graph_included when graph is called."""
    import json

    from app.eval_runner import _load_eval_schema, _validate_row, run

    valid_evidence = {
        "x_contract_version": "1.0",
        "request": {"user_query": "x"},
        "evidence": [
            {
                "card_id": "evid_001_tips",
                "summary": "Best times to visit are early morning.",
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
        "request": {"query_signature": "orlando:itinerary:en", "destination": None, "lang": None},
        "candidates": [],
    }
    valid_graph = {
        "x_contract_version": "1.0",
        "request": {"user_query": "suggest a 3-day itinerary for Orlando"},
        "subgraph": {"nodes": [], "edges": []},
        "paths": None,
    }

    queries_file = tmp_path / "queries.json"
    queries_file.write_text(
        json.dumps([{"user_query": "suggest a 3-day itinerary for Orlando", "destination": "Orlando"}]),
        encoding="utf-8",
    )
    out_file = tmp_path / "run.jsonl"

    with (
        patch.dict("os.environ", {"TEST_QUERIES_JSON": queries_file.read_text()}),
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock, return_value=valid_evidence),
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock, return_value=empty_products),
        patch("app.main.retrieve_travel_graph", new_callable=AsyncMock, return_value=valid_graph),
    ):
        await run(out_file)

    schema = _load_eval_schema()
    row = json.loads(out_file.read_text(encoding="utf-8").strip().split("\n")[0])
    _validate_row(row, schema)
    assert row["graph_included"] is True
    assert row["latency_ms_graph"] >= 0
