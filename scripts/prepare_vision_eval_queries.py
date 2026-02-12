#!/usr/bin/env python3
"""Prepare eval queries with image_ref (data URL) for vision MCP testing.

Discovers all images in docs/images_vision_test_cases/, assigns use cases by
prefix (outfit_* → packing, landmark_* → landmark, product_* → product_similarity),
and generates a comprehensive JSON query set. Each image gets at least one query.

Usage:
  python scripts/prepare_vision_eval_queries.py
  python scripts/prepare_vision_eval_queries.py --out services/agent-api/data/eval/vision_queries.json

Output: JSON string to stdout, or writes to --out file.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

# Query templates per (prefix, mode). Mode inferred from prefix by default.
# Use "product_similarity" explicitly for product_* or cross-mode tests.
QUERY_CASES: list[tuple[str, str, str | None, dict | None]] = [
    # outfit_summer.jpg
    ("outfit_summer.jpg", "packing", "Is this outfit okay for Disney in summer?", {"destination": "Orlando", "temp_band": "hot", "rain_risk": "low"}),
    ("outfit_summer.jpg", "packing", "What should I pack for Orlando in summer?", {"destination": "Orlando", "temp_band": "hot", "rain_risk": "low"}),
    # outfit_fall.jpg
    ("outfit_fall.jpg", "packing", "Is this outfit okay for Disney in fall?", {"destination": "Orlando", "temp_band": "mild", "rain_risk": "medium"}),
    ("outfit_fall.jpg", "packing", "What should I pack for Orlando in November?", {"destination": "Orlando", "temp_band": "mild", "rain_risk": "medium"}),
    # outfit_social.jpg
    ("outfit_social.jpg", "packing", "Is this outfit okay for a nice dinner at Disney Springs?", {"destination": "Orlando", "temp_band": "mild", "rain_risk": "low"}),
    ("outfit_social.jpg", "packing", "Can I wear this outfit to City Walk in Orlando?", {"destination": "Orlando", "temp_band": "mild", "rain_risk": "low"}),
    ("outfit_social.jpg", "product_similarity", "Find something like this outfit on Amazon", None),
    # landmark_animal_kingdom_avatar.jpg
    ("landmark_animal_kingdom_avatar.jpg", "landmark", "Where is this place in Orlando parks?", None),
    ("landmark_animal_kingdom_avatar.jpg", "landmark", "Which park is this attraction from?", None),
    # landmark_animal_kingdom_llife_tree.jpg
    ("landmark_animal_kingdom_llife_tree.jpg", "landmark", "Where is this in Animal Kingdom?", None),
    ("landmark_animal_kingdom_llife_tree.jpg", "landmark", "What is this tree? Where is it located?", None),
    # landmark_cheesecake_factory.jpg
    ("landmark_cheesecake_factory.jpg", "landmark", "What restaurant is this?", None),
    ("landmark_cheesecake_factory.jpg", "landmark", "Where can I eat this in Orlando?", None),
    # landmark_holywood_studios_starwars.jpg
    ("landmark_holywood_studios_starwars.jpg", "landmark", "Where is this in Hollywood Studios?", None),
    ("landmark_holywood_studios_starwars.jpg", "landmark", "Which Star Wars attraction is this in Orlando?", None),
]


def image_to_data_url(path: Path) -> str:
    """Read image file and return data URL."""
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
    return f"data:{mime};base64,{b64}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare vision eval queries with image_ref")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON to file instead of stdout (avoids env var size limits)",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=None,
        help="Directory with test images (default: docs/images_vision_test_cases)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    images_dir = args.images_dir or (repo_root / "docs" / "images_vision_test_cases")

    if not images_dir.exists():
        print(f"Error: images dir not found: {images_dir}", file=sys.stderr)
        return 1

    # Build image path -> data_url cache (only for images we use)
    image_paths: dict[str, Path] = {}
    for f in images_dir.iterdir():
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png"):
            image_paths[f.name] = f

    queries: list[dict] = []
    for filename, mode, user_query, trip_context in QUERY_CASES:
        if filename not in image_paths:
            print(f"Warning: skipping {filename} (not found in {images_dir})", file=sys.stderr)
            continue
        path = image_paths[filename]
        data_url = image_to_data_url(path)
        queries.append({
            "user_query": user_query,
            "destination": "Orlando",
            "lang": "en",
            "image_ref": data_url,
            "trip_context": trip_context,
        })

    # Ensure every image in the dir has at least one query
    used = {fn for fn, _, _, _ in QUERY_CASES}
    for name, path in image_paths.items():
        if name not in used:
            # Infer mode from prefix
            if name.startswith("outfit_"):
                q = "Is this outfit okay for Orlando parks?"
                ctx = {"destination": "Orlando", "temp_band": "mild", "rain_risk": "low"}
            elif name.startswith("landmark_"):
                q = "Where is this place in Orlando?"
                ctx = None
            elif name.startswith("product_"):
                q = "Find something like this"
                ctx = None
            else:
                q = "What is this?"
                ctx = None
            queries.append({
                "user_query": q,
                "destination": "Orlando",
                "lang": "en",
                "image_ref": image_to_data_url(path),
                "trip_context": ctx,
            })

    payload = json.dumps(queries, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
        print(f"Wrote {len(queries)} queries to {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
