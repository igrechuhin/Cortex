# Phase 62: Synapse Session Optimization – Harden Prompts and Rules

**Status**: Planning  
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

1. **Codify JSON boundary typing patterns** in Python rules so MCP utilities like `with_mcp_stability` have clear, enforced guidance.
2. **Clarify roadmap-sync semantics** by tightening agent/prompt language around which `invalid_references` categories must block commits.
3. **Make final validation gate ordering explicit** in agents and the commit prompt to avoid accidental parallelization of state-changing steps.
4. **Improve `manage_file` guidance** in agents/prompts to make required parameters and common failure modes obvious.
5. **Treat MCP validation errors as first-class issues** in error-fixer guidance and the commit prompt, feeding them back into Synapse as prompt/rule improvements.

## Implementation Steps

### 1. Strengthen Python JSON-Boundary Typing Rules

- Update `python-coding-standards.mdc` to add a dedicated subsection (e.g., **“JsonValue at MCP Boundaries”**) that:
  - Requires helpers like `_to_timeout_value()` to normalize `JsonValue` inputs (timeouts, metadata, tool params) into concrete Python types before use.
  - States that cross-cutting utilities must either:
    - Accept concrete types only and push JSON normalization to the callers, or
    - Accept `JsonValue` and perform normalization at the top of the function.
  - Includes `with_mcp_stability`-style examples demonstrating the correct pattern.
- Cross-check other MCP utilities that consume `JsonValue` and ensure they follow the same pattern.

### 2. Clarify Roadmap Sync Blocking Semantics

- Update `roadmap-sync-validator.md` and the roadmap-sync prompt to:
  - Distinguish clearly between:
    - **missing_roadmap_entries** (always critical, MUST block commit),
    - **invalid_references** to non-existent files (critical, MUST block commit),
    - **invalid_references** that are path-style mismatches (e.g., `plans/...` vs `../plans/...`) where the target plan exists and TODO tracking is correct (non-critical).
  - Add a “Result Interpretation” section that:
    - Specifies which categories must block commit.
    - Allows commits to proceed when only benign path-style mismatches are present, while logging a warning and creating/updating a small follow-up plan to normalize paths.
- Ensure future `/cortex/commit` logic treats roadmap-sync results according to this clarified policy.

### 3. Enforce Sequential Final Validation Gate Ordering

- Update `code-formatter.md`, `quality-checker.md`, and `commit.md` to:
  - Add explicit bullets under Step 12 (Final Validation Gate):
    - “NEVER run `fix_formatting.py` and `check_formatting.py` in parallel. They MUST run sequentially: first fix, then check.”
    - “Do not interleave other state-changing operations between final formatting fix and check.”
  - Optionally, recommend a single combined invocation (fix then check) as the canonical pattern.
- If needed, add a short note in `plan-archiver`/other agents referencing that Step 12 must be treated as atomic/sequential for formatting.

### 4. Improve `manage_file` Usage Guidance

- Update `memory-bank-updater.md` and any prompts that call `manage_file` to:
  - Add a “Correct `manage_file` Usage” section with:
    - Minimal read example:
      - `manage_file(file_name="activeContext.md", operation="read", include_metadata=False)`
    - Minimal write example including `change_description`.
    - Explicit warning: “`file_name` and `operation` are REQUIRED. Calling `manage_file` without these is a protocol violation and will raise a validation error.”
  - Add an anti-pattern callout:
    - “NEVER call `manage_file({})` or omit `file_name`/`operation`; this indicates a missing plan step or a bug in the orchestration prompt.”
- Ensure commit and memory-bank prompts show at least one full, correct usage example.

### 5. Elevate MCP Validation Errors in Error-Fixer and Commit Prompt

- Update `error-fixer.md` to:
  - Treat MCP argument validation errors (e.g., Pydantic missing fields, wrong types) as **FIX-ASAP** issues.
  - Instruct agents to:
    - Detect these errors in tool responses.
    - Update prompts/rules to always provide required parameters.
    - Re-run the relevant step after prompt/rule adjustments.
- Extend the commit prompt to:
  - Add a checklist item before or within Step 0/Step 12:
    - “Scan recent MCP tool invocations for validation errors; if present, update prompts/rules to eliminate them before proceeding.”

### 6. Tune Context Budgets and Memory Bank Selection Using Session Insights

- Use `analyze_context_effectiveness()` insights from the 2026-01-28 session to:
  - Update context-loading prompts so **fix/debug** and similar narrow tasks default to a smaller token budget (e.g., ~15,000 tokens instead of 50,000), increasing only when utilization regularly exceeds ~70%.
  - Prioritize high-value memory bank files (`activeContext.md`, `roadmap.md`, `progress.md`, and phase-specific plans) and treat consistently low-relevance files (`file.md`, `tmp-mcp-test.md`, `projectBrief.md`, `systemPatterns.md`, `productContext.md`, `techContext.md`) as optional for fix/debug workflows.
  - Document in Synapse prompts how to interpret `file_effectiveness` recommendations (high / moderate / lower relevance) when constructing context for different task types.

## Dependencies

- **Phase 56** – Commit workflow parallelization (Steps 9–11)  
- **Phase 57** – Fix markdown_lint MCP tool timeout  
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
  - **Mitigation**: Add explicit rules, examples, and a small inventory of MCP boundary helpers to audit.

- **Risk**: Increased complexity in commit prompts.  
  - **Mitigation**: Keep new wording concise and focused on sequencing/semantics, avoiding redundant detail already covered in agents.

## Timeline (Rough)

- **Day 1–2**: Update Python rules and clarify roadmap-sync semantics; align roadmap-sync plan.  
- **Day 3–4**: Update agents/prompts for final gate ordering and `manage_file` usage; adjust error-fixer guidance.  
- **Day 5**: Add/update tests, run full commit pipeline, and validate behavior under typical and edge-case scenarios.  
