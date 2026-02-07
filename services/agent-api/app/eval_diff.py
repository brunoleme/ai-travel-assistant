"""Regression diff helper: compares two eval JSONL files and prints human-readable stats."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_rows(path: Path) -> list[dict]:
    """Load JSONL file into list of dicts. Skips empty lines."""
    rows: list[dict] = []
    text = path.read_text(encoding="utf-8")
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _mean(values: list[float], default: float = 0.0) -> float:
    """Compute mean or default if empty."""
    if not values:
        return default
    return sum(values) / len(values)


def _pct_included(rows: list[dict]) -> float:
    """Fraction of rows with product_included=True, as percentage."""
    if not rows:
        return 0.0
    count = sum(1 for r in rows if r.get("product_included") is True)
    return 100.0 * count / len(rows)


def diff(left_path: Path, right_path: Path) -> str:
    """
    Compare two eval JSONL files. Returns human-readable diff summary.

    Compares by row index (assumes same query order). Stats include:
    - avg latency deltas (total, knowledge, products)
    - citations_count min/max/mean per file
    - % product_included per file
    - avg judge scores when present
    """
    left_rows = _load_rows(left_path)
    right_rows = _load_rows(right_path)

    lines: list[str] = []
    lines.append(f"=== Eval Diff: {left_path.name} vs {right_path.name} ===")
    lines.append(f"  Left:  {len(left_rows)} rows")
    lines.append(f"  Right: {len(right_rows)} rows")
    lines.append("")

    n = min(len(left_rows), len(right_rows))
    if n == 0:
        lines.append("(No rows to compare)")
        return "\n".join(lines)

    # Latency deltas (right - left)
    total_left = [r.get("latency_ms_total") or 0 for r in left_rows[:n]]
    total_right = [r.get("latency_ms_total") or 0 for r in right_rows[:n]]
    know_left = [r.get("latency_ms_knowledge") or 0 for r in left_rows[:n]]
    know_right = [r.get("latency_ms_knowledge") or 0 for r in right_rows[:n]]
    prod_left = [r.get("latency_ms_products") or 0 for r in left_rows[:n]]
    prod_right = [r.get("latency_ms_products") or 0 for r in right_rows[:n]]

    avg_total_left = _mean(total_left)
    avg_total_right = _mean(total_right)
    avg_know_left = _mean(know_left)
    avg_know_right = _mean(know_right)
    avg_prod_left = _mean(prod_left)
    avg_prod_right = _mean(prod_right)

    delta_total = avg_total_right - avg_total_left
    delta_know = avg_know_right - avg_know_left
    delta_prod = avg_prod_right - avg_prod_left

    lines.append("--- Avg Latency (ms) ---")
    lines.append(f"  Total:    left={avg_total_left:.2f}  right={avg_total_right:.2f}  delta={delta_total:+.2f}")
    lines.append(f"  Knowledge: left={avg_know_left:.2f}  right={avg_know_right:.2f}  delta={delta_know:+.2f}")
    lines.append(f"  Products:  left={avg_prod_left:.2f}  right={avg_prod_right:.2f}  delta={delta_prod:+.2f}")
    lines.append("")

    # Citations
    cite_left = [r.get("citations_count", 0) for r in left_rows[:n]]
    cite_right = [r.get("citations_count", 0) for r in right_rows[:n]]
    lines.append("--- Citations Count ---")
    lines.append(f"  Left:  min={min(cite_left)} max={max(cite_left)} avg={_mean(cite_left):.2f}")
    lines.append(f"  Right: min={min(cite_right)} max={max(cite_right)} avg={_mean(cite_right):.2f}")
    lines.append("")

    # Product included
    lines.append("--- % Product Included ---")
    lines.append(f"  Left:  {_pct_included(left_rows):.1f}%")
    lines.append(f"  Right: {_pct_included(right_rows):.1f}%")
    lines.append("")

    # Judge scores when present
    jg_left = [r["judge_groundedness_score"] for r in left_rows if r.get("judge_groundedness_score") is not None]
    jp_left = [r["judge_product_relevance_score"] for r in left_rows if r.get("judge_product_relevance_score") is not None]
    jg_right = [r["judge_groundedness_score"] for r in right_rows if r.get("judge_groundedness_score") is not None]
    jp_right = [r["judge_product_relevance_score"] for r in right_rows if r.get("judge_product_relevance_score") is not None]

    if jg_left or jg_right or jp_left or jp_right:
        lines.append("--- Avg Judge Scores ---")
        if jg_left or jg_right:
            lines.append(f"  Groundedness:     left={_mean(jg_left):.2f}  right={_mean(jg_right):.2f}")
        if jp_left or jp_right:
            lines.append(f"  Product Relevance: left={_mean(jp_left):.2f}  right={_mean(jp_right):.2f}")
    else:
        lines.append("--- Judge Scores --- (none present)")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two eval JSONL files")
    parser.add_argument("left", type=Path, help="First (baseline) JSONL file")
    parser.add_argument("right", type=Path, help="Second (compare) JSONL file")
    args = parser.parse_args()
    print(diff(args.left, args.right))


if __name__ == "__main__":
    main()
