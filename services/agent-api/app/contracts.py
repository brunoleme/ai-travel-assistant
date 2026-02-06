"""Contract validation helpers."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_schema(name: str) -> dict:
    p = repo_root() / "contracts" / name
    return json.loads(p.read_text(encoding="utf-8"))


def validate_or_raise(payload: dict, schema_name: str) -> None:
    jsonschema.validate(payload, load_schema(schema_name))
