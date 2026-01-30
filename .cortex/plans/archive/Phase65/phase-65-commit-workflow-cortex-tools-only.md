# Phase 65: Commit Workflow — Cortex Tools Only (No Direct Script Invocations)

## Status

- **Status**: Completed
- **Priority**: High
- **Created**: 2026-01-30
- **Completed**: 2026-01-30

## Goal

Remove all direct Python (or language-specific) script invocations from the commit prompt. All pre-commit and Step 12 validation operations must be invoked via Cortex MCP tools. Tools must resolve `{language}` (prompt stays language-agnostic; the tool performs language detection or accepts an optional language parameter).

## Context

### Current Problem

The commit prompt (`.cortex/synapse/prompts/commit.md`) instructs agents to run scripts directly, for example:

- `.venv/bin/python .cortex/synapse/scripts/{language}/run_tests.py` (fallback)
- `.venv/bin/python .cortex/synapse/scripts/{language}/check_linting.py` (fallback)
- `.venv/bin/python .cortex/synapse/scripts/{language}/fix_formatting.py`
- `.venv/bin/python .cortex/synapse/scripts/{language}/check_formatting.py`
- `.venv/bin/python .cortex/synapse/scripts/{language}/check_formatting_ci_parity.py`
- `.venv/bin/python .cortex/synapse/scripts/python/check_types.py` (and other Python-hardcoded paths)
- `.venv/bin/python .cortex/synapse/scripts/{language}/check_linting.py`
- `.venv/bin/python .cortex/synapse/scripts/{language}/check_test_naming.py`
- `.venv/bin/python .cortex/synapse/scripts/{language}/run_tests.py`
- `.venv/bin/python .cortex/synapse/scripts/{language}/check_file_sizes.py`
- `.venv/bin/python .cortex/synapse/scripts/{language}/check_function_lengths.py`

Additional references appear in checklist and summary sections (e.g. lines 818, 820, 846, 1161–1163, 1167, 1169–1171) that mention these script paths explicitly.

### User Requirement

- **No direct script invocations**: The commit prompt must not instruct agents to call Python (or other) scripts directly.
- **Cortex tools only**: All such operations must be performed via Cortex MCP tools.
- **Language resolution by tools**: The tools must resolve `{language}` (i.e. accept optional `language` and/or auto-detect); the prompt remains language-agnostic.

### Existing Tooling

- `execute_pre_commit_checks(checks=[...], language=None, ...)` already supports: `fix_errors`, `format`, `type_check`, `quality`, `tests`. It uses adapters (e.g. PythonAdapter) and accepts optional `language` (auto-detect if omitted).
- `fix_quality_issues(project_root=None)` runs fix_errors, format, type_check, and markdown lint (no tests).
- Step 12 in the prompt currently bypasses these tools and runs synapse scripts directly to match CI scope (e.g. scripts that check both `src/` and `tests/`).

### Affected Prompt Locations (from user selections)

- Line 189: run_tests fallback script
- Line 243: check_linting fallback script
- Lines 603–606: fix_formatting.py
- Lines 611–614: check_formatting.py
- Lines 628–631: check_formatting_ci_parity.py
- Lines 642–645: check_types.py (Python path)
- Lines 670–673: check_linting.py
- Lines 694–697: check_test_naming.py
- Lines 724–727: run_tests.py
- Lines 741–744: check_file_sizes.py
- Lines 756–759: check_function_lengths.py
- Line 818: Step 12.1.3 checklist (CI parity script)
- Line 820: Type check re-run command
- Line 846: Type check command evidence
- Lines 1161–1163, 1167, 1169–1171: Output format / verification (script paths)

## Approach

1. **Extend or add Cortex tool(s)** so that every operation currently invoked via a script in the commit workflow can be invoked via a tool that:
   - Accepts an optional `language` (or relies on existing auto-detect).
   - Internally runs the appropriate synapse script or adapter logic (scripts remain implementation detail).
2. **Update the commit prompt** so that:
   - Every reference to running a script is replaced by a reference to the corresponding Cortex tool and parameters.
   - All checklist and summary items refer to tool calls and results, not script paths.
   - Wording is language-agnostic; `{language}` is not used in the prompt for paths—only tool names and parameters.
3. **Ensure consistency** in other prompts or docs that reference the same scripts in the commit context.

## Implementation Steps

### Step 1: Define Tool Coverage for Step 12 and Fallbacks

- Map each script currently referenced in commit.md to a tool (existing or new):
  - **fix_formatting** → e.g. `execute_pre_commit_checks(checks=["format"])` or a dedicated step tool.
  - **check_formatting** → same tool with a “check-only” mode or separate check type if needed.
  - **check_formatting_ci_parity** → extend tooling to support a “format_ci_parity” check or equivalent.
  - **check_types** → `execute_pre_commit_checks(checks=["type_check"])` (ensure it covers `src/` and `tests/` like the script).
  - **check_linting** → covered by `quality` today; confirm scope matches script; expose as a distinct check if needed for Step 12.
  - **check_test_naming** → add support (new check type or new tool) so it can be invoked via tool.
  - **run_tests** → `execute_pre_commit_checks(checks=["tests"], ...)`.
  - **check_file_sizes** / **check_function_lengths** → already part of `quality`; confirm and, if needed, expose as separate checks for Step 12 granularity.
- Decide whether to extend `execute_pre_commit_checks` with additional check types (e.g. `format_ci_parity`, `test_naming`, `file_sizes_only`, `function_lengths_only`) or introduce a single “run_validation_step” tool that takes a step identifier and optional `language`. Document the decision and keep scripts as internal implementation.

### Step 2: Implement Tool Changes

- Implement the chosen design (extended `execute_pre_commit_checks` and/or new tool) so that:
  - All Step 12 operations and fallbacks are invokable via tools.
  - `language` is optional and resolved by the tool (auto-detect or parameter).
  - Behavior and scope (e.g. directories checked) match or exceed current script behavior (e.g. `src/` + `tests/` where applicable).
- Add or update docstrings and tool descriptors (e.g. USE WHEN, EXAMPLES) so the commit workflow can reference them unambiguously.

### Step 3: Update Commit Prompt (commit.md)

- Replace every direct script invocation with the corresponding Cortex tool call:
  - Steps 12.0 (markdown): keep or align with existing `fix_markdown_lint` MCP tool.
  - Steps 12.1.1–12.1.3 (format fix, format check, CI parity): use tool(s) only; remove script paths.
  - Step 12.2 (type check): use tool only; remove `.venv/bin/python .../check_types.py` and any Python-hardcoded path.
  - Step 12.3 (lint): use tool only.
  - Step 12.4 (test naming): use tool only.
  - Step 12.5.1/12.5.2 (file sizes, function lengths): use tool only.
  - Step 12.6 (markdown): use tool only.
  - Fallbacks (e.g. run_tests, check_linting): refer to tools only.
- Update all checklist and summary sections so they reference “Tool X with parameters Y” and “output/results of tool X” instead of script paths (e.g. lines 818, 820, 846, 1161–1163, 1167, 1169–1171).
- Remove any remaining `.venv/bin/python .cortex/synapse/scripts/...` or language-hardcoded script paths from the prompt. Ensure the prompt never instructs “run this script”; only “call this tool”.

### Step 4: Align CRITICAL RULE and Re-run Instructions

- Update “CRITICAL RULE (Step 12)” and “re-run after fixes” bullets so they refer to re-running the relevant **Cortex tool(s)** (e.g. format tool, then format check tool, then CI parity tool), not script names.
- Keep semantics: after any code change during Step 12, re-run formatting (fix + check + CI parity) and other checks via tools before proceeding.

### Step 5: Documentation and Consistency

- Update any other Synapse prompts or docs that reference running commit-related scripts directly so they use Cortex tools instead.
- Ensure `execute_pre_commit_checks` (and any new tool) is documented as the canonical way to run these checks; scripts are an implementation detail.

### Step 6: Testing

- **Unit tests**: Add or update tests for new or changed tool behavior (e.g. new check types or new tool), including language resolution and scope (e.g. `src/` + `tests/`).
- **Integration tests**: Add or extend a test that verifies the commit workflow can be followed using only MCP tools (no direct script invocations), e.g. by parsing commit.md and asserting it contains no script paths for these operations (or by running a minimal “dry” commit flow via tools only).
- **Regression**: Ensure existing tests for `execute_pre_commit_checks` and related tools still pass.

## Dependencies

- Existing `execute_pre_commit_checks` and adapters (PythonAdapter, TypeScriptAdapter, StubAdapter).
- Synapse scripts in `.cortex/synapse/scripts/{language}/` remain the implementation detail behind the tools; no requirement to remove them.

## Success Criteria

- No instructions in commit.md tell the agent to run `.venv/bin/python .cortex/synapse/scripts/...` or any direct script command for pre-commit or Step 12 checks.
- Every such operation is invokable via one or more Cortex MCP tools with optional `language` (or auto-detect).
- Checklist and summary sections in commit.md refer only to tool names and results, not script paths.
- Commit workflow remains language-agnostic at the prompt level; tools resolve language.
- All new or modified tool behavior is covered by tests; integration test confirms tool-only commit flow.

## Testing Strategy

- **Coverage target**: Minimum 95% for new or modified tool code.
- **Unit tests**: Tool handlers and any new check types (e.g. format_ci_parity, test_naming); language resolution; scope (directories) matching scripts.
- **Integration tests**: Commit workflow using only MCP tools (no script invocations); optional: automated check that commit.md contains no script paths for these operations.
- **AAA pattern**: All tests follow Arrange–Act–Assert.
- **No blanket skips**: Any skip must be justified and linked to a ticket.

## Risks and Mitigation

- **Scope mismatch**: Tools might check different directories than scripts. Mitigation: implement tool logic to call the same scripts or duplicate their scope (e.g. `src/` + `tests/`) and add tests that assert scope parity.
- **Prompt length**: Replacing script blocks with tool descriptions may lengthen the prompt. Mitigation: keep tool references concise (tool name + key parameters); move long examples to a separate section or doc.

## Timeline

- Steps 1–2: Design and tool implementation (estimate: 1–2 sessions).
- Step 3–4: Prompt updates (estimate: 1 session).
- Step 5–6: Docs and testing (estimate: 1 session).

## Notes

- Phase 12 (Convert Commit Workflow Prompts to MCP Tools) introduced `execute_pre_commit_checks`; this phase completes the migration by removing remaining direct script invocations from the commit prompt and ensuring tools resolve language.
- Related: Phase 28 (Enforce MCP Tools for .cortex Operations) — same principle applied to commit workflow instructions.
