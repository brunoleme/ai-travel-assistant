"""Feedback event storage."""

from __future__ import annotations

import json
from pathlib import Path


def append_jsonl(event: dict, rel_path: str = "data/feedback/events.jsonl") -> None:
    p = Path.cwd() / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
