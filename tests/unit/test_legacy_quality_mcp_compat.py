"""Guardrail: legacy quality MCP sunset annotation must stay until removal."""

from __future__ import annotations

from pathlib import Path


def test_legacy_quality_mcp_compat_module_keeps_sunset_annotation() -> None:
    """Fail if the hard-removal marker is dropped before migration completes."""
    root = Path(__file__).resolve().parents[2]
    path = (
        root / "src" / "cortex" / "tools" / "execution" / "legacy_quality_mcp_compat.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "DEPRECATED: remove by 2026-07-01" in text
