"""Session memory store with naive extraction."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

_STORE: dict[str, MemoryState] = {}


@dataclass
class MemoryState:
    """Session memory state."""

    preferences: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    recent_plan_steps: list[str] = field(default_factory=list)
    _max_steps: int = 3

    def to_summary(self, max_chars: int = 500) -> str:
        parts: list[str] = []
        if self.preferences:
            prefs = " ".join(f"{k}={v}" for k, v in self.preferences.items() if v is not None)
            if prefs:
                parts.append(f"prefs:{prefs}")
        if self.constraints:
            cons = " ".join(f"{k}={v}" for k, v in self.constraints.items() if v is not None)
            if cons:
                parts.append(f"constraints:{cons}")
        if self.recent_plan_steps:
            parts.append("recent:" + ";".join(self.recent_plan_steps))
        s = " ".join(parts)
        return s[:max_chars] if len(s) > max_chars else s or ""


def _extract(query: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Naive keyword extraction. Returns (preferences, constraints)."""
    q = query.lower()
    prefs: dict[str, Any] = {}
    constraints: dict[str, Any] = {}

    if re.search(r"\bbudget\b|\bcheap\b|\blow.?cost\b|\bhostel\b", q):
        prefs["budget_style"] = "budget"
    elif re.search(r"\bluxury\b|\bpremium\b|\b5.?star\b", q):
        prefs["budget_style"] = "luxury"

    if re.search(r"\badventure\b|\bhiking\b|\bbackpack\b", q):
        prefs["travel_style"] = "adventure"
    elif re.search(r"\brelax\b|\bbeach\b|\bspa\b", q):
        prefs["travel_style"] = "relaxation"
    elif re.search(r"\bfamily\b|\bkids?\b|\bchildren\b", q):
        prefs["travel_style"] = "family"

    if re.search(r"\bwheelchair\b|\bmobility\b|\baccessible\b|\bdisabilit", q):
        prefs["mobility_constraints"] = "wheelchair_accessible"

    m = re.search(r"\b(\d+)\s*(kids?|children|child)\b", q, re.I)
    if m:
        prefs["kids"] = True
        constraints["group_size"] = m.group(1)

    m = re.search(r"\b(\d+)\s*(adults?|people|persons?)\b", q, re.I)
    if m:
        constraints["group_size"] = m.group(1)

    m = re.search(r"\b(march|april|may|june|july|august|september|october|november|december)\s*(\d{4})?", q, re.I)
    if m:
        constraints["dates"] = m.group(0).strip()

    if re.search(r"\bmust\s+(?:see|visit|do)\b", q):
        constraints["must"] = "extracted"

    if re.search(r"\bavoid\b|\bno\b.*\b(crowds?|tourists?)\b", q):
        constraints["avoid"] = "extracted"

    return prefs, constraints


def get(session_id: str) -> MemoryState:
    if session_id not in _STORE:
        _STORE[session_id] = MemoryState()
    return _STORE[session_id]


def update(session_id: str, user_query: str, parsed_updates: dict[str, Any] | None = None) -> MemoryState:
    state = get(session_id)
    prefs, constraints = _extract(user_query)

    for k, v in prefs.items():
        if v is not None:
            state.preferences[k] = v
    for k, v in constraints.items():
        if v is not None:
            state.constraints[k] = v
    if parsed_updates:
        for k, v in parsed_updates.get("preferences", {}).items():
            if v is not None:
                state.preferences[k] = v
        for k, v in parsed_updates.get("constraints", {}).items():
            if v is not None:
                state.constraints[k] = v

    intent = user_query.strip()[:200]
    state.recent_plan_steps = [intent] + [
        s for s in state.recent_plan_steps if s != intent
    ][: state._max_steps - 1]

    return state


def summary(session_id: str, max_chars: int = 500) -> str:
    return get(session_id).to_summary(max_chars=max_chars)


def memory_hash(session_id: str, length: int = 8) -> str:
    s = summary(session_id)
    return hashlib.sha256(s.encode()).hexdigest()[:length] if s else ""
