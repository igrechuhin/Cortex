"""
Integration tests for commit workflow prompt–model alignment.

Verifies that the commit pipeline (orchestrator + phase agents) contains
required quality gates, tooling references, and workflow guidance.

The commit pipeline is split across:
- .cortex/synapse/prompts/commit.md (orchestrator)
- .cortex/synapse/cursor-agents/commit-preflight.md
- .cortex/synapse/cursor-agents/commit-checks.md (Phase A, job-based)
- .cortex/synapse/cursor-agents/commit-docs.md (Phase B)
- .cortex/synapse/cursor-agents/commit-validate.md (Phase C)
- .cortex/synapse/cursor-agents/commit-final-gate.md (Step 12, job-based)

Tests search across all pipeline files for semantic requirements,
not exact substring matches in a single file.
"""

from pathlib import Path

import pytest

from cortex.core.path_resolver import (
    CortexResourceType,
    ProjectResourceType,
    get_cortex_path,
)
from cortex.managers.initialization import get_project_root
from cortex.validation.commit_workflow_model import (
    get_commit_steps_metadata,
    get_parallel_block_step_ids,
    get_sequential_step_ranges,
)


def _repo_root() -> Path:
    """Return repository root (directory containing src/ and tests/)."""
    return get_project_root()


def _synapse_path() -> Path:
    """Return path to Synapse directory."""
    return get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE)


def _commit_prompt_path() -> Path:
    """Return path to commit prompt under .cortex/synapse/prompts/."""
    return _synapse_path() / "prompts" / "commit.md"


def _pipeline_agent_paths() -> list[Path]:
    """Return paths to all commit pipeline agent files (cursor-agents)."""
    cursor_agents_dir = _synapse_path() / "cursor-agents"
    return [
        cursor_agents_dir / "commit-preflight.md",
        cursor_agents_dir / "commit-checks.md",
        cursor_agents_dir / "commit-docs.md",
        cursor_agents_dir / "commit-validate.md",
        cursor_agents_dir / "commit-final-gate.md",
    ]


def _read_commit_pipeline_content() -> str:
    """Read and concatenate all commit pipeline files.

    Returns combined content of orchestrator + all phase agents
    for semantic searches across the entire pipeline.
    """
    parts: list[str] = []
    prompt = _commit_prompt_path()
    if prompt.exists():
        parts.append(prompt.read_text())
    for agent_path in _pipeline_agent_paths():
        if agent_path.exists():
            parts.append(agent_path.read_text())
    return "\n".join(parts)


def _implement_prompt_path() -> Path:
    """Return path to implement prompt."""
    return _synapse_path() / "prompts" / "implement-next-roadmap-step.md"


def _python_coding_standards_path() -> Path:
    """Return path to Python coding standards."""
    return _synapse_path() / "rules" / "python" / "python-coding-standards.mdc"


class TestCommitWorkflowModelInvariants:
    """Assert commit workflow model invariants."""

    def test_parallel_block_is_nine_ten_eleven(self) -> None:
        """Parallel block step ids are exactly 9, 10, 11."""
        assert get_parallel_block_step_ids() == (9, 10, 11)

    def test_sequential_ranges_are_zero_eight_and_twelve_fourteen(
        self,
    ) -> None:
        """Sequential ranges are (0, 8) and (12, 14)."""
        assert get_sequential_step_ranges() == [(0, 8), (12, 14)]

    def test_steps_9_10_11_have_parallel_metadata(self) -> None:
        """Steps 9-11 have can_run_in_parallel=True and same group_id."""
        steps = get_commit_steps_metadata()
        for step_id in (9, 10, 11):
            meta = next(s for s in steps if s.step_id == step_id)
            assert meta.can_run_in_parallel is True
            assert meta.group_id == "validation_parallel_block_9_11"


class TestCommitPipelineAlignment:
    """Assert commit pipeline contains required workflow guidance.

    Tests search the full pipeline (orchestrator + phase agents)
    for semantic concepts rather than exact substrings.
    """

    @pytest.fixture
    def pipeline_content(self) -> str:
        """Read all commit pipeline content."""
        content = _read_commit_pipeline_content()
        if not content.strip():
            pytest.skip("Commit pipeline files not found")
        return content

    @pytest.fixture
    def commit_prompt_content(self) -> str:
        """Read commit prompt content only."""
        path = _commit_prompt_path()
        if not path.exists():
            pytest.skip(f"Commit prompt not found at {path}")
        return path.read_text()

    # -- Structure --

    def test_pipeline_has_phase_structure(self, pipeline_content: str) -> None:
        """Pipeline defines Phase A, B, C structure."""
        lower = pipeline_content.lower()
        assert "phase a" in lower
        assert "phase b" in lower
        assert "phase c" in lower

    def test_pipeline_defines_execution_order(self, pipeline_content: str) -> None:
        """Pipeline defines sequential execution."""
        lower = pipeline_content.lower()
        assert any(
            kw in lower for kw in ("sequential", "strictly", "in order", "each phase")
        )

    def test_orchestrator_delegates_all_phases_to_subagents(
        self, commit_prompt_content: str
    ) -> None:
        """Orchestrator delegates every major phase to a named subagent."""
        for subagent in (
            "commit-preflight",
            "commit-checks",
            "commit-docs",
            "commit-validate",
            "commit-final-gate",
        ):
            assert (
                subagent in commit_prompt_content
            ), f"commit.md must reference subagent: {subagent}"

    def test_orchestrator_has_no_direct_execute_pre_commit_checks_calls(
        self, commit_prompt_content: str
    ) -> None:
        """Orchestrator must not call execute_pre_commit_checks directly (delegated to agents)."""
        assert (
            "execute_pre_commit_checks" not in commit_prompt_content
        ), "commit.md must delegate to cursor-agents, not call execute_pre_commit_checks directly"

    def test_phase_a_agent_uses_job_api(self, pipeline_content: str) -> None:
        """Phase A agent uses start_pre_commit_job + get_pre_commit_job_status."""
        assert "start_pre_commit_job" in pipeline_content
        assert "get_pre_commit_job_status" in pipeline_content

    def test_phase_a_agent_has_no_blocking_execute_call(self) -> None:
        """commit-checks.md must not use blocking execute_pre_commit_checks."""
        checks_agent = _synapse_path() / "cursor-agents" / "commit-checks.md"
        if not checks_agent.exists():
            pytest.skip("commit-checks.md not found")
        content = checks_agent.read_text()
        assert (
            "execute_pre_commit_checks" not in content
        ), "commit-checks.md must use job API (start_pre_commit_job), not blocking execute_pre_commit_checks"

    def test_final_gate_agent_uses_job_api(self) -> None:
        """commit-final-gate.md uses start_pre_commit_job + poll pattern."""
        gate_agent = _synapse_path() / "cursor-agents" / "commit-final-gate.md"
        if not gate_agent.exists():
            pytest.skip("commit-final-gate.md not found")
        content = gate_agent.read_text()
        assert "start_pre_commit_job" in content
        assert "get_pre_commit_job_status" in content
        assert (
            "execute_pre_commit_checks" not in content
        ), "commit-final-gate.md must use job API, not blocking execute_pre_commit_checks"

    # -- Quality checks --

    def test_pipeline_covers_all_quality_checks(self, pipeline_content: str) -> None:
        """Pipeline references all required check types."""
        lower = pipeline_content.lower()
        for check in ("format", "type", "quality", "test", "markdown"):
            assert check in lower, f"Missing check: {check}"

    def test_pipeline_defines_final_gate(self, pipeline_content: str) -> None:
        """Pipeline has a final validation gate before commit."""
        lower = pipeline_content.lower()
        assert "final" in lower and ("gate" in lower or "validation" in lower)

    # -- Compound engineering --

    def test_pipeline_references_compound_engineering(
        self, pipeline_content: str
    ) -> None:
        """Pipeline references compound loop and manage_file."""
        assert "compound" in pipeline_content.lower()
        assert "manage_file" in pipeline_content

    # -- Tooling --

    def test_pipeline_uses_tools_not_scripts(self, commit_prompt_content: str) -> None:
        """Commit prompt must not invoke scripts directly."""
        forbidden = (
            f"{ProjectResourceType.VENV.value}/bin/python" " .cortex/synapse/scripts"
        )
        assert forbidden not in commit_prompt_content

    def test_pipeline_requires_script_tooling(self, pipeline_content: str) -> None:
        """Pipeline requires manage_session_scripts for script use."""
        assert "manage_session_scripts" in pipeline_content
        assert any(kw in pipeline_content for kw in ("capture", "analyze", "suggest"))

    def test_pipeline_requires_rules_loading(self, pipeline_content: str) -> None:
        """Pipeline requires rules loading with disabled fallback."""
        assert "rules(" in pipeline_content
        assert "get_structure_info" in pipeline_content
        assert "disabled" in pipeline_content.lower()

    # -- Failure handling --

    def test_pipeline_contains_markdown_lint_fallback(
        self, pipeline_content: str
    ) -> None:
        """Pipeline documents markdown lint fallback command."""
        assert "rumdl" in pipeline_content

    def test_pipeline_contains_mcp_disconnect_recovery(
        self, pipeline_content: str
    ) -> None:
        """Pipeline documents MCP disconnect recovery."""
        lower = pipeline_content.lower()
        assert "mcp" in lower
        assert any(
            kw in lower
            for kw in ("disconnect", "connection closed", "connection error")
        )
        assert any(
            kw in lower for kw in ("retry", "re-run", "fallback", "circuit-breaker")
        )

    def test_pipeline_has_fix_loop_with_convergence(
        self, pipeline_content: str
    ) -> None:
        """Pipeline defines fix loops with convergence check."""
        lower = pipeline_content.lower()
        assert "3 iterations" in lower or "3 iteration" in lower
        assert "converg" in lower

    # -- Fix-loop re-run guidance --

    def test_pipeline_has_type_quality_rerun_after_fixes(
        self, pipeline_content: str
    ) -> None:
        """Pipeline requires re-running quality after type/lint fixes."""
        lower = pipeline_content.lower()
        assert "re-run" in lower or "re_run" in lower
        assert "format" in lower and "quality" in lower
        assert "type" in lower

    # -- Plan status / side-effect guidance --

    def test_pipeline_contains_plan_status_guidance(
        self, pipeline_content: str
    ) -> None:
        """Pipeline reminds about plan Status format (MD036)."""
        assert "MD036" in pipeline_content

    # -- Refactoring guidance --

    def test_pipeline_contains_intermediate_validation(
        self, pipeline_content: str
    ) -> None:
        """Pipeline advises running checks after each refactor."""
        lower = pipeline_content.lower()
        assert "refactor" in lower
        assert "type" in lower and "quality" in lower

    def test_pipeline_contains_duplicate_detection(self, pipeline_content: str) -> None:
        """Pipeline advises searching for existing functions."""
        lower = pipeline_content.lower()
        assert "existing functions" in lower or "duplicate" in lower
        assert "search" in lower or "grep" in lower

    # -- Git safety --

    def test_pipeline_defines_git_safety(self, pipeline_content: str) -> None:
        """Pipeline defines git safety rules."""
        lower = pipeline_content.lower()
        assert "git add" in lower
        assert ".env" in pipeline_content or "sensitive" in lower


class TestImplementPromptRefactoringGuidance:
    """Assert implement prompt contains refactoring guidance."""

    @pytest.fixture
    def implement_prompt_content(self) -> str:
        """Read implement prompt content; skip if missing."""
        path = _implement_prompt_path()
        if not path.exists():
            pytest.skip(f"Implement prompt not found at {path}")
        return path.read_text()

    def test_implement_prompt_contains_incremental_validation(
        self, implement_prompt_content: str
    ) -> None:
        """Implement prompt advises incremental validation."""
        assert "incremental" in implement_prompt_content.lower()
        assert "refactor" in implement_prompt_content.lower()

    def test_implement_prompt_contains_duplicate_detection(
        self, implement_prompt_content: str
    ) -> None:
        """Implement prompt advises duplicate detection."""
        assert "duplicate" in implement_prompt_content.lower()
        assert "helper" in implement_prompt_content.lower()

    def test_implement_prompt_contains_duplicate_definition_search(
        self, implement_prompt_content: str
    ) -> None:
        """Implement prompt requires searching for definitions."""
        lower = implement_prompt_content.lower()
        assert "duplicate-definition" in lower or "duplicate" in lower
        assert "definitions" in lower


class TestPythonCodingStandardsTypeNarrowing:
    """Assert Python coding standards document type narrowing."""

    @pytest.fixture
    def python_standards_content(self) -> str:
        """Read Python coding standards; skip if missing."""
        path = _python_coding_standards_path()
        if not path.exists():
            pytest.skip(f"Python standards not found at {path}")
        return path.read_text()

    def test_python_standards_contain_type_narrowing(
        self, python_standards_content: str
    ) -> None:
        """Standards include Type Narrowing with assert section."""
        assert "Type Narrowing with assert" in python_standards_content
        assert "assert value is not None" in python_standards_content

    def test_python_standards_type_hints_reference_narrowing(
        self, python_standards_content: str
    ) -> None:
        """Type Hints section cross-references Type Narrowing."""
        assert "Type Narrowing" in python_standards_content
