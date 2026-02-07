"""Judge (LLM-as-judge) tests (no network)."""

from __future__ import annotations

import pytest

from app.judge import _parse_judge_json, run_judges


def test_judge_parsing_success() -> None:
    """Valid JSON from judge -> parsing ok, scores extracted."""
    result = _parse_judge_json('{"groundedness_score": 0.85}', "groundedness_score")
    assert "error" not in result
    assert result["groundedness_score"] == 0.85

    result = _parse_judge_json('{"product_relevance_score": 0.7}', "product_relevance_score")
    assert "error" not in result
    assert result["product_relevance_score"] == 0.7


def test_judge_parsing_failure_fallback() -> None:
    """Invalid text from judge -> fallback, scores null, judge_error set."""
    result = _parse_judge_json("not valid json at all", "groundedness_score")
    assert "error" in result

    result = _parse_judge_json("{}", "groundedness_score")
    assert "error" in result

    result = _parse_judge_json('{"groundedness_score": 99}', "groundedness_score")
    assert "error" in result


@pytest.mark.asyncio
async def test_run_judges_parsing_success() -> None:
    """Mock JudgeClient returns valid JSON -> run_judges parses ok."""
    class MockClient:
        async def run_judges(self, row_input):
            return {
                "groundedness_score": 0.9,
                "product_relevance_score": 0.8,
                "judge_model": "gpt-4o-mini",
                "judge_error": None,
            }
    out = await run_judges({"user_query": "x", "answer_text": "y", "citations": []}, client=MockClient())
    assert out["groundedness_score"] == 0.9
    assert out["product_relevance_score"] == 0.8
    assert out["judge_model"] == "gpt-4o-mini"
    assert out["judge_error"] is None


@pytest.mark.asyncio
async def test_run_judges_parsing_failure_fallback() -> None:
    """Mock JudgeClient returns invalid / error -> scores null, judge_error set."""
    class FailingClient:
        async def run_judges(self, row_input):
            return {
                "groundedness_score": None,
                "product_relevance_score": None,
                "judge_model": "gpt-4o-mini",
                "judge_error": "groundedness: Expecting value",
            }
    out = await run_judges({"user_query": "x"}, client=FailingClient())
    assert out["groundedness_score"] is None
    assert out["product_relevance_score"] is None
    assert out["judge_error"] == "groundedness: Expecting value"
