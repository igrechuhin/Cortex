"""Tests for session_start health, suggestions, and token budget helpers."""

import json
from pathlib import Path

import pytest

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.tools.models import GitStatusSummary, SessionHealthSummary
from cortex.tools.session.brief_extraction_helpers import generate_session_suggestions
from cortex.tools.session.health import (
    calculate_health_summary,
    determine_token_budget_status,
    parse_mcp_health,
)
from cortex.tools.session.models import TokenBudgetStatus
from tests.helpers.managers import make_test_managers
from tests.helpers.path_helpers import ensure_test_cortex_structure
from tests.tools.session_start_fixtures import (
    managers_with_every_memory_bank_file,
    mcp_health_json,
)


class TestCalculateHealthSummary:
    """Tests for _calculate_health_summary helper."""

    @pytest.mark.asyncio
    async def test_calculate_health_summary_all_files(self, tmp_path: Path) -> None:
        """Test health summary with all files present."""
        managers = await managers_with_every_memory_bank_file(tmp_path)
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

    def test_generate_suggestions_memory_bank_sync_warning(self) -> None:
        """Memory bank sync violation appears in suggestions."""
        health = SessionHealthSummary(
            file_count=7,
            total_tokens=10000,
            token_budget_status=TokenBudgetStatus.HEALTHY,
            missing_files=[],
            has_errors=False,
        )
        progress = "- **Auth System** - PARTIAL. Work remaining."
        roadmap = "- **Unrelated Task** - PENDING - something else."
        suggestions = generate_session_suggestions(
            health,
            None,
            None,
            progress_content=progress,
            roadmap_content=roadmap,
        )
        assert any("Auth System" in s and "PARTIAL" in s for s in suggestions)

    def test_generate_suggestions_no_memory_bank_sync_warning_when_clean(self) -> None:
        """No sync warning when progress has no unresolved PARTIALs."""
        health = SessionHealthSummary(
            file_count=7,
            total_tokens=10000,
            token_budget_status=TokenBudgetStatus.HEALTHY,
            missing_files=[],
            has_errors=False,
        )
        progress = "- **Auth System** - COMPLETE. Done."
        roadmap = ""
        suggestions = generate_session_suggestions(
            health,
            None,
            None,
            progress_content=progress,
            roadmap_content=roadmap,
        )
        assert not any("PARTIAL" in s for s in suggestions)


class TestParseMCPHealth:
    """Tests for _parse_mcp_health helper."""

    def test_parse_mcp_health_success_healthy(self) -> None:
        """Parse successful healthy response."""
        ok, msg = parse_mcp_health(mcp_health_json(healthy=True))
        assert ok is True
        assert msg is None

    def test_parse_mcp_health_success_unhealthy(self) -> None:
        """Parse successful but unhealthy response."""
        ok, msg = parse_mcp_health(mcp_health_json(healthy=False))
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
