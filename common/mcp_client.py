"""Tiny async helper to invoke a tool on a FastMCP streamable-http server.

A new MCP session is opened per call. That's heavier than reusing a session,
but it keeps each FastAPI request self-contained and avoids cross-request
session state — fine for this demo's load profile.
"""
from __future__ import annotations

import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def mcp_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/mcp"


async def call_tool(port: int, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Open an MCP session, call one tool, return the parsed result."""
    url = mcp_url(port)
    async with streamablehttp_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments or {})
            # FastMCP returns structured content when the tool returns JSON-serializable data.
            if getattr(result, "structuredContent", None) is not None:
                sc = result.structuredContent
                # FastMCP wraps non-object returns under "result"
                if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
                    return sc["result"]
                return sc
            # Fallback: parse the first text block as JSON, else return raw text.
            for block in result.content or []:
                if getattr(block, "type", None) == "text":
                    try:
                        return json.loads(block.text)
                    except (json.JSONDecodeError, TypeError):
                        return block.text
            return None
