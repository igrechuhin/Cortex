"""
Integration tests for plan creation workflow compliance.

Verifies that the plan prompt enforces:
- Path resolution via .cortex/plans/ directory with Glob (zero-arg friendly).
- Roadmap updates via plan(operation="register"); manage_file(write) only as fallback; no StrReplace/direct Write.
"""

from pathlib import Path

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.initialization import get_project_root


def _repo_root() -> Path:
    """Return repository root (directory containing src/ and tests/)."""
    return get_project_root()


def _create_plan_prompt_path() -> Path:
    """Return path to plan prompt under .cortex/synapse/prompts/."""
    return (
        get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE)
        / "prompts"
        / "plan.md"
    )


class TestCreatePlanPathResolution:
    """Assert plan prompt uses correct path resolution for plans."""

    @pytest.fixture
    def create_plan_prompt_content(self) -> str:
        """Read plan prompt; skip if missing (e.g. synapse submodule)."""
        path = _create_plan_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Plan prompt not found at {path} (e.g. synapse submodule not present) (ref: cleanup-skipped-legacy-tests)"
            )
        return path.read_text()

    def test_prompt_uses_plans_directory(self, create_plan_prompt_content: str) -> None:
        """Plan prompt must reference .cortex/plans/ directory."""
        assert ".cortex/plans/" in create_plan_prompt_content

    def test_prompt_uses_glob_for_plan_listing(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan prompt must use Glob for listing plans."""
        assert "Glob" in create_plan_prompt_content
        assert ".cortex/plans/*.md" in create_plan_prompt_content

    def test_prompt_uses_manage_file_for_memory_bank(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan prompt must use manage_file() for memory bank reads."""
        assert "manage_file()" in create_plan_prompt_content
        assert ".cortex/memory-bank/" in create_plan_prompt_content

    def test_prompt_path_resolution_violation_language(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan prompt must state that roadmap corruption is a violation."""
        assert "VIOLATION" in create_plan_prompt_content
        assert (
            "path" in create_plan_prompt_content.lower()
            or "plans" in create_plan_prompt_content
        )


class TestCreatePlanPrefersCreatePlanTool:
    """Assert plan prompt prefers create_plan tool for new plan file creation."""

    @pytest.fixture
    def create_plan_prompt_content(self) -> str:
        """Read plan prompt; skip if missing."""
        path = _create_plan_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Plan prompt not found at {path} (e.g. synapse submodule not present) (ref: cleanup-skipped-legacy-tests)"
            )
        return path.read_text()

    def test_prompt_prefers_create_plan_for_new_plan_file(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan Step 7 must prefer plan(operation='create') for new plans."""
        assert "plan" in create_plan_prompt_content
        assert (
            "Prefer" in create_plan_prompt_content
            or "prefer" in create_plan_prompt_content
        )

    def test_prompt_mentions_fallback_write_for_plan_file(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan Step 7 must mention fallback (Write) when plan(operation='create') unavailable."""
        assert (
            "Fallback" in create_plan_prompt_content
            or "fallback" in create_plan_prompt_content
        )
        assert (
            "Write" in create_plan_prompt_content
            or 'plan(operation="create")' in create_plan_prompt_content
        )


class TestCreatePlanRoadmapUpdate:
    """Assert plan prompt requires plan(operation='register') for new plan; no StrReplace/direct Write."""

    @pytest.fixture
    def create_plan_prompt_content(self) -> str:
        """Read plan prompt; skip if missing."""
        path = _create_plan_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Plan prompt not found at {path} (e.g. synapse submodule not present) (ref: cleanup-skipped-legacy-tests)"
            )
        return path.read_text()

    def test_prompt_requires_register_plan_in_roadmap_for_new_plan(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan Step 8 must require plan(operation='register')."""
        assert 'plan(operation="register"' in create_plan_prompt_content
        assert "REQUIRED" in create_plan_prompt_content
        assert "roadmap" in create_plan_prompt_content.lower()

    def test_prompt_contains_prohibited_for_roadmap(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan Step 8 must explicitly PROHIBIT StrReplace/direct Write for roadmap."""
        assert "PROHIBITED" in create_plan_prompt_content
        assert "roadmap" in create_plan_prompt_content.lower()
        assert (
            "StrReplace" in create_plan_prompt_content
            or "direct Write" in create_plan_prompt_content
        )

    def test_prompt_mentions_fallback_manage_file_for_roadmap(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan Step 8 must mention manage_file only as fallback."""
        assert "roadmap.md" in create_plan_prompt_content
        assert "manage_file" in create_plan_prompt_content
        assert (
            "Fallback" in create_plan_prompt_content
            or "fallback" in create_plan_prompt_content
        )

    def test_prompt_contains_violation_for_str_replace_or_direct_write(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan must state StrReplace or direct Write for roadmap is a violation."""
        assert "VIOLATION" in create_plan_prompt_content
        assert (
            "StrReplace" in create_plan_prompt_content
            or "direct Write" in create_plan_prompt_content
        )

    def test_prompt_requires_full_content_when_using_fallback_write(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan must require full, unabridged roadmap content for fallback write."""
        assert (
            "full" in create_plan_prompt_content.lower()
            and "content" in create_plan_prompt_content.lower()
        )
        assert (
            "unabridged" in create_plan_prompt_content
            or "complete" in create_plan_prompt_content.lower()
        )


def _memory_bank_updater_agent_path() -> Path:
    """Return path to memory-bank-updater agent under .cortex/synapse/agents/."""
    return (
        get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE)
        / "agents"
        / "memory-bank-updater.md"
    )


class TestCreatePlanAntiTruncation:
    """Assert plan Step 8 contains anti-truncation and pre-write length check."""

    @pytest.fixture
    def create_plan_prompt_content(self) -> str:
        """Read plan prompt; skip if missing."""
        path = _create_plan_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Plan prompt not found at {path} (e.g. synapse submodule not present) (ref: cleanup-skipped-legacy-tests)"
            )
        return path.read_text()

    def test_prompt_prohibits_shortened_or_summarized_roadmap(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan Step 8 must prohibit shortened or summarized roadmap content."""
        assert (
            "never truncate" in create_plan_prompt_content.lower()
            or "never pass" in create_plan_prompt_content.lower()
        )
        assert (
            "shortened" in create_plan_prompt_content
            or "summarized" in create_plan_prompt_content
        )

    def test_prompt_requires_pre_write_content_length_check(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan Step 8 must require pre-write check that content >= roadmap as read."""
        assert (
            "pre-write" in create_plan_prompt_content.lower()
            or "content length" in create_plan_prompt_content.lower()
            or "string length" in create_plan_prompt_content.lower()
            or "len(content)" in create_plan_prompt_content
        )
        assert (
            "at least as long" in create_plan_prompt_content
            or "as long as" in create_plan_prompt_content
        )


class TestCreatePlanVerificationChecklist:
    """Assert plan prompt includes Verification Checklist."""

    @pytest.fixture
    def create_plan_prompt_content(self) -> str:
        """Read plan prompt; skip if missing."""
        path = _create_plan_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Plan prompt not found at {path} (e.g. synapse submodule not present) (ref: cleanup-skipped-legacy-tests)"
            )
        return path.read_text()

    def test_prompt_includes_verification_checklist_section(
        self, create_plan_prompt_content: str
    ) -> None:
        """Plan prompt structure must include Verification Checklist."""
        assert "Verification Checklist" in create_plan_prompt_content
        assert (
            "What to search for" in create_plan_prompt_content
            or "search for" in create_plan_prompt_content.lower()
        )
        assert (
            "Search scope" in create_plan_prompt_content
            or "scope" in create_plan_prompt_content.lower()
        )
        assert (
            "Files to re-read" in create_plan_prompt_content
            or "re-read" in create_plan_prompt_content
        )


class TestMemoryBankUpdaterAntiTruncation:
    """Assert memory-bank-updater agent contains no-truncation rule and recovery instruction."""

    @pytest.fixture
    def memory_bank_updater_content(self) -> str:
        """Read memory-bank-updater agent; skip if missing."""
        path = _memory_bank_updater_agent_path()
        if not path.exists():
            pytest.skip(
                f"Memory-bank-updater agent not found at {path} (e.g. synapse submodule not present) (ref: cleanup-skipped-legacy-tests)"
            )
        return path.read_text()

    def test_agent_prohibits_truncated_roadmap_content(
        self, memory_bank_updater_content: str
    ) -> None:
        """Memory-bank-updater must state never pass truncated or summarized content."""
        assert (
            "never pass truncated" in memory_bank_updater_content.lower()
            or "never truncate" in memory_bank_updater_content.lower()
        )
        assert "full" in memory_bank_updater_content.lower()

    def test_agent_includes_recovery_instruction(
        self, memory_bank_updater_content: str
    ) -> None:
        """Memory-bank-updater must include recovery instruction for accidental truncated write."""
        assert "restore" in memory_bank_updater_content.lower()
        assert (
            "version control" in memory_bank_updater_content
            or "git show" in memory_bank_updater_content
        )
