# Session Optimization Analysis – 2026-01-28

## Summary

During this session we executed the full `/cortex/commit` workflow, fixed a type-safety issue in `mcp_stability.py`, and synchronized the Synapse submodule and commit pipeline prompts/rules. Overall, checks and tests are clean, but the session exposed several preventable issues around MCP tool parameter typing, roadmap-sync semantics, and state-changing step ordering that can be addressed in Synapse.

## Mistake Patterns Identified

### Pattern 1: Unsafely Typed MCP Timeout Parameters

- **Description**: `with_mcp_stability` originally accepted `timeout: float | None` but was called with `JsonValue`, causing pyright errors and forcing ad‑hoc fixes late in the commit pipeline.
- **Examples**:
  - Pyright reported `JsonValue` not assignable to `float | None` for `timeout` and `stability_timeout` inside `with_mcp_stability`.
  - We added `_to_timeout_value()` and widened the function signature mid‑commit to resolve the type mismatch.
- **Frequency**: Once this session, but affects a core cross‑cutting helper used by many MCP tools.
- **Impact**: Blocks type checking, forces last‑minute fixes in stability‑critical code, and indicates Synapse rules weren’t explicit enough about how MCP JSON parameters should be typed and normalized at the boundary.

### Pattern 2: Roadmap Sync “invalid_references” Ambiguity

- **Description**: `validate(check_type="roadmap_sync")` returned `valid=false` with several `invalid_references` that actually pointed to legitimate, existing plan files, but with slightly different path expectations (e.g., `plans/phase-57-...` vs `../plans/phase-57-...`), leaving it unclear whether this should block commit.
- **Examples**:
  - `invalid_references` entries for:
    - `plans/archive/Phase57/phase-57-fix-markdown-lint-timeout.md`
    - `plans/roadmap-sync-validation-error-ux.md`
    - `plans/enhance-tool-descriptions.plan.md`
    - `plans/phase-60-improve-manage-file-discoverability.plan.md`
  - All of these are real plans already tracked in `roadmap.md` “Active Work” and “Future Enhancements”.
- **Frequency**: Triggered once in this session, but will recur whenever roadmap entries use relative links that don’t match the validator’s stricter expectations.
- **Impact**: Creates confusion in the commit workflow about whether `valid=false` due to `invalid_references` should hard‑block commits when the roadmap content is actually consistent with the codebase.

### Pattern 3: State‑Changing Final Gate Commands Initially Run in Parallel

- **Description**: In Step 12 (Final Validation Gate), we initially launched several state‑changing and validation commands in parallel (e.g., `fix_formatting.py` and `check_formatting.py`), then had to re‑run formatting fix+check sequentially to clear a transient “would reformat” failure.
- **Examples**:
  - First `fix_formatting.py` run reformatted `mcp_stability.py`, but an immediate `check_formatting.py` run still reported “would reformat” until we re‑invoked fix+check sequentially.
- **Frequency**: Once this session, but the commit prompt itself is long and easy to misinterpret around “sequential vs parallel” for final‑gate checks.
- **Impact**: Increases risk of subtle race conditions or false negatives in the final gate, and makes it harder for agents to know exactly which steps are allowed to run in parallel.

### Pattern 4: Early MCP Tool Invocation Without Required Arguments

- **Description**: Early in the commit workflow we invoked `manage_file` without mandatory `file_name`/`operation` arguments, causing Pydantic validation errors at the MCP boundary.
- **Examples**:
  - `manage_file` call with `{}` arguments produced “Field required: file_name, operation” errors before we corrected usage.
- **Frequency**: At least once this session; similar mistakes have been significant enough to spawn Phase 60 (“Improve `manage_file` Discoverability and Error UX”).
- **Impact**: Wastes cycles, clutters logs, and indicates that current prompts/rules do not make required parameters sufficiently obvious to tools or agents.

## Root Cause Analysis

### Cause 1: Insufficient Guidance on JSON Boundary Typing for MCP Utilities

- **Description**: Existing Python rules emphasize Pydantic models and concrete types, but Synapse prompts/rules do not explicitly call out how to handle loosely typed `JsonValue` inputs at utility boundaries like `with_mcp_stability`.
- **Contributing factors**:
  - `with_mcp_stability` signature mixed “nice” Python types (`float | None`) with JSON‑facing MCP call sites that naturally pass `JsonValue`.
  - No explicit pattern in Synapse rules for “accept `JsonValue`, normalize immediately into concrete Python types”.
- **Prevention opportunity**:
  - Strengthen Python rules and the commit prompt to require “normalize JSON inputs at the edge” helpers (e.g., `_to_timeout_value`) and to flag MCP utilities that accept raw `JsonValue` without an immediate conversion step.

### Cause 2: Roadmap Sync Semantics Not Clearly Defined for “Invalid References”

- **Description**: The roadmap‑sync validator treats some relative references as “invalid”, but Synapse prompts/rules do not break down which categories of issues (missing roadmap entries vs. stale line numbers vs. benign path differences) must block commits.
- **Contributing factors**:
  - `validate(check_type="roadmap_sync")` currently returns a single `valid` flag, aggregating diverse issues.
  - The commit prompt simply says “BLOCK COMMIT if critical synchronization issues remain” without specifying which `invalid_references` should be considered critical.
- **Prevention opportunity**:
  - Clarify in prompts/rules how to interpret `invalid_references` (e.g., missing files vs. minor path formatting differences) and when they must block commit vs. be logged as warnings.

### Cause 3: Ambiguity Around Parallelization in Final Validation Gate

- **Description**: The commit prompt both encourages limited parallelization for read‑only steps (9–11) and demands strict sequential execution for state‑changing steps, but Step 12’s formatting fix+check pair is not clearly called out as “must be sequential; do not parallelize”.
- **Contributing factors**:
  - Long, dense commit prompt text makes it easy to miss “fix must run before check”.
  - No explicit “DO NOT parallelize fix_formatting + check_formatting” bullet in the Synapse agents/rules.
- **Prevention opportunity**:
  - Add explicit anti‑patterns and ordering constraints to the `code-formatter` and `quality-checker` agents and commit prompt (e.g., “never run fix and check in parallel; always fix, then check, in a single sequential block”).

### Cause 4: `manage_file` Parameter Discoverability Gaps

- **Description**: While `manage_file` is well‑typed on the MCP side, Synapse prompts/rules do not strongly emphasize that `file_name` and `operation` are mandatory and must always be provided.
- **Contributing factors**:
  - Agent prompts treat `manage_file()` as a generic helper without showcasing its full argument set each time.
  - Phase 60 plan exists but isn’t yet fully reflected in prompts/scripts as hard “USE WHEN”/“HOW” guidance.
- **Prevention opportunity**:
  - Make `manage_file` usage patterns much more explicit in prompts (including concrete examples and failure modes), and add a rules check that flags calls without required parameters as a process violation.

## Optimization Recommendations

### Recommendation 1: Add JSON‑Boundary Typing Pattern to Python Rules

- **Priority**: Critical  
- **Target**: `.cortex/synapse/rules/python/python-coding-standards.mdc`  
- **Change**:
  - Add a subsection under **Type Safety / Pydantic / JsonValue** clarifying:
    - “When a function accepts MCP `JsonValue` inputs (e.g., `timeout`, `metadata`, tool params), it MUST immediately normalize them into concrete Python types via small, pure helper functions (e.g., `_to_timeout_value`) before using them or passing them to typed utilities.”
    - “Utility functions that are reused across tools MUST either (a) accept concrete types only and push JSON normalization to their callers, or (b) explicitly accept `JsonValue` and perform normalization at the top of the function.”
  - Include `with_mcp_stability`‑style examples showing the correct pattern.
- **Expected impact**:
  - Prevents future type mismatches between `JsonValue` and concrete timeout/parameter types.
  - Reduces late‑stage pyright failures in cross‑cutting MCP utilities.

### Recommendation 2: Clarify Roadmap Sync Blocking Semantics

- **Priority**: High  
- **Target**: `.cortex/synapse/agents/roadmap-sync-validator.md` and `.cortex/synapse/prompts/validate-roadmap-sync.md` (if present)  
- **Change**:
  - Add a “Result Interpretation” section that:
    - Distinguishes **missing_roadmap_entries** (always critical) from **invalid_references** (categorize into “missing file”, “stale line number”, “path style mismatch”).
    - States explicitly: “Commits MUST be blocked when roadmap_sync reports missing roadmap entries or references to non‑existent files. Commits MAY proceed when `invalid_references` are limited to benign path formatting differences but TODO tracking is correct; in that case, log a warning and create/update a plan to normalize paths.”
  - Update agent text so it tells the caller exactly which categories must block vs. may be tolerated.
- **Expected impact**:
  - Eliminates ambiguity when `valid=false` but the roadmap content is actually in sync.
  - Prevents unnecessary commit blocking while still enforcing true synchronization problems.

### Recommendation 3: Make Final Gate Sequential Constraints Explicit

- **Priority**: High  
- **Target**: `.cortex/synapse/agents/code-formatter.md`, `.cortex/synapse/agents/quality-checker.md`, and `commit` prompt (`.cortex/synapse/prompts/commit.md`)  
- **Change**:
  - In the agents and commit prompt, add explicit bullets:
    - “In Step 12 (Final Validation Gate), **never** run `fix_formatting.py` and `check_formatting.py` in parallel. They MUST run sequentially: first fix, **then** check, in a single command block or two clearly ordered calls.”
    - “Similarly, do not interleave other state‑changing operations with final formatting fixes.”
  - Optionally, recommend a single combined script (already effectively present) and treat it as the canonical pattern.
- **Expected impact**:
  - Reduces flakiness and confusion in Step 12.
  - Makes it easier for agents to respect the “state‑changing steps must be sequential” rule.

### Recommendation 4: Strengthen `manage_file` Usage Guidance and Examples

- **Priority**: High  
- **Target**: `.cortex/synapse/agents/memory-bank-updater.md` and any prompts that reference `manage_file` (e.g., memory‑bank and commit prompts)  
- **Change**:
  - Add a dedicated “Correct `manage_file` Usage” section showing:
    - Minimal **read** example: `manage_file(file_name="activeContext.md", operation="read", include_metadata=False)`.
    - Minimal **write** example with `change_description`.
    - Explicit statement: “`file_name` and `operation` are REQUIRED. Calling `manage_file` without these is a protocol violation and will raise a validation error.”
  - Add an anti‑pattern callout: “NEVER call `manage_file({})` or omit `file_name`/`operation`; this indicates a missing plan step or a bug in the orchestration prompt.”
- **Expected impact**:
  - Prevents Pydantic validation errors at the MCP boundary.
  - Speeds up development by making required parameters impossible to miss.

### Recommendation 5: Add Session‑Level Check for MCP Tool Argument Validation Errors

- **Priority**: Medium  
- **Target**: `.cortex/synapse/agents/error-fixer.md` and `commit` prompt  
- **Change**:
  - Extend error‑fixer guidance to explicitly treat MCP argument validation failures (e.g., Pydantic `missing` fields) as first‑class errors to fix:
    - “If MCP tool responses contain Pydantic validation errors (missing required fields, wrong types), treat them as **fix‑ASAP** issues and update prompts/agent logic to always pass the required parameters.”
  - Suggest adding a short checklist item before commit: “Scan recent MCP tool invocations for validation errors; if present, update prompts/rules to eliminate them.”
- **Expected impact**:
  - Turns temporary MCP argument mistakes into triggers for prompt/rule hardening.
  - Reduces repetition of the same shape of error across sessions.

## Implementation Plan

1. **Update Python coding standards** to include an explicit “JsonValue normalization at MCP boundaries” pattern (Recommendation 1).  
2. **Refine roadmap sync validator and prompt** to spell out which `invalid_references` categories block commits vs. can be logged and tracked (Recommendation 2).  
3. **Tighten final‑gate agents and commit prompt wording** so formatting fix+check are clearly required to be sequential (Recommendation 3).  
4. **Enhance `memory-bank-updater` and related prompts** with more explicit `manage_file` usage examples and anti‑patterns (Recommendation 4).  
5. **Augment error‑fixer guidance** to treat MCP validation errors as fix‑ASAP and to feed improvements back into prompts/rules (Recommendation 5).  

Together, these changes will make MCP boundary typing safer, roadmap synchronization behavior clearer, final validation more robust, and MCP tool usage more discoverable, reducing friction in future commit and maintenance sessions.

---

## Session Analysis – 2026-01-28 (Roadmap Sync & Markdown Lint Fix)

This section captures an additional optimization pass focused specifically on the Phase 57 and Roadmap Sync work from this session, using `analyze_context_effectiveness()` insights.

### Mistake Patterns Identified (Context Effectiveness Pass)

#### Pattern A: Oversized Token Budgets for Narrow Tasks

- **Description**: Both analyzed calls (`fix/debug` for markdown lint timeout and roadmap sync UX) used a `token_budget` of 50,000, but actual utilization was ~22–23%, leaving ~38k tokens unused per call.
- **Evidence**:
  - `utilization`: 0.2229 and 0.23152 for the two entries.
  - `files_selected`: Always 10 memory bank files, with several low-relevance entries (`file.md`, `tmp-mcp-test.md`).
- **Impact**:
  - Wasted context bandwidth and slower reasoning for tightly scoped fix/debug tasks.
  - Increases noise by pulling in low-relevance files when a smaller, more focused set would suffice.

#### Pattern B: Over-Inclusion of Low-Relevance Memory Bank Files

- **Description**: For both tasks, the same 10 files were selected, even though some had consistently low relevance scores.
- **Evidence**:
  - `activeContext.md`: avg relevance ~0.78, recommended as “High value – prioritize for loading”.
  - `roadmap.md`, `progress.md`, `phase-60-...plan.md`: “Moderate value – include when relevant”.
  - `file.md`, `tmp-mcp-test.md`, `projectBrief.md`, `systemPatterns.md`, `productContext.md`, `techContext.md`: “Lower relevance – consider excluding for most tasks”.
- **Impact**:
  - Agents scan more context than necessary.
  - Increases risk of distraction from historical or generic docs that are not essential to a single bugfix/roadmap item.

#### Pattern C: Ambiguity Around Coverage Gates in Targeted Test Runs

- **Description**: Targeted roadmap sync tests were run via `pytest tests/unit/test_roadmap_sync.py tests/tools/test_validation_operations.py -q`, but the repo-wide coverage gate (configured for the full suite) still fired and failed the run (~21.7% total coverage).
- **Evidence**:
  - Coverage report shows many unrelated analysis/structure modules at 0–30% coverage.
  - The intent of the run was to validate only the roadmap sync changes, not enforce global coverage.
- **Impact**:
  - Confusing signal during focused fix/debug iterations; it appears as if the change regressed coverage even when it improved coverage locally.
  - Encourages ad‑hoc interpretation instead of a clear, documented rule for when the global gate should be considered authoritative.

### Root Cause Analysis (Context Effectiveness Pass)

#### Cause A: Generic, High Default Budgets in Synapse Prompts

- **Description**: Synapse prompts treat 50k tokens as a safe default for many tasks, without distinguishing between “design/architecture” vs. “narrow bugfix” work.
- **Contributing Factors**:
  - No explicit guidance in prompts/rules tying `token_budget` to task type.
  - Lack of examples showing “small, focused” budgets for fix/debug.
- **Prevention Opportunity**:
  - Use task-type insights from `analyze_context_effectiveness()` (recommended 15k for `fix/debug` and `other`) to drive explicit budget defaults and caps in prompts.

#### Cause B: Memory Bank Selection Strategy Not Tuned by Learned File Effectiveness

- **Description**: Context loading strategies do not yet exploit the “file_effectiveness” recommendations returned by `analyze_context_effectiveness()`.
- **Contributing Factors**:
  - Prompts treat all core memory bank files as equally important for most tasks.
  - No rule that says “if average relevance for a file stays below X over recent sessions, de‑prioritize it”.
- **Prevention Opportunity**:
  - Incorporate “High value / Moderate / Lower relevance” recommendations into context-loading logic and Synapse guidance, especially for fix/debug workflows.

#### Cause C: Lack of Explicit Guidance on Coverage Expectations for Targeted vs Full Runs

- **Description**: Testing standards (and commit prompts) emphasize a 90% coverage minimum, but they don’t clearly differentiate:
  - Full-suite coverage gates (for `/cortex/commit` / CI).
  - Targeted local runs for validating a single module or fix.
- **Contributing Factors**:
  - Single global `fail-under=90` configuration applied even to narrow test invocations.
  - No Synapse guidance that explains when to interpret a low global coverage result as “expected legacy debt” vs. “new regression”.
- **Prevention Opportunity**:
  - Clarify in prompts/rules how to treat coverage gates in targeted fix/debug runs, and encourage using module-level coverage checks for new/changed code.

### Optimization Recommendations (Context Effectiveness Pass)

#### Recommendation A: Task-Aware Token Budget Defaults

- **Priority**: High  
- **Target**: `.cortex/synapse/prompts/context-loader.md` (or equivalent) and any fix/debug-oriented agents.  
- **Change**:
  - Add a table that maps task types to default `token_budget`:
    - `fix/debug`: **15,000** (from `analyze_context_effectiveness` recommendation).
    - `small feature/refactor`: 20,000–30,000.
    - `architecture / large design`: 40,000–50,000.
  - Instruct agents to:
    - Start with the recommended budget for the detected task type.
    - Increase only when `utilization` from previous runs regularly exceeds ~70%.
- **Expected Impact**:
  - Reduces wasted tokens and context noise for narrow tasks.
  - Aligns budget selection with observed utilization statistics.

#### Recommendation B: Context Loader Should Use File Effectiveness Signals

- **Priority**: High  
- **Target**: Synapse context-loading prompts and any “load_context” helper prompts.  
- **Change**:
  - Add explicit guidance:
    - “Always include `activeContext.md` for fix/debug tasks (high value).”
    - “Include `roadmap.md`, `progress.md`, and phase-specific plans when the task references a roadmap item or phase.”
    - “Treat `file.md`, `tmp-mcp-test.md`, `projectBrief.md`, `systemPatterns.md`, `productContext.md`, `techContext.md` as **optional** for fix/debug; include only when the task is exploratory or architectural.”
  - Encourage using the `file_effectiveness` section from `analyze_context_effectiveness()` to periodically tune default inclusion lists.
- **Expected Impact**:
  - Makes context loads leaner and more task-specific.
  - Reduces over-selection of low-relevance files for bugfix sessions.

#### Recommendation C: Clarify Coverage Expectations in Testing Prompts

- **Priority**: Medium  
- **Target**: `.cortex/synapse/rules/general/testing-standards.mdc` and any test/commit prompts that mention coverage.  
- **Change**:
  - Add a subsection:
    - Distinguish between:
      - **Local targeted runs** (module-level or file-level) where a global coverage gate may fail due to legacy untested modules.
      - **Full `/cortex/commit` / CI runs** where the 90% global threshold is enforced.
    - State explicitly:
      - “For targeted fix/debug runs, focus on ensuring **new or modified code** meets coverage expectations; do not interpret a global 20–30% coverage printout as a new regression if unchanged modules are under-tested.”
  - Encourage adding module-specific coverage checks for new code paths.
- **Expected Impact**:
  - Reduces confusion when focused runs trigger global coverage failures.
  - Keeps attention on the coverage of newly introduced or changed logic.

### Implementation Plan (Addendum)

1. **Update context-loading prompts** to adopt task-aware token budgets and reflect the 15k recommendation for `fix/debug` / “other” tasks derived from `analyze_context_effectiveness()`.  
2. **Modify context selection rules** so high/medium/low relevance memory bank files are used as guidance for inclusion, especially for narrow fix/debug workflows.  
3. **Refine testing standards and prompts** to separate expectations for full-suite vs targeted runs, framing global coverage failures during narrow tests as expected legacy debt unless new code is uncovered.  

These changes, combined with the earlier recommendations in this file, will make future sessions more efficient, with leaner context windows, clearer test expectations, and better use of the Memory Bank’s learned effectiveness metrics.
