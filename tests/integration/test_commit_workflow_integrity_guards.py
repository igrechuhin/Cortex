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


def _final_report_templates_path() -> Path:
    """Return path to Synapse final report templates guide."""
    return repo_root() / "docs" / "guides" / "synapse-final-report-templates.md"


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

    @pytest.fixture
    def final_report_templates_content(self) -> str:
        """Read final report templates guide content."""
        # AI: Keep the shared template guide under test so prompt-local fixes
        # cannot silently drift from the canonical /fix reporting contract.
        path = _final_report_templates_path()
        if not path.exists():
            pytest.skip(
                f"Final report templates guide not found at {path} (ref: cleanup-skipped-legacy-tests)"
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
        assert ".venv/bin/python -m py_compile" in workflows_guide_content
        assert (
            'PYTHONPATH=src .venv/bin/python -c "import <module_import_path>"'
            in workflows_guide_content
        )
        assert "any other interpreter is a critical error" in lower

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

    def test_workflows_guide_documents_coverage_fix_contract(
        self, workflows_guide_content: str
    ) -> None:
        """Workflow docs require the dedicated coverage target and telemetry schema."""
        # AI: Coverage uplift is owned by the 📈 coverage target via @fix-coverage.
        # Guards keep the guide aligned with fix.md's new 4-target structure.
        assert (
            "coverage below threshold with zero failing tests"
            in workflows_guide_content
        )
        assert "@fix-coverage" in workflows_guide_content
        assert "coverage_gaps" in workflows_guide_content
        assert "final_coverage" in workflows_guide_content
        assert "coverage_delta" in workflows_guide_content
        assert "tests_added" in workflows_guide_content
        assert "blocker_reason" in workflows_guide_content

    def test_fix_quality_tool_docs_warn_about_integrity_risks(
        self, fix_quality_tool_content: str
    ) -> None:
        """Tool docs require re-verification and rollback on regressions."""
        lower = fix_quality_tool_content.lower()
        assert "integrity safeguards" in lower
        assert "run_quality_gate()" in fix_quality_tool_content
        assert "roll back that" in lower

    def test_final_report_templates_document_coverage_fix_reporting(
        self, final_report_templates_content: str
    ) -> None:
        """Diagnostic template documents the coverage target contract and blocker reporting."""
        # AI: Lock the canonical report template to evidence-or-blocker wording for the
        # dedicated 📈 coverage target so exits cannot regress into policy-only summaries.
        assert "coverage target" in final_report_templates_content
        assert "final_coverage" in final_report_templates_content
        assert "tests_added" in final_report_templates_content
        assert "coverage_delta" in final_report_templates_content
        assert "blocker_reason" in final_report_templates_content
        assert "`Coverage | BLOCKED | <n>`" in final_report_templates_content


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
        assert ".venv/bin/python -m py_compile" in fix_prompt_content
        assert (
            'PYTHONPATH=src .venv/bin/python -c "import <module_import_path>"'
            in fix_prompt_content
        )
        assert "any other interpreter is a critical error" in lower

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

    def test_fix_prompt_requires_coverage_target_contract(
        self, fix_prompt_content: str
    ) -> None:
        """Fix prompt delegates coverage uplift to the 📈 coverage target / @fix-coverage."""
        # AI: Coverage uplift is a dedicated subagent. fix.md must document the target,
        # the pre-flight handoff payload, and that coverage runs FIRST in target=all.
        assert "@fix-coverage" in fix_prompt_content
        assert "coverage Target" in fix_prompt_content
        assert "coverage_gaps" in fix_prompt_content
        assert "coverage_threshold" in fix_prompt_content
        assert 'phase="coverage"' in fix_prompt_content
        assert "coverage → quality → tests → docs" in fix_prompt_content
        assert "blocker_reason" in fix_prompt_content
        assert "BLOCKED_NO_MCP" in fix_prompt_content

    def test_fix_prompt_short_circuits_pipeline_on_coverage_failure(
        self, fix_prompt_content: str
    ) -> None:
        """Fix prompt routes coverage failures correctly: tests_failing → Tests; failed/BLOCKED → hard stop."""
        # AI: Two distinct failure modes need different routes.
        # tests_failing: tests failed before coverage measured → fix tests first.
        # failed/BLOCKED: coverage measurable but below threshold → hard stop.
        assert "HARD STOP — Coverage gate" in fix_prompt_content
        assert (
            "Do NOT run `fix quality`, `fix tests`, or `fix docs`" in fix_prompt_content
        )
        assert "tests_failing" in fix_prompt_content
        assert "Coverage failure routing" in fix_prompt_content


class TestFixTestsAgentScope:
    """Assert fix-tests agent scopes out coverage uplift and routes to @fix-coverage."""

    @pytest.fixture
    def fix_tests_agent_content(self) -> str:
        """Read fix-tests cursor agent content."""
        path = synapse_path() / "cursor-agents" / "fix-tests.md"
        if not path.exists():
            pytest.skip(
                f"Fix-tests agent not found at {path} (ref: cleanup-skipped-legacy-tests)"
            )
        return path.read_text()

    def test_fix_tests_agent_delegates_coverage_to_fix_coverage(
        self, fix_tests_agent_content: str
    ) -> None:
        """Fix-tests agent must route coverage uplift to @fix-coverage, not do it inline."""
        # AI: Coverage uplift is owned by @fix-coverage. fix-tests only handles
        # assertion failures (Branch A) and subprocess crashes (Branch C).
        assert "@fix-coverage" in fix_tests_agent_content
        assert "OUT OF SCOPE" in fix_tests_agent_content
        assert "redirect" in fix_tests_agent_content
        assert "blocker_reason" in fix_tests_agent_content


class TestFixCoverageAgentContract:
    """Assert fix-coverage agent documents the uplift contract."""

    @pytest.fixture
    def fix_coverage_agent_content(self) -> str:
        """Read fix-coverage cursor agent content."""
        path = synapse_path() / "cursor-agents" / "fix-coverage.md"
        if not path.exists():
            pytest.skip(
                f"Fix-coverage agent not found at {path} (ref: cleanup-skipped-legacy-tests)"
            )
        return path.read_text()

    def test_fix_coverage_agent_declares_scope_and_contract(
        self, fix_coverage_agent_content: str
    ) -> None:
        """Agent defines OUT OF SCOPE boundaries and the pipeline_handoff contract."""
        assert "OUT OF SCOPE" in fix_coverage_agent_content
        assert "coverage_gaps" in fix_coverage_agent_content
        assert "coverage_threshold" in fix_coverage_agent_content
        assert 'phase="coverage"' in fix_coverage_agent_content
        assert "tests_added" in fix_coverage_agent_content
        assert "final_coverage" in fix_coverage_agent_content
        assert "coverage_delta" in fix_coverage_agent_content
        assert "blocker_reason" in fix_coverage_agent_content
        assert "BLOCKED" in fix_coverage_agent_content

    def test_fix_coverage_agent_routes_test_failures_not_blocks(
        self, fix_coverage_agent_content: str
    ) -> None:
        """Agent must emit tests_failing (not BLOCKED) when tests fail before coverage is measured."""
        # AI: it42 deadlock — coverage BLOCKED because tests_failed > 0, hard-stop fired,
        # Tests target skipped. tests_failing status lets orchestrator route to Tests instead.
        assert "tests_failing" in fix_coverage_agent_content
        assert "tests_failed > 0" in fix_coverage_agent_content
        assert "coverage == null" in fix_coverage_agent_content

    def test_fix_coverage_agent_enforces_three_iteration_discipline(
        self, fix_coverage_agent_content: str
    ) -> None:
        """Agent must run all 3 iterations unless threshold met or hard stall."""
        # AI: 1-iteration exits with positive delta were the failure mode in it40 —
        # agent added one test file (+0.22%) and gave up. Lock in the iteration discipline.
        assert "you MUST run all 3 iterations" in fix_coverage_agent_content
        assert (
            "do NOT exit after iteration 1 with a positive delta"
            in fix_coverage_agent_content
        )
        assert "two consecutive" in fix_coverage_agent_content
        assert "small positive delta" in fix_coverage_agent_content

    def test_fix_coverage_agent_switches_strategy_on_repeated_files(
        self, fix_coverage_agent_content: str
    ) -> None:
        """Agent must switch from entry-point tests to access-widening when same files recur."""
        # AI: it46 — agent looped on EvaluateStocksExecutor 3 iterations adding validation
        # tests (+0.01% each). Private pure methods were never widened. Lock in the rule.
        lower = fix_coverage_agent_content.lower()
        assert "strategy switch" in lower
        assert "same top" in lower or "recur" in lower
        assert "access" in lower

    def test_fix_coverage_agent_requires_import_pattern_check(
        self, fix_coverage_agent_content: str
    ) -> None:
        """Agent must read an existing test file for imports before writing new ones."""
        # AI: it46 failure — agent wrote EvaluateStocksExecutorAdditionalTests.swift
        # without `import Shared`, causing a compile error in the whole test target and
        # making coverage=null on the 3rd gate call. Mandate the import-copy step.
        assert "import" in fix_coverage_agent_content.lower()
        assert "existing test file" in fix_coverage_agent_content
        assert "same test target" in fix_coverage_agent_content

    def test_fix_coverage_agent_rolls_back_on_null_coverage(
        self, fix_coverage_agent_content: str
    ) -> None:
        """Agent must roll back the batch and not continue when gate returns null coverage."""
        # AI: it46 — 3rd iteration returned coverage=null (compile error), agent recorded
        # zero delta and stopped. Should have rolled back the broken files instead.
        assert "null coverage" in fix_coverage_agent_content or (
            "new_coverage == null" in fix_coverage_agent_content
        )
        assert "Roll back" in fix_coverage_agent_content or (
            "roll back" in fix_coverage_agent_content
        )

    def test_fix_coverage_agent_requires_swift_build_before_gate(
        self, fix_coverage_agent_content: str
    ) -> None:
        """Agent must run swift build --target before run_quality_gate to catch compile errors fast."""
        # AI: it46 — full gate takes 5-10 min; a fast build check catches missing imports in ~30s.
        assert "swift build --target" in fix_coverage_agent_content

    def test_fix_coverage_agent_preserves_test_writing_scope(
        self, fix_coverage_agent_content: str
    ) -> None:
        """Agent keeps coverage work focused on tests and bounded access widening."""
        lower = fix_coverage_agent_content.lower()
        assert "write tests" in lower
        assert "the only action in scope" in lower
        assert "out of scope" in lower

    def test_fix_coverage_agent_requires_access_widening_for_pure_logic(
        self, fix_coverage_agent_content: str
    ) -> None:
        """Agent MUST widen private pure-logic functions before writing tests for them."""
        # AI: it46 — agent ignored access widening and kept writing entry-point validation
        # tests with near-zero delta. Rule is now mandatory: classify lines, widen pure
        # private helpers first, only then write tests targeting those helpers directly.
        assert "You MUST widen" in fix_coverage_agent_content
        assert "Trapped in private" in fix_coverage_agent_content
        lower = fix_coverage_agent_content.lower()
        assert "pure logic" in lower
        assert "side effects" in lower


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

    def test_implement_prompt_requires_post_implementation_review_gate(
        self, implement_prompt_content: str
    ) -> None:
        """Implement prompt requires an inline mandatory review gate before completion."""
        assert "## Review Gate" in implement_prompt_content
        # Review must be performed inline — no system-provided subagent delegation.
        assert "inline" in implement_prompt_content
        assert "do NOT delegate to a subagent" in implement_prompt_content
        assert "review_outcome" in implement_prompt_content
        assert "no_gaps" in implement_prompt_content
        assert "gaps_found" in implement_prompt_content

    def test_implement_prompt_reopens_plan_with_deduplicated_gaps(
        self, implement_prompt_content: str
    ) -> None:
        """Review findings reopen the plan instead of allowing silent completion."""
        lower = implement_prompt_content.lower()
        assert "## review follow-up gaps" in lower
        assert "de-duplicate" in lower
        assert "status is `pending`" in lower
        assert (
            'do **not** call `plan(operation="complete")`' in implement_prompt_content
        )


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
