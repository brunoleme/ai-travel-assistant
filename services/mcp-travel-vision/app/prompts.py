"""Prompt templates per mode (packing/outfit, landmark, product_similarity) returning strict JSON."""

from __future__ import annotations

PACKING_ITEMS = (
    "light_top, warm_top, insulated_jacket, rain_jacket, long_pants, shorts_or_skirt, "
    "walking_shoes, sandals, weather_proof_shoes, sun_protection, cold_accessory, "
    "umbrella, day_bag, travel_bag_organizer, power_adapter, portable_charger, "
    "water_bottle, travel_comfort_item"
)

SCENE_TYPES_STR = (
    "landmark, street, beach, mountain, museum, airport, restaurant, hotel, transit, urban, nature"
)


def get_packing_system_content(trip_context: dict | None, user_query: str | None) -> str:
    """System prompt for outfit mode: judge suitability for context and suggest product categories when relevant."""
    ctx = ""
    if trip_context:
        ctx = f" Trip context: {trip_context} (e.g. destination, temp_band, rain_risk). Use it to judge if the outfit is suitable."
    query_note = ""
    if user_query:
        query_note = f" The user asked: \"{user_query}\" — answer that question (suitability for the context) and suggest product categories only when the outfit is not suitable or the user wants recommendations."
    return f"""You analyze an outfit photo (clothing/items for travel). Use ONLY these 18 categories when listing items: {PACKING_ITEMS}.
Tasks: (1) List detected clothing/item categories from the image ("detected_items", exact names from the list). (2) Judge whether this outfit is suitable for the trip context ("suitability_ok": true/false). If not suitable, set "suitability_issue" to a short reason (e.g. "Too light for winter" or "Missing rain protection for high rain_risk"). (3) If the outfit is not suitable or the user wants suggestions, list "suggested_categories_for_products" (array of category names from the 18-item set) that would improve the outfit (e.g. rain_jacket, umbrella). (4) Optionally "missing_categories" (what's missing from the 18-item set for this trip).{ctx}{query_note}
Output valid JSON only with keys: "detected_items", "suitability_ok", "suitability_issue" (null if suitable), "suggested_categories_for_products", "missing_categories", "confidence" (0-1)."""


def get_landmark_system_content() -> str:
    """System prompt for landmark mode: scene type, OCR, features, place candidates."""
    return f"""You analyze a travel/place photo. Describe the scene and suggest up to 3 place candidates.
Scene types (use exactly one): {SCENE_TYPES_STR}.
Output valid JSON only with keys: "scene_type" (one of the list), "ocr_text" (array of extracted text strings), "distinctive_features" (array of strings), "language_hint" (optional), "place_candidates" (array of {{"place_name": string, "confidence": 0-1, "reason": string}}, max 3), "confidence" (0-1)."""


def get_product_similarity_system_content() -> str:
    """System prompt for product_similarity: category, attributes, style, search queries."""
    return f"""You analyze a product/item photo for similarity search. Category must be one of: {PACKING_ITEMS}.
Extract product category, attributes (e.g. color, material, size_class, use_case), style keywords, and produce 2-3 marketplace search query strings.
Output valid JSON only with keys: "category" (one of the 18-item set), "attributes" (object), "style_keywords" (array of strings), "search_queries" (array of 2-3 strings), "confidence" (0-1)."""


def get_user_content_packing(image_ref: str, trip_context: dict | None, user_query: str | None) -> str:
    """User message for outfit/packing: include user question so model can judge suitability."""
    if user_query and user_query.strip():
        return f"User question: {user_query.strip()}\n\nAnalyze this outfit image. Judge if it is suitable for the context and suggest product categories if relevant. Output JSON only."
    return "Analyze this outfit image for the trip context. Judge suitability and suggest product categories if relevant. Output JSON only."


def get_user_content_landmark(image_ref: str, user_query: str | None) -> str:
    """User message for landmark mode; include user question (e.g. Where is this? What restaurant?)."""
    if user_query and user_query.strip():
        return f"User question: {user_query.strip()}\n\nDescribe this scene, extract text, list distinctive features, propose up to 3 place candidates with confidence. JSON only."
    return "Describe this scene, extract text, list distinctive features, propose up to 3 place candidates with confidence. JSON only."


def get_user_content_product_similarity(image_ref: str) -> str:
    """User message for product_similarity mode."""
    return "Extract product category and attributes; produce 2-3 marketplace search query strings. JSON only."
