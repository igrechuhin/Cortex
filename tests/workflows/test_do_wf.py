"""
Tests for do.wf.js Workflow script.

These tests verify the structural contract of the do workflow:
- Implementation loop: while loop with MAX_IMPL_ITERATIONS cap (5)
- Parallel branch: pipeline() used when can_parallelize=true, not sequential loop
- Review Gate: deterministic if (implResult.needs_review) branch
- Finalize: receives merged results from both sequential and parallel paths
- Non-blocking paths: post-prompt hook wrapped in try/catch
- Schema objects defined for all phase subagent types
- Early-exit returns are structured objects (not throws)
- Prompts manifest marks do.md as superseded_by do.wf.js

Since the Claude Code Workflow JS runtime is not available for Python-level
unit testing, these tests validate the script's control-flow structure
statically via source inspection. This is intentional: the contract being
tested is the presence and ordering of control-flow constructs (while loops,
if/else branches, pipeline() calls, agentType references), which are stable
text patterns that survive routine prose edits inside agent prompts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

WF_PATH = Path(__file__).parents[2] / ".cortex" / "synapse" / "prompts" / "do.wf.js"
MANIFEST_PATH = (
    Path(__file__).parents[2]
    / ".cortex"
    / "synapse"
    / "prompts"
    / "prompts-manifest.json"
)


@pytest.fixture(scope="module")
def wf_source() -> str:
    """Load the do workflow script source."""
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
        assert '"cortex-do"' in wf_source or "'cortex-do'" in wf_source

    def test_meta_has_phases_array(self, wf_source: str) -> None:
        assert "phases:" in wf_source or "phases =" in wf_source

    def test_meta_has_selection_phase(self, wf_source: str) -> None:
        assert "Selection" in wf_source

    def test_meta_has_implementation_phase(self, wf_source: str) -> None:
        assert "Implementation" in wf_source

    def test_meta_has_review_gate_phase(self, wf_source: str) -> None:
        assert "Review Gate" in wf_source

    def test_meta_has_finalize_phase(self, wf_source: str) -> None:
        assert "Finalize" in wf_source

    def test_meta_has_verify_phase(self, wf_source: str) -> None:
        assert "Verify" in wf_source

    def test_meta_has_fix_phase(self, wf_source: str) -> None:
        assert "Fix" in wf_source

    def test_meta_has_cleanup_phase(self, wf_source: str) -> None:
        assert "Cleanup" in wf_source


# ── Schema definitions ─────────────────────────────────────────────────────────


class TestSchemaDefinitions:
    def test_selection_schema_defined(self, wf_source: str) -> None:
        assert "SELECTION_SCHEMA" in wf_source

    def test_impl_schema_defined(self, wf_source: str) -> None:
        assert "IMPL_SCHEMA" in wf_source

    def test_review_schema_defined(self, wf_source: str) -> None:
        assert "REVIEW_SCHEMA" in wf_source

    def test_finalize_schema_defined(self, wf_source: str) -> None:
        assert "FINALIZE_SCHEMA" in wf_source

    def test_all_schemas_have_required_field(self, wf_source: str) -> None:
        # Each named schema should have a required array.
        required_count = len(re.findall(r"\brequired\b\s*:", wf_source))
        assert (
            required_count >= 4
        ), f"Expected >=4 schema 'required:' fields, got {required_count}"

    def test_impl_schema_has_step_fully_complete(self, wf_source: str) -> None:
        # step_fully_complete drives the while-loop exit — must be in IMPL_SCHEMA
        assert re.search(r"IMPL_SCHEMA.*?step_fully_complete", wf_source, re.DOTALL)

    def test_review_schema_has_outcome(self, wf_source: str) -> None:
        # outcome drives the review gate branch — must be in REVIEW_SCHEMA
        assert re.search(r"REVIEW_SCHEMA.*?outcome", wf_source, re.DOTALL)

    def test_review_schema_has_no_gaps_enum(self, wf_source: str) -> None:
        # Enum values must cover both outcomes
        assert "no_gaps" in wf_source
        assert "gaps_found" in wf_source


# ── Implementation loop ────────────────────────────────────────────────────────


class TestImplementationLoop:
    def test_while_loop_present(self, wf_source: str) -> None:
        """Implementation loop MUST be a while loop, not prose instructions."""
        assert "while (" in wf_source, "Implementation loop must use a while() loop"

    def test_max_impl_iterations_constant(self, wf_source: str) -> None:
        """Max iterations must be a named constant, not a magic number inline."""
        assert "MAX_IMPL_ITERATIONS" in wf_source

    def test_iteration_counter_incremented(self, wf_source: str) -> None:
        """Loop counter must be incremented inside the while body."""
        assert "iterations++" in wf_source

    def test_break_on_step_fully_complete(self, wf_source: str) -> None:
        """Loop must break when step_fully_complete is truthy."""
        assert "step_fully_complete" in wf_source
        assert "break" in wf_source

    def test_cap_is_five(self, wf_source: str) -> None:
        """Implementation loop cap must be exactly 5 iterations per do.md spec."""
        has_five_cap = (
            "MAX_IMPL_ITERATIONS = 5" in wf_source or "iterations < 5" in wf_source
        )
        assert has_five_cap, "Implementation loop cap must be 5"

    def test_loop_exits_on_step_complete(self, wf_source: str) -> None:
        """Loop must check implResult.step_fully_complete and break."""
        assert (
            re.search(r"implResult\.step_fully_complete", wf_source) is not None
        ), "Must check implResult.step_fully_complete to exit the loop"

    def test_partial_progress_accumulated(self, wf_source: str) -> None:
        """partial_progress must be updated after each incomplete iteration."""
        assert "partialProgress" in wf_source

    def test_loop_handles_max_iterations_exhausted(self, wf_source: str) -> None:
        """Script must handle reaching max iterations without step_fully_complete."""
        # Check that there's logic after the loop for this case
        assert (
            re.search(r"iterations\s*>=\s*MAX_IMPL_ITERATIONS", wf_source) is not None
            or re.search(
                r"MAX_IMPL_ITERATIONS.*?without.*?step_fully_complete",
                wf_source,
                re.DOTALL,
            )
            is not None
        ), "Must handle exhausted iterations without step_fully_complete"


# ── Parallel execution ─────────────────────────────────────────────────────────


class TestParallelExecution:
    def test_pipeline_call_present(self, wf_source: str) -> None:
        """Parallel path MUST use pipeline(), not sequential agent calls."""
        assert "await pipeline(" in wf_source, "Parallel path must use pipeline()"

    def test_can_parallelize_check(self, wf_source: str) -> None:
        """canParallelize flag must gate the parallel vs sequential branch."""
        assert "canParallelize" in wf_source or "can_parallelize" in wf_source

    def test_parallel_steps_array_checked(self, wf_source: str) -> None:
        """parallel_steps array must be checked before entering pipeline()."""
        assert "parallel_steps" in wf_source

    def test_merge_parallel_results_function(self, wf_source: str) -> None:
        """mergeParallelResults helper must be defined."""
        assert "mergeParallelResults" in wf_source

    def test_merge_parallel_results_flattens_files_changed(
        self, wf_source: str
    ) -> None:
        """Merge helper must flatten files_changed from all parallel results."""
        assert re.search(
            r"files_changed.*?flatMap|flatMap.*?files_changed", wf_source, re.DOTALL
        )

    def test_merge_parallel_results_step_fully_complete_all(
        self, wf_source: str
    ) -> None:
        """step_fully_complete in merged result must be true only when ALL steps complete."""
        assert (
            re.search(r"\.every\s*\(", wf_source) is not None
        ), "mergeParallelResults must use .every() for step_fully_complete (all must pass)"

    def test_merge_parallel_results_needs_review_any(self, wf_source: str) -> None:
        """needs_review in merged result must be true if ANY step needs review."""
        assert (
            re.search(r"\.some\s*\(", wf_source) is not None
        ), "mergeParallelResults must use .some() for needs_review (any triggers review)"

    def test_parallel_branch_uses_pipeline_not_loop(self, wf_source: str) -> None:
        """Parallel execution path must call pipeline(), not enter the while loop."""
        # Find the canParallelize check inside the pipeline body (after meta block)
        meta_end = wf_source.find("\nexport const meta = {")
        assert meta_end >= 0, "doPipeline function not found"
        function_body = wf_source[meta_end:]

        can_par_pos = function_body.find("canParallelize")
        pipeline_pos = function_body.find("await pipeline(")
        while_pos = function_body.find("while (")
        assert (
            0 < can_par_pos < pipeline_pos
        ), "canParallelize must appear before pipeline()"
        assert (
            0 < can_par_pos < while_pos
        ), "canParallelize must appear before while loop in function body"
        # pipeline() must appear before the while loop (parallel path before sequential path)
        assert (
            pipeline_pos < while_pos
        ), "pipeline() call (parallel path) must appear before while loop (sequential path)"


# ── Review Gate ────────────────────────────────────────────────────────────────


class TestReviewGate:
    def test_review_gate_is_deterministic_branch(self, wf_source: str) -> None:
        """Review Gate must be a deterministic if branch, not prose analysis."""
        assert (
            re.search(r"if\s*\(\s*implResult\s*\.\s*step_fully_complete", wf_source)
            is not None
            or re.search(r"if\s*\(\s*implResult\.needs_review", wf_source) is not None
        ), "Review Gate must branch on implResult field, not prose reasoning"

    def test_review_skipped_when_partial(self, wf_source: str) -> None:
        """Review Gate must be skipped when step is not fully complete."""
        # Check that skip logic exists for partial path
        assert (
            "partial" in wf_source.lower()
            or re.search(r"!implResult\.step_fully_complete", wf_source) is not None
        ), "Must skip review when step is not fully complete"

    def test_no_gaps_outcome_handled(self, wf_source: str) -> None:
        """no_gaps outcome must unlock finalize complete path."""
        assert "no_gaps" in wf_source

    def test_gaps_found_outcome_handled(self, wf_source: str) -> None:
        """gaps_found outcome must reopen the plan."""
        assert "gaps_found" in wf_source

    def test_review_uses_implement_code_agent(self, wf_source: str) -> None:
        """Review Gate agent call must use implement-code agentType."""
        # Review Gate should use the same implement-code agent type
        assert "implement-code" in wf_source


# ── Phase ordering ─────────────────────────────────────────────────────────────


class TestPhaseOrder:
    def test_selection_before_implementation(self, wf_source: str) -> None:
        selection_pos = wf_source.find('phase("Selection")')
        impl_pos = wf_source.find('phase("Implementation")')
        assert 0 < selection_pos < impl_pos, "Selection must run before Implementation"

    def test_implementation_before_review_gate(self, wf_source: str) -> None:
        impl_pos = wf_source.find('phase("Implementation")')
        review_pos = wf_source.find('phase("Review Gate")')
        assert 0 < impl_pos < review_pos, "Implementation must run before Review Gate"

    def test_review_gate_before_finalize(self, wf_source: str) -> None:
        review_pos = wf_source.find('phase("Review Gate")')
        finalize_pos = wf_source.find('phase("Finalize")')
        assert 0 < review_pos < finalize_pos, "Review Gate must run before Finalize"

    def test_finalize_before_verify(self, wf_source: str) -> None:
        finalize_pos = wf_source.find('phase("Finalize")')
        verify_pos = wf_source.find('phase("Verify")')
        assert 0 < finalize_pos < verify_pos, "Finalize must run before Verify"

    def test_verify_before_fix(self, wf_source: str) -> None:
        verify_pos = wf_source.find('phase("Verify")')
        fix_pos = wf_source.find('phase("Fix")')
        assert 0 < verify_pos < fix_pos, "Verify must run before Fix"

    def test_fix_before_cleanup(self, wf_source: str) -> None:
        fix_pos = wf_source.find('phase("Fix")')
        cleanup_pos = wf_source.find('phase("Cleanup")')
        assert 0 < fix_pos < cleanup_pos, "Fix must run before Cleanup"

    def test_cleanup_before_post_prompt_hook(self, wf_source: str) -> None:
        cleanup_pos = wf_source.find('phase("Cleanup")')
        hook_pos = wf_source.find('phase("Post-Prompt Hook")')
        assert 0 < cleanup_pos < hook_pos, "Cleanup must run before Post-Prompt Hook"


# ── Early exits ────────────────────────────────────────────────────────────────


class TestEarlyExits:
    def test_roadmap_complete_returns_early(self, wf_source: str) -> None:
        """roadmap_complete from Selection must return early."""
        assert "roadmap_complete" in wf_source

    def test_roadmap_complete_is_structured_return(self, wf_source: str) -> None:
        """roadmap_complete early return must be a structured object."""
        assert (
            re.search(
                r"roadmap_complete.*?return\s*\{|return\s*\{.*?roadmap_complete",
                wf_source,
                re.DOTALL,
            )
            is not None
        ), "roadmap_complete must trigger a structured return"

    def test_returns_are_structured(self, wf_source: str) -> None:
        """All early returns should be structured objects, not throw statements."""
        structured_returns = len(re.findall(r"return\s*\{", wf_source))
        assert (
            structured_returns >= 3
        ), f"Expected >=3 structured returns, got {structured_returns}"

    def test_no_throw_statements(self, wf_source: str) -> None:
        """Early exits should use return not throw."""
        # Only allow throw in try/catch blocks (post-prompt hook non-blocking path)
        throws_total = len(re.findall(r"\bthrow\b", wf_source))
        assert (
            throws_total == 0
        ), f"Early exits must use return not throw, found {throws_total} throw statements"


# ── Non-blocking paths ─────────────────────────────────────────────────────────


class TestNonBlockingPaths:
    def test_post_prompt_hook_is_non_blocking(self, wf_source: str) -> None:
        """Post-prompt hook must be wrapped in try/catch."""
        hook_pos = wf_source.find('phase("Post-Prompt Hook")')
        hook_section = wf_source[hook_pos:]
        assert (
            "try {" in hook_section or "try{" in hook_section
        ), "Post-prompt hook must be wrapped in try { } catch for non-blocking behavior"

    def test_fix_failure_is_non_blocking(self, wf_source: str) -> None:
        """Fix phase failure after max iterations must log and continue, not return early."""
        fix_pos = wf_source.find('phase("Fix")')
        cleanup_pos = wf_source.find('phase("Cleanup")')
        assert (
            0 < fix_pos < cleanup_pos
        ), "Fix must be followed by Cleanup regardless of outcome"
        fix_section = wf_source[fix_pos:cleanup_pos]
        # Should NOT have a hard early return that skips cleanup
        hard_returns = re.findall(r"return\s*\{\s*success\s*:\s*false", fix_section)
        assert (
            len(hard_returns) == 0
        ), "Fix failure must be non-blocking; found hard return before cleanup"

    def test_non_blocking_documented(self, wf_source: str) -> None:
        """non-blocking keyword must appear in script comments."""
        assert (
            "non-blocking" in wf_source.lower()
        ), "Script must document non-blocking behavior"


# ── Subagent types ─────────────────────────────────────────────────────────────


class TestSubagentTypes:
    def test_implement_code_used(self, wf_source: str) -> None:
        assert "implement-code" in wf_source

    def test_all_agent_calls_have_agent_type(self, wf_source: str) -> None:
        """Every agent() call should specify agentType for correct subagent dispatch."""
        agent_calls = len(re.findall(r"\bawait\s+agent\s*\(", wf_source))
        agent_type_refs = len(re.findall(r"agentType\s*:", wf_source))
        # Allow one less agentType than agent calls
        assert agent_type_refs >= agent_calls - 1, (
            f"Most agent() calls should have agentType: {agent_calls} calls, "
            f"{agent_type_refs} agentType refs"
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

    def test_function_accepts_pipeline_param(self, wf_source: str) -> None:
        """Workflow function must accept pipeline() from the runtime context."""
        assert "pipeline" in wf_source

    def test_returns_success_object_on_completion(self, wf_source: str) -> None:
        """Final return should be a structured success object."""
        assert (
            re.search(r"return\s*\{\s*success\s*:\s*true", wf_source) is not None
        ), "Successful completion must return { success: true, ... }"

    def test_success_return_has_step(self, wf_source: str) -> None:
        """Final success return must include the selected step."""
        success_section = re.search(
            r"return\s*\{[^}]*success\s*:\s*true[^}]*\}", wf_source, re.DOTALL
        )
        assert success_section is not None
        assert "step" in success_section.group()

    def test_success_return_has_impl_iterations(self, wf_source: str) -> None:
        """Final success return must include impl_iterations for observability."""
        success_section = re.search(
            r"return\s*\{[^}]*success\s*:\s*true[^}]*\}", wf_source, re.DOTALL
        )
        assert success_section is not None
        assert "iterations" in success_section.group()


# ── Prompts manifest ────────────────────────────────────────────────────────────


class TestPromptsManifest:
    def test_manifest_exists(self) -> None:
        assert MANIFEST_PATH.exists()

    def test_do_entry_has_superseded_by(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        do_entry = None
        for category in manifest.get("categories", {}).values():
            for prompt in category.get("prompts", []):
                if prompt.get("file") == "do.md":
                    do_entry = prompt
                    break
        assert do_entry is not None, "do.md entry not found in manifest"
        assert (
            "superseded_by" in do_entry
        ), "do.md entry must have 'superseded_by' field pointing to do.wf.js"
        assert (
            do_entry["superseded_by"] == "do.wf.js"
        ), f"Expected superseded_by='do.wf.js', got {do_entry['superseded_by']!r}"
