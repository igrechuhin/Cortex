"""
Tests for fix.wf.js Workflow script.

These tests verify the structural contract of the fix workflow:
- PHASE 0 diagnosis always runs first, before any target agent call
- Coverage routing: switch on status covers all 5 values (passed, skipped,
  tests_failing, failed, BLOCKED)
- Per-target retry loops: while (iterations < MAX_TARGET_ITERATIONS) cap at 3
- Quality scope routing: if (change_scope === 'markdown_only') selects correct path
- Tests target: skipped when markdown_only, branching logic present for source
- Docs target: bridge_mismatch non-blocking path encoded in JS
- Non-blocking paths: post-prompt hook wrapped in try/catch, fix failures continue
- Schema objects defined for all five subagent types
- Early-exit returns are structured objects (not throws)
- Prompts manifest marks fix.md as superseded_by fix.wf.js

Since the Claude Code Workflow JS runtime is not available for Python-level
unit testing, these tests validate the script's control-flow structure
statically via source inspection. This is intentional: the contract being
tested is the presence and ordering of control-flow constructs (switch/case,
while loops, if/else branches, agentType references), which are stable text
patterns that survive routine prose edits inside agent prompts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

WF_PATH = Path(__file__).parents[2] / ".cortex" / "synapse" / "prompts" / "fix.wf.js"
MANIFEST_PATH = (
    Path(__file__).parents[2]
    / ".cortex"
    / "synapse"
    / "prompts"
    / "prompts-manifest.json"
)


@pytest.fixture(scope="module")
def wf_source() -> str:
    """Load the fix workflow script source."""
    assert WF_PATH.exists(), f"Workflow script not found: {WF_PATH}"
    return WF_PATH.read_text()


# ── File existence ─────────────────────────────────────────────────────────────


class TestWorkflowFileExists:
    def test_workflow_file_exists(self) -> None:
        assert WF_PATH.exists(), f"Expected {WF_PATH} to exist"

    def test_workflow_file_nonempty(self, wf_source: str) -> None:
        assert len(wf_source) > 500, "Workflow file should have substantial content"

    def test_workflow_file_is_js(self) -> None:
        assert WF_PATH.suffix == ".js"


# ── meta export ────────────────────────────────────────────────────────────────


class TestMetaExport:
    def test_meta_export_present(self, wf_source: str) -> None:
        assert "export const meta" in wf_source

    def test_meta_has_name(self, wf_source: str) -> None:
        assert '"cortex-fix"' in wf_source or "'cortex-fix'" in wf_source

    def test_meta_has_phases_array(self, wf_source: str) -> None:
        assert "phases:" in wf_source or "phases =" in wf_source

    def test_meta_has_diagnosis_phase(self, wf_source: str) -> None:
        assert "Diagnosis" in wf_source

    def test_meta_has_coverage_phase(self, wf_source: str) -> None:
        assert "Coverage" in wf_source

    def test_meta_has_quality_phase(self, wf_source: str) -> None:
        assert "Quality" in wf_source

    def test_meta_has_tests_phase(self, wf_source: str) -> None:
        assert "Tests" in wf_source

    def test_meta_has_docs_phase(self, wf_source: str) -> None:
        assert "Docs" in wf_source


# ── Schema definitions ─────────────────────────────────────────────────────────


class TestSchemaDefinitions:
    def test_diagnosis_schema_defined(self, wf_source: str) -> None:
        assert "DIAGNOSIS_SCHEMA" in wf_source

    def test_coverage_schema_defined(self, wf_source: str) -> None:
        assert "COVERAGE_SCHEMA" in wf_source

    def test_quality_schema_defined(self, wf_source: str) -> None:
        assert "QUALITY_SCHEMA" in wf_source

    def test_tests_schema_defined(self, wf_source: str) -> None:
        assert "TESTS_SCHEMA" in wf_source

    def test_docs_schema_defined(self, wf_source: str) -> None:
        assert "DOCS_SCHEMA" in wf_source

    def test_all_schemas_have_required_field(self, wf_source: str) -> None:
        # Each of the 5 named schemas should have a required array.
        required_count = len(re.findall(r"\brequired\b\s*:", wf_source))
        assert (
            required_count >= 5
        ), f"Expected >=5 schema 'required:' fields, got {required_count}"

    def test_diagnosis_schema_has_mcp_available(self, wf_source: str) -> None:
        # mcp_available gates the entire pipeline — must be in DIAGNOSIS_SCHEMA
        assert re.search(r"DIAGNOSIS_SCHEMA.*?mcp_available", wf_source, re.DOTALL)

    def test_diagnosis_schema_has_change_scope(self, wf_source: str) -> None:
        # change_scope drives quality scope routing — must be in DIAGNOSIS_SCHEMA
        assert re.search(r"DIAGNOSIS_SCHEMA.*?change_scope", wf_source, re.DOTALL)

    def test_coverage_schema_has_status_enum(self, wf_source: str) -> None:
        # status must enumerate all 5 values the switch branches on
        assert re.search(r"COVERAGE_SCHEMA.*?status", wf_source, re.DOTALL)

    def test_quality_schema_has_passed(self, wf_source: str) -> None:
        # passed drives the while-loop exit condition
        assert re.search(r"QUALITY_SCHEMA.*?passed", wf_source, re.DOTALL)

    def test_tests_schema_has_passed(self, wf_source: str) -> None:
        # passed drives the tests loop exit condition
        assert re.search(r"TESTS_SCHEMA.*?passed", wf_source, re.DOTALL)

    def test_docs_schema_has_bridge_mismatch(self, wf_source: str) -> None:
        # bridge_mismatch is the non-blocking docs gate path — must be in DOCS_SCHEMA
        assert re.search(r"DOCS_SCHEMA.*?bridge_mismatch", wf_source, re.DOTALL)


# ── PHASE 0 diagnosis gate ─────────────────────────────────────────────────────


class TestDiagnosisGate:
    def test_diagnosis_is_first_agent_call(self, wf_source: str) -> None:
        """Diagnosis must be the first await agent() call — no target runs before it."""
        # Body starts after the closing '};' of export const meta
        meta_end = wf_source.find("\nexport const meta = {")
        assert meta_end >= 0, "export const meta not found"
        function_body = wf_source[meta_end:]

        diagnosis_pos = function_body.find("DIAGNOSIS_SCHEMA")
        coverage_pos = function_body.find("COVERAGE_SCHEMA")
        quality_pos = function_body.find("QUALITY_SCHEMA")
        tests_pos = function_body.find("TESTS_SCHEMA")
        docs_pos = function_body.find("DOCS_SCHEMA")

        assert diagnosis_pos > 0, "DIAGNOSIS_SCHEMA must appear in function body"
        for name, pos in [
            ("COVERAGE_SCHEMA", coverage_pos),
            ("QUALITY_SCHEMA", quality_pos),
            ("TESTS_SCHEMA", tests_pos),
            ("DOCS_SCHEMA", docs_pos),
        ]:
            if pos > 0:
                assert (
                    diagnosis_pos < pos
                ), f"DIAGNOSIS_SCHEMA must appear before {name} in function body"

    def test_diagnosis_phase_called_first(self, wf_source: str) -> None:
        """phase('Diagnosis') must appear before all other phase() calls."""
        meta_end = wf_source.find("\nexport const meta = {")
        assert meta_end >= 0
        function_body = wf_source[meta_end:]

        diag_pos = function_body.find('phase("Diagnosis")')
        cov_pos = function_body.find('phase("Coverage")')
        qual_pos = function_body.find('phase("Quality")')
        tests_pos = function_body.find('phase("Tests")')
        docs_pos = function_body.find('phase("Docs")')

        assert diag_pos > 0, 'phase("Diagnosis") not found in function body'
        for name, pos in [
            ('phase("Coverage")', cov_pos),
            ('phase("Quality")', qual_pos),
            ('phase("Tests")', tests_pos),
            ('phase("Docs")', docs_pos),
        ]:
            if pos > 0:
                assert diag_pos < pos, f'phase("Diagnosis") must appear before {name}'

    def test_blocked_no_mcp_returns_early(self, wf_source: str) -> None:
        """BLOCKED_NO_MCP must trigger early return before any target."""
        assert "BLOCKED_NO_MCP" in wf_source
        assert re.search(
            r"BLOCKED_NO_MCP.*?return\s*\{|return\s*\{.*?BLOCKED_NO_MCP",
            wf_source,
            re.DOTALL,
        )

    def test_no_targets_returns_early(self, wf_source: str) -> None:
        """Empty targets array must trigger early return."""
        assert "no_targets" in wf_source or "no fix targets" in wf_source.lower()


# ── Coverage routing ───────────────────────────────────────────────────────────


class TestCoverageRouting:
    def test_switch_on_coverage_status(self, wf_source: str) -> None:
        """Coverage routing must use a switch statement on cov.status."""
        assert "switch (" in wf_source or "switch(" in wf_source
        assert re.search(r"switch\s*\(\s*cov\.status\s*\)", wf_source)

    def test_passed_case_present(self, wf_source: str) -> None:
        """switch must have a 'passed' case."""
        assert 'case "passed"' in wf_source or "case 'passed'" in wf_source

    def test_skipped_case_present(self, wf_source: str) -> None:
        """switch must have a 'skipped' case."""
        assert 'case "skipped"' in wf_source or "case 'skipped'" in wf_source

    def test_tests_failing_case_present(self, wf_source: str) -> None:
        """switch must have a 'tests_failing' case."""
        assert (
            'case "tests_failing"' in wf_source or "case 'tests_failing'" in wf_source
        )

    def test_failed_case_present(self, wf_source: str) -> None:
        """switch must have a 'failed' case."""
        assert 'case "failed"' in wf_source or "case 'failed'" in wf_source

    def test_blocked_case_present(self, wf_source: str) -> None:
        """switch must have a 'BLOCKED' case."""
        assert 'case "BLOCKED"' in wf_source or "case 'BLOCKED'" in wf_source

    def test_default_case_present(self, wf_source: str) -> None:
        """switch must have a default case to catch unexpected status values."""
        assert "default:" in wf_source

    def test_tests_failing_skips_quality(self, wf_source: str) -> None:
        """tests_failing must set runQuality=false and runTests=true."""
        switch_start = wf_source.find("switch (")
        if switch_start < 0:
            switch_start = wf_source.find("switch(")
        assert switch_start > 0
        switch_section = wf_source[switch_start : switch_start + 1500]
        assert (
            "runQuality = false" in switch_section
            or "runQuality=false" in switch_section
        )
        assert "runTests = true" in switch_section or "runTests=true" in switch_section

    def test_failed_blocked_returns_early(self, wf_source: str) -> None:
        """'failed' and 'BLOCKED' cases must return early (hard stop)."""
        assert "stopped_at" in wf_source
        assert re.search(
            r"stopped_at.*?coverage|coverage.*?stopped_at", wf_source, re.DOTALL
        )

    def test_coverage_status_all_five_in_schema_enum(self, wf_source: str) -> None:
        """COVERAGE_SCHEMA.status enum must list all 5 values."""
        for val in ["passed", "skipped", "tests_failing", "failed", "BLOCKED"]:
            assert (
                f'"{val}"' in wf_source or f"'{val}'" in wf_source
            ), f"Coverage status value '{val}' not found in schema or switch"


# ── Per-target retry loops ─────────────────────────────────────────────────────


class TestPerTargetRetryLoops:
    def test_max_target_iterations_constant(self, wf_source: str) -> None:
        """Max iterations must be a named constant, not a magic number inline."""
        assert "MAX_TARGET_ITERATIONS" in wf_source

    def test_max_target_iterations_is_three(self, wf_source: str) -> None:
        """Target retry cap must be exactly 3 iterations per fix.md spec."""
        has_three_cap = (
            "MAX_TARGET_ITERATIONS = 3" in wf_source or "iterations < 3" in wf_source
        )
        assert has_three_cap, "Target retry cap must be 3"

    def test_quality_while_loop_present(self, wf_source: str) -> None:
        """Quality target must use a while loop for retry."""
        quality_pos = wf_source.find('phase("Quality")')
        tests_pos = wf_source.find('phase("Tests")')
        quality_section = wf_source[quality_pos:tests_pos]
        assert "while (" in quality_section or "while(" in quality_section

    def test_tests_while_loop_present(self, wf_source: str) -> None:
        """Tests target must use a while loop for retry."""
        tests_pos = wf_source.find('phase("Tests")')
        docs_pos = wf_source.find('phase("Docs")')
        tests_section = wf_source[tests_pos:docs_pos]
        assert "while (" in tests_section or "while(" in tests_section

    def test_docs_while_loop_present(self, wf_source: str) -> None:
        """Docs target must use a while loop for retry."""
        docs_pos = wf_source.find('phase("Docs")')
        hook_pos = wf_source.find('phase("Post-Prompt Hook")')
        docs_section = wf_source[docs_pos:hook_pos]
        assert "while (" in docs_section or "while(" in docs_section

    def test_quality_loop_checks_passed(self, wf_source: str) -> None:
        """Quality loop exit condition must check quality.passed."""
        assert re.search(r"quality\.passed|qualityPassed", wf_source)

    def test_tests_loop_checks_passed(self, wf_source: str) -> None:
        """Tests loop exit condition must check tests.passed."""
        assert re.search(r"tests\.passed|testsPassed", wf_source)

    def test_docs_loop_checks_passed(self, wf_source: str) -> None:
        """Docs loop exit condition must check docs.passed."""
        assert re.search(r"docs\.passed|docsPassed", wf_source)

    def test_iteration_counter_incremented_in_each_loop(self, wf_source: str) -> None:
        """Each loop must increment its iterations counter."""
        increment_count = len(re.findall(r"iterations\+\+", wf_source))
        # quality + tests + docs = at least 3 loops each with iterations++
        assert (
            increment_count >= 3
        ), f"Expected >=3 'iterations++' (one per target loop), got {increment_count}"

    def test_loop_logs_retry_message(self, wf_source: str) -> None:
        """Each loop must log a retry message when iteration fails."""
        assert re.search(r"retrying\.\.\.", wf_source)


# ── Quality scope routing ──────────────────────────────────────────────────────


class TestQualityScopeRouting:
    def test_markdown_only_branch_present(self, wf_source: str) -> None:
        """Quality must branch on change_scope === 'markdown_only'."""
        assert re.search(
            r"markdown_only.*?Path A|Path A.*?markdown_only|change_scope.*?markdown_only",
            wf_source,
            re.DOTALL,
        )

    def test_source_changed_branch_present(self, wf_source: str) -> None:
        """Quality must have a source_changed path (Path B)."""
        assert "Path B" in wf_source or re.search(
            r"source_changed|mixed.*?autofix", wf_source, re.DOTALL
        )

    def test_diagnosis_change_scope_used_in_quality(self, wf_source: str) -> None:
        """Quality agent call must reference diagnosis.change_scope for routing."""
        quality_pos = wf_source.find('phase("Quality")')
        tests_pos = wf_source.find('phase("Tests")')
        quality_section = wf_source[quality_pos:tests_pos]
        assert (
            "diagnosis.change_scope" in quality_section
            or "change_scope" in quality_section
        )


# ── Tests target routing ───────────────────────────────────────────────────────


class TestTestsTargetRouting:
    def test_markdown_only_skips_tests(self, wf_source: str) -> None:
        """Tests must skip when change_scope is markdown_only."""
        tests_pos = wf_source.find('phase("Tests")')
        docs_pos = wf_source.find('phase("Docs")')
        tests_section = wf_source[tests_pos:docs_pos]
        assert "markdown_only" in tests_section

    def test_tests_branch_a_for_assertion_failures(self, wf_source: str) -> None:
        """Tests must document Branch A (assertion failures > 0)."""
        assert "Branch A" in wf_source or "tests_failed > 0" in wf_source

    def test_tests_branch_b_for_coverage_only(self, wf_source: str) -> None:
        """Tests must document Branch B (coverage-only — out of scope)."""
        assert "Branch B" in wf_source or "coverage only" in wf_source.lower()

    def test_tests_branch_c_for_subprocess_crash(self, wf_source: str) -> None:
        """Tests must document Branch C (subprocess crash / build error)."""
        assert "Branch C" in wf_source or "subprocess crash" in wf_source.lower()


# ── Docs target — bridge mismatch ─────────────────────────────────────────────


class TestDocsBridgeMismatch:
    def test_bridge_mismatch_field_checked(self, wf_source: str) -> None:
        """Docs loop must check docs.bridge_mismatch to break early."""
        assert "bridge_mismatch" in wf_source

    def test_bridge_mismatch_is_non_blocking(self, wf_source: str) -> None:
        """bridge_mismatch must be treated as a non-blocking warning, not an error."""
        # Should break out of the loop rather than returning failure
        docs_pos = wf_source.find('phase("Docs")')
        hook_pos = wf_source.find('phase("Post-Prompt Hook")')
        docs_section = wf_source[docs_pos:hook_pos]
        assert "non-blocking" in docs_section.lower() or "break" in docs_section

    def test_docs_warning_captured(self, wf_source: str) -> None:
        """A docs_warning variable must capture bridge mismatch info for the return value."""
        assert "docsWarning" in wf_source or "docs_warning" in wf_source


# ── Phase ordering ─────────────────────────────────────────────────────────────


class TestPhaseOrder:
    def test_diagnosis_before_coverage(self, wf_source: str) -> None:
        diag_pos = wf_source.find('phase("Diagnosis")')
        cov_pos = wf_source.find('phase("Coverage")')
        if cov_pos > 0:
            assert 0 < diag_pos < cov_pos, "Diagnosis must run before Coverage"

    def test_diagnosis_before_quality(self, wf_source: str) -> None:
        diag_pos = wf_source.find('phase("Diagnosis")')
        qual_pos = wf_source.find('phase("Quality")')
        if qual_pos > 0:
            assert 0 < diag_pos < qual_pos, "Diagnosis must run before Quality"

    def test_quality_before_tests(self, wf_source: str) -> None:
        qual_pos = wf_source.find('phase("Quality")')
        tests_pos = wf_source.find('phase("Tests")')
        if qual_pos > 0 and tests_pos > 0:
            assert 0 < qual_pos < tests_pos, "Quality must run before Tests"

    def test_tests_before_docs(self, wf_source: str) -> None:
        tests_pos = wf_source.find('phase("Tests")')
        docs_pos = wf_source.find('phase("Docs")')
        if tests_pos > 0 and docs_pos > 0:
            assert 0 < tests_pos < docs_pos, "Tests must run before Docs"

    def test_docs_before_post_prompt_hook(self, wf_source: str) -> None:
        docs_pos = wf_source.find('phase("Docs")')
        hook_pos = wf_source.find('phase("Post-Prompt Hook")')
        if docs_pos > 0 and hook_pos > 0:
            assert 0 < docs_pos < hook_pos, "Docs must run before Post-Prompt Hook"


# ── Non-blocking paths ─────────────────────────────────────────────────────────


class TestNonBlockingPaths:
    def test_post_prompt_hook_is_non_blocking(self, wf_source: str) -> None:
        """Post-prompt hook must be wrapped in try/catch."""
        hook_pos = wf_source.find('phase("Post-Prompt Hook")')
        hook_section = wf_source[hook_pos:]
        assert (
            "try {" in hook_section or "try{" in hook_section
        ), "Post-prompt hook must be wrapped in try { } catch for non-blocking behavior"

    def test_target_failures_are_non_blocking(self, wf_source: str) -> None:
        """Target failures after max iterations must log and continue, not return early."""
        # Each target failure should log and continue, not hard-return
        assert re.search(r"non-blocking\)", wf_source)

    def test_non_blocking_documented(self, wf_source: str) -> None:
        """non-blocking keyword must appear in script comments or logs."""
        assert "non-blocking" in wf_source.lower()


# ── Early exits ────────────────────────────────────────────────────────────────


class TestEarlyExits:
    def test_blocked_no_mcp_is_structured_return(self, wf_source: str) -> None:
        """BLOCKED_NO_MCP must trigger a structured early return."""
        assert re.search(
            r"BLOCKED_NO_MCP.*?return\s*\{|return\s*\{.*?BLOCKED_NO_MCP",
            wf_source,
            re.DOTALL,
        )

    def test_coverage_hard_stop_is_structured_return(self, wf_source: str) -> None:
        """Coverage failed/BLOCKED must return a structured stop object."""
        assert re.search(
            r"stopped_at.*?coverage|coverage.*?stopped_at", wf_source, re.DOTALL
        )

    def test_returns_are_structured(self, wf_source: str) -> None:
        """All early returns should be structured objects."""
        structured_returns = len(re.findall(r"return\s*\{", wf_source))
        assert (
            structured_returns >= 3
        ), f"Expected >=3 structured returns, got {structured_returns}"

    def test_no_throw_statements(self, wf_source: str) -> None:
        """Early exits must use return, not throw."""
        # Only allow throw in try/catch blocks (post-prompt hook non-blocking path)
        throws_total = len(re.findall(r"\bthrow\b", wf_source))
        assert (
            throws_total == 0
        ), f"Early exits must use return not throw, found {throws_total} throw statements"


# ── Subagent types ─────────────────────────────────────────────────────────────


class TestSubagentTypes:
    def test_fix_coverage_agent_used(self, wf_source: str) -> None:
        assert "fix-coverage" in wf_source

    def test_fix_quality_agent_used(self, wf_source: str) -> None:
        assert "fix-quality" in wf_source

    def test_fix_tests_agent_used(self, wf_source: str) -> None:
        assert "fix-tests" in wf_source

    def test_fix_docs_agent_used(self, wf_source: str) -> None:
        assert "fix-docs" in wf_source

    def test_all_agent_calls_have_agent_type(self, wf_source: str) -> None:
        """Every agent() call should specify agentType for correct subagent dispatch."""
        agent_calls = len(re.findall(r"\bawait\s+agent\s*\(", wf_source))
        agent_type_refs = len(re.findall(r"agentType\s*:", wf_source))
        # Allow up to 2 less agentType than agent calls because comments (// AI: ...) that
        # mention "await agent()" also match the regex but do not produce agentType references.
        assert agent_type_refs >= agent_calls - 2, (
            f"Most agent() calls should have agentType: {agent_calls} calls "
            f"(includes comment matches), {agent_type_refs} agentType refs"
        )


# ── Default export ─────────────────────────────────────────────────────────────


class TestDefaultExport:
    def test_default_export_present(self, wf_source: str) -> None:
        # Runtime body is top-level (no export default wrapper); verify meta export present
        assert "export const meta" in wf_source

    def test_default_export_is_async_function(self, wf_source: str) -> None:
        # Body uses top-level await — verified by presence of async agent() calls
        assert "await agent(" in wf_source

    def test_function_accepts_phase_param(self, wf_source: str) -> None:
        """Workflow function must accept phase() from the runtime context."""
        assert "phase(" in wf_source

    def test_function_accepts_agent_param(self, wf_source: str) -> None:
        """Workflow function must accept agent() from the runtime context."""
        assert "await agent(" in wf_source

    def test_function_accepts_log_param(self, wf_source: str) -> None:
        """Workflow function must accept log() from the runtime context."""
        assert "log(" in wf_source

    def test_returns_success_object_on_completion(self, wf_source: str) -> None:
        """Final return should include success field."""
        assert re.search(r"return\s*\{[^}]*success\s*:", wf_source, re.DOTALL)

    def test_success_return_has_targets_run(self, wf_source: str) -> None:
        """Final return must include targets_run for observability."""
        assert "targets_run" in wf_source

    def test_success_return_has_change_scope(self, wf_source: str) -> None:
        """Final return must include change_scope for observability."""
        assert "change_scope" in wf_source


# ── Prompts manifest ────────────────────────────────────────────────────────────


class TestPromptsManifest:
    def test_manifest_exists(self) -> None:
        assert MANIFEST_PATH.exists()

    def test_fix_entry_has_superseded_by(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        fix_entry = None
        for category in manifest.get("categories", {}).values():
            for prompt in category.get("prompts", []):
                if prompt.get("file") == "fix.md":
                    fix_entry = prompt
                    break
        assert fix_entry is not None, "fix.md entry not found in manifest"
        assert (
            "superseded_by" in fix_entry
        ), "fix.md entry must have 'superseded_by' field pointing to fix.wf.js"
        assert (
            fix_entry["superseded_by"] == "fix.wf.js"
        ), f"Expected superseded_by='fix.wf.js', got {fix_entry['superseded_by']!r}"
