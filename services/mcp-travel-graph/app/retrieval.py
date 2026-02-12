"""Neo4j retrieval for travel graph (Entity + REL). Returns subgraph and optional paths."""

from __future__ import annotations

import os

from app import adapter as adapter_module
from app.models import Evidence, GraphEdge, GraphNode, PathItem, Subgraph


def _get_driver():
    """Connect to Neo4j using env NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD. Returns None on failure."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return None
    uri = os.environ.get("NEO4J_URI", "").strip()
    user = os.environ.get("NEO4J_USER", "").strip()
    password = os.environ.get("NEO4J_PASSWORD", "").strip()
    if not uri or not user or not password:
        return None
    try:
        return GraphDatabase.driver(uri, auth=(user, password))
    except Exception:
        print('{"neo4j_fallback": true}')
        return None


def _get_database() -> str:
    """Database name from env (default neo4j)."""
    return os.environ.get("NEO4J_DATABASE", "neo4j")


def get_subgraph(
    user_query: str,
    destination: str | None,
    limit: int = 20,
) -> tuple[Subgraph, bool]:
    """
    Query Neo4j for Entity nodes and REL edges; return subgraph and neo4j_fallback.
    Strategy: text match on user_query/destination against node name/aliases, then expand N hops.
    Never raises; returns (empty Subgraph, True) on connection or query failure.
    """
    driver = _get_driver()
    if driver is None:
        subgraph, _ = get_subgraph_mock(user_query, destination, limit)
        return (subgraph, True)

    db = _get_database()
    # Build search terms: query + destination if provided (first term used in Cypher)
    terms = [user_query.strip().lower()]
    if destination:
        terms.append(destination.strip().lower())

    try:
        with driver.session(database=db) as session:
            # 1) Find Entity nodes matching name or aliases (simple CONTAINS; no full-text required)
            node_limit = min(limit, 50)
            term0 = terms[0] if terms else ""
            node_result = session.run(
                """
                MATCH (n:Entity)
                WHERE toLower(n.name) CONTAINS $term0
                   OR (n.aliases IS NOT NULL AND ANY(a IN n.aliases WHERE toLower(toString(a)) CONTAINS $term0))
                WITH n LIMIT $node_limit
                RETURN n.id AS id, n.type AS type, n.name AS name, n.aliases AS aliases, n.properties AS properties
                """,
                term0=term0,
                node_limit=node_limit,
            )
            nodes_raw = [dict(record) for record in node_result]
            if not nodes_raw:
                # Fallback: return a few nodes if no match (e.g. empty DB)
                node_result = session.run(
                    "MATCH (n:Entity) RETURN n.id AS id, n.type AS type, n.name AS name, n.aliases AS aliases, n.properties AS properties LIMIT $node_limit",
                    node_limit=node_limit,
                )
                nodes_raw = [dict(record) for record in node_result]

            node_ids = {r["id"] for r in nodes_raw}
            nodes: list[GraphNode] = []
            for r in nodes_raw:
                try:
                    mapped = adapter_module.neo4j_node_to_graph_node(r)
                    nodes.append(GraphNode(**mapped))
                except (ValueError, TypeError):
                    continue

            if not node_ids:
                return (Subgraph(nodes=nodes, edges=[]), False)

            # 2) Fetch RELs between these nodes (1–2 hops)
            edge_result = session.run(
                """
                MATCH (a:Entity)-[r:REL]->(b:Entity)
                WHERE a.id IN $ids AND b.id IN $ids
                RETURN a.id AS source, b.id AS target, r.type AS type, r.evidence AS evidence
                LIMIT $edge_limit
                """,
                ids=list(node_ids),
                edge_limit=min(limit * 2, 100),
            )
            edges: list[GraphEdge] = []
            for rec in edge_result:
                try:
                    ev = rec.get("evidence")
                    if ev is None:
                        continue
                    mapped = adapter_module.neo4j_edge_to_graph_edge(
                        rec["source"],
                        rec["target"],
                        rec.get("type", "REL"),
                        ev,
                    )
                    edges.append(GraphEdge(**mapped))
                except (ValueError, TypeError):
                    continue

            return (Subgraph(nodes=nodes, edges=edges), False)
    except Exception:
        print('{"neo4j_fallback": true}')
        return (Subgraph(nodes=[], edges=[]), True)
    finally:
        driver.close()


def get_subgraph_mock(
    user_query: str,
    destination: str | None,
    limit: int = 20,
) -> tuple[Subgraph, bool]:
    """
    Return a minimal mock subgraph that validates against graph_rag.schema.json (for G1 / tests).
    """
    mock_node = GraphNode(
        id="poi:mock_poi",
        type="poi",
        name="Mock POI",
        aliases=[],
        properties={},
    )
    mock_evidence = Evidence(
        videoUrl="https://example.com/watch?v=mock",
        timestampUrl="https://example.com/watch?v=mock&t=0",
        startSec=0,
        endSec=60,
        chunkIdx=0,
    )
    mock_edge = GraphEdge(
        source="itinerary:mock",
        type="INCLUDES_POI",
        target="poi:mock_poi",
        properties={},
        evidence=mock_evidence,
    )
    return (
        Subgraph(
            nodes=[mock_node],
            edges=[mock_edge],
        ),
        False,
    )


def compute_paths(subgraph: Subgraph) -> list[PathItem]:
    """
    From subgraph, compute 1–3 ordered paths (e.g. itinerary → days → POIs) for narrative answers.
    Returns empty list if no itinerary-shaped structure found.
    """
    if not subgraph.nodes and not subgraph.edges:
        return []
    node_ids = {n.id for n in subgraph.nodes}
    # Find itinerary/dayplan nodes and build paths: itinerary -HAS_DAY-> dayplan -INCLUDES_POI-> poi
    paths: list[PathItem] = []
    itineraries = [n for n in subgraph.nodes if n.type == "itinerary"]
    for it_node in itineraries[:3]:  # at most 3 paths
        path_node_ids: list[str] = [it_node.id]
        path_edge_types: list[str] = []
        path_evidence: list[Evidence] = []
        for edge in subgraph.edges:
            if edge.source == it_node.id and edge.type == "HAS_DAY":
                path_node_ids.append(edge.target)
                path_edge_types.append(edge.type)
                path_evidence.append(edge.evidence)
                for e2 in subgraph.edges:
                    if (
                        e2.source == edge.target
                        and e2.type == "INCLUDES_POI"
                        and e2.target in node_ids
                    ):
                        path_node_ids.append(e2.target)
                        path_edge_types.append(e2.type)
                        path_evidence.append(e2.evidence)
                break
        if len(path_node_ids) > 1:
            paths.append(
                PathItem(
                    path_id=it_node.id,
                    label=it_node.name,
                    nodes=path_node_ids,
                    edges=path_edge_types,
                    evidence=path_evidence,
                )
            )
    return paths
