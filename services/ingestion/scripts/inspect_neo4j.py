#!/usr/bin/env python3
"""
One-off script to inspect Neo4j graph data ingested by youtube_kg pipeline.
Run from repo root with env loaded: set -a && . configs/.env && set +a && cd services/ingestion && uv run python scripts/inspect_neo4j.py
"""
from __future__ import annotations

import json
import os
import sys

def main() -> None:
    uri = os.environ.get("NEO4J_URI", "").strip()
    user = os.environ.get("NEO4J_USER", "").strip()
    password = os.environ.get("NEO4J_PASSWORD", "").strip()
    if not uri or not user or not password:
        print("Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD", file=sys.stderr)
        sys.exit(2)

    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(uri, auth=(user, password))
    db = os.environ.get("NEO4J_DATABASE", "neo4j")

    try:
        with driver.session(database=db) as session:
            # Counts
            r = session.run("MATCH (n:Entity) RETURN count(n) AS c")
            n_count = r.single()["c"]
            r = session.run("MATCH ()-[r:REL]->() RETURN count(r) AS c")
            rel_count = r.single()["c"]

            print("=== Neo4j graph (youtube_kg) ===\n")
            print(f"Entities: {n_count}")
            print(f"Relationships (REL): {rel_count}\n")

            # Nodes by type
            r = session.run("""
                MATCH (n:Entity) RETURN n.type AS type, count(*) AS c
                ORDER BY c DESC
            """)
            print("Nodes by type:")
            for rec in r:
                print(f"  {rec['type']}: {rec['c']}")

            # Edge types
            r = session.run("""
                MATCH ()-[r:REL]->() RETURN r.type AS type, count(*) AS c
                ORDER BY c DESC
            """)
            print("\nEdges by type:")
            for rec in r:
                print(f"  {rec['type']}: {rec['c']}")

            # Sample nodes (limit 10)
            r = session.run("""
                MATCH (n:Entity) RETURN n.id AS id, n.type AS type, n.name AS name
                LIMIT 10
            """)
            print("\nSample nodes (up to 10):")
            for rec in r:
                print(f"  {rec['id']} | {rec['type']} | {rec['name']}")

            # Sample edges with evidence (parse JSON evidence)
            r = session.run("""
                MATCH (a:Entity)-[r:REL]->(b:Entity)
                RETURN a.id AS source, r.type AS type, b.id AS target, r.evidence AS evidence
                LIMIT 5
            """)
            print("\nSample edges (up to 5) with evidence:")
            for rec in r:
                ev = rec["evidence"]
                if isinstance(ev, str):
                    try:
                        ev = json.loads(ev)
                    except json.JSONDecodeError:
                        ev = {"raw": ev[:80]}
                print(f"  ({rec['source']}) -[{rec['type']}]-> ({rec['target']})")
                print(f"    evidence: {ev}")

            # Video coverage (from evidence.videoUrl if present)
            r = session.run("""
                MATCH ()-[r:REL]->() WHERE r.evidence IS NOT NULL
                RETURN r.evidence AS evidence LIMIT 100
            """)
            videos = set()
            for rec in r:
                ev = rec["evidence"]
                if isinstance(ev, str):
                    try:
                        ev = json.loads(ev)
                    except json.JSONDecodeError:
                        continue
                url = ev.get("videoUrl") or ev.get("timestampUrl")
                if url and "youtube.com" in url:
                    vid = url.split("v=")[-1].split("&")[0]
                    if len(vid) == 11:
                        videos.add(vid)
            if videos:
                print(f"\nVideos referenced in evidence: {len(videos)}")
                for v in sorted(videos)[:5]:
                    print(f"  https://www.youtube.com/watch?v={v}")
                if len(videos) > 5:
                    print(f"  ... and {len(videos) - 5} more")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
