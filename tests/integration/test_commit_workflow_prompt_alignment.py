"""
Integration tests for commit workflow prompt–model alignment.

Verifies that the commit workflow model (parallel block 9–11, sequential
ranges) is reflected in the commit prompt (Concurrency rules, parallel block).
Orchestration is prompt-driven; no Python TaskGroup runner.
"""

from pathlib import Path

import pytest

from cortex.core.path_resolver import ProjectResourceType
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

    def test_prompt_mentions_compound_and_checklist(
        self, commit_prompt_content: str
    ) -> None:
        """Commit prompt references compound loop and compound checklist."""
        assert "compound" in commit_prompt_content.lower()
        assert "manage_file" in commit_prompt_content

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
        forbidden = (
            f"{ProjectResourceType.VENV.value}/bin/python .cortex/synapse/scripts"
        )
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

    def test_commit_prompt_requires_rules_file_read_when_rules_disabled(
        self, commit_prompt_content: str
    ) -> None:
        """Commit prompt must require explicit rule file read when rules() returns disabled.

        Session optimization (2026-02-02): When rules tool is disabled, agent must
        read rule files via Read tool and record 'Rules loaded: Yes (via file read)'.
        """
        assert (
            "rules() returns status" in commit_prompt_content
            and "disabled" in commit_prompt_content
        ) or "Rules loaded: Yes (via file read)" in commit_prompt_content
        assert "get_structure_info" in commit_prompt_content
        assert (
            "Read tool" in commit_prompt_content
            or "rule files" in commit_prompt_content
        )

    def test_commit_prompt_contains_markdown_lint_fallback_example(
        self, commit_prompt_content: str
    ) -> None:
        """Commit prompt must contain example markdown lint fallback command for Step 12.6.

        Session optimization (2026-02-02): When fix_markdown_lint is unavailable,
        fallback command (e.g. markdownlint-cli2) must be documented so agents
        do not need to infer it.
        """
        assert "markdownlint-cli2" in commit_prompt_content
        assert "MCP connection closed; fallback used" in commit_prompt_content

    def test_commit_prompt_requires_rerun_step_12_3_after_fix_in_step_12_2_or_12_3(
        self, commit_prompt_content: str
    ) -> None:
        """Commit prompt must require re-run of Step 12.3 (quality) after code fixes in 12.2 or 12.3.

        Fix commit workflow (2026-02-02): After any code change in Step 12.2 (type)
        or 12.3 (lint), agent MUST re-run Step 12.3 and verify results.quality.success
        with zero errors to prevent CI Ruff failure (e.g. E402) when type/lint fixes
        introduce new lint.
        """
        assert (
            "re-run Step 12.3" in commit_prompt_content
            or "re-run 12.3" in commit_prompt_content
        )
        assert "12.2" in commit_prompt_content and "12.3" in commit_prompt_content
        assert "results.quality.success" in commit_prompt_content
        assert (
            "Do NOT proceed to Step 12.4" in commit_prompt_content
            or "until Step 12.3 has been run again" in commit_prompt_content
        )
        assert (
            "E402" in commit_prompt_content
            or "type or lint fixes" in commit_prompt_content.lower()
            or "fixes can introduce new lint" in commit_prompt_content
        )

    def test_commit_prompt_contains_plan_status_and_side_effect_import_reminders(
        self, commit_prompt_content: str
    ) -> None:
        """Commit prompt must remind agents about plan Status format and side-effect imports.

        Session optimization (2026-02-02): Plan Status MD036 and side-effect imports.
        New/modified plan files: Status section uses Status: VALUE or heading, not **VALUE**.
        New/modified tests with side-effect imports: reference import (e.g. _ = module).
        """
        assert (
            "Plan Status" in commit_prompt_content
            or "plan Status" in commit_prompt_content
        )
        assert (
            "MD036" in commit_prompt_content or "Status: VALUE" in commit_prompt_content
        )
        assert (
            "side-effect" in commit_prompt_content
            or "side_effect" in commit_prompt_content
        )
        assert (
            "_ = module" in commit_prompt_content
            or "reportUnusedImport" in commit_prompt_content
        )
