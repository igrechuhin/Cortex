"""
Integration tests for commit workflow prompt–model alignment.

Verifies that the commit workflow model (parallel block 9–11, sequential
ranges) is reflected in the commit prompt (Concurrency rules, parallel block).
Orchestration is prompt-driven; no Python TaskGroup runner.
"""

from pathlib import Path

import pytest

from cortex.validation.commit_workflow_model import (
    get_commit_steps_metadata,
    get_parallel_block_step_ids,
    get_sequential_step_ranges,
)


def _repo_root() -> Path:
    """Return repository root (directory containing src/ and tests/)."""
    return Path(__file__).resolve().parents[2]


def _commit_prompt_path() -> Path:
    """Return path to commit prompt under .cortex/synapse/prompts/."""
    return _repo_root() / ".cortex" / "synapse" / "prompts" / "commit.md"


class TestCommitWorkflowModelInvariants:
    """Assert commit workflow model invariants used by the commit prompt."""

    def test_parallel_block_is_nine_ten_eleven(self) -> None:
        """Parallel block step ids are exactly 9, 10, 11."""
        assert get_parallel_block_step_ids() == (9, 10, 11)

    def test_sequential_ranges_are_zero_eight_and_twelve_fourteen(self) -> None:
        """Sequential ranges are (0, 8) and (12, 14)."""
        assert get_sequential_step_ranges() == [(0, 8), (12, 14)]

    def test_steps_9_10_11_have_parallel_metadata(self) -> None:
        """Steps 9, 10, 11 have can_run_in_parallel=True and same group_id."""
        steps = get_commit_steps_metadata()
        for step_id in (9, 10, 11):
            meta = next(s for s in steps if s.step_id == step_id)
            assert meta.can_run_in_parallel is True
            assert meta.group_id == "validation_parallel_block_9_11"


class TestCommitPromptAlignment:
    """Assert commit prompt documents the parallel block and concurrency rules."""

    @pytest.fixture
    def commit_prompt_content(self) -> str:
        """Read commit prompt content; skip if file missing (e.g. sparse checkout)."""
        path = _commit_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Commit prompt not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_prompt_contains_concurrency_rules(
        self, commit_prompt_content: str
    ) -> None:
        """Commit prompt has a Concurrency rules section."""
        assert "Concurrency rules" in commit_prompt_content

    def test_prompt_mentions_parallel_block_9_11(
        self, commit_prompt_content: str
    ) -> None:
        """Commit prompt mentions steps 9–11 as a parallel block."""
        assert "9" in commit_prompt_content and "11" in commit_prompt_content
        assert "parallel" in commit_prompt_content.lower()

    def test_prompt_mentions_sequential_steps(self, commit_prompt_content: str) -> None:
        """Commit prompt mentions sequential steps 0–8 and 12–14."""
        assert "0–8" in commit_prompt_content or "0-8" in commit_prompt_content
        assert "12–14" in commit_prompt_content or "12-14" in commit_prompt_content
