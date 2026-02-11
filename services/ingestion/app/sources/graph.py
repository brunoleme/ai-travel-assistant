"""
Knowledge graph extraction from transcript chunks and Neo4j ingestion.

Single-video pipeline: chunks -> extract_graph_from_chunk (per chunk) -> merge_graph -> ingest_into_neo4j.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

EDGE_TYPES = frozenset({
    "ITINERARY_FOR",
    "HAS_DAY",
    "INCLUDES_POI",
    "IN_AREA",
    "ORDER_BEFORE",
    "CLUSTERED_BY",
    "SUGGESTED_DAYS",
    "HAS_ACTIVITY_TYPE",
    "HAS_ADVICE",
    "HAS_CONSTRAINT",
})

NODE_TYPES = frozenset({
    "city", "place", "poi", "itinerary", "dayplan",
    "activity_type", "advice", "constraint",
})


def _make_timestamp_url(video_url: str, start_sec: int) -> str:
    """Build YouTube timestamp URL (?t= or &t=)."""
    if "t=" in video_url:
        return video_url
    joiner = "&" if "?" in video_url else "?"
    return f"{video_url}{joiner}t={start_sec}s"


class GraphNode(BaseModel):
    """One node in the knowledge graph."""
    id: str
    type: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    """Evidence for an edge (video segment)."""
    videoUrl: str
    startSec: int
    endSec: int
    chunkIdx: int
    timestampUrl: str


class GraphEdge(BaseModel):
    """One directed edge with evidence."""
    source: str
    type: str
    target: str
    properties: dict[str, Any] = Field(default_factory=dict)
    evidence: Evidence


class GraphExtraction(BaseModel):
    """Nodes and edges extracted from one chunk."""
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


def extract_graph_from_chunk(
    *,
    client: OpenAI,
    model: str,
    video_url: str,
    chunk_idx: int,
    start_sec: int,
    end_sec: int,
    chunk_text: str,
    destination_hint: str | None = None,
) -> GraphExtraction:
    """
    Grounded extraction: nodes/edges must be supported by this chunk.
    Returns empty GraphExtraction on parse/validation failure.
    """
    system = """You are extracting a travel knowledge graph from ONE transcript chunk.

You MUST follow ALL rules below:

GROUNDING (NO HALLUCINATION)
- Use ONLY what is explicitly supported by the chunk text.
- Do NOT add external facts (country, language, history, architecture explanations, etc.) unless the chunk literally says them.

LANGUAGE
- The transcript is in Portuguese (pt). Node "name" MUST be in Portuguese.
- Aliases may include ASR spellings or English variants IF they appear in the chunk.

NODE TYPES (allowed)
- city, place, poi, itinerary, dayplan, activity_type, advice, constraint

NODE ID FORMAT
- id: "<type>:<slug>"
- slug rules: lowercase, remove accents, spaces -> "_", keep only [a-z0-9_]
- If needed to disambiguate (same name), append "_barcelona" etc.

PLACE vs POI (strict)
- place: neighborhoods, streets/avenues, squares, regions/areas (ex: "La Rambla", "Praça da Catalúnia", "Bairro Gótico", "Montjuïc")
- poi: visitable attractions/venues (ex: "Sagrada Família", "Parc Güell", "Camp Nou", "Praia da Barceloneta", museums, parks)

PROPERTIES
- Keep properties minimal. Prefer {}.
- Only include properties directly stated in the chunk (e.g., "3-4€" if clearly said).
- Never include generic encyclopedia definitions.

EDGE TYPES (allowed)
ITINERARY_FOR, HAS_DAY, INCLUDES_POI, IN_AREA, ORDER_BEFORE, CLUSTERED_BY,
SUGGESTED_DAYS, HAS_ACTIVITY_TYPE, HAS_ADVICE, HAS_CONSTRAINT

EDGE DIRECTION (strict conventions)
- itinerary  --ITINERARY_FOR--> city
- itinerary  --HAS_DAY--> dayplan
- dayplan    --INCLUDES_POI--> poi
- poi/place  --IN_AREA--> place/city
- city/itinerary/dayplan/place/poi --HAS_ADVICE--> advice
- dayplan/poi --HAS_CONSTRAINT--> constraint
- poi/dayplan/place --HAS_ACTIVITY_TYPE--> activity_type

ORDER_BEFORE (very strict)
- Only output ORDER_BEFORE if the chunk clearly indicates sequence using words like:
  "começa", "primeiro", "depois", "em seguida", "aí", "descendo", "por fim".
- Put the earlier thing as source and the later thing as target.

NOISE FILTER
- Ignore YouTube/meta/CTA content (like/subscribe), sponsor blurbs, or vague chatter.
- If an entity name looks corrupted (ASR), only include it if it is repeated OR clearly a known place name in the chunk.

EVIDENCE (required for every edge)
- Every edge MUST include evidence:
  {videoUrl, startSec, endSec, chunkIdx, timestampUrl}

OUTPUT
Return ONLY valid JSON matching:
{
  "nodes":[{"id":"...", "type":"...", "name":"...", "aliases":[...], "properties":{...}}],
  "edges":[{"source":"...", "type":"...", "target":"...", "properties":{...}, "evidence":{...}}]
}
No markdown. No commentary.
"""
    timestamp_url = _make_timestamp_url(video_url, start_sec)
    user_payload = {
        "destination_hint": destination_hint or "",
        "videoUrl": video_url,
        "chunkIdx": chunk_idx,
        "startSec": start_sec,
        "endSec": end_sec,
        "timestampUrl": timestamp_url,
        "chunk_text": chunk_text,
    }
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        temperature=0.1,
    )
    raw = (resp.choices[0].message.content or "").strip()
    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not m:
        return GraphExtraction()
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return GraphExtraction()
    try:
        ge = GraphExtraction(**data)
    except ValidationError:
        return GraphExtraction()
    # Enforce allowed types and evidence
    filtered_nodes = [n for n in ge.nodes if n.type in NODE_TYPES and ":" in n.id]
    filtered_edges = [e for e in ge.edges if e.type in EDGE_TYPES and e.source and e.target]
    return GraphExtraction(nodes=filtered_nodes, edges=filtered_edges)


def merge_graph(extractions: list[GraphExtraction]) -> dict[str, Any]:
    """
    Merge nodes by id (merge aliases/properties); unique edges by (type, source, target, startSec, endSec).
    """
    node_map: dict[str, GraphNode] = {}
    edge_keys: set[tuple[str, str, str, int, int]] = set()
    edges_out: list[dict[str, Any]] = []

    for ex in extractions:
        for n in ex.nodes:
            if n.id not in node_map:
                node_map[n.id] = n
            else:
                existing = node_map[n.id]
                merged_aliases = set(existing.aliases or [])
                merged_aliases.update(n.aliases or [])
                existing.aliases = sorted(merged_aliases)
                for k, v in (n.properties or {}).items():
                    if k not in existing.properties:
                        existing.properties[k] = v
        for e in ex.edges:
            key = (e.type, e.source, e.target, e.evidence.startSec, e.evidence.endSec)
            if key in edge_keys:
                continue
            edge_keys.add(key)
            edges_out.append(e.model_dump())

    return {
        "nodes": [node_map[k].model_dump() for k in sorted(node_map.keys())],
        "edges": edges_out,
        "debug": {"node_count": len(node_map), "edge_count": len(edges_out)},
    }


def ingest_into_neo4j(
    graph: dict[str, Any],
    uri: str | None = None,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
) -> None:
    """Write merged graph to Neo4j. Reads uri/user/password from env if not passed."""
    from neo4j import GraphDatabase

    uri = uri or os.environ.get("NEO4J_URI", "").strip()
    user = user or os.environ.get("NEO4J_USER", "").strip()
    password = password or os.environ.get("NEO4J_PASSWORD", "").strip()
    if not uri or not user or not password:
        raise RuntimeError("NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD required for Neo4j write.")
    db = database or os.environ.get("NEO4J_DATABASE", "neo4j")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=db) as session:
            for n in graph.get("nodes", []):
                session.run(
                    """
                    MERGE (x:Entity {id: $id})
                    SET x.type = $type, x.name = $name, x.aliases = $aliases, x += $properties
                    """,
                    id=n["id"],
                    type=n["type"],
                    name=n["name"],
                    aliases=n.get("aliases", []),
                    properties=n.get("properties", {}),
                )
            for e in graph.get("edges", []):
                ev = e.get("evidence", {})
                key = f'{e["type"]}|{e["source"]}|{e["target"]}|{ev.get("startSec", 0)}|{ev.get("endSec", 0)}'
                # Neo4j only allows primitive or array-of-primitive properties; store evidence as JSON string
                evidence_json = json.dumps(ev)
                session.run(
                    """
                    MATCH (a:Entity {id: $source}), (b:Entity {id: $target})
                    MERGE (a)-[r:REL {key: $key}]->(b)
                    SET r.type = $etype, r += $props, r.evidence = $evidence
                    """,
                    source=e["source"],
                    target=e["target"],
                    etype=e["type"],
                    props=e.get("properties", {}),
                    evidence=evidence_json,
                    key=key,
                )
    finally:
        driver.close()
