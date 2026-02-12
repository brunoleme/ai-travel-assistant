"""MCP client for Knowledge, Products, and Graph services."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class MCPConfig:
    knowledge_base_url: str = "http://127.0.0.1:8010"
    products_base_url: str = "http://127.0.0.1:8020"
    graph_base_url: str = "http://127.0.0.1:8031"
    vision_base_url: str = "http://127.0.0.1:8032"
    stt_base_url: str = "http://127.0.0.1:8033"
    tts_base_url: str = "http://127.0.0.1:8034"
    timeout_s: float = 3.0

    @classmethod
    def from_env(cls) -> "MCPConfig":
        return cls(
            knowledge_base_url=os.environ.get("KNOWLEDGE_MCP_URL", cls.knowledge_base_url),
            products_base_url=os.environ.get("PRODUCTS_MCP_URL", cls.products_base_url),
            graph_base_url=os.environ.get("GRAPH_MCP_URL", cls.graph_base_url),
            vision_base_url=os.environ.get("VISION_MCP_URL", cls.vision_base_url),
            stt_base_url=os.environ.get("STT_MCP_URL", cls.stt_base_url),
            tts_base_url=os.environ.get("TTS_MCP_URL", cls.tts_base_url),
            timeout_s=float(os.environ.get("MCP_TIMEOUT_S", str(cls.timeout_s))),
        )


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


async def retrieve_travel_graph(
    client: httpx.AsyncClient,
    base_url: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    """Call mcp-travel-graph; response must validate against graph_rag.schema.json."""
    r = await client.post(
        f"{base_url}/mcp/retrieve_travel_graph",
        json={"x_contract_version": "1.0", "request": request},
        timeout=3.0,
    )
    r.raise_for_status()
    return r.json()


async def analyze_image(
    client: httpx.AsyncClient,
    base_url: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    """Call mcp-travel-vision; response must validate against vision_signals.schema.json."""
    r = await client.post(
        f"{base_url}/mcp/analyze_image",
        json={"x_contract_version": "1.0", "request": request},
        timeout=10.0,
    )
    r.raise_for_status()
    return r.json()


async def transcribe(
    client: httpx.AsyncClient,
    base_url: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    """Call mcp-travel-stt; response must validate against stt_transcript.schema.json."""
    r = await client.post(
        f"{base_url}/mcp/transcribe",
        json={"x_contract_version": "1.0", "request": request},
        timeout=15.0,
    )
    r.raise_for_status()
    return r.json()


async def synthesize(
    client: httpx.AsyncClient,
    base_url: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    """Call mcp-travel-tts; response must validate against tts_audio.schema.json."""
    r = await client.post(
        f"{base_url}/mcp/synthesize",
        json={"x_contract_version": "1.0", "request": request},
        timeout=15.0,
    )
    r.raise_for_status()
    return r.json()
