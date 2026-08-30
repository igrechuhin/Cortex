---
title: "Blocker: Implement-Select Must Respect Explicit Plan Targets"
component: "Cortex MCP implement pipeline (selection phase)"
work_type: fix
status: DONE
priority: Blocker
created: 2026-03-12
execution_order: 1
depends_on: []
---

## Blocker: Implement-Select Must Respect Explicit Plan Targets

**Status**: COMPLETE (2026-03-14)
**Priority**: Blocker  
**Complexity**: Medium  
**Category**: Implement pipeline / Selection correctness  
**Component**: Cortex MCP implement pipeline (selection phase)  
**Work Type**: bugfix  
**Execution Order**: 1

## Goal

Ensure that `/user-cortex/implement` honors an explicitly referenced plan (for example, `/user-cortex/implement @.cortex/plans/fix-mcp-plan-tool-argument-bridging.md`) when selecting work, instead of silently choosing another roadmap item with similar priority.

## Context

- In this session, `/user-cortex/implement @.cortex/plans/fix-mcp-plan-tool-argument-bridging.md` was invoked.  
- The `implement-select` subagent instead chose `[MED-8] Reduce Prompt-Alignment Test Fragility` based on roadmap ordering, effectively **ignoring the user’s explicit plan reference**.  
- This undermines user intent and can cause work on the wrong plan, confusion about progress, and misaligned updates in the memory bank.

We need a clear, deterministic contract for how explicit plan references interact with roadmap priority ordering.

## Completion Summary (2026-03-14)

All implementation steps are complete:

- **Prompt/docs layer**: Explicit-plan-first selection precedence documented; `implement-select` accepts and prefers `explicit_plan_path` hints.
- **Runtime layer** (`.claude/agents/implement-select.md`): Step 0 reads `pipeline_handoff` for `explicit_plan_path`; Step 2a resolves the plan, validates eligibility (not archived/COMPLETE, dependencies not blocked), selects it as primary if eligible, falls back to roadmap ordering with a note if not.
- **Tests**: `tests/tools/test_implement_select_explicit_plan_prompt.py` covers all three scenarios (no explicit plan, valid explicit plan, invalid/ineligible).
- **No additional wiring needed**: The agent file fully enforces the contract at runtime.

## Implementation Steps

### Step 1: Define selection precedence rules

1. Document the desired selection behavior for `/user-cortex/implement` when a plan file or slug is explicitly provided (e.g., via `@.cortex/plans/<slug>.md` or plan title):
   - If a valid, existing plan is explicitly referenced, **prefer that plan** as the selected work item unless it is explicitly blocked (e.g., dependency not satisfied, status COMPLETE/ARCHIVED).
   - If the referenced plan does not exist or is not eligible, fall back to the standard roadmap priority order (Blockers → Active Work → Pending plans).
2. Align these rules with roadmap semantics (Blocker/High/Medium) and ensure they are recorded in the implement prompt/agent documentation.

### Step 2: Extend implement-select to accept explicit plan hints

1. Update the `implement-select` subagent interface and orchestration so that it can receive:
   - An optional `explicit_plan_path` (e.g., `.cortex/plans/fix-mcp-plan-tool-argument-bridging.md`).
   - Or an `explicit_plan_slug/title` if that is how the agent is invoked.
2. Have `implement-select`:
   - Resolve the referenced plan via the `plan` MCP tool or direct plan file lookup (using `get_structure_info` and plan listing helpers).
   - Validate that the plan is not archived and has a status that allows work (e.g., `PENDING` or `IN_PROGRESS`).

### Step 3: Implement explicit-plan-first selection logic

1. In `implement-select`’s selection algorithm:
   - If an eligible explicit plan is provided, construct the selected step from that plan and return it as the primary result, including its roadmap section and metadata.
   - Only if the explicit plan is missing, archived, or ineligible, proceed to the normal roadmap-scanning logic (Blockers → Active Work → Pending plans).
2. Ensure that the selected step includes:
   - `selected_step_title` and `selected_step_description` derived from the plan and any roadmap entry.
   - `selected_step_section` that clearly marks whether this came from an explicit-plan override vs. normal roadmap order.

### Step 4: Update prompts and documentation

1. Update the `/user-cortex/implement` prompt (and any related docs) to:
   - Describe how to target a specific plan (e.g., `@.cortex/plans/<slug>.md`).
   - State that explicit plan references take precedence over roadmap ordering, subject to eligibility checks.
2. Add guidance for other agents and tools that invoke `/user-cortex/implement` so they can pass explicit plan hints when appropriate.

### Step 5: Add tests for selection behavior

1. Add unit and/or integration tests for `implement-select` to cover:
   - Case A: No explicit plan provided → selection falls back to roadmap priority order (current behavior).
   - Case B: Explicit plan provided and eligible → that plan is selected, even if a different Medium-priority item is earlier in the roadmap.
   - Case C: Explicit plan provided but archived/COMPLETE or blocked → implement-select reports an appropriate error or falls back to roadmap ordering with a clear note.
2. Add a regression test mirroring this session’s scenario (explicitly targeting `fix-mcp-plan-tool-argument-bridging.md` while `[MED-8]` is also present) and assert that the explicit plan is selected.

## Verification Checklist

| What to search for | Search scope | Expected result |
|---|---|---|
| `explicit_plan` or `explicit_plan_path` handling in implement-select | Implement selection code / MCP subagent | Logic to honor explicit plan hints exists and is covered by tests |
| `/user-cortex/implement @.cortex/plans/` usage docs | Implement prompt / docs | Documented behavior that explicit plans are preferred over roadmap ordering when eligible |
| Integration test for explicit plan selection | Tests for implement-select / implement pipeline | Test case passes, confirming referenced plan is chosen |

## Dependencies

- Existing `plan` MCP tool and plan listing helpers to resolve plan slugs/paths.  
- Implement-selection subagent and its orchestration layer must be modifiable in this phase.

## Success Criteria

- When a user invokes `/user-cortex/implement` with an explicit plan reference, that plan is selected if it exists and is eligible.  
- Roadmap priority ordering is used only as a fallback when no explicit plan is provided or the reference is invalid/blocked.  
- Tests and documentation clearly reflect the new selection precedence contract.

## Testing Strategy

- **Coverage Target**: ≥95% for new selection-path logic.  
- Add tests for explicit plan precedence, fallback behavior, and error reporting when an explicit plan is invalid or blocked.  
- Run the full implement pipeline in a test environment with an explicit plan reference to confirm the correct plan is chosen and end-to-end behavior is stable.
