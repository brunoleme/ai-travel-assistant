"""LLM-as-judge: score groundedness and product relevance."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

import httpx

JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-4o-mini")

GROUNDEDNESS_PROMPT = """Score 0-1: Is the answer supported by the citations/evidence? Output JSON only: {"groundedness_score": <0-1>}"""
PRODUCT_PROMPT = """Score 0-1: Does the product addon match the user's intent? Output JSON only: {"product_relevance_score": <0-1>}"""


class JudgeClient(Protocol):
    """Injective judge client interface."""

    async def run_judges(self, row_input: dict[str, Any]) -> dict[str, Any]:
        """Run judges and return scores. Keys: groundedness_score, product_relevance_score, judge_model, judge_error."""
        ...


async def run_judges(row_input: dict[str, Any], client: JudgeClient | None = None) -> dict[str, Any]:
    """Run judges via injectable client or default implementation."""
    if client is None:
        client = _DefaultJudgeClient()
    return await client.run_judges(row_input)


class _DefaultJudgeClient:
    """Default LLM judge using OpenAI-compatible API."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.model = JUDGE_MODEL

    async def run_judges(self, row_input: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {
            "groundedness_score": None,
            "product_relevance_score": None,
            "judge_model": None,
            "judge_error": None,
        }
        if not self.api_key:
            out["judge_error"] = "OPENAI_API_KEY not set"
            return out

        user_query = row_input.get("user_query", "")
        answer_text = row_input.get("answer_text", "")
        citations = row_input.get("citations") or []
        addon = row_input.get("addon") or row_input.get("addon_bucket")
        errors: list[str] = []

        # Groundedness judge
        try:
            evidence_str = "\n".join(citations[:5]) if citations else "No citations"
            groundedness_input = f"Answer:\n{answer_text[:1500]}\n\nEvidence/Citations:\n{evidence_str}"
            g_resp = await _call_llm(self.api_key, self.model, GROUNDEDNESS_PROMPT, groundedness_input)
        except Exception as e:
            errors.append(f"groundedness call: {e}")
            out["judge_error"] = "; ".join(errors)
            out["judge_model"] = self.model
            return out
        g_parsed = _parse_judge_json(g_resp, "groundedness_score")
        if g_parsed.get("error"):
            errors.append(f"groundedness: {g_parsed['error']}")
        else:
            out["groundedness_score"] = g_parsed.get("groundedness_score")
        out["judge_model"] = self.model

        # Product relevance judge
        try:
            addon_str = json.dumps(addon) if isinstance(addon, dict) else str(addon or "")
            product_input = f"User query: {user_query}\n\nAddon: {addon_str}"
            p_resp = await _call_llm(self.api_key, self.model, PRODUCT_PROMPT, product_input)
        except Exception as e:
            errors.append(f"product_relevance call: {e}")
            p_resp = ""
        p_parsed = _parse_judge_json(p_resp, "product_relevance_score") if p_resp else {"error": "no response"}
        if p_parsed.get("error"):
            errors.append(f"product_relevance: {p_parsed['error']}")
        else:
            out["product_relevance_score"] = p_parsed.get("product_relevance_score")

        if errors:
            out["judge_error"] = "; ".join(errors)
        return out


async def _call_llm(api_key: str, model: str, system: str, user: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()


def _parse_judge_json(text: str, score_key: str) -> dict[str, Any]:
    """Parse LLM output as JSON; return {score_key: float} or {error: str}."""
    try:
        # Extract JSON block if wrapped in markdown
        s = text.strip()
        if "```" in s:
            start = s.find("{")
            end = s.rfind("}") + 1
            if start >= 0 and end > start:
                s = s[start:end]
        obj = json.loads(s)
        val = obj.get(score_key)
        if val is not None:
            v = float(val)
            if 0 <= v <= 1:
                return {score_key: v}
        return {"error": f"Invalid or missing {score_key}"}
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return {"error": str(e)}
