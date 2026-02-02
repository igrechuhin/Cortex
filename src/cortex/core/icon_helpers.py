# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Icon helper utilities for creating emoji-based MCP icons."""

import base64
from typing import Literal

from mcp.types import Icon


def create_emoji_icon(
    emoji: str,
    size: int = 24,
    mime_type: Literal["image/svg+xml"] = "image/svg+xml",
) -> Icon:
    """Create an Icon from an emoji using SVG data URI.

    Args:
        emoji: Emoji character(s) to use as icon
        size: Icon size in pixels (default: 24)
        mime_type: MIME type for the icon (default: "image/svg+xml")

    Returns:
        Icon object with emoji rendered as SVG data URI
    """
    font_size = max(8, int(size * 0.8))
    svg_content = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}">'
        f'<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" '
        f'font-size="{font_size}px">{emoji}</text></svg>'
    )
    svg_bytes = svg_content.encode("utf-8")
    base64_svg = base64.b64encode(svg_bytes).decode("utf-8")
    data_uri = f"data:{mime_type};base64,{base64_svg}"
    return Icon(
        src=data_uri,
        mimeType=mime_type,
        sizes=[f"{size}x{size}"],
    )


def create_emoji_icons(
    emoji: str,
    sizes: list[str] | None = None,
) -> list[Icon]:
    """Create multiple Icon objects for different sizes.

    Args:
        emoji: Emoji character(s) to use as icon
        sizes: List of size descriptors (e.g., ["24x24", "48x48"])

    Returns:
        List of Icon objects for each size
    """
    if sizes is None:
        sizes = ["24x24", "48x48"]
    icons: list[Icon] = []
    for size_desc in sizes:
        try:
            size = int(size_desc.split("x")[0])
        except (ValueError, IndexError):
            size = 24
        icons.append(create_emoji_icon(emoji, size=size))
    return icons
