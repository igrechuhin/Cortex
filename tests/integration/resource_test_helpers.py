"""Read actual text from the published FastMCP resource surface in integration tests."""

import importlib

from cortex.server import mcp


async def read_resource_text(uri: str) -> str:
    """Flatten text content, rejecting binary payloads instead of comparing model reprs."""
    _ = importlib.import_module("cortex.tools")
    result = await mcp.read_resource(uri)
    parts: list[str] = []
    for part in result.contents:
        assert isinstance(part.content, str), f"{uri} returned binary content"
        parts.append(part.content)
    return "".join(parts)
