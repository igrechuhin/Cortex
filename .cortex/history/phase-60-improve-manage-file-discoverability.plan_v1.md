# Phase 60: Improve `manage_file` Discoverability and Error UX

## Status

- Status: PLANNED
- Priority: High (developer ergonomics, MCP UX)
- Owner: Cortex maintainers
- Start Date: 2026-01-28

## Goal

Improve the discoverability and error experience of the `manage_file` MCP tool so that:

- Callers (LLMs and humans) can easily discover required parameters (`file_name`, `operation`).
- Missing/invalid parameter errors are surfaced as clear, actionable, structured responses.
- Higher-level workflows (e.g., commit pipeline via `execute_pre_commit_checks` Step 0 `fix_errors`) can handle `manage_file` misuse gracefully without obscure Pydantic validation traces.

## Context

- A recent commit workflow run triggered a Pydantic validation error by calling `manage_file` with no arguments (missing required `file_name` and `operation`).
- The failure surfaced as a generic validation error, with limited guidance on how to correct the call.
- Cortex strongly encourages using MCP tools (`manage_file`, `get_memory_bank_stats`, etc.) for memory bank operations, so their ergonomics and discoverability significantly affect developer and LLM experience.
- Existing roadmap/plans already cover broader MCP tool description improvements and validation error UX; this plan focuses specifically on `manage_file` as a high-impact, frequently used tool.

## Problem Statement

**Current behavior:**

- `manage_file` is defined with required parameters `file_name` and `operation` in its schema.
- When called without arguments (or with missing `file_name`/`operation`), the FastMCP/Pydantic layer raises a validation error.
- The error is surfaced as a low-level schema/validation failure rather than a domain-specific, structured error with guidance.

**Why it is undesirable:**

- LLM agents may attempt a "probe" call with no arguments and receive a confusing error, instead of guidance.
- Human callers must inspect tool schemas or source code to understand required parameters.
- Higher-level workflows (e.g., commit pipeline orchestrators) may treat this as an opaque MCP failure.

**Where it surfaced:**

- During a commit workflow step that attempted to use `manage_file` without specifying `file_name` and `operation` while preparing to run `execute_pre_commit_checks` Step 0 (`fix_errors`).

## Approach

We will address the problem in three phases, starting with targeted improvements and leaving room for future generalization to other tools.

1. **Investigation & Baseline (Phase 60.1)**
   - Confirm current `manage_file` behavior, schema, and error surfacing paths.
   - Map all call sites and prompts that reference `manage_file`.
   - Capture real-world error examples from transcripts.

2. **Targeted UX Improvements for `manage_file` (Phase 60.2)**
   - Enhance error messages for missing/invalid parameters.
   - Improve tool descriptions and docs for better discoverability.

3. **Optional Generalization to Other Tools (Phase 60.3)**
   - Evaluate whether similar patterns affect other MCP tools.
   - If beneficial, design a shared pattern for parameter discoverability and validation UX.

## Implementation Steps

### Phase 60.1: Investigation & Baseline

1. **Code and Schema Review**
   - Inspect the `manage_file` implementation module to understand how it is registered and how arguments are validated (FastMCP/Pydantic layer vs. in-function checks).
   - Review the generated MCP tool schema for `manage_file` (server-level `list_tools` or equivalent) to confirm:
     - Required vs optional parameters (`file_name`, `operation`, `content`, `include_metadata`, `change_description`, `project_root`).
     - Enum values for `operation` (`"read"`, `"write"`, `"metadata"`).

2. **Error Path Analysis**
   - Reproduce the `manage_file()`-without-arguments call in a controlled environment.
   - Capture the exact error payload returned by the server (including Pydantic error structure).
   - Trace how this error propagates through any Cortex error-handling layers (e.g., MCP failure handlers, wrappers around tool execution).

3. **Workflow and Prompt Review**
   - Identify all locations where `manage_file` is referenced in:
     - `.cortex/synapse/prompts/` (especially commit-related prompts that mention memory bank operations).
     - Any higher-level MCP tools or orchestration helpers that wrap `manage_file`.
   - Determine whether there are implicit assumptions that `manage_file` can be "probed" without parameters.

4. **Documentation Survey**
   - Review `docs/api/tools.md`, `docs/api/managers.md`, and any existing MDR for `manage_file` to see how its usage is described.
   - Compare documentation against the actual schema to identify gaps (e.g., missing explicit list of required parameters, missing examples).

**Exit criteria (Phase 60.1):**

- Clear mapping of all `manage_file` call sites.
- Captured baseline error payload for missing-argument scenario.
- Gap analysis between current docs/schemas and desired discoverability.

### Phase 60.2: Targeted UX Improvements for `manage_file`

We will focus on Option B-style improvements (with Option A quick wins) from the outline.

1. **Error Message Improvements (Quick Wins)**
   - Design a domain-specific error shape for parameter validation issues, e.g.:
     - `status: "error"`
     - `error: "Missing required parameters: file_name, operation"`
     - `details: { "missing": ["file_name", "operation"], "required": ["file_name", "operation"], "operation_values": ["read", "write", "metadata"] }`
     - `hint: "Call manage_file(file_name=..., operation=...) for read/write/metadata operations. See docs/api/tools.md#manage_file."`
   - Ensure this error shape is compatible with existing clients (no breaking changes to top-level keys; additive where possible).

2. **Guardrails Around Argument Validation**
   - Introduce a pre-validation layer (where feasible) that detects the absence of `file_name` and/or `operation` before Pydantic raises a generic error.
   - When this condition is detected, return the domain-specific error structure instead of a raw Pydantic error, while preserving debug information in logs.

3. **Tool Description Enhancements**
   - Update the `manage_file` tool docstring to include:
     - A **REQUIRED PARAMETERS** section explicitly listing `file_name` and `operation`.
     - An **OPERATIONS** table documenting `"read"`, `"write"`, `"metadata"` with examples.
     - At least one concrete call example for each operation mode.
   - Ensure the updated docstring is reflected in the MCP tool schema (used by clients for documentation/discoverability).

4. **Documentation Updates**
   - Update `docs/api/tools.md` (and related docs) with:
     - A dedicated subsection for `manage_file` including:
       - Description
       - Parameter table (name, type, required/optional, description)
       - Operation enum values and behavior
       - Example calls
     - Guidance on how higher-level workflows (e.g., commit prompts) should use `manage_file`.

5. **Prompt-Level Guidance**
   - Update relevant `.cortex/synapse/prompts/` to:
     - Remind agents that `manage_file` requires `file_name` and `operation`.
     - Provide concise examples of proper usage in memory-bank related workflows.

**Exit criteria (Phase 60.2):**

- `manage_file` returns clear, structured, actionable errors for missing/invalid parameters.
- Tool schema and docs clearly surface required parameters and valid `operation` values.
- Commit and memory-bank prompts guide correct usage.

### Phase 60.3: Optional Generalization to Other Tools

1. **Cross-Tool Survey**
   - Identify other high-traffic MCP tools with required parameters that may suffer from similar discoverability issues.
   - Examples may include: memory bank tools (`get_memory_bank_stats`, etc.), validation tools (`validate`, `check_structure_health`), optimization tools, etc.

2. **Pattern Extraction**
   - If recurring patterns of missing-argument errors are found:
     - Define a shared internal helper for building consistent validation error responses.
     - Consider a simple `get_tool_schema(tool_name)` helper or documentation link pattern to encourage schema introspection.

3. **Scope Control**
   - Decide whether to extend the `manage_file` improvements to a small set of critical tools only, or to a broader subset.
   - Avoid over-engineering a full discovery API unless clear demand exists.

**Exit criteria (Phase 60.3):**

- Decision documented on whether to generalize beyond `manage_file`.
- If generalized, at least one additional tool updated and validated with the same pattern.

## Testing Strategy (95%+ Coverage Target)

All new/changed behavior MUST be covered by tests with a target of **95% code coverage** for the affected areas.

### Unit Tests

- **Parameter Validation Scenarios**
  - `test_manage_file_missing_both_required_parameters()`
    - Arrange: Call `manage_file` without `file_name` and `operation` (through the appropriate interface).
    - Act: Capture error response.
    - Assert: Error structure includes missing parameters list, valid operation values, and helpful hint.
  - `test_manage_file_missing_file_name_only()`
  - `test_manage_file_missing_operation_only()`
  - `test_manage_file_invalid_operation_value()` (e.g., `operation="delete"`).

- **Error Response Shape**
  - Verify top-level keys (`status`, `error`) remain present and compatible.
  - Verify structured details (`details.missing`, `details.required`, `details.operation_values`, `hint`).

- **Tool Description Consistency**
  - (If tooling exists) tests that introspect the `manage_file` schema to ensure required parameters and enum values are correctly exposed.

### Integration Tests

- **MCP-Level Behavior**
  - Call `manage_file` via the MCP server interface with:
    - No arguments.
    - Missing one required argument.
    - Invalid `operation` value.
  - Assert that:
    - The error is returned as a structured JSON payload.
    - The message is clear and points to the correct usage.

- **Commit Workflow / Step 0 (`fix_errors`) Interaction**
  - Simulate a commit pipeline run where `execute_pre_commit_checks` orchestration interacts with memory-bank operations:
    - Ensure that if a misconfigured call to `manage_file` occurs, the pipeline surfaces a clear, actionable error rather than an opaque validation failure.
    - Ensure that once the usage is corrected (proper `file_name`/`operation`), the pipeline proceeds normally.

- **Transcript-Based Regression Scenarios**
  - Capture or simulate agent transcripts that previously produced the Pydantic validation error.
  - Re-run them with the updated error handling and confirm that:
    - The new error messages guide the agent toward specifying `file_name` and `operation`.
    - No regressions occur in successful paths.

### Acceptance Criteria

- 95%+ coverage on new/modified `manage_file`-related logic and error-handling code.
- All new unit and integration tests passing.
- No regressions in existing MCP tool behavior.
- Commit workflow (`execute_pre_commit_checks`) behaves correctly under both proper and improper `manage_file` usage.

## Risks and Mitigations

- **Risk: Over-Constraining Behavior**
  - Overly strict validation may reject edge-case calls that are currently valid.
  - *Mitigation*: Limit new validations to truly required parameters; avoid changing semantics for optional fields.

- **Risk: Backward Compatibility Issues**
  - Clients relying on the exact Pydantic error shape may be affected.
  - *Mitigation*: Preserve top-level structure; treat new fields as additive; document the change.

- **Risk: Noise in Logs**
  - More verbose error details may clutter logs.
  - *Mitigation*: Use structured logging with severity levels; keep logs concise while responses remain rich.

- **Risk: Over-Generalization**
  - Attempting to roll out a complex discovery API (Option C) prematurely.
  - *Mitigation*: Keep Phase 60 focused on `manage_file` and only generalize after concrete evidence of broader need.

## Timeline

- **Phase 60.1 (Investigation & Baseline)**: 0.5–1 day
- **Phase 60.2 (Targeted `manage_file` UX Improvements)**: 1–2 days (including tests and docs)
- **Phase 60.3 (Optional Generalization)**: 1–2 days (only if prioritized)

## Dependencies

- Access to recent MCP error logs and/or agent transcripts demonstrating the `manage_file`-without-arguments issue.
- Existing documentation structure for MCP tools (`docs/api/tools.md` and related files).
- Existing testing harness for MCP tool invocation (unit + integration).

## Success Criteria

- `manage_file` misuse (missing `file_name`/`operation`) results in clear, actionable, structured error messages.
- LLM and human callers can easily discover required parameters and valid `operation` values from tool descriptions and docs.
- Commit pipeline interactions that rely on `manage_file` behave predictably and are resilient to configuration mistakes.
- All new behavior is thoroughly tested with 95%+ coverage in affected areas.
