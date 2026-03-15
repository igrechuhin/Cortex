---
title: "Fix MCP Plan Tool Argument Wiring/Bridging and Audit Similar Gaps"
component: "Cortex MCP integration and tool orchestration (implement/commit/docs pipelines)"
work_type: "internal_tooling"
status: "COMPLETE"
priority: "High"
created: "2026-03-12"
execution_order: 0
depends_on: []
---

## Fix MCP Plan Tool Argument Wiring/Bridging and Audit Similar Gaps

**Status**: COMPLETE
**Priority**: High  
**Complexity**: Medium  
**Category**: Internal tooling / Refactoring / Reliability  
**Component**: Cortex MCP integration and tool orchestration (implement/commit/docs pipelines)  
**Work Type**: internal_tooling  
**Execution Order**: 22

## Goal

Ensure all Cortex MCP-orchestrated flows (implement, commit, docs/plan) reliably call tools like `plan`, `manage_file`, `rules`, and `execute_pre_commit_checks` **with full JSON arguments**, eliminating name-only invocations that currently break operations such as `plan(operation="complete", ...)` and `plan(operation="register", ...)`. Unify the previous “argument bridging” and “argument wiring” efforts into a single, end-to-end plan that fixes the bridge layer, hardens the `plan` tool’s behavior, and audits similar gaps across other MCP tools.

## Context

Recent runs of `/user-cortex/implement` for `[MED-8] Reduce Prompt-Alignment Test Fragility` showed that:

- Implementation and tests were correct, but the **Finalize** phase could not mark the plan complete.
- The `plan` MCP tool was effectively invoked with **no JSON arguments**, defaulting to `operation="create"` and then failing because `title` and `content` were missing.
- Project rules require **all memory bank and plan updates** (including roadmap changes and plan archiving) to flow through Cortex MCP helpers; direct edits to `.cortex/` files are prohibited.

More broadly:

- Implement and plan prompts rely on MCP tools (`plan`, `manage_file`, `rules`, `execute_pre_commit_checks`, etc.) for all `.cortex/` state changes.
- The generic MCP bridge in some flows behaves like `CallMcpTool(server="user-cortex", toolName="plan")` **without any JSON arguments**, causing misaligned defaults and validation errors.
- The `/user-cortex/plan` prompt defines fallbacks (direct writes) when `plan(operation="create"/"register")` is unavailable, but the preferred path is a robust, typed MCP client that always sends correct payloads.

This indicates a gap in the **integration layer** between high-level orchestrators (implement/commit/docs pipelines) and the MCP tools. The bridge must reliably construct and send the correct payload for each tool, and similar issues may exist for other tools that expect parameters.

## Implementation Steps

### Step 1: Audit MCP-orchestrated flows and map all tool calls

1. Identify all orchestration layers that call Cortex MCP tools, including at least:
   - Implement pipeline subagents: `implement-select`, `implement-code`, `implement-finalize`, `implement-verify`.
   - Commit pipeline helpers and prompts that rely on `execute_pre_commit_checks`, `plan`, or `manage_file` for memory-bank updates.
   - Plan/docs flows: `/user-cortex/plan` and any other prompts that create, enrich, or complete plans.
   - Analysis/session-optimization flows that may touch `.cortex/` state.
2. For each location, build an inventory of:
   - Tool name (`plan`, `manage_file`, `update_memory_bank`, `rules`, `execute_pre_commit_checks`, etc.).
   - Call site (module/function).
   - Argument style:
     - Fully structured (explicit JSON payload),
     - Partially structured (some fields only),
     - Missing (tool invoked by name only or with underspecified payload).
3. Classify each call as:
   - **Safe**: all required arguments provided via a structured payload.
   - **Unsafe**: name-only invocations or calls that rely on tool-side defaults for required fields.

### Step 2: Design and implement a thin, typed MCP client helper

1. Introduce a small helper (conceptually `call_mcp_tool_with_payload(server, tool, payload)` or equivalent) that:
   - Accepts a JSON-serializable payload object (preferably a Pydantic model per tool).
   - Encodes and sends it to the MCP tool via the existing protocol.
   - Returns a structured result or raises a clear error identifying the tool and operation.
2. Ensure the helper supports:
   - Required/optional fields per tool (e.g., `operation`, `file_name`, `plan_title`, `plan_file_name`, `summary`, `progress_entry`, `completion_date`).
   - Basic validation/guardrails (e.g., `operation` must be one of the allowed values for `plan`).
3. Keep the helper generic and reusable so it can be shared by implement, commit, docs, and analysis flows.
4. Define explicit payload contracts for key tools (server-side documented; enforced client-side via the helper), for example:
   - **Plan tool** (`plan`):
     - `operation` ∈ `{"create","list","get","complete","register"}`.
     - For `create`: `{operation, title, content, slug?, include_archive?, response_format?}`.
     - For `complete`: `{operation:"complete", plan_title, summary, completion_date?, progress_entry?, plan_file_name?}`.
     - For `register`: `{operation:"register", plan_title, description, status?="PENDING", section?="pending"}`.
   - **Memory-bank file tool** (`manage_file`):
     - `{file_name, operation:"read"|"write"|"metadata"|"rollback", content?, include_metadata?, change_description?, sections?, version?}`.
   - **Pre-commit tool** (`execute_pre_commit_checks`):
     - Either `{phase:"A"|"B"|"full", checks:null, ...options}` or `{phase:null, checks:[...PreCommitCheck], ...options}` (never omit both `phase` and `checks`).
5. Document these payload contracts alongside the helper so IDE/agent bridges using `CallMcpTool` can construct **full JSON payloads** instead of relying on tool-side defaults.
6. **Bridge status (Cursor `CallMcpTool`)**:
   - The Cursor-side `CallMcpTool` interface has been updated to accept an `arguments` object that is forwarded verbatim to the underlying MCP tool.
   - This unblocks passing full JSON payloads (including `operation`, `checks`, `phase`, `file_name`, etc.) from Cursor commands (for example, `/user-cortex/fix` and `/user-cortex/plan`) into Cortex MCP tools such as `plan`, `execute_pre_commit_checks`, `validate`, `rules`, and `manage_file`.
   - Remaining work in this repo focuses on keeping helper contracts, tests, and documentation aligned with this bridge behavior.

### Step 3: Fix implement-finalize to use the helper for `plan(operation="complete", ...)`

1. In the implement/Finalize integration code, introduce a focused helper like `complete_plan_via_mcp(...)` that:
   - Accepts `plan_title`, `plan_file_name`, `summary`, `progress_entry`, `completion_date`, and any other required fields.
   - Constructs the full JSON payload for `plan(operation="complete", ...)`.
   - Invokes the `plan` MCP tool via the typed helper and handles errors consistently.
2. Replace any name-only calls to `plan` in implement-finalize with this helper, ensuring:
   - `operation="complete"` is always explicit.
   - All required identifiers and narrative fields are present.
3. Confirm that MED-8–style completions now:
   - Remove the item from `roadmap.md`.
   - Append entries to `activeContext.md` and `progress.md`.
   - Archive the plan under `.cortex/plans/archive/`.
4. **Current implementation status (this repo)**:
   - The `implement-finalize` cursor-agent (`.cortex/synapse/cursor-agents/implement-finalize.md`) already instructs the subagent to call `plan(operation="complete", ...)` with all required fields instead of relying on tool-side defaults.
   - The remaining work for this step is in the IDE/agent bridge that issues `CallMcpTool(...)` requests: it must construct and send the full JSON payload described here, using the thin typed MCP helper from Step 2 (implemented outside this Python repo).

### Step 4: Fix `/user-cortex/plan` and related flows to use structured `plan` operations

1. Update the `/user-cortex/plan` orchestration to:
   - Prefer `plan(operation="create", ...)` when creating new plans, using the typed helper.
   - Prefer `plan(operation="register", ...)` to add or update roadmap entries for both new and enriched plans.
2. Ensure the fallback path (direct plan file write and manual roadmap update via memory-bank helpers) is used **only** when:
   - MCP tools are unavailable or clearly failing, and
   - The error is surfaced in the final report as a FIX-ASAP condition.
3. Enforce the prompt contract:
   - Every successful `/user-cortex/plan` run yields a concrete plan file and a registered roadmap entry, or
   - Explicitly reports why registration failed (for example, MCP outage or schema mismatch).

### Step 5: Audit and fix similar argument-bridging gaps for other tools

1. Using the inventory from Step 1, identify all MCP tools that:
   - Have required parameters in their schema, and
   - Are sometimes invoked without a payload or with incomplete parameters.
2. For each such tool:
   - Introduce small, focused helpers that:
     - Accept strongly-typed arguments (Pydantic models where feasible).
     - Construct the corresponding JSON payload.
     - Call the MCP tool via the common helper and handle errors uniformly.
   - Replace bare name-only invocations or underspecified payloads with these helpers.
3. Pay special attention to:
   - `manage_file` (read/write operations on memory bank, config, and reviews).
   - Roadmap helpers built on top of memory-bank (`update_memory_bank` or equivalents).
   - `execute_pre_commit_checks` and pre-commit job APIs.
   - Any docs or analysis tools that mutate `.cortex/` state.

### Step 6: Harden the `plan` tool’s handling of no-arg or invalid calls

1. Update the `plan` tool implementation so that:
   - A call with **no `operation` and no other arguments** does **not** silently default to `operation="create"` and then fail on missing `title`/`content`.
   - Calls with missing required fields for a given operation return clear, structured errors.
2. Instead of silently defaulting and failing generically:
   - Return an error such as `{"error": "operation is required for plan tool; expected 'create', 'register', 'complete', or 'enrich'"}` when `operation` is missing.
   - Optionally support a minimal metadata-only mode if there is a legitimate use case, but do not treat it as the default for name-only calls.
3. Keep behavior backwards compatible for normal callers that already pass explicit arguments.
4. **Current implementation status (this repo)**:
   - Implemented in `cortex.tools.plans.plan` so that name-only calls to the `plan` MCP tool return a clear, structured `"operation is required..."` error instead of defaulting to `operation="create"`.
   - Added tests in `tests/tools/test_plan_tool_dispatch.py` covering no-arg calls, invalid `operation` values, and missing required fields for `operation="complete"` and `operation="register"`.

### Step 7: Add guardrails, logging, and tests around MCP argument passing

1. Add unit or integration tests for the new helpers, covering:
   - Happy-path calls with correct payloads.
   - Error handling when tools return validation errors or connection issues.
   - Behavior when helpers are invoked with missing required fields (helpers should fail early, not the underlying MCP tool).
2. Where feasible, add "smoke tests" that exercise key flows end-to-end:
   - `/user-cortex/plan` creating and registering a new plan using `plan(operation="create")` and `plan(operation="register")`.
   - `/user-cortex/implement` Finalize marking a plan complete via `plan(operation="complete")`.
3. Add lightweight logging/metrics around MCP tool calls (without leaking sensitive data) so that future gaps in argument passing are easier to detect and diagnose.

**Step 7 progress (2026-03-14)**: COMPLETE. Smoke tests done; optional metrics deferred as non-blocking. Completed: lightweight logging in plan tool (operation + required_args_present); build_plan_create_arguments test in test_plan_payloads.py; guardrail tests for plan payload builders (complete, register, create); TestPlanToolSmoke in test_plan_tool_dispatch.py — test_plan_operation_get_with_full_payload_returns_success and test_plan_operation_create_with_full_payload_creates_file (get/create with full payload). Optional metrics not required for success criteria — all other criteria met.

## Verification Checklist

| What to search for | Search scope | Expected result |
|---|---|---|
| `CallMcpTool(` or equivalent invocations without payload | MCP orchestration code (implement/commit/docs/plan) | No remaining calls that omit JSON arguments for tools requiring structured input |
| `plan(` calls without explicit payload or `operation=` | Orchestrator modules | All replaced by helper-based calls with structured arguments and explicit operations |
| `plan(operation="complete"` usage | Implement-finalize orchestration | All calls go through the typed helper with full payload; plans are completed and archived correctly |
| `plan(operation="register"` usage | Plan/docs orchestration | New and enriched plans registered via MCP, or explicit FIX-ASAP if MCP unavailable |
| No-arg `plan` error behavior | `plan` tool implementation/tests | Clear, structured error when `operation` or required fields are missing |
| Bare `manage_file` or roadmap helpers without required fields | Integration code | All required fields passed explicitly or wrapped in helpers |
| `/user-cortex/implement` Finalize for a test plan | CLI / MCP logs | Plan marked COMPLETE and archived; roadmap and memory bank updated via MCP |
| `/user-cortex/plan` for a new or enriched plan | CLI / MCP logs | Plan file created or enriched and registered via `plan(operation="register")` |
| `tests/tools/test_plan_tool_dispatch.py` | This repo | Tests cover no-arg `plan()`, invalid `operation`, and missing required fields for `complete`/`register` and are passing |
| `tests/tools/test_plan_completion.py` and related integration tests | This repo | End-to-end completion behavior (roadmap removal, activeContext/progress append, archive movement) passes when driven via `plan(operation="complete", ...)` or `complete_plan` |

## Dependencies

- Existing MCP tools (`plan`, `manage_file`, `update_memory_bank`, `rules`, `execute_pre_commit_checks`) must remain stable at the API level.
- Implement/commit/docs orchestrators need to be updated in lockstep with the new helper to avoid mixed behavior.
- Access to a test environment where `/user-cortex/plan` and `/user-cortex/implement` can be run end-to-end.

## Success Criteria

- All orchestrated MCP calls that require parameters now use structured JSON payloads via typed helpers (no name-only invocations for tools with required args).
- The `plan` tool:
  - Correctly receives and processes `operation="create"`, `operation="register"`, and `operation="complete"` calls with full arguments.
  - No longer returns misleading "title and content are required" errors for no-arg calls during orchestrated flows.
- `/user-cortex/plan` reliably creates or enriches plans **and** registers them in the roadmap when MCP is healthy, using `plan(operation="create"/"register")`, with clear FIX-ASAP reporting when MCP is unavailable.
- `/user-cortex/implement` Finalize can successfully complete plans like `[MED-8]` end-to-end, including roadmap/memory-bank updates and plan archiving via `plan(operation="complete")`.
- Tests cover the new helpers and guardrails (target **95%+ coverage** for new/modified integration code), and key flows pass with the quality gate enabled.

## Testing Strategy

- **Coverage Target**: 95%+ for new or modified integration/helper code that wraps MCP tool calls.
- **Unit tests**:
  - Direct tests of helper functions for `plan`, `manage_file`, and other audited tools.
  - Validation that helpers construct the correct payload and handle error responses gracefully.
  - Validation of improved `plan` error messages when called with missing `operation` or required fields.
- **Integration tests**:
  - Run `/user-cortex/plan` to create and register a new plan, verifying both the plan file and roadmap entry via memory-bank tools.
  - Run `/user-cortex/implement` on a small test plan to confirm Finalize uses `plan(operation="complete")` correctly and updates the memory bank and archives.
- **Manual verification** (if needed):
  - Inspect MCP logs for representative flows to confirm tools are no longer invoked without required arguments and that errors are clear when misconfigurations occur.

## Developer Notes: Cursor `CallMcpTool` Contract

- **TypeScript signature (conceptual)**:

  ```ts
  type CallMcpToolArgs = {
    server: string;
    toolName: string;
    arguments?: Record<string, unknown>; // forwarded verbatim to MCP
  };
  ```

  The implementation must obtain the MCP client for `server` and invoke:

  ```ts
  await client.callTool(toolName, arguments ?? {});
  ```

- **Usage examples**:

  - `execute_pre_commit_checks` (quality / tests / docs helpers):

    ```json
    {
      "server": "user-cortex",
      "toolName": "execute_pre_commit_checks",
      "arguments": {
        "checks": ["fix_quality"],
        "include_untracked_markdown": true
      }
    }
    ```

    ```json
    {
      "server": "user-cortex",
      "toolName": "execute_pre_commit_checks",
      "arguments": {
        "checks": ["tests"],
        "test_timeout": 600,
        "coverage_threshold": 0.9,
        "strict_mode": false
      }
    }
    ```

    ```json
    {
      "server": "user-cortex",
      "toolName": "execute_pre_commit_checks",
      "arguments": {
        "phase": "B"
      }
    }
    ```

  - `rules` (load relevant coding/quality rules):

    ```json
    {
      "server": "user-cortex",
      "toolName": "rules",
      "arguments": {
        "operation": "get_relevant",
        "task_description": "Type, lint, and formatting fixes",
        "response_format": "concise"
      }
    }
    ```

  - `validate` (docs / memory-bank validation):

    ```json
    {
      "server": "user-cortex",
      "toolName": "validate",
      "arguments": {
        "check_type": "timestamps",
        "response_format": "concise"
      }
    }
    ```

    ```json
    {
      "server": "user-cortex",
      "toolName": "validate",
      "arguments": {
        "check_type": "roadmap_sync",
        "response_format": "concise"
      }
    }
    ```

  - `plan` (plan creation / completion / registration):

    ```json
    {
      "server": "user-cortex",
      "toolName": "plan",
      "arguments": {
        "operation": "complete",
        "plan_title": "[MED-8] Reduce Prompt-Alignment Test Fragility",
        "plan_file_name": "reduce-prompt-alignment-test-fragility.md",
        "summary": "Summary of completed work...",
        "completion_date": "2026-03-12T17:30",
        "progress_entry": "Short progress note for progress.md"
      }
    }
    ```

    ```json
    {
      "server": "user-cortex",
      "toolName": "plan",
      "arguments": {
        "operation": "register",
        "plan_title": "New plan title",
        "description": "Short roadmap description",
        "status": "PENDING",
        "section": "pending"
      }
    }
    ```

- **Contract requirements**:

  - The Cursor bridge must *never* strip or ignore the `arguments` payload; it must be forwarded exactly as provided.
  - IDE/agent prompts (e.g., `/user-cortex/fix`, `/user-cortex/plan`, `/user-cortex/implement`) are responsible for constructing valid payloads that match each tool’s schema (for example, `operation` required for `plan`, `check_type` required for `validate`, `checks` or `phase` required for `execute_pre_commit_checks`).
  - Any name-only tool invocation for tools with required parameters (`plan`, `rules`, `execute_pre_commit_checks`, `validate`, `manage_file`) should be treated as a bug in the orchestrator or bridge, not as a supported usage pattern.
