"""
Integration tests for Phase 55: Implement prompt quality gates.

Verifies that implement-next-roadmap-step.md and python-coding-standards.mdc
contain the mandatory quality gates (Pydantic/TypedDict, format/type steps,
error handling, checklist, implicit-concatenation, ReadLints before 4.5,
token budget; TypedDict prohibition in rules).
"""

from pathlib import Path

import pytest


def _repo_root() -> Path:
    """Return repository root (directory containing src/ and tests/)."""
    return Path(__file__).resolve().parents[2]


def _implement_prompt_path() -> Path:
    """Return path to implement-next-roadmap-step prompt."""
    return (
        _repo_root()
        / ".cortex"
        / "synapse"
        / "prompts"
        / "implement-next-roadmap-step.md"
    )


def _python_coding_standards_path() -> Path:
    """Return path to Python coding standards rules."""
    return (
        _repo_root()
        / ".cortex"
        / "synapse"
        / "rules"
        / "python"
        / "python-coding-standards.mdc"
    )


class TestImplementPromptQualityGates:
    """Assert Phase 55 quality gates are present in implement prompt."""

    @pytest.fixture
    def prompt_content(self) -> str:
        """Read implement prompt; skip if missing."""
        path = _implement_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Implement prompt not found at {path} (e.g. synapse submodule not present)"
            )
        return path.read_text()

    def test_step_35_includes_pydantic_and_typeddict_prohibition(
        self, prompt_content: str
    ) -> None:
        """Step 3.5 includes explicit Pydantic requirement and TypedDict prohibition."""
        assert "Pydantic" in prompt_content and "BaseModel" in prompt_content
        assert "TypedDict" in prompt_content and "STRICTLY FORBIDDEN" in prompt_content

    def test_step_35_includes_pre_implementation_checklist(
        self, prompt_content: str
    ) -> None:
        """Step 3.5 includes pre-implementation checklist."""
        assert "Pre-Implementation Checklist" in prompt_content
        assert "FOR PYTHON" in prompt_content and "NOT TypedDict" in prompt_content

    def test_step_2_includes_load_context_error_handling(
        self, prompt_content: str
    ) -> None:
        """Step 2 includes non-critical load_context error handling and alternatives."""
        assert (
            "load_context()" in prompt_content and "validation error" in prompt_content
        )
        assert "manage_file" in prompt_content and "activeContext.md" in prompt_content

    def test_step_4_includes_mandatory_format_step(self, prompt_content: str) -> None:
        """Step 4 includes mandatory formatting step before type checking (language-agnostic)."""
        assert "MANDATORY: Format code" in prompt_content
        assert (
            "execute_pre_commit_checks" in prompt_content
            or "formatter" in prompt_content.lower()
        )

    def test_step_4_includes_mandatory_type_checking_step(
        self, prompt_content: str
    ) -> None:
        """Step 4 includes mandatory type checking step before test writing."""
        assert "MANDATORY: Run type checking" in prompt_content
        assert "pyright" in prompt_content.lower()

    def test_step_4_includes_readlints_before_step_45(
        self, prompt_content: str
    ) -> None:
        """Step 4 requires run ReadLints or fix_quality_issues before Step 4.5."""
        assert "Before Step 4.5" in prompt_content
        assert "ReadLints" in prompt_content or "fix_quality_issues" in prompt_content

    def test_step_46_includes_implicit_concatenation_check(
        self, prompt_content: str
    ) -> None:
        """Step 4.6 includes multi-line string / implicit concatenation check."""
        assert "implicit concatenation" in prompt_content
        assert "reportImplicitStringConcatenation" in prompt_content

    def test_token_budget_mentions_narrow_implement_steps(
        self, prompt_content: str
    ) -> None:
        """Token budget guidance mentions 15k–20k for narrow implement steps."""
        assert "15000" in prompt_content or "15k" in prompt_content
        assert "20000" in prompt_content or "20k" in prompt_content


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
