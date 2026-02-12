"""Eval harness runner: run test queries through the agent pipeline and write JSONL."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from app.guardrails import infer_addon_bucket, validate_and_fix
from app.judge import run_judges
from app.main import run_pipeline_raw

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "eval_row.schema.json"


def _load_queries() -> list[dict]:
    queries_file = os.environ.get("TEST_QUERIES_FILE")
    if queries_file and Path(queries_file).exists():
        return json.loads(Path(queries_file).read_text(encoding="utf-8"))
    raw = os.environ.get("TEST_QUERIES_JSON")
    if raw:
        return json.loads(raw)
    fallback = Path.cwd() / "data" / "eval" / "test_queries.json"
    if fallback.exists():
        return json.loads(fallback.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        "No queries: set TEST_QUERIES_FILE, TEST_QUERIES_JSON, or create data/eval/test_queries.json"
    )


def _load_eval_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate_row(row: dict, schema: dict) -> None:
    jsonschema.validate(row, schema)


async def _run_one(
    query: dict,
    run_id: str,
    schema: dict,
    out_path: Path,
    judge_client=None,
) -> None:
    user_query = query.get("user_query", "")
    destination = query.get("destination")
    lang = query.get("lang")
    market = query.get("market")
    image_ref = query.get("image_ref")
    trip_context = query.get("trip_context")
    session_id = f"eval-{run_id}-{uuid.uuid4().hex[:8]}"
    request_id = f"req-{uuid.uuid4().hex[:8]}"

    timing: dict[str, float] = {}
    raw = await run_pipeline_raw(
        session_id=session_id,
        request_id=request_id,
        user_query=user_query,
        destination=destination,
        lang=lang,
        image_ref=image_ref,
        trip_context=trip_context,
        timing_out=timing,
    )
    final = validate_and_fix(raw, user_query)

    guardrails_rewritten = (
        raw["answer_text"] != final["answer_text"]
        or (raw.get("addon") is None) != (final.get("addon") is None)
    )

    addon = final.get("addon")
    addon_bucket = infer_addon_bucket(addon) if addon else None

    citations = final.get("citations") or []
    citations_count = len(citations)
    groundedness_proxy = min(1.0, citations_count / 3.0)

    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "session_id": session_id,
        "request_id": request_id,
        "user_query": user_query,
        "destination": destination,
        "lang": lang,
        "market": market,
        "latency_ms_total": timing.get("total_ms", 0),
        "latency_ms_knowledge": timing.get("knowledge_ms", 0),
        "latency_ms_products": timing.get("products_ms", 0),
        "latency_ms_graph": timing.get("graph_ms", 0),
        "graph_included": timing.get("graph_ms", 0) > 0,
        "latency_ms_vision": timing.get("vision_ms", 0),
        "vision_included": timing.get("vision_ms", 0) > 0,
        "vision_mode": timing.get("vision_mode"),
        "citations_count": citations_count,
        "product_included": addon is not None,
        "groundedness_proxy": groundedness_proxy,
        "guardrails_rewritten": guardrails_rewritten,
        "judge_groundedness_score": None,
        "judge_product_relevance_score": None,
        "judge_model": None,
        "judge_error": None,
        "response_snapshot": {
            "answer_text": final.get("answer_text", ""),
            "citations": citations,
            "addon_bucket": addon_bucket,
        },
    }

    if os.environ.get("JUDGE_ENABLED") == "1":
        judge_input = {
            "user_query": user_query,
            "answer_text": final.get("answer_text", ""),
            "citations": citations,
            "addon": addon,
            "addon_bucket": addon_bucket,
        }
        judge_out = await run_judges(judge_input, client=judge_client)
        row["judge_groundedness_score"] = judge_out.get("groundedness_score")
        row["judge_product_relevance_score"] = judge_out.get("product_relevance_score")
        row["judge_model"] = judge_out.get("judge_model")
        row["judge_error"] = judge_out.get("judge_error")

    _validate_row(row, schema)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


async def run(out: Path, judge_client=None) -> None:
    queries = _load_queries()
    schema = _load_eval_schema()
    run_id = str(uuid.uuid4())

    if out.exists():
        out.unlink()

    for query in queries:
        await _run_one(query, run_id, schema, out, judge_client=judge_client)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("data/eval/run.jsonl"))
    args = parser.parse_args()
    asyncio.run(run(args.out))


if __name__ == "__main__":
    main()
