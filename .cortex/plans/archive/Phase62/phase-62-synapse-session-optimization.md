# Phase 62: Synapse Session Optimization – Harden Prompts and Rules

**Status**: COMPLETE (2026-01-29)  
**Phase**: 62  
**Owner**: Cortex MCP / Synapse  
**Created**: 2026-01-28  

## Goal

Use findings from the 2026-01-28 session optimization report to harden Synapse prompts, rules, and commit workflow guidance so that common mistakes around MCP timeout typing, roadmap synchronization, final validation sequencing, and `manage_file` usage are proactively prevented in future sessions.

## Context

Recent `/cortex/commit` and Synapse update work surfaced several recurring issues:

- Type checker failures in `with_mcp_stability` due to passing `JsonValue` timeouts into `float | None` parameters.
- Ambiguous `roadmap_sync` results where `invalid_references` flagged path style differences even when roadmap entries and plans were correctly tracked.
- Initial attempts to run final validation gate commands (e.g., `fix_formatting.py` and `check_formatting.py`) in parallel before re-running them sequentially.
- Early `manage_file` invocations without required `file_name`/`operation` parameters, causing Pydantic validation errors.

These issues did not break the final commit after fixes, but they indicate gaps in Synapse prompts/rules that can and should be closed.

A follow-up session optimization review (`session-optimization-2026-01-28T18-31.md`) highlighted additional patterns:

- Tests asserting on raw decoded JSON dicts instead of using small Pydantic v2 models for MCP JSON responses.
- Coverage gate “fail-under=90” noise when running narrow, file-scoped test targets where the modified modules already exceed coverage targets.
- Brittle assumptions about session artifacts (transcripts, `load_context` traces) that can lead to “no_data” analysis results even when rich signals (Memory Bank updates, tool calls, diffs) exist.

## Scope

In scope:

- Updates to Synapse **rules** and **agents** for:
  - Python MCP JSON-boundary typing patterns.
  - Roadmap synchronization semantics and blocking criteria.
  - Final validation gate ordering and parallelization constraints.
  - `manage_file` usage guidance and MCP validation error handling.
- Documentation alignment for the above in relevant prompts (e.g., `commit`, roadmap sync, memory-bank prompts).

Out of scope:

- New MCP tool implementations beyond documentation/rule updates.
- Changes to business logic in core tools unrelated to prompts/rules.

## Approach

1. **Harden git write safety (CRITICAL)** by adding explicit precondition gates in `commit.md` to prevent unauthorized commits/pushes.
2. **Make Step 11 submodule handling deterministic (HIGH)** with explicit command sequences and acceptance criteria.
3. **Enforce roadmap_sync as a true commit gate (HIGH)** by treating `valid: false` as an absolute block, not a warning.
4. **Fix tooling/process mismatch (MEDIUM-HIGH)** by updating plan archiver to use preferred tool primitives instead of shell commands.
5. **Codify JSON boundary typing patterns** in Python rules so MCP utilities like `with_mcp_stability` have clear, enforced guidance.
6. **Clarify roadmap-sync semantics** by tightening agent/prompt language around which `invalid_references` categories must block commits.
7. **Make final validation gate ordering explicit** in agents and the commit prompt to avoid accidental parallelization of state-changing steps.
8. **Improve `manage_file` guidance** in agents/prompts to make required parameters and common failure modes obvious.
9. **Treat MCP validation errors as first-class issues** in error-fixer guidance and the commit prompt, feeding them back into Synapse as prompt/rule improvements.

## Implementation Steps

### 0. Harden `commit.md` Against Unauthorized Git Writes (CRITICAL PRIORITY) — ✅ IMPLEMENTED (2026-01-29)

- **Target**: `.cortex/synapse/prompts/commit.md`
- **Changes** (all applied):
  - Added explicit precondition gate at the very beginning: ONLY run when user explicitly invoked `/cortex/commit`; NEVER commit or push based on implicit assumptions.
  - "Git Write Safety" section (with Branch Safety Rule and Git Write Preconditions) present before Step 0; fixed corrupted "Git Write Preconditions" subsection to list the three mandatory checks and reference Step 13/14.
  - Step 13 and Step 14 already contain mandatory precondition checks (user explicitly requested commit/push; branch check; push to `main` requires explicit confirmation).
- **Expected impact**: Prevents the single most costly failure mode (unapproved commits/pushes to `main`).

### 1. Make Step 11 Submodule Handling Deterministic (HIGH PRIORITY) — ✅ IMPLEMENTED (2026-01-29)

- **Target**: `.cortex/synapse/prompts/commit.md` (Step 11 section)
- **Changes** (all applied): Replaced prose with an explicit, minimal command sequence and strict decision rule:
  - **Step 11.1**: Check parent repo status: `git status --porcelain`
    - If output contains `m .cortex/synapse` (dirty submodule), proceed to Step 11.2.
    - If no `m .cortex/synapse`, skip to Step 12.
  - **Step 11.2**: Check submodule working tree: `git -C .cortex/synapse status --porcelain`
    - If empty: skip (submodule pointer changed but no local edits)
    - If non-empty: proceed to Step 11.3
  - **Step 11.3**: Commit and push in submodule:
    - `git -C .cortex/synapse add -A`
    - `git -C .cortex/synapse commit -m "Update Synapse prompts/rules"`
    - `git -C .cortex/synapse push`
  - **Step 11.4**: Update parent repo submodule pointer:
    - `git add .cortex/synapse`
    - Verify with: `git diff --submodule=log -- .cortex/synapse` (should show pointer movement)
  - **Step 11.5 - Verify submodule is clean (CRITICAL - NEW)** — ✅ IMPLEMENTED (2026-01-29):
    - **MANDATORY**: After Step 11.4, verify no uncommitted changes remain:

### 2. Enforce roadmap_sync as a True Commit Gate (HIGH PRIORITY) — ✅ IMPLEMENTED (2026-01-29)

- **Target**: `.cortex/synapse/prompts/commit.md` (Step 10), `.cortex/synapse/agents/roadmap-sync-validator.md`
- **Changes** (all applied):
  - **In Step 10**: Explicit blocking rule present:
    - **"If `validate(check_type="roadmap_sync")` returns `valid: false`, STOP the commit workflow immediately. Do NOT proceed to Step 11. This is a hard gate, not a warning."**
  - **In roadmap-sync-validator agent**: Add remediation playbook:
    - **"When `valid: false` is returned, the agent MUST:**
      1. Fix invalid references by using canonical repo-relative paths (e.g., `src/cortex/tools/file_operation_helpers.py`, `.cortex/synapse/prompts/commit.md`) instead of bare filenames.
      2. If references are still flagged as invalid but the target file exists, create a plan to refine validator heuristics (do NOT bypass the validator)."
  - **Distinguish blocking vs non-blocking issues**:
    - `missing_roadmap_entries`: ALWAYS blocks commit
    - `invalid_references` to non-existent files: ALWAYS blocks commit
    - `invalid_references` that are path-style mismatches where target exists: Log warning, create follow-up plan, but allow commit if TODO tracking is correct
- **Expected impact**: Prevents "validator bypass culture" and maintains integrity of memory bank process. Commit.md Step 10 and roadmap-sync-validator agent already contain blocking rule, remediation playbook, and blocking vs non-blocking criteria.

### 3. Update Plan Archiver to Use Preferred Tool Primitives (MEDIUM-HIGH PRIORITY) — ✅ IMPLEMENTED (2026-01-29)

- **Target**: `.cortex/synapse/agents/plan-archiver.md`
- **Changes** (all applied):
  - Replaced shell `find`/`grep` with preferred tool primitives:
    - **"Use `Glob` tool to find plan files**: `Glob(pattern="phase-*.md*", path=".cortex/plans")`**
    - **"Use `Grep` tool to search for status markers**: `Grep(pattern="Status.*COMPLETE", path=".cortex/plans", files=["phase-*.md"])`**
  - Ensure archiving logic ignores non-plan files like `README.md`, `STATUS.md`, `QUICK_START.md`
  - Add explicit guidance: **"NEVER use shell `find` or `grep` for file operations. Use standard tools (`Glob`, `Grep`, `Read`, `LS`) instead."**
- **Expected impact**: More reliable archiving detection and better consistency with repo tool policies. Plan-archiver already uses Glob/Grep, "NEVER use shell find or grep", and excludes non-plan files.

### 4. Strengthen Python JSON-Boundary Typing Rules — ✅ IMPLEMENTED (2026-01-29)

- **Rules**: `.cortex/synapse/rules/python/python-coding-standards.mdc` already contains **"JsonValue at MCP Boundaries"** with `_to_timeout_value()` pattern and `with_mcp_stability` examples.
- **Tests**: Added `TestJsonValueTimeoutNormalization` in `tests/unit/test_mcp_stability_timeouts.py` (numeric string timeout accepted and enforced; invalid string falls back to default).
- Update `python-coding-standards.mdc` to add a dedicated subsection (e.g., **“JsonValue at MCP Boundaries”**) that:
  - Requires helpers like `_to_timeout_value()` to normalize `JsonValue` inputs (timeouts, metadata, tool params) into concrete Python types before use.
  - States that cross-cutting utilities must either:
    - Accept concrete types only and push JSON normalization to the callers, or
    - Accept `JsonValue` and perform normalization at the top of the function.
  - Includes `with_mcp_stability`-style examples demonstrating the correct pattern.
- Cross-check other MCP utilities that consume `JsonValue` and ensure they follow the same pattern.

### 5. Clarify Roadmap Sync Blocking Semantics (Updated with Gate Enforcement) — ✅ IMPLEMENTED (2026-01-29)

- **Target**: `.cortex/synapse/agents/roadmap-sync-validator.md` (Result Interpretation and blocking criteria already present).
- **Changes** (all applied): roadmap-sync-validator and commit.md Step 10 already distinguish:
  - Distinguish clearly between:
    - **missing_roadmap_entries** (always critical, MUST block commit),
    - **invalid_references** to non-existent files (critical, MUST block commit),
    - **invalid_references** that are path-style mismatches (e.g., `plans/...` vs `../plans/...`) where the target plan exists and TODO tracking is correct (non-critical).
  - Add a “Result Interpretation” section that:
    - Specifies which categories must block commit.
    - Allows commits to proceed when only benign path-style mismatches are present, while logging a warning and creating/updating a small follow-up plan to normalize paths.
- Ensure future `/cortex/commit` logic treats roadmap-sync results according to this clarified policy.

### 6. Enforce Sequential Final Validation Gate Ordering — ✅ IMPLEMENTED (2026-01-29)

- Update `code-formatter.md`, `quality-checker.md`, and `commit.md` to:
  - Add explicit bullets under Step 12 (Final Validation Gate):
    - “NEVER run `fix_formatting.py` and `check_formatting.py` in parallel. They MUST run sequentially: first fix, then check.”
    - “Do not interleave other state-changing operations between final formatting fix and check.”

  - Optionally, recommend a single combined invocation (fix then check) as the canonical pattern.
- If needed, add a short note in `plan-archiver`/other agents referencing that Step 12 must be treated as atomic/sequential for formatting.

### 6.5. Add Immediate Markdown Lint Validation (NEW - MEDIUM PRIORITY) — ✅ IMPLEMENTED (2026-01-29)

- **Target**: `.cortex/synapse/prompts/commit.md` - Step 12

- **Changes**: Add immediate markdown lint validation before submodule handling or after modifying markdown files:
  - **Option A**: Add Step 12.0 before Step 12.1:

- Add an anti-pattern callout:
  - “NEVER call `manage_file({})` or omit `file_name`/`operation`; this indicates a missing plan step or a bug in the orchestration prompt.”
**Step 7** — ✅ IMPLEMENTED (2026-01-29): Anti-pattern added in commit.md; commit and memory-bank prompts show full usage examples.

### 8. Elevate MCP Validation Errors in Error-Fixer and Commit Prompt — ✅ IMPLEMENTED (2026-01-29)

- **Changes** (all applied): error-fixer.md has "MCP Validation Errors (FIX-ASAP)" section; commit.md checklist includes "Scan for MCP validation errors".
- Update `error-fixer.md` to:
  - Treat MCP argument validation errors (e.g., Pydantic missing fields, wrong types) as **FIX-ASAP** issues.
  - Instruct agents to:
    - Detect these errors in tool responses.
    - Update prompts/rules to always provide required parameters.
    - Re-run the relevant step after prompt/rule adjustments.
- Extend the commit prompt to:
  - Add a checklist item before or within Step 0/Step 12:
    - “Scan recent MCP tool invocations for validation errors; if present, update prompts/rules to eliminate them before proceeding.”

### 9. Tune Context Budgets and Memory Bank Selection Using Session Insights — ✅ IMPLEMENTED (2026-01-29)

- **Changes** (all applied): implement-next-roadmap-step.md has task-aware token budgets, memory bank file selection, and file_effectiveness interpretation.
- Use `analyze_context_effectiveness()` insights from the 2026-01-28 session to:
  - Update context-loading prompts so **fix/debug** and similar narrow tasks default to a smaller token budget (e.g., ~15,000 tokens instead of 50,000), increasing only when utilization regularly exceeds ~70%.
  - Prioritize high-value memory bank files (`activeContext.md`, `roadmap.md`, `progress.md`, and phase-specific plans) and treat consistently low-relevance files (`file.md`, `tmp-mcp-test.md`, `projectBrief.md`, `systemPatterns.md`, `productContext.md`, `techContext.md`) as optional for fix/debug workflows.
  - **Changes** (all applied): implement-next-roadmap-step.md has task-aware token budgets (fix/debug 15k, small 20–30k, architecture 40–50k), memory bank file selection (high/moderate/lower), and file_effectiveness interpretation.

### 10. Incorporate Post-Commit Session Optimization Recommendations (2026-01-28T02) — ✅ IMPLEMENTED (2026-01-29)

- Extend this phase to also cover the additional patterns and recommendations identified in the post-commit analysis `session-optimization-2026-01-28T02.md`:
  - **Roadmap ↔ plan coupling**: Ensure roadmap prompts/agents require a concrete plan file (or DRY wrapper) for every PLANNED phase, so roadmap_sync never reports references to non-existent plans (e.g., Phase 60).
  - **Review addenda and MD024**: Update session-review / analyze-session prompts to recommend suffixed headings (e.g., “(Context Effectiveness Pass)”) when appending additional analysis passes to an existing review file, preventing duplicate-heading (`MD024`) violations that propagate through memory-bank transclusions.
  - **Timely plan archiving**: Strengthen guidance in `plan-archiver` and related prompts so completed plans are archived to `archive/PhaseX/` as soon as their status becomes COMPLETE, rather than waiting for a later `/cortex/commit` run.
  - **Workflow-only sessions and `analyze_context_effectiveness()`**: Clarify in session-optimization prompts/agents that “no_data” from `analyze_context_effectiveness(analyze_all_sessions=False)` is expected for workflow/quality-only sessions (like `/cortex/commit` that do not call `load_context`), and suggest using commit-tool outputs and memory-bank diffs as alternative signals in those cases.

### 11. Normalize Session Review Filename Conventions — ✅ IMPLEMENTED (2026-01-29)

- Define and document a single canonical filename pattern for session optimization reviews in Synapse prompts and agents (e.g., `session-optimization-YYYY-MM-DDTHH-MM.md`), and ensure all new review files are created via helpers that follow this pattern.
- Update any review/analysis prompts (including session-optimization agents) to:
  - Treat the timestamp suffix after `T` as a full time-of-day component (hours and minutes), not a bare counter.
  - Recommend deriving this suffix from the actual session time (e.g., `T17-58`), avoiding ad-hoc names like `T02` that don’t encode a true timestamp.
- **Changes** (all applied): session-optimization-analyzer and analyze-session-optimization.md document canonical pattern (session-optimization-YYYY-MM-DDTHH-MM.md), timestamp suffix (HH-MM), and malformed-filename detection/suggestions.

### 12. Make Pydantic v2 the Default for JSON Assertions in Tests — ✅ IMPLEMENTED (2026-01-29)

- Align Synapse prompts and rules with `python-pydantic-standards.mdc` by adding a **“Testing JSON Responses”** subsection that:
  - Prohibits asserting on raw `dict` shapes for MCP JSON responses in tests.
  - Requires small Pydantic v2 `BaseModel` types and `model_validate_json()` / `model_validate()` for structured JSON produced by tools like `manage_file`, `rules`, and `execute_pre_commit_checks`.
- **Changes** (all applied): python-pydantic-standards.mdc has "Testing JSON Responses" subsection; implement-next-roadmap-step, review.md, and create-plan.md reference Pydantic v2 and ManageFileErrorResponse pattern; commit.md has language-agnostic "Testing MCP JSON in tests" note.

### 13. Clarify Coverage Handling for Focused Work — ✅ IMPLEMENTED (2026-01-29)

- Extend commit / implement prompts with a short **“Coverage Interpretation”** note that:
  - Emphasizes that new or modified code must meet ≥95% coverage for this phase’s changes, even when running focused tests.
  - Explains that global `fail-under=90` failures dominated by untouched modules should be logged as technical debt in `progress.md` / `activeContext.md` (and, where appropriate, new coverage-raising phases), not “fixed ad hoc” during unrelated, narrow tasks.
- **Changes** (all applied): implement-next-roadmap-step and commit.md have "Coverage Interpretation for Focused Work" with recording coverage debt wording and reference to coverage-improvement plans.

### 14. Harden Session-Analysis Prompts Against Missing Telemetry and Fragile Transcript Paths — ✅ IMPLEMENTED (2026-01-29)

- Update session-optimization agents (e.g., `session-optimization-analyzer.md` and related prompts) to:
  - Treat `analyze_context_effectiveness()` returning `status: "no_data"` as expected for workflow-only sessions and fall back to Memory Bank diffs, git/file diffs, and recent MCP tool invocations.
  - Discover transcripts dynamically by listing `agent-transcripts` directories and selecting the most recent transcript whose recorded `rootdir` matches the current project, instead of relying on hardcoded transcript IDs or paths.
- Add guidance for a **“multi-signal”** analysis approach that:
  - Prioritizes Memory Bank files (`progress.md`, `activeContext.md`, phase plans) and structured tool responses as primary signals.
  - Uses transcripts and `load_context` traces as helpful but optional inputs rather than single points of failure for session optimization.
- **Changes** (all applied): session-optimization-analyzer has Multi-Signal Analysis, no_data handling, dynamic transcript discovery; analyze-session-optimization.md has no_data fallback.

- **Phase 60** – Improve `manage_file` discoverability and error UX  
- **Roadmap Sync & Validation Error UX plan** (`roadmap-sync-validation-error-ux.md`)  
- **Enhance Tool Descriptions plan** (`enhance-tool-descriptions.plan.md`)  

This phase coordinates and amplifies those efforts by turning concrete session findings into Synapse rule and prompt changes.

## Testing Strategy (MANDATORY, ≥95% Coverage for New Work)

- **Rule/Prompt Consistency Tests**:
  - Add or update tests (where applicable) to verify:
    - New JsonValue boundary rules are enforced in any helper functions with typing tests or static analysis expectations.
    - Roadmap-sync behavior is exercised in scenarios with:
      - Missing roadmap entries,
      - References to non-existent files,
      - Benign path-style mismatches.
    - Commit pipeline tests cover Step 12 fix-then-check ordering.
- **Integration Tests**:
  - Extend existing `/cortex/commit` and roadmap-sync integration tests to:
    - Assert that benign `invalid_references` do not block commit when TODO tracking is correct, but critical issues do.
    - Verify that formatting fix+check sequencing is respected and no parallelization occurs.
  - Add tests for `manage_file` usage through MCP to ensure missing `file_name`/`operation` is caught and surfaced clearly.
- **Edge Cases**:
  - Test JsonValue normalization helpers with:
    - `None`, `int`, `float`, numeric strings, and invalid strings.
  - Test roadmap-sync with mixed valid/invalid references.
- **Coverage Target**:
  - Achieve ≥95% coverage for all new helper logic and any new code paths added to validators, agents, or prompts-adjacent scripts.
  - Ensure no reduction in existing coverage for related modules.

## Risks and Mitigations

- **Risk**: Over-constraining roadmap-sync behavior and blocking legitimate commits.  
  - **Mitigation**: Clearly separate critical vs. non-critical issues and document behavior in both agents and prompts.

- **Risk**: Inconsistent application of JsonValue normalization patterns across existing utilities.  
  - **Mitigation**:Add explicit rules, examples, and a small inventory of MCP boundary helpers to audit.

- **Risk**: Increased complexity in commit prompts.  
  - **Mitigation**: Kee new wording concise and focused on sequencing/semantics, avoiding redundant detail already covered in agents.

## Timeline (Rough, Updated with Critical Priorities)

- **Day 1 (CRITICAL)**:
  - Harden `mit.d` against unauthorized git writes (Step 0) — ✅ Step 0 implemented 2026-01-29
  - Make Step 11 submodule handling deterministic (Step 1) **+ Add Step 11.5 validation (CRITICAL - NEW)** — ✅ Step 11.5 implemented 2026-01-29
  - Strengthen Step 11 validation requirements (enhancement to Step 1)
  These address the highest-severity failures including the newly discovered submodule validation gap.
- **Day 2 (H)**:
  - Enforce roadmap_sync as a true commit gate (Step 2)
  - Update plan archiver to use preferred tool primitives (Step 3)
  - Add MCP tool failure investigation section (enhancement to Step 8)
- **Day 3**:
  - Update Python rules for JSON-boundary typing (Step 4)
  - Clarify roadmap-sync blocking semantics (Step 5)
  - Add immediate markdown lint validation (Step 6.5 - NEW)
- **Day 4**:
  - Update agents/prompts for final gate ordering (Step 6)
  - `manage_file` usage (Step 7)
  - MCP validation error handling (Step 8)
- **Day 5**:
  - Incorporate remaining recommendations (Steps 9–14)
  - Add/update tests
  - Run full commit pipeline
  - Validate behavior under typical and edge-case scenarios
  - **Test Step 11.5 validation** to ensure it catches uncommitted submodule changes  
