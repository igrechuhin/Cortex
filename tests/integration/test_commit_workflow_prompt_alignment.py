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

    def test_commit_prompt_uses_tools_only_no_direct_script_invocations(
        self, commit_prompt_content: str
    ) -> None:
        """Commit prompt must not instruct running pre-commit/Step 12 scripts directly.

        Phase 65: All pre-commit and Step 12 operations must be via Cortex MCP tools
        (execute_pre_commit_checks, fix_markdown_lint); no .venv/bin/python script paths.
        """
        forbidden = ".venv/bin/python .cortex/synapse/scripts"
        assert forbidden not in commit_prompt_content, (
            "Commit prompt must not contain direct script invocations; "
            "use execute_pre_commit_checks() and fix_markdown_lint() only."
        )

    def test_commit_prompt_requires_script_tooling_when_script_run(
        self, commit_prompt_content: str
    ) -> None:
        """Commit prompt must require script tooling when a script was created or executed.

        Session optimization (2026-02-01): If during the run a script was created or
        executed, agent MUST use capture_session_script and/or analyze_session_scripts
        or suggest_tool_improvements.
        """
        assert "capture_session_script" in commit_prompt_content
        assert (
            "analyze_session_scripts" in commit_prompt_content
            or "suggest_tool_improvements" in commit_prompt_content
        )
        assert (
            "Script use" in commit_prompt_content
            or "script tooling" in commit_prompt_content.lower()
        )

    def test_commit_prompt_lists_script_run_without_analysis_common_error(
        self, commit_prompt_content: str
    ) -> None:
        """Commit prompt must list 'Script run without analysis' as a common error.

        Session optimization (2026-02-01): Process violation when script was run
        without using script tooling; must be in COMMON ERRORS TO CATCH.
        """
        assert "Script run without analysis" in commit_prompt_content
        assert "COMMON ERRORS TO CATCH" in commit_prompt_content
