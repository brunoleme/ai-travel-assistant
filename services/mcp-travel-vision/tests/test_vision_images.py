"""
Optional tests using real images from docs/images_vision_test_cases/.

File name convention:
- outfit_*  -> mode=packing
- landmark_* -> mode=landmark
- product_* -> mode=product_similarity

Skipped when OPENAI_API_KEY is unset or the images directory is missing.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient

from app.main import app

# Repo root: services/mcp-travel-vision/tests -> parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]
IMAGES_DIR = REPO_ROOT / "docs" / "images_vision_test_cases"

SCHEMA_PATH = REPO_ROOT / "contracts" / "vision_signals.schema.json"
with open(SCHEMA_PATH) as f:
    VISION_SIGNALS_SCHEMA = json.load(f)


def _filename_to_mode(name: str) -> str | None:
    """Infer mode from filename prefix."""
    lower = name.lower()
    if lower.startswith("outfit_"):
        return "packing"
    if lower.startswith("landmark_"):
        return "landmark"
    if lower.startswith("product_"):
        return "product_similarity"
    return None


def _image_to_data_url(path: Path) -> str:
    """Read image file and return data URL."""
    raw = path.read_bytes()
    b64 = base64.standard_b64encode(raw).decode("ascii")
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
    return f"data:{mime};base64,{b64}"


def _collect_image_cases():
    """Collect (path, mode) for each image with a known prefix."""
    if not IMAGES_DIR.is_dir():
        return []
    cases = []
    for p in sorted(IMAGES_DIR.iterdir()):
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        mode = _filename_to_mode(p.name)
        if mode is not None:
            cases.append((p, mode))
    return cases


_IMAGE_CASES = _collect_image_cases()
_HAS_OPENAI_KEY = bool((os.environ.get("OPENAI_API_KEY") or "").strip())

skip_no_images = pytest.mark.skipif(
    len(_IMAGE_CASES) == 0,
    reason="No images in docs/images_vision_test_cases (outfit_*, landmark_*, product_*)",
)
skip_no_api_key = pytest.mark.skipif(
    not _HAS_OPENAI_KEY,
    reason="OPENAI_API_KEY not set",
)


@skip_no_images
@skip_no_api_key
@pytest.mark.parametrize("image_path,mode", _IMAGE_CASES, ids=[p.name for p, _ in _IMAGE_CASES])
def test_analyze_image_with_real_image(image_path: Path, mode: str) -> None:
    """
    POST /mcp/analyze_image with real image; response validates and has mode-specific fields.
    """
    data_url = _image_to_data_url(image_path)
    client = TestClient(app)
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "image_ref": data_url,
            "mode": mode,
            "debug": False,
        },
    }
    if mode == "packing":
        payload["request"]["trip_context"] = {"destination": "Orlando", "temp_band": "mild"}

    r = client.post("/mcp/analyze_image", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    jsonschema.validate(instance=body, schema=VISION_SIGNALS_SCHEMA)
    assert body["signals"]["mode"] == mode
    assert body["signals"]["confidence"] is not None

    if mode == "packing":
        assert "detected_items" in body["signals"] or "missing_categories" in body["signals"]
    elif mode == "landmark":
        assert "scene_type" in body["signals"] or "place_candidates" in body["signals"]
    elif mode == "product_similarity":
        assert "search_queries" in body["signals"] or "category" in body["signals"]
