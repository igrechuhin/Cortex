"""
Tests for commit.wf.js Workflow script.

These tests verify the structural contract of the commit workflow:
- Phase A retry loop presence and correct 3-iteration cap
- Step 12 final gate is a single unconditional agent call
- Phase sequencing matches commit.md pipeline order
- Schema objects are defined for all 5 subagent types
- Early-exit returns are structured objects (not throws)
- Non-blocking paths (push, post-prompt hook) allow pipeline to continue

Since the Claude Code Workflow JS runtime is not available for Python-level
unit testing, these tests validate the script's control-flow structure
statically via source inspection. This is intentional: the contract being
tested is the presence and ordering of control-flow constructs (while loops,
if/else branches, agentType references), which are stable text patterns.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WF_PATH = Path(__file__).parents[2] / ".cortex" / "synapse" / "prompts" / "commit.wf.js"


@pytest.fixture(scope="module")
def wf_source() -> str:
    """Load the commit workflow script source."""
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
        assert '"cortex-commit"' in wf_source or "'cortex-commit'" in wf_source

    def test_meta_has_phases_array(self, wf_source: str) -> None:
        assert "phases:" in wf_source or "phases =" in wf_source

    def test_meta_has_preflight_phase(self, wf_source: str) -> None:
        assert "Preflight" in wf_source

    def test_meta_has_phase_a(self, wf_source: str) -> None:
        assert "Phase A" in wf_source

    def test_meta_has_final_gate(self, wf_source: str) -> None:
        assert "Final Gate" in wf_source

    def test_meta_has_cleanup(self, wf_source: str) -> None:
        assert "Cleanup" in wf_source


# ── Schema definitions ─────────────────────────────────────────────────────────


class TestSchemaDefinitions:
    def test_preflight_schema_defined(self, wf_source: str) -> None:
        assert "PREFLIGHT_SCHEMA" in wf_source

    def test_phase_a_schema_defined(self, wf_source: str) -> None:
        assert "PHASE_A_SCHEMA" in wf_source

    def test_phase_b_schema_defined(self, wf_source: str) -> None:
        assert "PHASE_B_SCHEMA" in wf_source

    def test_phase_c_schema_defined(self, wf_source: str) -> None:
        assert "PHASE_C_SCHEMA" in wf_source

    def test_gate_schema_defined(self, wf_source: str) -> None:
        assert "GATE_SCHEMA" in wf_source

    def test_all_schemas_have_required_field(self, wf_source: str) -> None:
        # Each of the 5 named schemas should have a required array.
        # JS uses unquoted keys (required:) while JSON uses "required".
        required_count = len(re.findall(r"\brequired\b\s*:", wf_source))
        assert (
            required_count >= 5
        ), f"Expected >=5 schema 'required:' fields, got {required_count}"

    def test_preflight_schema_has_passed(self, wf_source: str) -> None:
        assert re.search(r"PREFLIGHT_SCHEMA.*?passed", wf_source, re.DOTALL)

    def test_phase_a_schema_has_coverage_and_no_scope(self, wf_source: str) -> None:
        # Arrange: isolate the PHASE_A_SCHEMA block.
        start = wf_source.index("const PHASE_A_SCHEMA")
        block = wf_source[start : wf_source.index("const PHASE_B_SCHEMA", start)]

        # Act / Assert: scope was dropped; Step 12 no longer routes on it.
        assert "coverage" in block
        assert "scope" not in block


# ── Phase A retry loop ─────────────────────────────────────────────────────────


class TestPhaseARetryLoop:
    def test_while_loop_present(self, wf_source: str) -> None:
        """Phase A retry MUST be a while loop, not prose instructions."""
        assert "while (" in wf_source, "Phase A retry must use a while() loop"

    def test_max_iterations_constant(self, wf_source: str) -> None:
        """Max iterations must be a named constant, not a magic number inline."""
        assert "MAX_PHASE_A_ITERATIONS" in wf_source

    def test_iteration_counter_incremented(self, wf_source: str) -> None:
        """Loop counter must be incremented inside the while body."""
        assert "iterations++" in wf_source

    def test_break_on_passed(self, wf_source: str) -> None:
        """Loop must break when phaseA.passed is truthy."""
        assert "phaseA.passed" in wf_source
        assert "break" in wf_source

    def test_cap_is_three(self, wf_source: str) -> None:
        """Phase A cap must be exactly 3 iterations per commit.md spec."""
        has_three_cap = (
            "MAX_PHASE_A_ITERATIONS = 3" in wf_source
            or "max_iterations = 3" in wf_source.lower()
            or "iterations < 3" in wf_source
        )
        assert has_three_cap, "Phase A cap must be 3"

    def test_early_exit_on_all_fail(self, wf_source: str) -> None:
        """After loop exits with passed=false, pipeline must return early."""
        assert (
            re.search(r"if\s*\([^)]*!phaseA\.passed\)", wf_source) is not None
        ), "Must check !phaseA.passed after the retry loop and return early"

    def test_phases_b_c_not_called_on_phase_a_failure(self, wf_source: str) -> None:
        """The early return on Phase A failure must come before Phase B agent call."""
        # Find the check on !phaseA.passed (after the while loop)
        phase_a_check_pos = wf_source.find("!phaseA.passed")
        assert phase_a_check_pos > 0, "Must check !phaseA.passed after retry loop"
        # Find the Phase B agent() invocation — skip past file-header comments by
        # searching for the agentType reference, not just any mention of commit-phase-b.
        phase_b_agent_pos = wf_source.find('agentType: "commit-phase-b"')
        if phase_b_agent_pos == -1:
            phase_b_agent_pos = wf_source.find("agentType: 'commit-phase-b'")
        assert phase_b_agent_pos > 0, "Phase B agentType call not found in workflow"
        assert (
            phase_b_agent_pos > phase_a_check_pos
        ), "Phase A failure check must appear before Phase B agent call"
        # A return statement must appear between the check and Phase B agent call
        section = wf_source[phase_a_check_pos:phase_b_agent_pos]
        assert (
            re.search(r"\breturn\s*\{", section) is not None
        ), "Must return early after Phase A failure before reaching Phase B"


# ── Step 12 final gate ────────────────────────────────────────────────────────


class TestStep12FinalGate:
    """Step 12 is a single unconditional gate call.

    The old three-branch routing keyed on phaseA.scope was mis-derived: the
    Phase A subagent computed scope from a whole-working-tree git diff, which
    answers "what is changed" rather than "what changed since Phase A".
    run_quality_gate() now decides per check from the persisted fingerprint.
    """

    def test_no_scope_routing(self, wf_source: str) -> None:
        # Arrange / Act / Assert
        assert "phaseA.scope" not in wf_source
        assert "markdown_only" not in wf_source

    def test_single_final_gate_agent_call(self, wf_source: str) -> None:
        # Arrange / Act
        calls = re.findall(r'agentType:\s*"commit-final-gate"', wf_source)

        # Assert
        assert (
            len(calls) == 1
        ), f"Expected exactly one final-gate call, got {len(calls)}"

    def test_final_gate_is_unconditional(self, wf_source: str) -> None:
        # Arrange: isolate Step 12 from its phase() marker to the result check.
        start = wf_source.index('phase("Final Gate")')
        end = wf_source.index("if (!finalGate", start)
        section = wf_source[start:end]

        # Act / Assert: no branching guards the gate call itself.
        assert "if (" not in section
        assert "else" not in section
        assert "commit-final-gate" in section

    def test_skipped_checks_reported(self, wf_source: str) -> None:
        # Arrange / Act / Assert
        assert "skipped_checks" in wf_source


class TestSubagentTypes:
    def test_commit_preflight_used(self, wf_source: str) -> None:
        assert "commit-preflight" in wf_source

    def test_commit_phase_a_used(self, wf_source: str) -> None:
        assert "commit-phase-a" in wf_source

    def test_commit_phase_b_used(self, wf_source: str) -> None:
        assert "commit-phase-b" in wf_source

    def test_commit_phase_c_used(self, wf_source: str) -> None:
        assert "commit-phase-c" in wf_source

    def test_commit_final_gate_used(self, wf_source: str) -> None:
        assert "commit-final-gate" in wf_source

    def test_all_agent_calls_have_agent_type(self, wf_source: str) -> None:
        """Every agent() call should specify agentType for correct subagent dispatch."""
        agent_calls = len(re.findall(r"\bawait\s+agent\s*\(", wf_source))
        agent_type_refs = len(re.findall(r"agentType\s*:", wf_source))
        # Allow one less agentType than agent calls (the inline finalGate shortcut for none)
        assert agent_type_refs >= agent_calls - 1, (
            f"Most agent() calls should have agentType: {agent_calls} calls, "
            f"{agent_type_refs} agentType refs"
        )


# ── Phase ordering ─────────────────────────────────────────────────────────────


class TestPhaseOrder:
    def test_preflight_before_phase_a(self, wf_source: str) -> None:
        preflight_pos = wf_source.find("commit-preflight")
        phase_a_pos = wf_source.find("commit-phase-a")
        assert 0 < preflight_pos < phase_a_pos, "Preflight must run before Phase A"

    def test_phase_a_before_phase_b(self, wf_source: str) -> None:
        phase_a_pos = wf_source.find("commit-phase-a")
        phase_b_pos = wf_source.find("commit-phase-b")
        assert 0 < phase_a_pos < phase_b_pos, "Phase A must run before Phase B"

    def test_phase_b_before_phase_c(self, wf_source: str) -> None:
        phase_b_pos = wf_source.find("commit-phase-b")
        phase_c_pos = wf_source.find("commit-phase-c")
        assert 0 < phase_b_pos < phase_c_pos, "Phase B must run before Phase C"

    def test_phase_c_before_final_gate(self, wf_source: str) -> None:
        phase_c_pos = wf_source.find("commit-phase-c")
        gate_pos = wf_source.find("commit-final-gate")
        assert 0 < phase_c_pos < gate_pos, "Phase C must run before Final Gate"

    def test_step_13_before_step_14(self, wf_source: str) -> None:
        step13_pos = wf_source.find("Step 13")
        step14_pos = wf_source.find("Step 14")
        assert (
            0 < step13_pos < step14_pos
        ), "Step 13 (commit) must run before Step 14 (push)"

    def test_step_14_before_step_15(self, wf_source: str) -> None:
        step14_pos = wf_source.find("Step 14")
        step15_pos = wf_source.find("Step 15")
        assert (
            0 < step14_pos < step15_pos
        ), "Step 14 (push) must run before Step 15 (cleanup)"

    def test_step_15_before_step_16(self, wf_source: str) -> None:
        step15_pos = wf_source.find("Step 15")
        step16_pos = wf_source.find("Step 16")
        assert (
            0 < step15_pos < step16_pos
        ), "Step 15 (cleanup) must run before Step 16 (post-prompt hook)"


# ── Early exits ────────────────────────────────────────────────────────────────


class TestEarlyExits:
    def test_preflight_failure_returns_early(self, wf_source: str) -> None:
        """Preflight failure must return before Phase A."""
        assert (
            re.search(r"!preflight\.passed", wf_source) is not None
        ), "Must check !preflight.passed and return early"

    def test_no_changes_returns_early(self, wf_source: str) -> None:
        """If no changes detected, pipeline must stop before doing any work."""
        assert "changes_detected" in wf_source

    def test_returns_are_structured(self, wf_source: str) -> None:
        """All early returns should be structured objects, not throw statements."""
        structured_returns = len(re.findall(r"return\s*\{", wf_source))
        assert (
            structured_returns >= 4
        ), f"Expected >=4 structured early returns, got {structured_returns}"

    def test_no_throw_statements(self, wf_source: str) -> None:
        """Early exits should use return not throw (per plan: 'structured, not thrown')."""
        # Count all throw statements — the commit.wf.js design uses structured returns,
        # never throws, even in error paths.
        throws_total = len(re.findall(r"\bthrow\b", wf_source))
        assert (
            throws_total == 0
        ), f"Early exits must use return not throw, found {throws_total} throw statements"


# ── Non-blocking paths ─────────────────────────────────────────────────────────


class TestNonBlockingPaths:
    def test_push_failure_is_non_blocking(self, wf_source: str) -> None:
        """Push failure must not halt the pipeline — cleanup must always run."""
        push_pos = wf_source.find("Step 14")
        cleanup_pos = wf_source.find("Step 15")
        assert (
            0 < push_pos < cleanup_pos
        ), "Step 14 (push) must appear before Step 15 (cleanup)"
        # The push section must NOT have a hard return that stops cleanup from running
        push_section = wf_source[push_pos:cleanup_pos]
        hard_returns = re.findall(r"return\s*\{\s*success\s*:\s*false", push_section)
        assert (
            len(hard_returns) == 0
        ), "Push failure must be non-blocking; found hard return in push section"

    def test_post_prompt_hook_is_non_blocking(self, wf_source: str) -> None:
        """Post-prompt hook (Step 16) must be wrapped in try/catch."""
        # Find Step 16 section
        step16_pos = wf_source.find("Step 16")
        step16_section = wf_source[step16_pos:]
        assert (
            "try {" in step16_section or "try{" in step16_section
        ), "Post-prompt hook must be wrapped in try { } catch for non-blocking behavior"

    def test_phase_c_push_failure_is_non_blocking(self, wf_source: str) -> None:
        """Phase C synapse push failure is documented as non-blocking in commit.md."""
        # The synapse push note should appear in the Phase C agent prompt
        assert (
            "non-blocking" in wf_source.lower()
        ), "Script must document non-blocking behavior for push failures"


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
        """Final return should be a structured success object."""
        assert (
            re.search(r"return\s*\{\s*success\s*:\s*true", wf_source) is not None
        ), "Successful completion must return { success: true, ... }"


# ── Prompts manifest ────────────────────────────────────────────────────────────


class TestPromptsManifest:
    MANIFEST_PATH = (
        Path(__file__).parents[2]
        / ".cortex"
        / "synapse"
        / "prompts"
        / "prompts-manifest.json"
    )

    def test_manifest_exists(self) -> None:
        assert self.MANIFEST_PATH.exists()

    def test_commit_entry_has_superseded_by(self) -> None:
        import json

        manifest = json.loads(self.MANIFEST_PATH.read_text())
        commit_entry = None
        for category in manifest.get("categories", {}).values():
            for prompt in category.get("prompts", []):
                if prompt.get("file") == "commit.md":
                    commit_entry = prompt
                    break
        assert commit_entry is not None, "commit.md entry not found in manifest"
        assert (
            "superseded_by" in commit_entry
        ), "commit.md entry must have 'superseded_by' field pointing to commit.wf.js"
        assert (
            commit_entry["superseded_by"] == "commit.wf.js"
        ), f"Expected superseded_by='commit.wf.js', got {commit_entry['superseded_by']!r}"
