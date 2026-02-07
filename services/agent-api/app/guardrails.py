"""Response guardrails: no invented facts, citations required, addon only when requested."""

from __future__ import annotations

import re
from typing import Any

SAFE_FALLBACK = "Não tenho fontes suficientes para confirmar essas informações."

CURRENCY_PATTERN = re.compile(
    r"R\$\s*\d|USD\s*\d|BRL\s*\d|\$\s*\d|\d+\s*(?:R\$|USD|BRL)",
    re.I,
)

FACTUAL_PATTERNS = (
    r"\(Source:",
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d+\s*(?:am|pm|h|horas?)\b",
    r"\bmust\b",
    r"\brequires?\b",
    r"\brule[s]?\b",
)

BUCKET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "tickets": ("ingresso", "ticket", "pass", "passes", "bilhete"),
    "hotel": ("hotel", "hospedagem", "accommodation", "stay", "reserva"),
    "insurance": ("seguro", "insurance"),
    "esim": ("esim", "e-sim", "chip"),
    "transport": ("transporte", "transport", "voo", "flight", "carro", "car"),
    "planner": ("planner", "planejador", "roteiro"),
    "shopping": ("comprar", "buy", "shopping"),
}


def _has_currency(text: str) -> bool:
    return bool(CURRENCY_PATTERN.search(text))


def _looks_factual(text: str) -> bool:
    for pat in FACTUAL_PATTERNS:
        if re.search(pat, text, re.I):
            return True
    return False


def infer_addon_bucket(addon: dict[str, Any]) -> str | None:
    combined = " ".join(
        str(addon.get(k, ""))
        for k in ("summary", "primary_category", "merchant")
    ).lower()
    combined += " " + " ".join(
        c for c in addon.get("categories") or []
    ).lower()

    for bucket, keywords in BUCKET_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return bucket
    return None


def _user_requested_bucket(user_query: str, bucket: str) -> bool:
    q = user_query.lower()
    keywords = BUCKET_KEYWORDS.get(bucket, ())
    return any(kw in q for kw in keywords)


def validate_and_fix(
    response: dict[str, Any],
    user_query: str,
) -> dict[str, Any]:
    """Apply guardrails: fix or block unsafe answers and unsolicited addons."""
    out = dict(response)
    answer = out.get("answer_text", "")
    citations = out.get("citations") or []
    addon = out.get("addon")
    has_citations = len(citations) > 0

    if not has_citations:
        if _has_currency(answer):
            out["answer_text"] = SAFE_FALLBACK
            out["citations"] = []
        elif _looks_factual(answer) or "(Source:" in answer:
            out["answer_text"] = SAFE_FALLBACK
            out["citations"] = []

    if addon:
        bucket = infer_addon_bucket(addon)
        if bucket and not _user_requested_bucket(user_query, bucket):
            out["addon"] = None

    return out
