"""
Integration tests for Phase 66: Plan creation workflow compliance.

Verifies that the create-plan prompt enforces:
- Path resolution via structure_info.paths.plans (absolute path; no hardcoding).
- Roadmap updates for new plan entry via register_plan_in_roadmap (or add_roadmap_entry); manage_file(write) only as fallback; no StrReplace/direct Write.
"""

from pathlib import Path

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.initialization import get_project_root


def _repo_root() -> Path:
    """Return repository root (directory containing src/ and tests/)."""
    return get_project_root()


def _create_plan_prompt_path() -> Path:
    """Return path to create-plan prompt under .cortex/synapse/prompts/."""
    return (
        get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE)
        / "prompts"
        / "create-plan.md"
    )


class TestCreatePlanPathResolution:
    """Assert create-plan prompt requires canonical path resolution for plans."""

    @pytest.fixture
    def create_plan_prompt_content(self) -> str:
        """Read create-plan prompt; skip if missing (e.g. synapse submodule)."""
        path = _create_plan_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Create-plan prompt not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_prompt_requires_structure_info_paths_plans(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan prompt must use structure_info.paths.plans for plans directory."""
        assert "structure_info.paths.plans" in create_plan_prompt_content

    def test_prompt_requires_absolute_path_for_plans(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan prompt must require absolute path from tool, not inferred."""
        assert "absolute path" in create_plan_prompt_content
        assert "structure_info.paths.plans" in create_plan_prompt_content

    def test_prompt_prohibits_hardcoding_plans_path(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan prompt must prohibit hardcoding .cortex/plans or inferring from root."""
        assert (
            "Do not hardcode" in create_plan_prompt_content
            or "hardcode" in create_plan_prompt_content.lower()
        )
        assert (
            "structure_info.root" in create_plan_prompt_content
            or "canonical" in create_plan_prompt_content.lower()
        )

    def test_prompt_path_resolution_violation_language(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan prompt must state that hardcoding/inferring plans path is a violation."""
        assert "VIOLATION" in create_plan_prompt_content
        assert (
            "path" in create_plan_prompt_content.lower()
            or "plans" in create_plan_prompt_content
        )


class TestCreatePlanPrefersCreatePlanTool:
    """Assert create-plan prompt prefers create_plan tool for new plan file creation."""

    @pytest.fixture
    def create_plan_prompt_content(self) -> str:
        """Read create-plan prompt; skip if missing."""
        path = _create_plan_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Create-plan prompt not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_prompt_prefers_create_plan_for_new_plan_file(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan Step 5 must prefer create_plan when creating a new plan file."""
        assert "create_plan" in create_plan_prompt_content
        assert (
            "Prefer" in create_plan_prompt_content
            or "prefer" in create_plan_prompt_content
        )

    def test_prompt_mentions_fallback_write_for_plan_file(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan Step 5 must mention fallback (Write) when create_plan unavailable."""
        assert (
            "Fallback" in create_plan_prompt_content
            or "fallback" in create_plan_prompt_content
        )
        assert (
            "Write" in create_plan_prompt_content
            or "create_plan" in create_plan_prompt_content
        )


class TestCreatePlanRoadmapUpdate:
    """Assert create-plan prompt requires register_plan_in_roadmap for new plan; no StrReplace/direct Write."""

    @pytest.fixture
    def create_plan_prompt_content(self) -> str:
        """Read create-plan prompt; skip if missing."""
        path = _create_plan_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Create-plan prompt not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_prompt_requires_register_plan_in_roadmap_for_new_plan(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan Step 6 must require register_plan_in_roadmap for adding a new plan entry."""
        assert "register_plan_in_roadmap" in create_plan_prompt_content
        assert "REQUIRED" in create_plan_prompt_content
        assert "roadmap" in create_plan_prompt_content.lower()

    def test_prompt_contains_prohibited_for_roadmap(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan Step 6 must explicitly PROHIBIT StrReplace/direct Write for roadmap."""
        assert "PROHIBITED" in create_plan_prompt_content
        assert "roadmap" in create_plan_prompt_content.lower()
        assert (
            "StrReplace" in create_plan_prompt_content
            or "direct Write" in create_plan_prompt_content
        )

    def test_prompt_mentions_fallback_manage_file_for_roadmap(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan Step 6 must mention manage_file only as fallback for roadmap writes."""
        assert "roadmap.md" in create_plan_prompt_content
        assert "manage_file" in create_plan_prompt_content
        assert (
            "Fallback" in create_plan_prompt_content
            or "fallback" in create_plan_prompt_content
        )

    def test_prompt_contains_violation_for_str_replace_or_direct_write(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan must state that StrReplace or direct Write for roadmap is a critical violation."""
        assert "VIOLATION" in create_plan_prompt_content
        assert (
            "StrReplace" in create_plan_prompt_content
            or "direct Write" in create_plan_prompt_content
        )

    def test_prompt_requires_full_content_when_using_fallback_write(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan must require full, unabridged roadmap content when using fallback manage_file write."""
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
    """Assert create-plan Step 6 contains anti-truncation and pre-write length check (roadmap full-content enforcement)."""

    @pytest.fixture
    def create_plan_prompt_content(self) -> str:
        """Read create-plan prompt; skip if missing."""
        path = _create_plan_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Create-plan prompt not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_prompt_prohibits_shortened_or_summarized_roadmap(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan Step 6 must prohibit passing shortened or summarized roadmap content."""
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
        """Create-plan Step 6 must require pre-write check that content length >= roadmap as read."""
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


class TestMemoryBankUpdaterAntiTruncation:
    """Assert memory-bank-updater agent contains no-truncation rule and recovery instruction."""

    @pytest.fixture
    def memory_bank_updater_content(self) -> str:
        """Read memory-bank-updater agent; skip if missing."""
        path = _memory_bank_updater_agent_path()
        if not path.exists():
            pytest.skip(
                f"Memory-bank-updater agent not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_agent_prohibits_truncated_roadmap_content(
        self, memory_bank_updater_content: str
    ) -> None:
        """Memory-bank-updater must state never pass truncated or summarized roadmap content."""
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
