"""Adapter: Neo4j result rows → Contract GraphNode, GraphEdge, Evidence."""

from __future__ import annotations

import json
from typing import Any


def neo4j_node_to_graph_node(record: dict[str, Any]) -> dict[str, Any]:
    """
    Map a Neo4j Entity node (id, type, name, aliases, properties) to contract GraphNode.
    """
    node_id = record.get("id")
    if not node_id or len(str(node_id)) < 2:
        raise ValueError("Neo4j node must have 'id' with min length 2")
    node_type = record.get("type", "place")
    name = record.get("name", "")
    if not name:
        raise ValueError("Neo4j node must have 'name'")
    aliases = record.get("aliases")
    if aliases is None:
        aliases = []
    properties = record.get("properties")
    if properties is None:
        properties = {}
    if isinstance(properties, str):
        try:
            properties = json.loads(properties) if properties else {}
        except json.JSONDecodeError:
            properties = {}
    return {
        "id": str(node_id),
        "type": str(node_type),
        "name": str(name),
        "aliases": list(aliases) if isinstance(aliases, (list, tuple)) else [],
        "properties": dict(properties) if isinstance(properties, dict) else {},
    }


def neo4j_edge_to_graph_edge(
    source: str,
    target: str,
    rel_type: str,
    evidence_raw: str | dict[str, Any],
) -> dict[str, Any]:
    """
    Map Neo4j REL (source, target, type, evidence JSON) to contract GraphEdge.
    evidence_raw is the REL.evidence value (JSON string from ingestion).
    """
    if isinstance(evidence_raw, str):
        try:
            ev = json.loads(evidence_raw)
        except (json.JSONDecodeError, TypeError):
            raise ValueError(
                "REL.evidence must be valid JSON with videoUrl, timestampUrl, startSec, endSec"
            )
    else:
        ev = dict(evidence_raw) if evidence_raw else {}
    video_url = ev.get("videoUrl") or ""
    timestamp_url = ev.get("timestampUrl") or ""
    if len(video_url) < 8 or len(timestamp_url) < 8:
        raise ValueError(
            "Evidence must have videoUrl and timestampUrl with min length 8"
        )
    return {
        "source": str(source),
        "type": str(rel_type),
        "target": str(target),
        "properties": ev.get("properties", {}),
        "evidence": {
            "videoUrl": video_url,
            "timestampUrl": timestamp_url,
            "startSec": int(ev.get("startSec", 0)),
            "endSec": int(ev.get("endSec", 0)),
            "chunkIdx": ev.get("chunkIdx"),
        },
    }
