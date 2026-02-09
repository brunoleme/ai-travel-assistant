"""Tests for eval_diff: deterministic diff behavior using fixture JSONLs."""

from __future__ import annotations

from pathlib import Path

from app.eval_diff import _load_rows, _mean, _pct_included, diff

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EVAL_A = FIXTURES / "eval_a.jsonl"
EVAL_B = FIXTURES / "eval_b.jsonl"


def test_load_rows_deterministic() -> None:
    """Loading same file twice yields identical rows."""
    rows1 = _load_rows(EVAL_A)
    rows2 = _load_rows(EVAL_A)
    assert rows1 == rows2
    assert len(rows1) == 2


def test_mean_empty() -> None:
    """Mean of empty list returns default."""
    assert _mean([]) == 0.0
    assert _mean([], default=99.0) == 99.0


def test_mean_values() -> None:
    """Mean is computed correctly."""
    assert _mean([10.0, 20.0]) == 15.0


def test_pct_included() -> None:
    """Product included percentage is correct."""
    rows_a = _load_rows(EVAL_A)
    assert _pct_included(rows_a) == 50.0  # 1 of 2
    assert _pct_included([]) == 0.0


def test_diff_deterministic() -> None:
    """Diff output is identical for same input order (A vs B and B vs A are consistent)."""
    out_ab = diff(EVAL_A, EVAL_B)
    out_ab2 = diff(EVAL_A, EVAL_B)
    assert out_ab == out_ab2

    out_ba = diff(EVAL_B, EVAL_A)
    out_ba2 = diff(EVAL_B, EVAL_A)
    assert out_ba == out_ba2


def test_diff_contains_expected_sections() -> None:
    """Diff output includes latency, citations, product_included, judge scores."""
    out = diff(EVAL_A, EVAL_B)

    assert "Avg Latency" in out
    assert "Citations Count" in out
    assert "% Product Included" in out
    assert "Judge" in out
    assert "delta=" in out


def test_diff_latency_deltas() -> None:
    """A has higher avg latency than B; diff A vs B shows negative deltas for right (B)."""
    out = diff(EVAL_A, EVAL_B)

    # A: avg total = (100+200)/2 = 150, B: avg total = (50+150)/2 = 100
    # delta = right - left = 100 - 150 = -50
    assert "delta=-50" in out


def test_diff_judge_scores() -> None:
    """Both fixtures have judge scores; diff shows them."""
    out = diff(EVAL_A, EVAL_B)
    assert "Groundedness" in out
    assert "Product Relevance" in out
    assert "0.8" in out or "0.85" in out  # groundedness values
    assert "0.7" in out or "0.8" in out   # product relevance values


def test_diff_empty_file() -> None:
    """Diff with empty file yields minimal output."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write("\n")
        empty_path = Path(f.name)
    try:
        out = diff(empty_path, EVAL_A)
        assert "No rows to compare" in out or "0 rows" in out
    finally:
        empty_path.unlink()
