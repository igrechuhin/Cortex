"""
Integration tests for Phase 66: Plan creation workflow compliance.

Verifies that the create-plan prompt enforces:
- Path resolution via structure_info.paths.plans (absolute path; no hardcoding).
- Roadmap updates only via manage_file(roadmap.md, write, full content); no StrReplace/direct Write.
"""

from pathlib import Path

import pytest


def _repo_root() -> Path:
    """Return repository root (directory containing src/ and tests/)."""
    return Path(__file__).resolve().parents[2]


def _create_plan_prompt_path() -> Path:
    """Return path to create-plan prompt under .cortex/synapse/prompts/."""
    return _repo_root() / ".cortex" / "synapse" / "prompts" / "create-plan.md"


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


class TestCreatePlanRoadmapUpdate:
    """Assert create-plan prompt requires roadmap updates only via manage_file."""

    @pytest.fixture
    def create_plan_prompt_content(self) -> str:
        """Read create-plan prompt; skip if missing."""
        path = _create_plan_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Create-plan prompt not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_prompt_contains_prohibited_for_roadmap(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan Step 6 must explicitly PROHIBIT non-manage_file roadmap updates."""
        assert "PROHIBITED" in create_plan_prompt_content
        assert "roadmap" in create_plan_prompt_content.lower()
        assert "manage_file" in create_plan_prompt_content

    def test_prompt_contains_required_manage_file_for_roadmap(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan Step 6 must REQUIRE manage_file(roadmap.md, write, full content)."""
        assert "REQUIRED" in create_plan_prompt_content
        assert "roadmap.md" in create_plan_prompt_content
        assert (
            'operation="write"' in create_plan_prompt_content
            or 'operation="write"' in create_plan_prompt_content
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

    def test_prompt_requires_full_content_for_roadmap_write(
        self, create_plan_prompt_content: str
    ) -> None:
        """Create-plan must require full, unabridged roadmap content when writing."""
        assert (
            "full" in create_plan_prompt_content.lower()
            and "content" in create_plan_prompt_content.lower()
        )
        assert (
            "unabridged" in create_plan_prompt_content
            or "complete" in create_plan_prompt_content.lower()
        )
