"""Eval runner tests (TDD, no network)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.eval_runner import _load_eval_schema, _validate_row, run

FIXED_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
FIXED_TS = "2025-02-05T12:00:00.000000+00:00"

VALID_EVIDENCE = {
    "x_contract_version": "1.0",
    "request": {"user_query": "dicas"},
    "evidence": [
        {
            "card_id": "evid_001_tips",
            "summary": "Best times to visit are early morning.",
            "signals": [],
            "places": [],
            "categories": [],
            "primary_category": "tips",
            "confidence": 0.9,
            "source_url": "https://example.com/tips",
        },
    ],
}

EMPTY_PRODUCTS = {
    "x_contract_version": "1.0",
    "request": {"query_signature": "orlando:dicas:en"},
    "candidates": [],
}


@pytest.fixture
def mock_mcp():
    """Patch MCP calls to return fixed responses."""
    with (
        patch("app.main.retrieve_travel_evidence", new_callable=AsyncMock) as m_ev,
        patch("app.main.retrieve_product_candidates", new_callable=AsyncMock) as m_prod,
    ):
        m_ev.return_value = VALID_EVIDENCE
        m_prod.return_value = EMPTY_PRODUCTS
        yield m_ev, m_prod


@pytest.fixture
def mock_time_and_uuid():
    """Patch time and uuid for determinism."""
    counter = [0.0]

    def perf_counter():
        v = counter[0]
        counter[0] += 0.001
        return v

    with (
        patch("app.main.time.perf_counter", side_effect=perf_counter),
        patch("app.eval_runner.datetime") as m_dt,
    ):
        m_dt.now.return_value = datetime(2025, 2, 5, 12, 0, 0, tzinfo=timezone.utc)
        yield


def _uuid4_hex_side_effect():
    count = [0]

    def fn():
        count[0] += 1
        return type("U", (), {"hex": lambda s: hex(count[0])[2:].zfill(8)[:8]})()

    return fn


def _make_uuid(hex_val: str = "deadbeef"):
    return type("U", (), {"hex": hex_val, "__str__": lambda s: f"{hex_val}-0000-0000-0000-000000000000"})()


def test_eval_runner_writes_valid_jsonl_rows(mock_mcp, mock_time_and_uuid, tmp_path):
    """Runs runner over 2 test queries; output has 2 lines, each validates against schema."""
    queries_file = tmp_path / "queries.json"
    queries_file.write_text(
        json.dumps([
            {"user_query": "dicas Disney", "destination": "Orlando"},
            {"user_query": "best hotels Paris", "destination": "Paris"},
        ]),
        encoding="utf-8",
    )
    out_file = tmp_path / "run.jsonl"

    with (
        patch.dict("os.environ", {"TEST_QUERIES_JSON": queries_file.read_text()}),
        patch("app.eval_runner.uuid.uuid4", side_effect=lambda: _make_uuid("deadbeef")),
    ):
        import asyncio
        asyncio.run(run(out_file))

    lines = out_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    schema = _load_eval_schema()
    for line in lines:
        row = json.loads(line)
        _validate_row(row, schema)
        assert "run_id" in row
        assert "user_query" in row
        assert "latency_ms_total" in row
        assert "response_snapshot" in row


def test_eval_runner_deterministic_with_mocks(mock_mcp, mock_time_and_uuid, tmp_path):
    """Two runs with same mocks produce identical rows except for run_id."""
    queries_file = tmp_path / "queries.json"
    queries_file.write_text(
        json.dumps([{"user_query": "dicas Disney"}]),
        encoding="utf-8",
    )
    out1 = tmp_path / "run1.jsonl"
    out2 = tmp_path / "run2.jsonl"

    counter = [0]

    def uuid4_mock():
        counter[0] += 1
        h = hex(counter[0])[2:].zfill(8)
        return type("U", (), {"hex": h, "__str__": lambda s: f"{h}-0000-0000-0000-000000000000"})()

    with (
        patch.dict("os.environ", {"TEST_QUERIES_JSON": queries_file.read_text()}),
        patch("app.eval_runner.uuid.uuid4", side_effect=uuid4_mock),
    ):
        import asyncio
        asyncio.run(run(out1))

    with (
        patch.dict("os.environ", {"TEST_QUERIES_JSON": queries_file.read_text()}),
        patch("app.eval_runner.uuid.uuid4", side_effect=uuid4_mock),
    ):
        import asyncio
        asyncio.run(run(out2))

    row1 = json.loads(out1.read_text().strip().split("\n")[0])
    row2 = json.loads(out2.read_text().strip().split("\n")[0])

    # run_id, session_id, request_id, ts can differ; everything else identical
    skip = {"run_id", "session_id", "request_id", "ts"}
    for key in row1:
        if key in skip:
            continue
        v1, v2 = row1[key], row2[key]
        if isinstance(v1, float) and isinstance(v2, float):
            assert v1 == pytest.approx(v2), f"Mismatch on {key}: {v1} vs {v2}"
        else:
            assert v1 == v2, f"Mismatch on {key}: {v1} vs {v2}"


@pytest.mark.asyncio
async def test_eval_runner_with_judge_enabled(mock_mcp, mock_time_and_uuid, tmp_path):
    """When JUDGE_ENABLED=1 and mock client, row includes judge outputs."""
    class MockJudgeClient:
        async def run_judges(self, row_input):
            return {
                "groundedness_score": 0.88,
                "product_relevance_score": 0.75,
                "judge_model": "gpt-4o-mini",
                "judge_error": None,
            }

    queries_file = tmp_path / "queries.json"
    queries_file.write_text(json.dumps([{"user_query": "dicas Disney"}]), encoding="utf-8")
    out_file = tmp_path / "run.jsonl"

    with (
        patch.dict("os.environ", {"TEST_QUERIES_JSON": queries_file.read_text(), "JUDGE_ENABLED": "1"}),
        patch("app.eval_runner.uuid.uuid4", side_effect=lambda: _make_uuid("deadbeef")),
    ):
        from app.eval_runner import run
        await run(out_file, judge_client=MockJudgeClient())

    row = json.loads(out_file.read_text().strip().split("\n")[0])
    assert row["judge_groundedness_score"] == 0.88
    assert row["judge_product_relevance_score"] == 0.75
    assert row["judge_model"] == "gpt-4o-mini"
    assert row["judge_error"] is None
