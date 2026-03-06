"""
Integration tests for Phase 55: Implement prompt quality gates.

Verifies that implement-next-roadmap-step.md and python-coding-standards.mdc
contain the mandatory quality gates (Pydantic/TypedDict, format/type steps,
error handling, checklist, implicit-concatenation, ReadLints before 4.5,
token budget; TypedDict prohibition in rules).
"""

from pathlib import Path

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.initialization import get_project_root


def _repo_root() -> Path:
    """Return repository root (directory containing src/ and tests/)."""
    return get_project_root()


def _implement_prompt_path() -> Path:
    """Return path to implement-next-roadmap-step prompt."""
    return (
        get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE)
        / "prompts"
        / "implement-next-roadmap-step.md"
    )


def _create_plan_prompt_path() -> Path:
    """Return path to create-plan prompt."""
    return (
        get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE)
        / "prompts"
        / "create-plan.md"
    )


def _implement_executor_path() -> Path:
    """Return path to implement-executor agent (quality gates live here after delegation)."""
    return (
        get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE)
        / "agents"
        / "implement-executor.md"
    )


def _python_coding_standards_path() -> Path:
    """Return path to Python coding standards rules."""
    return (
        get_cortex_path(_repo_root(), CortexResourceType.SYNAPSE)
        / "rules"
        / "python"
        / "python-coding-standards.mdc"
    )


class TestImplementPromptQualityGates:
    """Assert Phase 55 quality gates are present in implement prompt or implement-executor agent."""

    @pytest.fixture
    def prompt_content(self) -> str:
        """Read implement prompt; skip if missing."""
        path = _implement_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Implement prompt not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    @pytest.fixture
    def executor_content(self) -> str:
        """Read implement-executor agent; skip if missing."""
        path = _implement_executor_path()
        if not path.exists():
            pytest.skip(
                f"Implement-executor agent not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_step_35_includes_pydantic_and_typeddict_prohibition(
        self, executor_content: str
    ) -> None:
        """Step 3.5 (executor Phase 2) includes explicit Pydantic requirement and TypedDict prohibition."""
        assert "Pydantic" in executor_content and "BaseModel" in executor_content
        assert (
            "TypedDict" in executor_content and "STRICTLY FORBIDDEN" in executor_content
        )

    def test_step_35_includes_pre_implementation_checklist(
        self, executor_content: str
    ) -> None:
        """Step 3.5 (executor Phase 2) includes pre-implementation checklist."""
        assert "Pre-Implementation Checklist" in executor_content
        assert "FOR PYTHON" in executor_content and "NOT TypedDict" in executor_content

    def test_mentions_compound_engineering_loop(self, prompt_content: str) -> None:
        """Implement prompt references compound-engineering loop (Plan→Work→Review→Compound)."""
        assert "compound" in prompt_content.lower()
        assert "memory bank" in prompt_content.lower()

    def test_step_2_includes_load_context_error_handling(
        self, executor_content: str
    ) -> None:
        """Implement-executor includes load_context error handling and alternatives."""
        assert "load_context" in executor_content
        assert "validation error" in executor_content or "error" in executor_content
        assert "manage_file" in executor_content and "activeContext" in executor_content

    def test_step_4_includes_mandatory_format_step(self, executor_content: str) -> None:
        """Executor includes mandatory formatting step before type checking."""
        assert "MANDATORY: Format code" in executor_content
        assert (
            "execute_pre_commit_checks" in executor_content
            or "formatter" in executor_content.lower()
        )

    def test_step_4_includes_mandatory_type_checking_step(
        self, executor_content: str
    ) -> None:
        """Executor includes mandatory type checking step before test writing."""
        assert "MANDATORY: Run type checking" in executor_content
        assert "pyright" in executor_content.lower()

    def test_step_4_includes_readlints_before_step_45(
        self, executor_content: str
    ) -> None:
        """Executor requires run ReadLints or fix_quality before Step 3.5/4.5."""
        assert (
            "Before Step 3.5" in executor_content
            or "Before Step 4.5" in executor_content
        )
        assert (
            "ReadLints" in executor_content
            or "fix_quality" in executor_content
            or "execute_pre_commit_checks" in executor_content
        )

    def test_step_46_includes_implicit_concatenation_check(
        self, executor_content: str
    ) -> None:
        """Executor includes implicit concatenation / reportImplicitStringConcatenation check."""
        assert "implicit concatenation" in executor_content
        assert "reportImplicitStringConcatenation" in executor_content

    def test_token_budget_mentions_narrow_implement_steps(
        self, executor_content: str
    ) -> None:
        """Executor token budget guidance mentions 15k–20k for implement steps."""
        assert (
            "15000" in executor_content
            or "15k" in executor_content
            or "15,000" in executor_content
        )
        assert (
            "20000" in executor_content
            or "20k" in executor_content
            or "20,000" in executor_content
        )

    def test_plan_step_sequence_mandatory_block(
        self, prompt_content: str, executor_content: str
    ) -> None:
        """Implement prompt or executor contains Plan step sequence (MANDATORY) and in-order execution."""
        combined = prompt_content + "\n" + executor_content
        assert "Plan step sequence" in combined
        assert "MANDATORY" in combined and "plan" in combined.lower()
        assert "in order" in combined
        assert "first uncompleted step" in combined or "do not skip" in combined


class TestCreatePlanImplementationSequence:
    """Assert create-plan prompt documents implementation sequence (Session Optimization 2026-02-01)."""

    @pytest.fixture
    def create_plan_content(self) -> str:
        """Read create-plan prompt; skip if missing."""
        path = _create_plan_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Create-plan prompt not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_implementation_steps_section_sequence_wording(
        self, create_plan_content: str
    ) -> None:
        """Implementation Steps section states steps define implementation sequence and execute in order."""
        assert "implementation sequence" in create_plan_content
        assert "execute them in order" in create_plan_content
        assert "Step 1" in create_plan_content and "Step 2" in create_plan_content


class TestPythonCodingStandardsTypedDictProhibition:
    """Assert Phase 55 TypedDict prohibition in Python coding standards."""

    @pytest.fixture
    def rules_content(self) -> str:
        """Read Python coding standards; skip if missing."""
        path = _python_coding_standards_path()
        if not path.exists():
            pytest.skip(
                f"Python coding standards not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_pydantic_section_includes_typeddict_forbidden(
        self, rules_content: str
    ) -> None:
        """Pydantic 2 Models section states TypedDict is FORBIDDEN for new code."""
        assert "TypedDict" in rules_content
        assert "FORBIDDEN" in rules_content or "forbidden" in rules_content.lower()

    def test_pydantic_section_includes_validation_step(
        self, rules_content: str
    ) -> None:
        """Pydantic section includes validation step (pyright) for TypedDict."""
        assert "pyright" in rules_content.lower()
        assert "BaseModel" in rules_content
