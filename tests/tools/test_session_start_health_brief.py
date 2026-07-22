"""Tests for session_start health, suggestions, and token budget helpers."""

import json
import os
import time
from pathlib import Path

import pytest

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import CortexResourceType
from cortex.core.session_logger import record_spend_tokens
from cortex.tools.models import GitStatusSummary, SessionHealthSummary
from cortex.tools.session.brief_extraction_helpers import generate_session_suggestions
from cortex.tools.session.health import (
    calculate_health_summary,
    determine_spend_status,
    determine_token_budget_status,
    parse_mcp_health,
)
from cortex.tools.session.models import (
    SessionSpendStatus,
    SessionSpendSummary,
    TokenBudgetStatus,
    WikiStatusSummary,
)
from tests.helpers.managers import make_test_managers
from tests.helpers.path_helpers import (
    ensure_test_cortex_structure,
    get_test_cortex_path,
)
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

    @pytest.mark.asyncio
    async def test_calculate_health_summary_spend_defaults_healthy(
        self, tmp_path: Path
    ) -> None:
        """spend defaults to healthy/0 when no session log has been written."""
        managers = await managers_with_every_memory_bank_file(tmp_path)

        health = await calculate_health_summary(
            managers,
            tmp_path,  # type: ignore[arg-type]
        )
        assert health.spend.cumulative_tokens == 0
        assert health.spend.spend_status == SessionSpendStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_calculate_health_summary_reflects_recorded_spend(
        self, tmp_path: Path
    ) -> None:
        """spend reflects tokens already recorded via record_spend_tokens()."""
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "health_spend_test"
        try:
            _ = record_spend_tokens(tmp_path, 250_000)
            managers = await managers_with_every_memory_bank_file(tmp_path)

            health = await calculate_health_summary(
                managers,
                tmp_path,  # type: ignore[arg-type]
            )
            assert health.spend.cumulative_tokens == 250_000
            assert health.spend.spend_status == SessionSpendStatus.OVER_BUDGET
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)


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

    def test_generate_suggestions_wiki_init_hint(self, tmp_path: Path) -> None:
        """When Cortex exists, wiki is absent, and README exists, suggest init-wiki."""
        _ = (tmp_path / ".cortex").mkdir()
        _ = (tmp_path / "README.md").write_text("# Project\n")
        health = SessionHealthSummary(
            file_count=7,
            total_tokens=10000,
            token_budget_status=TokenBudgetStatus.HEALTHY,
            missing_files=[],
            has_errors=False,
        )
        wiki = WikiStatusSummary(
            wiki_enabled=False, wiki_page_count=0, wiki_path=".cortex/wiki"
        )
        suggestions = generate_session_suggestions(
            health,
            None,
            None,
            wiki_status=wiki,
            project_root=tmp_path,
        )
        assert any("init-wiki" in s for s in suggestions)

    def test_generate_suggestions_spend_over_budget(self) -> None:
        """Suggestion appended when runtime spend is over budget."""
        health = SessionHealthSummary(
            file_count=7,
            total_tokens=10000,
            token_budget_status=TokenBudgetStatus.HEALTHY,
            missing_files=[],
            has_errors=False,
            spend=SessionSpendSummary(
                cumulative_tokens=250_000,
                budget=200_000,
                spend_status=SessionSpendStatus.OVER_BUDGET,
            ),
        )
        suggestions = generate_session_suggestions(health, None, None)
        assert any("runtime spend over budget" in s.lower() for s in suggestions)

    def test_generate_suggestions_spend_warning(self) -> None:
        """Suggestion appended when runtime spend crosses the warning band."""
        health = SessionHealthSummary(
            file_count=7,
            total_tokens=10000,
            token_budget_status=TokenBudgetStatus.HEALTHY,
            missing_files=[],
            has_errors=False,
            spend=SessionSpendSummary(
                cumulative_tokens=180_000,
                budget=200_000,
                spend_status=SessionSpendStatus.WARNING,
            ),
        )
        suggestions = generate_session_suggestions(health, None, None)
        assert any("runtime spend at" in s.lower() for s in suggestions)

    def test_generate_suggestions_spend_healthy_no_suggestion(self) -> None:
        """No spend suggestion is appended when spend is healthy."""
        health = SessionHealthSummary(
            file_count=7,
            total_tokens=10000,
            token_budget_status=TokenBudgetStatus.HEALTHY,
            missing_files=[],
            has_errors=False,
        )
        suggestions = generate_session_suggestions(health, None, None)
        assert not any("runtime spend" in s.lower() for s in suggestions)

    def test_generate_suggestions_stale_plan_drafts(self, tmp_path: Path) -> None:
        """Stale draft-*.md files yield a session suggestion."""
        _ = ensure_test_cortex_structure(tmp_path)
        plans = get_test_cortex_path(tmp_path, CortexResourceType.PLANS)
        plans.mkdir(parents=True, exist_ok=True)
        draft = plans / "draft-stale-session.md"
        _ = draft.write_text("x", encoding="utf-8")
        old = time.time() - (50 * 60 * 60)
        os.utime(draft, (old, old))
        health = SessionHealthSummary(
            file_count=7,
            total_tokens=10000,
            token_budget_status=TokenBudgetStatus.HEALTHY,
            missing_files=[],
            has_errors=False,
        )
        suggestions = generate_session_suggestions(
            health, None, None, project_root=tmp_path
        )
        assert any("stale plan draft" in s.lower() for s in suggestions)


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


class TestDetermineSpendStatus:
    """Tests for determine_spend_status boundary values."""

    def test_healthy_when_under_85_percent(self) -> None:
        """Returns HEALTHY when spend is below 85% of budget."""
        assert determine_spend_status(0, 100_000) == SessionSpendStatus.HEALTHY
        assert determine_spend_status(84_999, 100_000) == SessionSpendStatus.HEALTHY

    def test_warning_at_lower_boundary(self) -> None:
        """Returns WARNING exactly at the 85% boundary."""
        assert determine_spend_status(85_000, 100_000) == SessionSpendStatus.WARNING

    def test_warning_just_under_100_percent(self) -> None:
        """Returns WARNING just under the 100% boundary."""
        assert determine_spend_status(99_999, 100_000) == SessionSpendStatus.WARNING

    def test_over_budget_at_exact_boundary(self) -> None:
        """Returns OVER_BUDGET exactly at 100% of budget."""
        assert (
            determine_spend_status(100_000, 100_000) == SessionSpendStatus.OVER_BUDGET
        )

    def test_over_budget_above_boundary(self) -> None:
        """Returns OVER_BUDGET above 100% of budget."""
        assert (
            determine_spend_status(150_000, 100_000) == SessionSpendStatus.OVER_BUDGET
        )

    def test_uses_default_budget_when_not_specified(self) -> None:
        """Uses DEFAULT_SESSION_SPEND_BUDGET when budget arg omitted."""
        assert determine_spend_status(0) == SessionSpendStatus.HEALTHY
