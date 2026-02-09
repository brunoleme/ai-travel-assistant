"""
Products ingestion: enrich (OpenAI) and write (Weaviate Product + ProductCard).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
import weaviate

from app.weaviate_schema import ensure_collections

LangCode = Literal["pt", "en", "es"]
MarketCode = Literal["BR", "US", "Global"]

ALLOWED_CATS = {
    "insurance", "esim", "flights", "hotel", "tickets", "transport", "planner",
    "gear", "experiences", "finance", "shopping", "official", "other",
}


def _norm_cat(x: str) -> str | None:
    if not isinstance(x, str):
        return None
    x = x.strip().lower()
    return x if x in ALLOWED_CATS else None


def _merchant_from_link(link: str) -> str:
    from urllib.parse import urlparse
    try:
        host = urlparse(link).netloc.lower().replace("www.", "")
        return host
    except Exception:
        return ""


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ProductInput(BaseModel):
    """One product input for enrichment."""
    question: str = Field(min_length=5)
    opportunity: str = Field(min_length=10)
    link: str = Field(min_length=8)
    destination: str = ""
    lang: LangCode = "pt"
    market: MarketCode = "BR"


class ProductCardModel(BaseModel):
    """Enriched product card."""
    summary: str = Field(min_length=20)
    primaryCategory: str = "other"
    categories: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    affiliatePriority: float = Field(ge=0.0, le=1.0, default=0.5)
    userValue: float = Field(ge=0.0, le=1.0, default=0.5)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: str | None = None


def _fallback_product_card(pi: ProductInput) -> ProductCardModel:
    s = f"Opportunity related with the question: {pi.question}. {pi.opportunity}"
    s = (s[:260] + "…") if len(s) > 260 else s
    return ProductCardModel(
        summary=s if len(s) >= 20 else "Product card not available.",
        primaryCategory="other",
        categories=["other"],
        triggers=[],
        constraints=[],
        affiliatePriority=0.2,
        userValue=0.2,
        confidence=0.2,
        rationale="Fallback: parsing/enriching failure.",
    )


def _clamp01(x: Any, default: float = 0.4) -> float:
    try:
        v = float(x)
    except Exception:
        v = default
    return max(0.0, min(1.0, v))


def enrich_product_to_card(
    *,
    pi: ProductInput,
    model: str = "gpt-4.1-mini",
) -> ProductCardModel:
    """Enrich one product input to ProductCard via OpenAI."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required for enrich.")
    client = OpenAI(api_key=api_key)
    system = """You extract a ProductCard from question, opportunity description, and link.
Return ONLY valid JSON. No markdown.
SUMMARY: 1–2 sentences, >= 20 chars. CATEGORIES: primaryCategory one of insurance,esim,flights,hotel,tickets,transport,planner,gear,experiences,finance,shopping,official,other; categories 1..6.
TRIGGERS: 2..8 short imperative phrases (when to recommend), no brands. CONSTRAINTS: 0..6 items.
affiliatePriority, userValue, confidence: 0..1. If triggers empty => confidence <= 0.4, primaryCategory other.
Output in same language as input."""
    payload = {
        "question": pi.question,
        "opportunity": pi.opportunity,
        "link": pi.link,
        "destination": pi.destination,
        "market": pi.market,
    }
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            data = json.loads((resp.choices[0].message.content or "").strip())
            break
        except Exception:
            if attempt == 2:
                return _fallback_product_card(pi)
            time.sleep(0.8 * (2**attempt))
    else:
        return _fallback_product_card(pi)
    data.setdefault("categories", [])
    data.setdefault("triggers", [])
    data.setdefault("constraints", [])
    data["primaryCategory"] = data.get("primaryCategory") or "other"
    if not isinstance(data.get("summary"), str) or len((data["summary"] or "").strip()) < 20:
        data["summary"] = _fallback_product_card(pi).summary
    data["affiliatePriority"] = _clamp01(data.get("affiliatePriority", 0.4))
    data["userValue"] = _clamp01(data.get("userValue", 0.4))
    data["confidence"] = _clamp01(data.get("confidence", 0.4))
    if not isinstance(data["categories"], list):
        data["categories"] = []
    if data["primaryCategory"] not in data["categories"]:
        data["categories"] = [data["primaryCategory"]] + [c for c in data["categories"] if c != data["primaryCategory"]]
    data["categories"] = data["categories"][:6]
    if not data["triggers"]:
        data["confidence"] = min(data["confidence"], 0.4)
        data["primaryCategory"] = "other"
        data["categories"] = ["other"]
    try:
        return ProductCardModel(**data)
    except ValidationError:
        return _fallback_product_card(pi)


def _stable_uuid_for_product(link: str, question: str) -> str:
    key = f"{link}::{question}".strip()
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _stable_uuid_for_card(product_uuid: str, question: str, opportunity: str) -> str:
    import hashlib
    h = hashlib.md5((question + "||" + opportunity).encode("utf-8", errors="ignore")).hexdigest()[:10]
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{product_uuid}:{h}"))


def _connect_weaviate() -> weaviate.WeaviateClient:
    host = os.environ.get("WEAVIATE_HOST", "localhost")
    port = int(os.environ.get("WEAVIATE_PORT", "8080"))
    grpc_port = int(os.environ.get("WEAVIATE_GRPC_PORT", "50051"))
    return weaviate.connect_to_custom(
        http_host=host,
        http_port=port,
        http_secure=False,
        grpc_host=host,
        grpc_port=grpc_port,
        grpc_secure=False,
        skip_init_checks=True,
    )


def write_products_to_weaviate(
    products: list[dict[str, Any]],
    cards: list[ProductCardModel],
) -> None:
    """Ensure schema, upsert Products, insert ProductCards with refs."""
    ensure_collections()
    client = _connect_weaviate()
    try:
        products_coll = client.collections.use("Product")
        cards_coll = client.collections.use("ProductCard")
        for i, (p_dict, card) in enumerate(zip(products, cards)):
            pi = ProductInput(**p_dict) if isinstance(p_dict, dict) else ProductInput(**p_dict)
            product_uuid = _stable_uuid_for_product(pi.link, pi.question)
            if not products_coll.data.exists(product_uuid):
                products_coll.data.insert(
                    uuid=product_uuid,
                    properties={
                        "question": pi.question,
                        "opportunity": pi.opportunity,
                        "link": pi.link,
                        "destination": pi.destination,
                        "lang": pi.lang,
                        "market": pi.market,
                        "merchant": _merchant_from_link(pi.link),
                        "createdAt": _now_rfc3339(),
                    },
                )
            card_uuid = _stable_uuid_for_card(product_uuid, pi.question, pi.opportunity)
            if cards_coll.data.exists(card_uuid):
                continue
            cards_coll.data.insert(
                uuid=card_uuid,
                properties={
                    "summary": card.summary,
                    "question": pi.question,
                    "opportunity": pi.opportunity,
                    "link": pi.link,
                    "merchant": _merchant_from_link(pi.link),
                    "lang": pi.lang,
                    "market": pi.market,
                    "destination": pi.destination,
                    "primaryCategory": card.primaryCategory,
                    "categories": card.categories,
                    "triggers": card.triggers,
                    "constraints": card.constraints,
                    "affiliatePriority": float(card.affiliatePriority),
                    "userValue": float(card.userValue),
                    "confidence": float(card.confidence),
                    "rationale": card.rationale or "",
                    "createdAt": _now_rfc3339(),
                },
                references={"fromProduct": product_uuid},
            )
    finally:
        client.close()
