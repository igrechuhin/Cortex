"""Tests for session_start roadmap parsing and git helpers."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.tools.session.brief_extraction_helpers import (
    extract_current_focus,
    extract_recent_completed,
)
from cortex.tools.session.start_tools import (
    extract_next_work_item,
    get_git_status,
    parse_roadmap_sections,
    run_git_command,
)


class TestParseRoadmapSections:
    """Tests for parse_roadmap_sections helper."""

    def test_parse_roadmap_sections_basic(self) -> None:
        """Test parsing roadmap with all sections."""
        content = """# Roadmap

## Blockers (ASAP Priority)
- Item 1

## Active Work (in progress)
- Item 2

## Future Enhancements
- Item 3

## Pending plans (from .cortex/plans)
- Item 4
"""
        sections = parse_roadmap_sections(content)
        assert "blockers" in sections
        assert "active_work" in sections
        assert "future" in sections
        assert "pending" in sections

    def test_parse_roadmap_sections_partial(self) -> None:
        """Test parsing roadmap with only some sections."""
        content = """# Roadmap

## Blockers (ASAP Priority)
- Item 1
"""
        sections = parse_roadmap_sections(content)
        assert "blockers" in sections
        assert "active_work" not in sections

    def test_parse_roadmap_sections_empty(self) -> None:
        """Test parsing empty roadmap."""
        sections = parse_roadmap_sections("")
        assert sections == {}


class TestExtractCurrentFocus:
    """Tests for extract_current_focus helper."""

    def test_extract_current_focus_found(self) -> None:
        """Test extracting current focus when section exists."""
        content = """# Active Context

## Current Focus

Working on Phase 54.

## Next Steps
"""
        focus = extract_current_focus(content)
        assert "Working on Phase 54" in focus

    def test_extract_current_focus_not_found(self) -> None:
        """Test extracting current focus when section doesn't exist."""
        content = """# Active Context

## Next Steps
"""
        focus = extract_current_focus(content)
        assert focus == ""

    def test_extract_current_focus_empty_section(self) -> None:
        """Test extracting current focus when section is empty."""
        content = """# Active Context

## Current Focus

## Next Steps
"""
        focus = extract_current_focus(content)
        assert focus == ""


class TestExtractRecentCompleted:
    """Tests for extract_recent_completed helper."""

    def test_extract_recent_completed_found(self) -> None:
        """Test extracting recent completed items."""
        content = """# Active Context

## Completed Work

- ✅ Item 1 - COMPLETE
- ✅ Item 2 - COMPLETE
- ✅ Item 3 - COMPLETE

## Next Steps
"""
        completed = extract_recent_completed(content)
        assert len(completed) == 3
        assert "Item 1" in completed[0]
        assert "Item 2" in completed[1]
        assert "Item 3" in completed[2]

    def test_extract_recent_completed_with_max_items(self) -> None:
        """Test extracting recent completed items with max limit."""
        content = """# Active Context

## Completed Work

- ✅ Item 1 - COMPLETE
- ✅ Item 2 - COMPLETE
- ✅ Item 3 - COMPLETE
- ✅ Item 4 - COMPLETE
- ✅ Item 5 - COMPLETE
- ✅ Item 6 - COMPLETE
"""
        completed = extract_recent_completed(content, max_items=3)
        assert len(completed) == 3

    def test_extract_recent_completed_not_found(self) -> None:
        """Test extracting recent completed when section doesn't exist."""
        content = """# Active Context

## Next Steps
"""
        completed = extract_recent_completed(content)
        assert completed == []

    def test_extract_recent_completed_bold_format(self) -> None:
        """Test extracting recent completed items with bold format."""
        content = """# Active Context

## Completed Work

- **Item 1** - COMPLETE
- **Item 2** - COMPLETE
"""
        completed = extract_recent_completed(content)
        assert len(completed) == 2
        assert "Item 1" in completed[0]
        assert "Item 2" in completed[1]


class TestExtractNextWorkItem:
    """Tests for extract_next_work_item helper."""

    @pytest.mark.asyncio
    async def test_extract_next_work_item_pending(self) -> None:
        """Test extracting next PENDING work item."""
        content = """# Roadmap

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Phase 54** - PENDING - Description here
"""
        work_item, plan_path = await extract_next_work_item(content, project_root=None)
        assert work_item is not None
        assert "Phase 54" in work_item
        assert plan_path is None

    @pytest.mark.asyncio
    async def test_extract_next_work_item_with_plan_path(self) -> None:
        """Test extracting next work item with plan path."""
        content = """# Roadmap

## Pending plans (from .cortex/plans)

- **Phase 54** - PENDING - Description. Plan: .cortex/plans/phase-54.md
"""
        work_item, plan_path = await extract_next_work_item(content, project_root=None)
        assert work_item is not None
        assert plan_path == ".cortex/plans/phase-54.md"

    @pytest.mark.asyncio
    async def test_extract_next_work_item_not_found(self) -> None:
        """Test extracting next work item when none exists."""
        content = """# Roadmap

## Pending plans (from .cortex/plans)

- **Phase 54** - IN PROGRESS - Description
"""
        work_item, plan_path = await extract_next_work_item(content, project_root=None)
        assert work_item is None
        assert plan_path is None

    @pytest.mark.asyncio
    async def test_extract_next_work_item_priority_order(self) -> None:
        """Test that blockers are checked before pending."""
        content = """# Roadmap

## Blockers (ASAP Priority)

- **Blocker** - PENDING - Urgent

## Pending plans (from .cortex/plans)

- **Phase 54** - PENDING - Description
"""
        work_item, _ = await extract_next_work_item(content, project_root=None)
        assert work_item is not None
        assert "Blocker" in work_item


class TestRunGitCommand:
    """Tests for run_git_command helper."""

    @pytest.mark.asyncio
    async def test_run_git_command_success(self, tmp_path: Path) -> None:
        """Test running git command successfully."""
        # Mock subprocess to avoid real git init (fails in sandbox/restricted envs)
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(b"On branch main\nNo commits yet\n", b"")
        )
        with patch(
            "cortex.tools.session.start_tools.asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=mock_process,
        ):
            result = await run_git_command(["git", "status"], cwd=tmp_path)
        assert result.success
        assert "On branch" in result.stdout or "No commits yet" in result.stdout

    @pytest.mark.asyncio
    async def test_run_git_command_timeout(self) -> None:
        """Test git command timeout."""
        result = await run_git_command(
            ["sleep", "10"],
            timeout=0.1,  # Will timeout quickly
        )
        assert not result.success
        assert (
            "timed out" in result.stderr.lower()
            or "timed out" in (result.error or "").lower()
        )

    @pytest.mark.asyncio
    async def test_run_git_command_failure(self) -> None:
        """Test git command failure."""
        result = await run_git_command(["git", "nonexistent-command"])
        assert not result.success


class TestGetGitStatus:
    """Tests for get_git_status helper."""

    @pytest.mark.asyncio
    async def test_get_git_status_no_git(self, tmp_path: Path) -> None:
        """Test git status when .git doesn't exist."""
        status = await get_git_status(tmp_path)
        assert status is None

    @pytest.mark.asyncio
    async def test_get_git_status_clean(self, tmp_path: Path) -> None:
        """Test git status with clean working directory."""
        (tmp_path / ".git").mkdir()  # Satisfy get_git_status .git check
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        with patch(
            "cortex.tools.session.start_tools.asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=mock_process,
        ):
            status = await get_git_status(tmp_path)
        assert status is not None
        assert status.has_uncommitted_changes is False

    @pytest.mark.asyncio
    async def test_get_git_status_with_changes(self, tmp_path: Path) -> None:
        """Test git status with uncommitted changes."""
        (tmp_path / ".git").mkdir()
        # Porcelain output: M = modified, ?? = untracked
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(b" M modified.txt\n?? untracked.txt\n", b"")
        )
        with patch(
            "cortex.tools.session.start_tools.asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=mock_process,
        ):
            status = await get_git_status(tmp_path)
            assert status is not None
            assert status.has_uncommitted_changes is True
            assert status.modified_files_count > 0 or status.untracked_files_count > 0
