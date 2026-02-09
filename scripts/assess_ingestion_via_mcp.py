#!/usr/bin/env python3
"""
Call the MCP travel-knowledge service to assess ingested content.

Usage (from repo root, with configs/.env loaded so WEAVIATE_* is set for the MCP):
  make run-knowledge   # in another terminal
  python scripts/assess_ingestion_via_mcp.py

Or set KNOWLEDGE_URL (default http://localhost:8010) and run.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request


def main() -> int:
    base_url = os.environ.get("KNOWLEDGE_URL", "http://localhost:8010").rstrip("/")
    payload = {
        "x_contract_version": "1.0",
        "request": {
            "user_query": "dicas de viagem Playa del Carmen, quando ir, o que fazer",
            "destination": "Playa del Carmen",
            "lang": "pt",
            "debug": True,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/mcp/retrieve_travel_evidence",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"Cannot reach MCP at {base_url}: {e}", file=sys.stderr)
        print("Start the knowledge server: make run-knowledge", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 1

    evidence = data.get("evidence") or []
    request_info = data.get("request") or {}
    print("=== MCP travel-knowledge assessment ===\n")
    print(f"Query: {request_info.get('user_query')}")
    print(f"Destination: {request_info.get('destination')}")
    print(f"Evidence cards returned: {len(evidence)}\n")
    if data.get("debug"):
        print(f"Debug: {data['debug']}\n")
    for i, card in enumerate(evidence[:10], 1):
        print(f"  [{i}] {card.get('summary', '')[:120]}...")
        print(f"      source_url: {card.get('source_url', '')[:80]}...")
        print(f"      primary_category: {card.get('primary_category')} confidence: {card.get('confidence')}")
        print()
    if len(evidence) > 10:
        print(f"  ... and {len(evidence) - 10} more cards.\n")
    print("=== Assessment summary ===")
    if evidence:
        urls = {c.get("source_url", "").split("&t=")[0] for c in evidence if c.get("source_url")}
        print(f"  Unique video URLs in top results: {len(urls)}")
        for u in list(urls)[:5]:
            print(f"    {u}")
    else:
        print("  No evidence returned. Check that Weaviate has RecommendationCards and the MCP can connect.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
