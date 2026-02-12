"""Unit tests for Neo4j → contract adapter. No network."""

from __future__ import annotations

import json
import pytest

from app.adapter import neo4j_node_to_graph_node, neo4j_edge_to_graph_edge
from app.models import GraphEdge, GraphNode


def test_neo4j_node_to_graph_node_minimal() -> None:
    """Neo4j node with id, type, name maps to contract GraphNode."""
    record = {"id": "poi:sagrada", "type": "poi", "name": "Sagrada Família"}
    out = neo4j_node_to_graph_node(record)
    assert out["id"] == "poi:sagrada"
    assert out["type"] == "poi"
    assert out["name"] == "Sagrada Família"
    assert out["aliases"] == []
    assert out["properties"] == {}


def test_neo4j_node_to_graph_node_with_aliases_and_properties() -> None:
    """Neo4j node with aliases and properties maps correctly."""
    record = {
        "id": "city:barcelona",
        "type": "city",
        "name": "Barcelona",
        "aliases": ["Barna"],
        "properties": {"country": "Spain"},
    }
    out = neo4j_node_to_graph_node(record)
    assert out["aliases"] == ["Barna"]
    assert out["properties"] == {"country": "Spain"}


def test_neo4j_node_missing_id_raises() -> None:
    """Neo4j node without id raises ValueError."""
    with pytest.raises(ValueError, match="id"):
        neo4j_node_to_graph_node({"type": "poi", "name": "X"})


def test_neo4j_node_short_id_raises() -> None:
    """Neo4j node with id length < 2 raises ValueError."""
    with pytest.raises(ValueError, match="id"):
        neo4j_node_to_graph_node({"id": "x", "type": "poi", "name": "X"})


def test_neo4j_node_missing_name_raises() -> None:
    """Neo4j node without name raises ValueError."""
    with pytest.raises(ValueError, match="name"):
        neo4j_node_to_graph_node({"id": "poi:abc", "type": "poi", "name": ""})


def test_neo4j_edge_to_graph_edge_json_evidence() -> None:
    """Neo4j REL with evidence as JSON string maps to contract GraphEdge."""
    ev = {
        "videoUrl": "https://youtube.com/watch?v=abc",
        "timestampUrl": "https://youtube.com/watch?v=abc&t=120",
        "startSec": 120,
        "endSec": 180,
        "chunkIdx": 1,
    }
    out = neo4j_edge_to_graph_edge("it:1", "poi:1", "INCLUDES_POI", json.dumps(ev))
    assert out["source"] == "it:1"
    assert out["target"] == "poi:1"
    assert out["type"] == "INCLUDES_POI"
    assert out["evidence"]["videoUrl"] == ev["videoUrl"]
    assert out["evidence"]["startSec"] == 120
    assert out["evidence"]["endSec"] == 180
    assert out["evidence"]["chunkIdx"] == 1


def test_neo4j_edge_to_graph_edge_dict_evidence() -> None:
    """Neo4j REL with evidence as dict maps to contract GraphEdge."""
    ev = {
        "videoUrl": "https://youtube.com/watch?v=xyz",
        "timestampUrl": "https://youtube.com/watch?v=xyz&t=0",
        "startSec": 0,
        "endSec": 60,
    }
    out = neo4j_edge_to_graph_edge("a", "b", "HAS_DAY", ev)
    assert out["evidence"]["videoUrl"] == ev["videoUrl"]
    assert out["evidence"]["chunkIdx"] is None


def test_neo4j_edge_invalid_evidence_raises() -> None:
    """Evidence without videoUrl/timestampUrl min length raises ValueError."""
    with pytest.raises(ValueError, match="videoUrl|timestampUrl"):
        neo4j_edge_to_graph_edge(
            "a",
            "b",
            "REL",
            json.dumps(
                {
                    "videoUrl": "short",
                    "timestampUrl": "https://example.com/ok",
                    "startSec": 0,
                    "endSec": 1,
                }
            ),
        )


def test_adapter_output_validates_as_contract() -> None:
    """Adapter output can be used to build contract GraphNode and GraphEdge."""
    node_record = {
        "id": "poi:test",
        "type": "poi",
        "name": "Test POI",
        "aliases": [],
        "properties": {},
    }
    node = GraphNode(**neo4j_node_to_graph_node(node_record))
    assert node.id == "poi:test"

    ev = {
        "videoUrl": "https://example.com/watch?v=abc",
        "timestampUrl": "https://example.com/watch?v=abc&t=0",
        "startSec": 0,
        "endSec": 60,
    }
    edge_dict = neo4j_edge_to_graph_edge(
        "it:1", "poi:test", "INCLUDES_POI", json.dumps(ev)
    )
    edge = GraphEdge(**edge_dict)
    assert edge.source == "it:1"
    assert edge.evidence.videoUrl == ev["videoUrl"]
