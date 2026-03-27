"""Unit tests for session_start tool.

Tests the session_start tool that combines orientation tasks into a single call.
"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.tools.context.effectiveness_operations import analyze_current_session
from cortex.tools.memory.compaction_operations import compact_session, write_handoff
from cortex.tools.models import (
    GitStatusSummary,
    SessionHandoff,
    SessionHealthSummary,
    SessionStartErrorResult,
    SessionStartResult,
)
from cortex.tools.session.brief_extraction_helpers import (
    extract_current_focus,
    extract_recent_completed,
    generate_session_suggestions,
)
from cortex.tools.session.health import (
    calculate_health_summary,
    determine_token_budget_status,
    parse_mcp_health,
)
from cortex.tools.session.models import SESSION_SCOPE_PROMPT, TokenBudgetStatus
from cortex.tools.session.start_tools import (
    extract_next_work_item,
    get_git_status,
    parse_roadmap_sections,
    run_git_command,
    session_start,
    session_start_impl,
)
from tests.helpers.managers import make_test_managers
from tests.helpers.path_helpers import ensure_test_cortex_structure
from tests.helpers.tool_call_helpers import get_tool_fn


# ConnectionHealth (cortex.core.models) shape matching health_check
def _mcp_health_json(healthy: bool) -> str:
    """Build valid health_check-style JSON for tests."""
    health = {
        "healthy": healthy,
        "concurrent_operations": 0,
        "max_concurrent": 5,
        "semaphore_available": 5,
        "utilization_percent": 0.0,
        "long_running_holder": None,
    }
    return json.dumps({"status": "success", "health": health})


# ============================================================================
# Helper Function Tests
# ============================================================================


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


class TestCalculateHealthSummary:
    """Tests for _calculate_health_summary helper."""

    @pytest.mark.asyncio
    async def test_calculate_health_summary_all_files(self, tmp_path: Path) -> None:
        """Test health summary with all files present."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)

        # Create all required files
        required_files = [
            "projectBrief.md",
            "activeContext.md",
            "roadmap.md",
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]
        for file_name in required_files:
            _ = (memory_bank_dir / file_name).write_text(f"# {file_name}\n\nContent")

        # Create managers with metadata index
        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()

        # Update metadata for all files
        for file_name in required_files:
            file_path = memory_bank_dir / file_name
            await metadata_index.update_file_metadata(
                file_name=file_name,
                path=file_path,
                exists=True,
                size_bytes=100,
                token_count=50,
                content_hash="sha256:test",
                sections=[],
            )

        managers = make_test_managers(fs=fs_manager, index=metadata_index)

        health = await calculate_health_summary(
            managers,
            tmp_path,  # type: ignore[arg-type]
        )
        assert health.file_count == 7
        assert health.total_tokens == 350  # 7 files * 50 tokens
        assert health.token_budget_status == "healthy"
        assert len(health.missing_files) == 0
        assert health.has_errors is False

    @pytest.mark.asyncio
    async def test_calculate_health_summary_missing_files(self, tmp_path: Path) -> None:
        """Test health summary with missing files."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)

        # Create only some files
        _ = (memory_bank_dir / "activeContext.md").write_text("# Active Context")
        _ = (memory_bank_dir / "roadmap.md").write_text("# Roadmap")

        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()

        managers = make_test_managers(fs=fs_manager, index=metadata_index)

        health = await calculate_health_summary(
            managers,
            tmp_path,  # type: ignore[arg-type]
        )
        assert health.file_count == 2
        assert len(health.missing_files) == 5
        assert health.has_errors is True

    @pytest.mark.asyncio
    async def test_calculate_health_summary_over_budget(self, tmp_path: Path) -> None:
        """Test health summary when token budget is exceeded."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)

        # Create file with high token count
        _ = (memory_bank_dir / "activeContext.md").write_text("# Active Context")

        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()

        # Set token count to exceed budget (80000)
        await metadata_index.update_file_metadata(
            file_name="activeContext.md",
            path=memory_bank_dir / "activeContext.md",
            exists=True,
            size_bytes=100,
            token_count=90000,  # Exceeds 80000 budget
            content_hash="sha256:test",
            sections=[],
        )

        managers = make_test_managers(fs=fs_manager, index=metadata_index)

        health = await calculate_health_summary(
            managers,
            tmp_path,  # type: ignore[arg-type]
        )
        assert health.token_budget_status == "over_budget"


class TestGenerateSessionSuggestions:
    """Tests for generate_session_suggestions helper."""

    def test_generate_suggestions_git_changes(self) -> None:
        """Test suggestions when git has uncommitted changes."""
        health = SessionHealthSummary(
            file_count=7,
            total_tokens=10000,
            token_budget_status=TokenBudgetStatus.HEALTHY,
            missing_files=[],
            has_errors=False,
        )
        git_status = GitStatusSummary(
            has_uncommitted_changes=True,
            modified_files_count=2,
            untracked_files_count=1,
        )
        suggestions = generate_session_suggestions(health, git_status, None)
        assert len(suggestions) > 0
        assert any("uncommitted changes" in s.lower() for s in suggestions)

    def test_generate_suggestions_over_budget(self) -> None:
        """Test suggestions when token budget is exceeded."""
        health = SessionHealthSummary(
            file_count=7,
            total_tokens=90000,
            token_budget_status=TokenBudgetStatus.OVER_BUDGET,
            missing_files=[],
            has_errors=False,
        )
        suggestions = generate_session_suggestions(health, None, None)
        assert len(suggestions) > 0
        assert any("budget" in s.lower() for s in suggestions)

    def test_generate_suggestions_missing_files(self) -> None:
        """Test suggestions when files are missing."""
        health = SessionHealthSummary(
            file_count=5,
            total_tokens=10000,
            token_budget_status=TokenBudgetStatus.HEALTHY,
            missing_files=["projectBrief.md", "systemPatterns.md"],
            has_errors=True,
        )
        suggestions = generate_session_suggestions(health, None, None)
        assert len(suggestions) > 0
        assert any("missing" in s.lower() for s in suggestions)

    def test_generate_suggestions_next_work_item(self) -> None:
        """Test suggestions include next work item."""
        health = SessionHealthSummary(
            file_count=7,
            total_tokens=10000,
            token_budget_status=TokenBudgetStatus.HEALTHY,
            missing_files=[],
            has_errors=False,
        )
        suggestions = generate_session_suggestions(
            health, None, "Phase 54: Session Start"
        )
        assert len(suggestions) > 0
        assert any("Phase 54" in s for s in suggestions)

    def test_generate_suggestions_mcp_unhealthy(self) -> None:
        """Test that MCP unhealthy prepends critical suggestion."""
        health = SessionHealthSummary(
            file_count=7,
            total_tokens=10000,
            token_budget_status=TokenBudgetStatus.HEALTHY,
            missing_files=[],
            has_errors=False,
        )
        suggestions = generate_session_suggestions(
            health, None, None, mcp_healthy=False
        )
        assert len(suggestions) > 0
        assert "do not proceed without mcp" in suggestions[0].lower()


class TestParseMCPHealth:
    """Tests for _parse_mcp_health helper."""

    def test_parse_mcp_health_success_healthy(self) -> None:
        """Parse successful healthy response."""
        ok, msg = parse_mcp_health(_mcp_health_json(healthy=True))
        assert ok is True
        assert msg is None

    def test_parse_mcp_health_success_unhealthy(self) -> None:
        """Parse successful but unhealthy response."""
        ok, msg = parse_mcp_health(_mcp_health_json(healthy=False))
        assert ok is False
        assert msg == "MCP connection unhealthy"

    def test_parse_mcp_health_error_status(self) -> None:
        """Parse error status response."""
        err = json.dumps({"status": "error", "error": "Connection failed"})
        ok, msg = parse_mcp_health(err)
        assert ok is False
        assert "Connection failed" in (msg or "")

    def test_parse_mcp_health_invalid_json(self) -> None:
        """Parse invalid JSON returns unhealthy."""
        ok, msg = parse_mcp_health("not json")
        assert ok is False
        assert msg is not None

    def test_parse_mcp_health_health_none(self) -> None:
        """Parse success status with health null returns unhealthy."""
        payload = json.dumps({"status": "success", "health": None})
        ok, msg = parse_mcp_health(payload)
        assert ok is False
        assert msg == "MCP health check response invalid"


class TestDetermineTokenBudgetStatus:
    """Tests for determine_token_budget_status."""

    def test_healthy_when_under_85_percent(self) -> None:
        """Returns HEALTHY when usage is below 85%."""
        assert determine_token_budget_status(0) == TokenBudgetStatus.HEALTHY
        assert determine_token_budget_status(84999, 100000) == TokenBudgetStatus.HEALTHY

    def test_warning_when_85_to_99_percent(self) -> None:
        """Returns WARNING when usage is 85% to under 100%."""
        assert determine_token_budget_status(85000, 100000) == TokenBudgetStatus.WARNING
        assert determine_token_budget_status(99999, 100000) == TokenBudgetStatus.WARNING

    def test_over_budget_when_100_percent_or_more(self) -> None:
        """Returns OVER_BUDGET when usage is 100% or more."""
        assert (
            determine_token_budget_status(100000, 100000)
            == TokenBudgetStatus.OVER_BUDGET
        )
        assert (
            determine_token_budget_status(100001, 100000)
            == TokenBudgetStatus.OVER_BUDGET
        )


# ============================================================================
# Implementation Tests
# ============================================================================


class TestSessionStartImpl:
    """Tests for session_start_impl."""

    @pytest.mark.asyncio
    async def test_session_start_impl_success(self, tmp_path: Path) -> None:
        """Test successful session start."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)

        # Create required files
        active_context_content = """# Active Context

## Current Focus

Working on Phase 54.

## Completed Work

- ✅ Phase 50 - COMPLETE
- ✅ Phase 51 - COMPLETE

## Next Steps
"""
        _ = (memory_bank_dir / "activeContext.md").write_text(active_context_content)

        roadmap_content = """# Roadmap

## Pending plans (from .cortex/plans)

- **Phase 54** - PENDING - Session Start Initializer
"""
        _ = (memory_bank_dir / "roadmap.md").write_text(roadmap_content)

        project_brief_content = "# Cortex\n\nProject description."
        _ = (memory_bank_dir / "projectBrief.md").write_text(project_brief_content)

        # Create other required files
        for file_name in [
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            _ = (memory_bank_dir / file_name).write_text(f"# {file_name}\n\nContent")

        # Setup managers
        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()

        token_counter = TokenCounter()

        # Update metadata
        for file_name in [
            "activeContext.md",
            "roadmap.md",
            "projectBrief.md",
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            await metadata_index.update_file_metadata(
                file_name=file_name,
                path=memory_bank_dir / file_name,
                exists=True,
                size_bytes=100,
                token_count=50,
                content_hash="sha256:test",
                sections=[],
            )

        managers = make_test_managers(
            fs=fs_manager, index=metadata_index, tokens=token_counter
        )

        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            result = await session_start_impl(
                None,
                tmp_path,
                managers,  # type: ignore[arg-type]
            )

        assert isinstance(result, SessionStartResult)
        assert result.status == "success"
        assert result.brief is not None
        assert result.brief.project_name == "Cortex"
        assert "Phase 54" in result.brief.current_focus
        assert len(result.brief.recent_completed) == 2
        assert result.brief.next_work_item is not None
        assert "Phase 54" in result.brief.next_work_item
        assert result.token_count > 0
        assert result.brief.mcp_healthy is True
        assert result.brief.session_scope
        assert result.brief.session_scope == SESSION_SCOPE_PROMPT
        assert "Session Scope" in result.brief.session_scope

    @pytest.mark.asyncio
    async def test_session_start_impl_seeds_context_telemetry_for_analysis(
        self, tmp_path: Path
    ) -> None:
        """Successful session_start writes one telemetry call to avoid no_data."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        _ = (memory_bank_dir / "activeContext.md").write_text(
            "# Active Context\n\n## Current Focus\n\nTest.\n"
        )
        _ = (memory_bank_dir / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending plans (from .cortex/plans)\n\n- **Task** - PENDING - Desc\n"
        )
        _ = (memory_bank_dir / "projectBrief.md").write_text("# Cortex\n")
        for file_name in [
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            _ = (memory_bank_dir / file_name).write_text(f"# {file_name}\n")

        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()
        for file_name in [
            "activeContext.md",
            "roadmap.md",
            "projectBrief.md",
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            await metadata_index.update_file_metadata(
                file_name=file_name,
                path=memory_bank_dir / file_name,
                exists=True,
                size_bytes=100,
                token_count=50,
                content_hash="sha256:test",
                sections=[],
            )
        managers = make_test_managers(
            fs=fs_manager,
            index=metadata_index,
            tokens=TokenCounter(),
        )
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "session_start_seed_1"
        try:
            with patch(
                "cortex.tools.session.health.get_mcp_health_status",
                new_callable=AsyncMock,
                return_value=(True, None),
            ):
                result = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]
            assert isinstance(result, SessionStartResult)
            assert result.status == "success"
            analysis = analyze_current_session(tmp_path)
            assert analysis.status == "success"
            current_raw = analysis.current_session
            assert current_raw is not None
            current = current_raw.model_dump(mode="python")
            assert current["calls_analyzed"] == 1
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_session_start_impl_does_not_duplicate_seeded_context_telemetry(
        self, tmp_path: Path
    ) -> None:
        """Repeated session_start in same session keeps a single seeded telemetry row."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        _ = (memory_bank_dir / "activeContext.md").write_text(
            "# Active Context\n\n## Current Focus\n\nTest.\n"
        )
        _ = (memory_bank_dir / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending plans (from .cortex/plans)\n\n- **Task** - PENDING - Desc\n"
        )
        _ = (memory_bank_dir / "projectBrief.md").write_text("# Cortex\n")
        for file_name in [
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            _ = (memory_bank_dir / file_name).write_text(f"# {file_name}\n")

        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()
        for file_name in [
            "activeContext.md",
            "roadmap.md",
            "projectBrief.md",
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            await metadata_index.update_file_metadata(
                file_name=file_name,
                path=memory_bank_dir / file_name,
                exists=True,
                size_bytes=100,
                token_count=50,
                content_hash="sha256:test",
                sections=[],
            )
        managers = make_test_managers(
            fs=fs_manager,
            index=metadata_index,
            tokens=TokenCounter(),
        )
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "session_start_seed_2"
        try:
            with patch(
                "cortex.tools.session.health.get_mcp_health_status",
                new_callable=AsyncMock,
                return_value=(True, None),
            ):
                _ = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]
                _ = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]
            analysis = analyze_current_session(tmp_path)
            assert analysis.status == "success"
            current_raw = analysis.current_session
            assert current_raw is not None
            current = current_raw.model_dump(mode="python")
            assert current["calls_analyzed"] == 1
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_session_start_impl_includes_handoff(self, tmp_path: Path) -> None:
        """Test that session_start includes handoff when it exists."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)

        # Create required files
        active_context_content = """# Active Context

## Current Focus

Working on Phase 54.

## Completed Work

- ✅ Phase 50 - COMPLETE
"""
        _ = (memory_bank_dir / "activeContext.md").write_text(active_context_content)

        roadmap_content = """# Roadmap

## Pending plans (from .cortex/plans)

- **Phase 54** - PENDING - Session Start Initializer
"""
        _ = (memory_bank_dir / "roadmap.md").write_text(roadmap_content)

        project_brief_content = "# Cortex\n\nProject description."
        _ = (memory_bank_dir / "projectBrief.md").write_text(project_brief_content)

        # Create other required files
        for file_name in [
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            _ = (memory_bank_dir / file_name).write_text(f"# {file_name}\n\nContent")

        # Setup managers
        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()

        token_counter = TokenCounter()

        # Update metadata
        for file_name in [
            "activeContext.md",
            "roadmap.md",
            "projectBrief.md",
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            await metadata_index.update_file_metadata(
                file_name=file_name,
                path=memory_bank_dir / file_name,
                exists=True,
                size_bytes=100,
                token_count=50,
                content_hash="sha256:test",
                sections=[],
            )

        # Create a handoff file before calling session_start
        handoff = SessionHandoff(
            session_id="2026-02-20T17-00",
            completed_tasks=["Phase 50 Step 1", "Phase 50 Step 2"],
            in_progress=None,
            decisions_made=["Use Pydantic v2"],
            blockers=[],
            next_actions=["Complete Phase 54"],
        )
        await write_handoff(tmp_path, handoff, fs_manager)

        managers = make_test_managers(
            fs=fs_manager, index=metadata_index, tokens=token_counter
        )

        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            result = await session_start_impl(
                None,
                tmp_path,
                managers,  # type: ignore[arg-type]
            )

        assert isinstance(result, SessionStartResult)
        assert result.status == "success"
        assert result.brief is not None
        assert result.brief.last_handoff is not None
        assert result.brief.last_handoff.session_id == "2026-02-20T17-00"
        assert len(result.brief.last_handoff.completed_tasks) == 2
        assert "Phase 50 Step 1" in result.brief.last_handoff.completed_tasks
        assert "Phase 50 Step 2" in result.brief.last_handoff.completed_tasks
        assert result.brief.last_handoff.next_actions == ["Complete Phase 54"]

    @pytest.mark.asyncio
    async def test_session_start_impl_handoff_none_when_missing(
        self, tmp_path: Path
    ) -> None:
        """Test that session_start returns None handoff when file doesn't exist."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)

        # Create required files
        active_context_content = """# Active Context

## Current Focus

Working on Phase 54.
"""
        _ = (memory_bank_dir / "activeContext.md").write_text(active_context_content)

        roadmap_content = """# Roadmap

## Pending plans (from .cortex/plans)

- **Phase 54** - PENDING - Session Start Initializer
"""
        _ = (memory_bank_dir / "roadmap.md").write_text(roadmap_content)

        project_brief_content = "# Cortex\n\nProject description."
        _ = (memory_bank_dir / "projectBrief.md").write_text(project_brief_content)

        # Create other required files
        for file_name in [
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            _ = (memory_bank_dir / file_name).write_text(f"# {file_name}\n\nContent")

        # Setup managers
        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()

        token_counter = TokenCounter()

        # Update metadata
        for file_name in [
            "activeContext.md",
            "roadmap.md",
            "projectBrief.md",
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            await metadata_index.update_file_metadata(
                file_name=file_name,
                path=memory_bank_dir / file_name,
                exists=True,
                size_bytes=100,
                token_count=50,
                content_hash="sha256:test",
                sections=[],
            )

        # Don't create handoff file - should return None

        managers = make_test_managers(
            fs=fs_manager, index=metadata_index, tokens=token_counter
        )

        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            result = await session_start_impl(
                None,
                tmp_path,
                managers,  # type: ignore[arg-type]
            )

        assert isinstance(result, SessionStartResult)
        assert result.status == "success"
        assert result.brief is not None
        assert result.brief.last_handoff is None

    @pytest.mark.asyncio
    async def test_session_lifecycle_compact_then_session_start_sees_handoff(
        self, tmp_path: Path
    ) -> None:
        """Integration: compact_session then session_start returns handoff in brief."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        active_content = """# Active Context

## Current Focus

Test.

## Completed Work (2026-02-01)

- Old task
"""
        _ = (memory_bank_dir / "activeContext.md").write_text(active_content)
        _ = (memory_bank_dir / "progress.md").write_text(
            "# Progress\n\n## 2026-02-21\n\n- Entry\n"
        )
        _ = (memory_bank_dir / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- Item\n"
        )
        _ = (memory_bank_dir / "projectBrief.md").write_text("# Cortex\n")
        for f in ["systemPatterns.md", "techContext.md", "productContext.md"]:
            _ = (memory_bank_dir / f).write_text(f"# {f}\n")

        fs_manager = FileSystemManager(tmp_path)
        token_counter = TokenCounter()
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()
        version_manager = VersionManager(tmp_path)
        for file_name in [
            "activeContext.md",
            "roadmap.md",
            "projectBrief.md",
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            await metadata_index.update_file_metadata(
                file_name=file_name,
                path=memory_bank_dir / file_name,
                exists=True,
                size_bytes=100,
                token_count=50,
                content_hash="sha256:test",
                sections=[],
            )
        managers = make_test_managers(
            fs=fs_manager,
            tokens=token_counter,
            index=metadata_index,
            versions=version_manager,
        )
        # Patch in compaction_operations so compact_session uses tmp_path and our test managers
        with (
            patch(
                "cortex.tools.compaction_operations.get_current_managers",
                return_value=managers,
            ),
            patch(
                "cortex.tools.compaction_operations.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
        ):
            tool_fn = get_tool_fn(compact_session)
            _ = await tool_fn(summary="Lifecycle integration test", ctx=None)

        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            result = await session_start_impl(
                None,
                tmp_path,
                managers,  # type: ignore[arg-type]
            )
        assert isinstance(result, SessionStartResult)
        assert result.status == "success"
        assert result.brief is not None
        assert result.brief.last_handoff is not None
        assert "Lifecycle integration test" in result.brief.last_handoff.next_actions

    @pytest.mark.asyncio
    async def test_session_start_impl_mcp_unhealthy(self, tmp_path: Path) -> None:
        """Test session start when MCP health check returns unhealthy."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        _ = (memory_bank_dir / "activeContext.md").write_text(
            "# Active Context\n\n## Current Focus\n\nTest.\n"
        )
        _ = (memory_bank_dir / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- **Task** - PENDING\n"
        )
        _ = (memory_bank_dir / "projectBrief.md").write_text("# Cortex\n")
        for f in [
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            _ = (memory_bank_dir / f).write_text(f"# {f}\n")
        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()
        for file_name in [
            "activeContext.md",
            "roadmap.md",
            "projectBrief.md",
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            await metadata_index.update_file_metadata(
                file_name=file_name,
                path=memory_bank_dir / file_name,
                exists=True,
                size_bytes=100,
                token_count=50,
                content_hash="sha256:test",
                sections=[],
            )
        managers = make_test_managers(
            fs=fs_manager, index=metadata_index, tokens=TokenCounter()
        )
        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(False, "MCP connection unhealthy"),
        ):
            result = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]
        assert isinstance(result, SessionStartResult)
        assert result.brief.mcp_healthy is False
        assert result.brief.mcp_health_message == "MCP connection unhealthy"
        assert any(
            "do not proceed without mcp" in s.lower()
            for s in result.brief.session_suggestions
        )

    @pytest.mark.asyncio
    async def test_session_start_impl_missing_active_context(
        self, tmp_path: Path
    ) -> None:
        """Test session start when activeContext.md is missing."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        _ = (memory_bank_dir / "roadmap.md").write_text("# Roadmap")

        fs_manager = FileSystemManager(tmp_path)
        managers = make_test_managers(fs=fs_manager)

        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            result = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]

        assert isinstance(result, SessionStartErrorResult)
        assert result.status == "error"
        assert "activeContext.md" in result.error

    @pytest.mark.asyncio
    async def test_session_start_impl_missing_roadmap(self, tmp_path: Path) -> None:
        """Test session start when roadmap.md is missing."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        _ = (memory_bank_dir / "activeContext.md").write_text("# Active Context")

        fs_manager = FileSystemManager(tmp_path)
        managers = make_test_managers(fs=fs_manager)

        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            result = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]

        assert isinstance(result, SessionStartErrorResult)
        assert result.status == "error"
        assert "roadmap.md" in result.error

    @pytest.mark.asyncio
    async def test_session_start_impl_exception_handling(self, tmp_path: Path) -> None:
        """Test session start handles exceptions gracefully."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        _ = (memory_bank_dir / "activeContext.md").write_text("# Active Context")
        _ = (memory_bank_dir / "roadmap.md").write_text("# Roadmap")

        # Create a mock fs_manager that raises an exception
        fs_manager = MagicMock(spec=FileSystemManager)
        fs_manager.memory_bank_dir = memory_bank_dir
        fs_manager.read_file = AsyncMock(side_effect=Exception("Test error"))

        managers = make_test_managers(fs=fs_manager)

        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            result = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]

        assert isinstance(result, SessionStartErrorResult)
        assert result.status == "error"
        assert "Failed to generate session brief" in result.error


# ============================================================================
# Tool Wrapper Tests
# ============================================================================


class TestSessionStartTool:
    """Tests for session_start tool wrapper."""

    @pytest.mark.asyncio
    async def test_session_start_success(self, tmp_path: Path) -> None:
        """Test successful session_start tool call."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)

        _ = (memory_bank_dir / "activeContext.md").write_text(
            """# Active Context

## Current Focus

Working on Phase 54.
"""
        )
        _ = (memory_bank_dir / "roadmap.md").write_text(
            """# Roadmap

## Pending plans (from .cortex/plans)

- **Phase 54** - PENDING - Description
"""
        )
        _ = (memory_bank_dir / "projectBrief.md").write_text("# Cortex")

        for file_name in [
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            _ = (memory_bank_dir / file_name).write_text(f"# {file_name}")

        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()

        token_counter = TokenCounter()

        for file_name in [
            "activeContext.md",
            "roadmap.md",
            "projectBrief.md",
            "progress.md",
            "systemPatterns.md",
            "techContext.md",
            "productContext.md",
        ]:
            await metadata_index.update_file_metadata(
                file_name=file_name,
                path=memory_bank_dir / file_name,
                exists=True,
                size_bytes=100,
                token_count=50,
                content_hash="sha256:test",
                sections=[],
            )

        managers = make_test_managers(
            fs=fs_manager, index=metadata_index, tokens=token_counter
        )

        with (
            patch(
                "cortex.tools.session.start_tools.get_or_resolve_project_root"
            ) as mock_root,
            patch(
                "cortex.tools.session.start_tools.get_current_managers"
            ) as mock_managers,
            patch(
                "cortex.tools.session.health.get_mcp_health_status",
                new_callable=AsyncMock,
                return_value=(True, None),
            ),
        ):
            mock_root.return_value = tmp_path
            mock_managers.return_value = managers

            tool_fn = get_tool_fn(session_start)
            result_json = await tool_fn(task_description=None, ctx=None)
            assert isinstance(result_json, str)
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert "brief" in result
            assert result["token_count"] > 0

    @pytest.mark.asyncio
    async def test_session_start_no_managers(self) -> None:
        """Test session_start when managers are not initialized."""
        with (
            patch(
                "cortex.tools.session.start_tools.get_or_resolve_project_root"
            ) as mock_root,
            patch(
                "cortex.tools.session.start_tools.get_current_managers"
            ) as mock_managers,
        ):
            mock_root.return_value = Path("/tmp/test")
            mock_managers.return_value = None

            tool_fn = get_tool_fn(session_start)
            result_json = await tool_fn(task_description=None, ctx=None)
            assert isinstance(result_json, str)
            result = json.loads(result_json)

            assert result["status"] == "error"
            assert "Managers not initialized" in result["error"]
