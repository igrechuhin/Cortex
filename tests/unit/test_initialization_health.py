"""
Tests for initialization_health.py - file change handlers and health monitoring.

This module tests:
- handle_file_change for deleted events
- handle_file_change for modified events
- error handling when underlying initialization fails
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.managers.initialization_health import handle_file_change


@pytest.mark.asyncio
async def test_handle_file_change_deleted_updates_metadata() -> None:
    """handle_file_change should update metadata on deleted events."""
    file_path = Path("/fake/project/.cortex/memory-bank/file.md")

    metadata_index = AsyncMock()
    fs_manager = SimpleNamespace()
    token_counter = MagicMock()

    managers = SimpleNamespace(
        index=metadata_index, fs=fs_manager, tokens=token_counter
    )

    async def fake_get_managers(
        project_root: Path,
    ) -> object:  # pragma: no cover - trivial
        return managers

    with patch(
        "cortex.managers.initialization.get_managers",
        new=fake_get_managers,
    ):
        await handle_file_change(file_path, "deleted")

    metadata_index.update_file_metadata.assert_awaited_once_with(
        file_name=file_path.name,
        path=file_path,
        exists=False,
        size_bytes=0,
        token_count=0,
        content_hash="",
        sections=[],
        change_source="external",
    )


@pytest.mark.asyncio
async def test_handle_file_change_modified_updates_metadata_and_tokens() -> None:
    """handle_file_change should refresh metadata on modified events."""
    file_path = Path("/fake/project/.cortex/memory-bank/file.md")
    content = "section-content"
    content_hash = "hash123"

    class DummySection:
        def __init__(self, value: str) -> None:
            self.value = value

        def model_dump(self, mode: str = "json") -> dict[str, str]:
            return {"value": self.value, "mode": mode}

    metadata_index = AsyncMock()
    fs_manager = SimpleNamespace()
    fs_manager.read_file = AsyncMock(return_value=(content, content_hash))
    fs_manager.parse_sections = MagicMock(return_value=[DummySection("one")])
    token_counter = MagicMock()
    token_counter.count_tokens.return_value = 42

    managers = SimpleNamespace(
        index=metadata_index, fs=fs_manager, tokens=token_counter
    )

    async def fake_get_managers(
        project_root: Path,
    ) -> object:  # pragma: no cover - trivial
        return managers

    with patch(
        "cortex.managers.initialization.get_managers",
        new=fake_get_managers,
    ):
        await handle_file_change(file_path, "modified")

    fs_manager.read_file.assert_awaited_once_with(file_path)
    fs_manager.parse_sections.assert_called_once_with(content)
    token_counter.count_tokens.assert_called_once_with(content)

    metadata_index.update_file_metadata.assert_awaited_once_with(
        file_name=file_path.name,
        path=file_path,
        exists=True,
        size_bytes=len(content.encode("utf-8")),
        token_count=42,
        content_hash=content_hash,
        sections=[{"value": "one", "mode": "json"}],
        change_source="external",
    )


@pytest.mark.asyncio
async def test_handle_file_change_swallows_exceptions() -> None:
    """handle_file_change should not raise if initialization fails."""
    file_path = Path("/fake/project/.cortex/memory-bank/file.md")

    async def failing_get_managers(project_root: Path) -> object:
        raise RuntimeError("init failed")

    with patch(
        "cortex.managers.initialization.get_managers",
        new=failing_get_managers,
    ):
        # Should not raise despite the underlying failure
        await handle_file_change(file_path, "modified")
