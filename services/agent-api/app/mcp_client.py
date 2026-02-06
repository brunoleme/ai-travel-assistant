"""MCP client for Knowledge and Products services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class MCPConfig:
    knowledge_base_url: str = "http://127.0.0.1:8010"
    products_base_url: str = "http://127.0.0.1:8020"
    timeout_s: float = 3.0


async def retrieve_travel_evidence(
    client: httpx.AsyncClient,
    base_url: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    r = await client.post(
        f"{base_url}/mcp/retrieve_travel_evidence",
        json={"x_contract_version": "1.0", "request": request},
        timeout=3.0,
    )
    r.raise_for_status()
    return r.json()


async def retrieve_product_candidates(
    client: httpx.AsyncClient,
    base_url: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    r = await client.post(
        f"{base_url}/mcp/retrieve_product_candidates",
        json={"x_contract_version": "1.0", "request": request},
        timeout=3.0,
    )
    r.raise_for_status()
    return r.json()
