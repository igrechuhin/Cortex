import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.roadmap_corruption import (
    fix_memory_bank_content_if_needed,
    fix_roadmap_content_if_needed,
    fix_roadmap_corruption,
)


@pytest.mark.asyncio
class TestFixRoadmapCorruption:
    async def test_fix_roadmap_corruption_when_file_missing_returns_error(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        with patch(
            "cortex.tools.roadmap_corruption.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            # Act
            result_str = await fix_roadmap_corruption(dry_run=True)
            result = json.loads(result_str)

        # Assert
        assert result["success"] is False
        assert "not found" in result["error_message"]

    async def test_fix_roadmap_corruption_when_dry_run_does_not_modify_file(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        roadmap_path = tmp_path / ".cortex" / "memory-bank" / "roadmap.md"
        roadmap_path.parent.mkdir(parents=True, exist_ok=True)
        original = "Target completion:2026-01-01P\n"
        _ = roadmap_path.write_text(original, encoding="utf-8")

        with patch(
            "cortex.tools.roadmap_corruption.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            # Act
            result_str = await fix_roadmap_corruption(dry_run=True)
            result = json.loads(result_str)

        # Assert
        assert result["success"] is True
        assert result["corruption_count"] >= 1
        assert roadmap_path.read_text(encoding="utf-8") == original

    async def test_fix_roadmap_corruption_when_not_dry_run_modifies_file(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        roadmap_path = tmp_path / ".cortex" / "memory-bank" / "roadmap.md"
        roadmap_path.parent.mkdir(parents=True, exist_ok=True)
        original = "Target completion:2026-01-01P\n"
        _ = roadmap_path.write_text(original, encoding="utf-8")

        with patch(
            "cortex.tools.roadmap_corruption.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            # Act
            result_str = await fix_roadmap_corruption(dry_run=False)
            result = json.loads(result_str)

        # Assert
        assert result["success"] is True
        assert result["corruption_count"] >= 1
        updated = roadmap_path.read_text(encoding="utf-8")
        assert "Target completion: 2026-01-01" in updated


def test_fix_roadmap_content_if_needed_returns_fixed_content_when_corruption():
    """fix_roadmap_content_if_needed fixes corruption and returns corrected string."""
    content = "89.89to 0ctual ceeds90 285es unchanged 90.32coverage"
    result = fix_roadmap_content_if_needed(content)
    assert "89.89% to" in result
    assert "0 actual" in result
    assert "(exceeds 90%" in result
    assert "285 files unchanged" in result
    assert "90.32% coverage" in result


def test_fix_roadmap_content_if_needed_returns_same_when_no_corruption():
    """fix_roadmap_content_if_needed returns content unchanged when no corruption."""
    content = "# Roadmap\n\n## Section\n\nNo corruption here."
    result = fix_roadmap_content_if_needed(content)
    assert result == content


def test_fix_memory_bank_content_if_needed_fixes_progress_phrase_corruption():
    """fix_memory_bank_content_if_needed fixes phrase corruption for progress.md."""
    content = "## 2026-02-10\n\n- 90.32coverage 89.89to 0ctual\n"
    result = fix_memory_bank_content_if_needed(content, "progress.md")
    assert "90.32% coverage" in result
    assert "89.89% to" in result
    assert "0 actual" in result


def test_fix_memory_bank_content_if_needed_roadmap_gets_full_fix():
    """fix_memory_bank_content_if_needed applies full roadmap fix for roadmap.md."""
    content = "89.89to 90.32coverage"
    result = fix_memory_bank_content_if_needed(content, "roadmap.md")
    assert "89.89% to" in result
    assert "90.32% coverage" in result


def test_fix_memory_bank_content_if_needed_returns_unchanged_for_other_files():
    """fix_memory_bank_content_if_needed returns content unchanged for non-roadmap/progress."""
    content = "90.32coverage in activeContext"
    result = fix_memory_bank_content_if_needed(content, "activeContext.md")
    assert result == content


def test_fix_memory_bank_content_if_needed_progress_unchanged_when_no_phrase_corruption():
    """fix_memory_bank_content_if_needed returns progress unchanged when no phrase corruption."""
    content = "# Progress\n\n## 2026-02-10\n\n- Done.\n"
    result = fix_memory_bank_content_if_needed(content, "progress.md")
    assert result == content


class TestFixRoadmapCorruptionContextLogging:
    """Test fix_roadmap_corruption Context logging (FastMCP)."""

    @pytest.mark.asyncio
    async def test_fix_roadmap_corruption_calls_log_client_on_start_and_completion_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When ctx is passed, fix_roadmap_corruption logs start and completion."""
        # Arrange
        roadmap_path = tmp_path / ".cortex" / "memory-bank" / "roadmap.md"
        roadmap_path.parent.mkdir(parents=True, exist_ok=True)
        _ = roadmap_path.write_text("# Roadmap\n\n## Section\n", encoding="utf-8")
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.roadmap_corruption.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.roadmap_corruption.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
        ):
            # Act
            result_str = await fix_roadmap_corruption(dry_run=True, ctx=mock_ctx)
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True
            args_list = [c[0] for c in mock_log.call_args_list]
            levels_and_messages = [(a[1], a[2]) for a in args_list]
            assert (
                "info",
                "fix_roadmap_corruption: starting",
            ) in levels_and_messages
            assert (
                "info",
                "fix_roadmap_corruption: completed",
            ) in levels_and_messages

    @pytest.mark.asyncio
    async def test_fix_roadmap_corruption_calls_log_client_warning_when_file_missing_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When roadmap not found and ctx is passed, logs warning."""
        # Arrange
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.roadmap_corruption.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.roadmap_corruption.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
        ):
            # Act
            result_str = await fix_roadmap_corruption(dry_run=True, ctx=mock_ctx)
            result = json.loads(result_str)

            # Assert
            assert result["success"] is False
            assert any(
                c[0][1] == "warning"
                and "fix_roadmap_corruption: roadmap not found" in str(c[0][2])
                for c in mock_log.call_args_list
                if len(c[0]) >= 3
            )
