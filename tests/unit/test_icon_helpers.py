# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Unit tests for cortex.core.icon_helpers."""

import base64

from mcp.types import Icon

from cortex.core.icon_helpers import create_emoji_icon, create_emoji_icons


class TestCreateEmojiIcon:
    """Test create_emoji_icon helper."""

    def test_returns_icon_instance(self) -> None:
        """create_emoji_icon returns an Icon instance."""
        icon = create_emoji_icon("🚀")
        assert isinstance(icon, Icon)

    def test_src_is_data_uri(self) -> None:
        """Icon src is a data URI with base64 SVG."""
        icon = create_emoji_icon("📝")
        assert icon.src.startswith("data:image/svg+xml;base64,")
        payload = icon.src.split(",", 1)[1]
        decoded = base64.b64decode(payload).decode("utf-8")
        assert "svg" in decoded
        assert "📝" in decoded

    def test_mime_type_default(self) -> None:
        """Default mimeType is image/svg+xml."""
        icon = create_emoji_icon("✅")
        assert icon.mimeType == "image/svg+xml"

    def test_sizes_default_24(self) -> None:
        """Default size 24 produces sizes [24x24]."""
        icon = create_emoji_icon("🔧")
        assert icon.sizes == ["24x24"]

    def test_custom_size(self) -> None:
        """Custom size is reflected in sizes."""
        icon = create_emoji_icon("📁", size=48)
        assert icon.sizes == ["48x48"]
        decoded = base64.b64decode(icon.src.split(",", 1)[1]).decode("utf-8")
        assert 'width="48"' in decoded
        assert 'height="48"' in decoded

    def test_different_emojis_produce_different_svg(self) -> None:
        """Different emoji strings produce different SVG content."""
        icon_a = create_emoji_icon("🏗️")
        icon_b = create_emoji_icon("📦")
        assert icon_a.src != icon_b.src
        dec_a = base64.b64decode(icon_a.src.split(",", 1)[1]).decode("utf-8")
        dec_b = base64.b64decode(icon_b.src.split(",", 1)[1]).decode("utf-8")
        assert "🏗️" in dec_a
        assert "📦" in dec_b


class TestCreateEmojiIcons:
    """Test create_emoji_icons helper."""

    def test_returns_list_of_icons(self) -> None:
        """create_emoji_icons returns list of Icon."""
        icons = create_emoji_icons("💾")
        assert isinstance(icons, list)
        assert all(isinstance(i, Icon) for i in icons)

    def test_default_sizes(self) -> None:
        """Default sizes are 24x24 and 48x48."""
        icons = create_emoji_icons("🔗")
        assert len(icons) == 2
        assert icons[0].sizes == ["24x24"]
        assert icons[1].sizes == ["48x48"]

    def test_custom_sizes(self) -> None:
        """Custom sizes list is respected."""
        icons = create_emoji_icons("⚙️", sizes=["32x32", "64x64"])
        assert len(icons) == 2
        assert icons[0].sizes == ["32x32"]
        assert icons[1].sizes == ["64x64"]

    def test_invalid_size_fallback(self) -> None:
        """Invalid size descriptor falls back to 24."""
        icons = create_emoji_icons("📋", sizes=["bad", "12x12"])
        assert len(icons) == 2
        assert icons[0].sizes == ["24x24"]
        assert icons[1].sizes == ["12x12"]
