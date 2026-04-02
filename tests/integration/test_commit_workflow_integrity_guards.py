"""
Integration tests for fix-loop integrity guards and coding standards.

Split from test_commit_workflow_prompt_alignment.py to stay within
the 400-line file limit.
"""

from pathlib import Path

import pytest

from tests.integration.conftest import repo_root, synapse_path


def _fix_quality_tool_source_path() -> Path:
    """Return path to zero-arg quality tools source."""
    return (
        repo_root()
        / "src"
        / "cortex"
        / "tools"
        / "execution"
        / "pre_commit_zero_arg_tools.py"
    )


def _workflows_guide_path() -> Path:
    """Return path to workflows guide."""
    return repo_root() / "docs" / "guides" / "workflows.md"


def _fix_prompt_path() -> Path:
    """Return path to fix helper prompt under .cortex/synapse/prompts/."""
    return synapse_path() / "prompts" / "fix.md"


def _implement_prompt_path() -> Path:
    """Return path to implement helper prompt under .cortex/synapse/prompts/."""
    return synapse_path() / "prompts" / "do.md"


def _python_coding_standards_path() -> Path:
    """Return path to Python coding standards."""
    return synapse_path() / "rules" / "python" / "python-coding-standards.mdc"


class TestFixLoopIntegrityGuard:
    """Assert fix-loop integrity safeguards are documented."""

    @pytest.fixture
    def workflows_guide_content(self) -> str:
        """Read workflows guide content."""
        path = _workflows_guide_path()
        if not path.exists():
            pytest.skip(
                f"Workflows guide not found at {path} (ref: cleanup-skipped-legacy-tests)"
            )
        return path.read_text()

    @pytest.fixture
    def fix_quality_tool_content(self) -> str:
        """Read autofix tool source content."""
        path = _fix_quality_tool_source_path()
        if not path.exists():
            pytest.skip(
                f"autofix source not found at {path} (ref: cleanup-skipped-legacy-tests)"
            )
        return path.read_text()

    def test_workflows_guide_contains_no_go_integrity_list(
        self, workflows_guide_content: str
    ) -> None:
        """Workflow docs include explicit NO-GO corruption safeguards."""
        lower = workflows_guide_content.lower()
        assert "no-go" in lower
        assert "duplicate function/class definitions" in lower
        assert "type_checking" in lower
        assert "circular imports" in lower
        assert "syntax-invalid python" in lower

    def test_workflows_guide_contains_post_fix_module_validation(
        self, workflows_guide_content: str
    ) -> None:
        """Workflow docs require import/syntax checks before success."""
        lower = workflows_guide_content.lower()
        assert "post-fix validation" in lower
        assert "python3 -m py_compile" in lower
        assert 'python3 -c "import <module_import_path>"' in workflows_guide_content

    def test_workflows_guide_contains_rollback_guidance_for_regressions(
        self, workflows_guide_content: str
    ) -> None:
        """Workflow docs require rollback and bounded retry on regressions."""
        lower = workflows_guide_content.lower()
        assert "roll back that attempt" in lower
        assert "max 3 attempts" in lower

    def test_workflows_guide_requires_submodule_first_fix_routing(
        self, workflows_guide_content: str
    ) -> None:
        """Workflow docs require submodule-first remediation before root checks."""
        lower = workflows_guide_content.lower()
        assert "submodule-first routing" in lower
        assert "git submodule foreach" in workflows_guide_content
        assert "run its fix loop first" in lower

    def test_fix_quality_tool_docs_warn_about_integrity_risks(
        self, fix_quality_tool_content: str
    ) -> None:
        """Tool docs require re-verification and rollback on regressions."""
        lower = fix_quality_tool_content.lower()
        assert "integrity safeguards" in lower
        assert "run_quality_gate()" in fix_quality_tool_content
        assert "roll back that" in lower


class TestFixPromptIntegrityGuard:
    """Assert fix.md documents the same integrity safeguards as workflows.md."""

    @pytest.fixture
    def fix_prompt_content(self) -> str:
        """Read fix helper prompt content."""
        path = _fix_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Fix prompt not found at {path} (ref: cleanup-skipped-legacy-tests)"
            )
        return path.read_text()

    def test_fix_prompt_contains_no_go_integrity_list(
        self, fix_prompt_content: str
    ) -> None:
        """Fix prompt includes explicit NO-GO corruption safeguards."""
        lower = fix_prompt_content.lower()
        assert "no-go" in lower
        assert "duplicate function/class definitions" in lower
        assert "type_checking" in lower
        assert "circular imports" in lower
        assert "syntax-invalid python" in lower

    def test_fix_prompt_contains_post_fix_module_validation(
        self, fix_prompt_content: str
    ) -> None:
        """Fix prompt requires import/syntax checks before success."""
        lower = fix_prompt_content.lower()
        assert "post-fix validation" in lower
        assert "python3 -m py_compile" in lower
        assert 'python3 -c "import <module_import_path>"' in fix_prompt_content

    def test_fix_prompt_contains_rollback_guidance_for_regressions(
        self, fix_prompt_content: str
    ) -> None:
        """Fix prompt requires rollback and bounded retry on regressions."""
        lower = fix_prompt_content.lower()
        assert "roll back that attempt" in lower
        assert "max 3 attempts" in lower

    def test_fix_prompt_requires_submodule_first_fix_routing(
        self, fix_prompt_content: str
    ) -> None:
        """Fix prompt requires submodule-first remediation before root gates."""
        lower = fix_prompt_content.lower()
        assert "submodule-first fix routing" in lower
        assert "git submodule foreach" in fix_prompt_content
        assert 'not automatically "dirty state to reject"' in lower

    def test_fix_prompt_forbids_synthetic_roadmap_backlog(
        self, fix_prompt_content: str
    ) -> None:
        """Fix prompt disallows fake pending backlog fabrication."""
        lower = fix_prompt_content.lower()
        assert "no-go — synthetic roadmap backlog" in lower
        assert "never fabricate generic `pending` roadmap bullets" in lower


class TestImplementPromptIntegrityGuard:
    """Assert implement prompt blocks metadata-only roadmap churn."""

    @pytest.fixture
    def implement_prompt_content(self) -> str:
        """Read implement helper prompt content."""
        path = _implement_prompt_path()
        if not path.exists():
            pytest.skip(
                f"Implement prompt not found at {path} (ref: cleanup-skipped-legacy-tests)"
            )
        return path.read_text()

    def test_implement_prompt_contains_no_op_anti_scrap_guard(
        self, implement_prompt_content: str
    ) -> None:
        """Implement prompt must treat bookkeeping-only runs as no-op."""
        lower = implement_prompt_content.lower()
        assert "hard guardrail (anti-scrap backlog)" in lower
        assert "if `phases.code.files_changed` is empty" in lower
        assert "do not create/add/split roadmap pending items" in lower
        assert "note `no_op_run`" in lower


class TestPythonCodingStandardsTypeNarrowing:
    """Assert Python coding standards document type narrowing."""

    @pytest.fixture
    def python_standards_content(self) -> str:
        """Read Python coding standards; skip if missing."""
        path = _python_coding_standards_path()
        if not path.exists():
            pytest.skip(
                f"Python standards not found at {path} (ref: cleanup-skipped-legacy-tests)"
            )
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
