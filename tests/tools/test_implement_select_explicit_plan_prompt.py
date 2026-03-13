"""
Tests for implement-select prompt explicit-plan-first behavior.

These tests assert that the implement pipeline documentation encodes the
selection precedence contract for explicit plans versus roadmap ordering.
"""

from pathlib import Path

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def _synapse_path() -> Path:
    """Return path to Synapse directory."""
    # Mirrors helpers in tests/integration/test_commit_workflow_prompt_alignment.py
    repo_root = Path(__file__).resolve().parents[2]
    return get_cortex_path(repo_root, CortexResourceType.SYNAPSE)


def _implement_select_path() -> Path:
    """Return path to implement-select cursor-agent prompt."""
    return _synapse_path() / "cursor-agents" / "implement-select.md"


def _implement_prompt_path() -> Path:
    """Return path to implement orchestrator prompt."""
    return _synapse_path() / "prompts" / "implement-next-roadmap-step.md"


@pytest.fixture
def implement_select_content() -> str:
    """Read implement-select cursor-agent content."""
    path = _implement_select_path()
    if not path.exists():
        pytest.skip(f"implement-select prompt not found at {path}")
    return path.read_text()


@pytest.fixture
def implement_prompt_content() -> str:
    """Read implement orchestrator prompt content."""
    path = _implement_prompt_path()
    if not path.exists():
        pytest.skip(f"implement prompt not found at {path}")
    return path.read_text()


class TestExplicitPlanSelectionContract:
    """Assert implement-selection documents explicit-plan-first behavior."""

    def test_no_explicit_plan_uses_roadmap_priority(
        self, implement_select_content: str
    ) -> None:
        """When no explicit plan is provided, roadmap priority ordering is used."""
        lower = implement_select_content.lower()
        # Prompt must still describe priority order: Blockers → Active Work → Pending plans.
        assert "priority order" in lower
        assert "blockers" in lower
        assert "active work" in lower
        assert "pending plans" in lower

    def test_valid_explicit_plan_is_preferred(
        self, implement_select_content: str, implement_prompt_content: str
    ) -> None:
        """An eligible explicit plan is preferred over roadmap ordering."""
        combined = (implement_select_content + "\n" + implement_prompt_content).lower()
        # Combined content should clearly state that explicit plans are preferred when eligible.
        assert "explicit plan" in combined
        assert "explicit_plan_path" in combined or "explicit plan reference" in combined
        assert "prefer that plan" in combined or "preferred over roadmap" in combined

    def test_invalid_or_ineligible_explicit_plan_falls_back_with_note(
        self, implement_select_content: str, implement_prompt_content: str
    ) -> None:
        """Invalid or ineligible explicit plans fall back to roadmap with a clear note."""
        combined = (implement_select_content + "\n" + implement_prompt_content).lower()
        # Must document fallback behavior and that a note/error is recorded.
        assert (
            "ineligible" in combined or "archived" in combined or "complete" in combined
        )
        assert "fall back" in combined or "fallback" in combined
        assert "note" in combined or "error" in combined
