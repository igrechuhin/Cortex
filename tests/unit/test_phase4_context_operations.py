"""
Unit tests for Phase 4 context loading operations.

Tests load_context_impl skips stale index entries (files in index but not on disk).
"""

import json
from pathlib import Path

import pytest

from cortex.managers.initialization import get_managers
from cortex.tools.phase4_context_operations import load_context_impl
from tests.helpers.path_helpers import ensure_test_cortex_structure


class TestLoadContextSkipsStaleIndexEntries:
    """Tests that load_context skips stale index entries."""

    @pytest.mark.asyncio
    async def test_load_context_skips_stale_index_entries(
        self, temp_project_root: Path
    ) -> None:
        """Stale index entries (in index but not on disk) are skipped."""
        # Arrange: memory-bank with one existing file
        memory_bank_dir = ensure_test_cortex_structure(temp_project_root)
        existing_path = memory_bank_dir / "existing.md"
        existing_content = "# Existing\n\nContent."
        _ = existing_path.write_text(existing_content)

        mgrs = await get_managers(temp_project_root)
        metadata_index = mgrs.index
        _ = await metadata_index.load()
        await metadata_index.update_file_metadata(
            file_name="existing.md",
            path=existing_path,
            exists=True,
            size_bytes=len(existing_content.encode("utf-8")),
            token_count=10,
            content_hash="sha256:abc",
            sections=[],
        )
        stale_path = memory_bank_dir / "stale.md"
        await metadata_index.update_file_metadata(
            file_name="stale.md",
            path=stale_path,
            exists=False,
            size_bytes=0,
            token_count=0,
            content_hash="",
            sections=[],
        )

        # Act
        result_json = await load_context_impl(
            mgrs,
            task_description="test",
            token_budget=50000,  # Enough budget after subtracting 10000 reserve
            strategy="dependency_aware",
            project_root=temp_project_root,
        )

        # Assert: result includes only existing file, not stale
        result = json.loads(result_json)
        assert result.get("status") == "success"
        selected = result.get("selected_files", [])
        assert "existing.md" in selected
        assert "stale.md" not in selected
