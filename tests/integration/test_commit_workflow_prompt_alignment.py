"""
Integration tests for commit workflow prompt–model alignment.

Verifies that the commit pipeline (orchestrator) contains
required quality gates, tooling references, and workflow guidance.

The commit pipeline runs entirely inline in the orchestrator:
- .cortex/synapse/prompts/commit.md (all phases inline, no subagents)

Tests search the orchestrator prompt for semantic requirements.
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


def _read_commit_pipeline_content() -> str:
    """Read commit pipeline content (orchestrator prompt only — no subagents).

    All commit phases run inline in the orchestrator since simplification.
    """
    prompt = _commit_prompt_path()
    if prompt.exists():
        return prompt.read_text()
    return ""


def _implement_prompt_path() -> Path:
    """Return path to implement prompt."""
    return _synapse_path() / "prompts" / "implement-next-roadmap-step.md"


def _read_implement_pipeline_content() -> str:
    """Read implement prompt + implement-code agent.

    Selection, finalize, and verify phases run inline in the orchestrator.
    Only implement-code delegates to a subagent.
    """
    parts: list[str] = []
    prompt = _implement_prompt_path()
    if prompt.exists():
        parts.append(prompt.read_text())
    code_agent = _synapse_path() / "cursor-agents" / "implement-code.md"
    if code_agent.exists():
        parts.append(code_agent.read_text())
    return "\n".join(parts)


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

    def test_orchestrator_runs_all_phases_inline(
        self, commit_prompt_content: str
    ) -> None:
        """Orchestrator runs all phases inline (no subagent delegation)."""
        lower = commit_prompt_content.lower()
        assert "run inline" in lower or "no subagent" in lower

    def test_orchestrator_uses_zero_arg_quality_tools(
        self, commit_prompt_content: str
    ) -> None:
        """Orchestrator uses zero-arg tools, not execute_pre_commit_checks."""
        assert "run_quality_gate" in commit_prompt_content
        assert "execute_pre_commit_checks" not in commit_prompt_content

    def test_phase_a_uses_zero_arg_quality_gate(self, pipeline_content: str) -> None:
        """Phase A uses run_quality_gate() zero-arg tool."""
        assert "run_quality_gate" in pipeline_content

    def test_pipeline_uses_fix_quality_issues(self, pipeline_content: str) -> None:
        """Pipeline uses fix_quality_issues() zero-arg tool."""
        assert "fix_quality_issues" in pipeline_content

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

    def test_pipeline_references_analyze(self, pipeline_content: str) -> None:
        """Pipeline references analyze for end-of-session analysis."""
        assert "analyze" in pipeline_content.lower()

    def test_pipeline_requires_rules_loading(self, pipeline_content: str) -> None:
        """Pipeline requires rules loading."""
        assert "rules(" in pipeline_content or "rules" in pipeline_content.lower()

    # -- Failure handling --

    def test_pipeline_contains_markdown_lint_fallback(
        self, pipeline_content: str
    ) -> None:
        """Pipeline documents a markdown lint fallback mechanism."""
        lower = pipeline_content.lower()
        assert "markdown lint" in lower or "markdown_lint" in lower
        assert any(kw in lower for kw in ("fallback", "fix", "fix_markdown"))

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

    def test_pipeline_has_fix_loop_with_iteration_limit(
        self, pipeline_content: str
    ) -> None:
        """Pipeline defines fix loops with iteration limit."""
        lower = pipeline_content.lower()
        # Iteration limit exists (any reasonable number)
        assert (
            any(
                f"{n} iteration" in lower or f"{n} time" in lower or f"max {n}" in lower
                for n in range(2, 6)
            )
            or "repeat up to" in lower
        ), "Pipeline must specify an iteration limit for fix loops"

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

    def test_pipeline_contains_markdown_fix_guidance(
        self, pipeline_content: str
    ) -> None:
        """Pipeline contains markdown fix guidance."""
        lower = pipeline_content.lower()
        assert "markdown" in lower

    # -- Synapse submodule --

    def test_pipeline_handles_synapse_submodule_commit(
        self, pipeline_content: str
    ) -> None:
        """Pipeline handles Synapse submodule commit in Phase C."""
        lower = pipeline_content.lower()
        assert "submodule" in lower
        assert "synapse" in lower
        assert "commit" in lower

    def test_pipeline_stages_submodule_pointer(self, pipeline_content: str) -> None:
        """Pipeline stages submodule pointer in Step 13 when Synapse was committed."""
        assert "git add .cortex/synapse" in pipeline_content

    def test_pipeline_pushes_submodule_before_superproject(
        self, pipeline_content: str
    ) -> None:
        """Pipeline pushes Synapse submodule before superproject in Step 14."""
        lower = pipeline_content.lower()
        assert "push" in lower and "submodule" in lower

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
        """Read implement prompt + all implement cursor-agents content."""
        content = _read_implement_pipeline_content()
        if not content.strip():
            pytest.skip("Implement pipeline files not found")
        return content

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
        """Standards include type narrowing guidance."""
        lower = python_standards_content.lower()
        assert "type narrowing" in lower, "Standards must cover type narrowing"
        assert any(
            kw in lower for kw in ("assert", "isinstance", "is not none")
        ), "Standards must show a narrowing technique"

    def test_python_standards_type_hints_reference_narrowing(
        self, python_standards_content: str
    ) -> None:
        """Type Hints section cross-references type narrowing."""
        lower = python_standards_content.lower()
        assert "type narrowing" in lower
