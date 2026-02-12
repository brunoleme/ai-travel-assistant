"""Call OpenAI vision API with image + mode-specific prompts; parse structured JSON to VisionSignals."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from app.models import (
    TRAVEL_ITEM_CATEGORIES,
    SCENE_TYPES,
    VisionAnalyzeRequest,
    VisionSignals,
    PlaceCandidate,
)
from app.prompts import (
    get_packing_system_content,
    get_landmark_system_content,
    get_product_similarity_system_content,
    get_user_content_landmark,
    get_user_content_packing,
    get_user_content_product_similarity,
)


def _get_client():  # noqa: ANN202
    """Return OpenAI client or None if no API key."""
    try:
        from openai import OpenAI
    except ImportError:
        return None
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    return OpenAI(api_key=key)


def _get_model() -> str:
    """Vision model from env (default gpt-4.1-mini)."""
    return os.environ.get("VISION_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"


def _image_content(image_ref: str) -> dict[str, Any]:
    """Build OpenAI image content: URL or base64. image_ref is data URL or HTTP URL."""
    ref = image_ref.strip()
    if ref.startswith("data:"):
        # data:image/xxx;base64,<data>
        return {"type": "image_url", "image_url": {"url": ref}}
    return {"type": "image_url", "image_url": {"url": ref}}


def _extract_json_from_text(text: str) -> dict[str, Any] | None:
    """Extract JSON object from model output (may be wrapped in markdown)."""
    text = (text or "").strip()
    # Try to find ```json ... ``` or raw {...}
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _mock_signals(mode: str) -> VisionSignals:
    """Return mock signals for scaffold / no API key (validates against contract)."""
    if mode == "packing":
        return VisionSignals(
            mode="packing",
            confidence=0.9,
            detected_items=["light_top", "long_pants", "walking_shoes"],
            missing_categories=["rain_jacket"],
            suitability_ok=False,
            suitability_issue="Consider adding a layer for rain.",
            suggested_categories_for_products=["rain_jacket", "umbrella"],
        )
    if mode == "landmark":
        return VisionSignals(
            mode="landmark",
            confidence=0.85,
            scene_type="landmark",
            ocr_text=[],
            distinctive_features=["famous tower"],
            place_candidates=[
                PlaceCandidate(place_name="Eiffel Tower", confidence=0.9, reason="Distinctive shape"),
            ],
        )
    if mode == "product_similarity":
        return VisionSignals(
            mode="product_similarity",
            confidence=0.88,
            category="day_bag",
            attributes={"color": "black", "style": "minimal"},
            style_keywords=["minimal", "urban"],
            search_queries=["black minimal day bag", "urban travel daypack"],
        )
    return VisionSignals(mode=mode, confidence=0.0, error=f"Unknown mode: {mode}")


def _parse_packing(raw: dict[str, Any], mode: str) -> VisionSignals:
    """Map raw JSON to VisionSignals for outfit mode; filter items to 18-item set."""
    try:
        conf = float(raw.get("confidence", 0.5))
        conf = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        conf = 0.5
    detected = raw.get("detected_items")
    if isinstance(detected, list):
        detected = [str(x).strip() for x in detected if str(x).strip() in TRAVEL_ITEM_CATEGORIES]
    else:
        detected = None
    missing = raw.get("missing_categories")
    if isinstance(missing, list):
        missing = [str(x).strip() for x in missing if str(x).strip() in TRAVEL_ITEM_CATEGORIES]
    else:
        missing = None
    suitability_ok = raw.get("suitability_ok")
    if suitability_ok is not None and not isinstance(suitability_ok, bool):
        suitability_ok = None
    suitability_issue = raw.get("suitability_issue")
    if suitability_issue is not None:
        suitability_issue = str(suitability_issue).strip() or None
    suggested = raw.get("suggested_categories_for_products")
    if isinstance(suggested, list):
        suggested = [str(x).strip() for x in suggested if str(x).strip() in TRAVEL_ITEM_CATEGORIES]
    else:
        suggested = None
    return VisionSignals(
        mode=mode,
        confidence=conf,
        detected_items=detected or [],
        missing_categories=missing or [],
        suitability_ok=suitability_ok,
        suitability_issue=suitability_issue,
        suggested_categories_for_products=suggested or None,
    )


def _parse_landmark(raw: dict[str, Any], mode: str) -> VisionSignals:
    """Map raw JSON to VisionSignals for landmark mode."""
    try:
        conf = float(raw.get("confidence", 0.5))
        conf = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        conf = 0.5
    scene = raw.get("scene_type")
    if scene is not None and scene not in SCENE_TYPES:
        scene = None
    ocr = raw.get("ocr_text")
    if isinstance(ocr, list):
        ocr = [str(x).strip() for x in ocr if x]
    else:
        ocr = None
    features = raw.get("distinctive_features")
    if isinstance(features, list):
        features = [str(x).strip() for x in features if x]
    else:
        features = None
    candidates_raw = raw.get("place_candidates") or []
    place_candidates: list[PlaceCandidate] = []
    for c in candidates_raw[:3]:
        if isinstance(c, dict) and c.get("place_name"):
            place_candidates.append(
                PlaceCandidate(
                    place_name=str(c["place_name"]).strip(),
                    confidence=float(c["confidence"]) if c.get("confidence") is not None else None,
                    reason=str(c["reason"]).strip() if c.get("reason") else None,
                )
            )
    return VisionSignals(
        mode=mode,
        confidence=conf,
        scene_type=scene,
        ocr_text=ocr,
        distinctive_features=features,
        language_hint=raw.get("language_hint"),
        place_candidates=place_candidates or None,
    )


def _parse_product_similarity(raw: dict[str, Any], mode: str) -> VisionSignals:
    """Map raw JSON to VisionSignals for product_similarity mode."""
    try:
        conf = float(raw.get("confidence", 0.5))
        conf = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        conf = 0.5
    category = raw.get("category")
    if category and str(category).strip() not in TRAVEL_ITEM_CATEGORIES:
        category = None
    elif category:
        category = str(category).strip()
    attrs = raw.get("attributes")
    if not isinstance(attrs, dict):
        attrs = None
    style_kw = raw.get("style_keywords")
    if isinstance(style_kw, list):
        style_kw = [str(x).strip() for x in style_kw if x]
    else:
        style_kw = None
    queries = raw.get("search_queries")
    if isinstance(queries, list):
        queries = [str(x).strip() for x in queries if x][:3]
    else:
        queries = None
    return VisionSignals(
        mode=mode,
        confidence=conf,
        category=category,
        attributes=attrs,
        style_keywords=style_kw,
        search_queries=queries,
    )


def analyze_image(request: VisionAnalyzeRequest) -> VisionSignals:
    """
    Call OpenAI vision API for the given mode; parse JSON and return VisionSignals.
    On parse failure or API error, return VisionSignals with error set and confidence=0.
    """
    client = _get_client()
    if client is None:
        return _mock_signals(request.mode)

    model = _get_model()
    mode = request.mode

    if mode == "packing":
        system = get_packing_system_content(request.trip_context, request.user_query)
        user_text = get_user_content_packing(request.image_ref, request.trip_context, request.user_query)
    elif mode == "landmark":
        system = get_landmark_system_content()
        user_text = get_user_content_landmark(request.image_ref, request.user_query)
    elif mode == "product_similarity":
        system = get_product_similarity_system_content()
        user_text = get_user_content_product_similarity(request.image_ref)
    else:
        return VisionSignals(mode=mode, confidence=0.0, error=f"Unknown mode: {mode}")

    content: list[Any] = [{"type": "text", "text": user_text}, _image_content(request.image_ref)]

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            max_tokens=1024,
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return VisionSignals(mode=mode, confidence=0.0, error=str(e))

    parsed = _extract_json_from_text(text)
    if not parsed or not isinstance(parsed, dict):
        return VisionSignals(mode=mode, confidence=0.0, error="Failed to parse model JSON")

    try:
        if mode == "packing":
            return _parse_packing(parsed, mode)
        if mode == "landmark":
            return _parse_landmark(parsed, mode)
        if mode == "product_similarity":
            return _parse_product_similarity(parsed, mode)
    except Exception as e:
        return VisionSignals(mode=mode, confidence=0.0, error=str(e))

    return VisionSignals(mode=mode, confidence=0.0, error="Unknown mode")
