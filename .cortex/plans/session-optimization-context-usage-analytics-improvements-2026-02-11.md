# Session Optimization: Context & Usage Analytics Improvements (2026-02-11)

## Status

Status: PENDING

## Overview

This plan implements improvements suggested by the end-of-session analysis on 2026-02-11, focusing on:

- Context loading effectiveness for commit/test and fix/debug sessions
- Usage analytics observability (structured failure output, test failure visibility)
- Guardrails to keep low-relevance files out of default context while preserving discoverability

## Goals

- Maintain or improve high token utilization (current session ~0.86, global ~0.52) while avoiding over-provisioning.
- Ensure at least one always-on path to see failing test names and assertions even when MCP test output is truncated.
- Keep `activeContext.md`, `techContext.md`, `systemPatterns.md`, `roadmap.md`, `productContext.md` as high/medium value defaults; treat `projectBrief.md` and synthetic files as opt-in.

## Current Findings (2026-02-11 Analysis)

- **Context effectiveness (current session)**:
  - 4 `load_context` calls; avg token utilization **0.856**; avg files selected **4.5**; avg relevance **0.667**.
  - Task patterns this session: `update/modify` (1), `testing` (3).
  - Selected files consistently: `techContext.md`, `systemPatterns.md`, `productContext.md`, `projectBrief.md`, `activeContext.md`, `roadmap.md`.
- **Global usage statistics**:
  - 35 sessions, 45 total calls; avg token utilization **0.517**, avg files selected **5.84**, avg relevance **0.611**.
  - Most common task type: **implement/add** (13), then `other` (10), `testing` (6), `fix/debug` (5).
  - `techContext.md` is most frequently loaded (39/45 calls).
  - File effectiveness:
    - `activeContext.md`: high value (avg relevance ~0.81, 30 selections).
    - `techContext.md`, `systemPatterns.md`, `productContext.md`, `roadmap.md`, `progress.md`: moderate value.
    - `projectBrief.md` and synthetic files (`file.md`, `tmp-mcp-test.md`) have **low average relevance**.
- **Budget recommendations**: All task types except `review` are well served by a 10k budget; `review` prefers 15k.
- **Gap observed this session**: MCP `execute_pre_commit_checks(checks=["tests"])` reports 1 failing test with coverage 90.2%, but the structured output does not surface the failing test name/traceback, and local `pytest` is not available in the agent environment.

## Scope

This plan focuses on:

1. **Context defaults and hygiene** for commit, testing, and fix/debug flows.
2. **Usage analytics / test-failure observability** (ensuring test names and key failures are visible in structured MCP output or logs).
3. **Rules/docs alignment** so future agents follow the same patterns.

## Non-Goals

- Broad refactor of context analytics engine internals.
- Changing memory-bank schema or file responsibilities beyond what is already tracked in `reconsider-memory-bank-structure.md`.

## Work Items

### 1. Context Defaults for Commit/Test and Fix/Debug

1.1 **Ensure high-value files are always considered**

- Confirm commit/test prompts (AGENTS.md, commit.md, fix-tests.md) explicitly mention the high-value set:
  - `activeContext.md`, `techContext.md`, `systemPatterns.md`, `roadmap.md`, `productContext.md`, `progress.md`.
- Add a short rule to memory-bank-workflow.mdc that these are the **default context set** for commit/test/fix-debug tasks.

1.2 **Demote low-relevance files from default context**

- Update memory-bank-workflow.mdc and any relevant prompts to **not** include `projectBrief.md` and synthetic files (e.g. `file.md`, `tmp-mcp-test.md`) in default context for commit/test/fix-debug.
- Keep them discoverable via `load_context` search and explicit selection, but not auto-loaded.

1.3 **Tune default token budgets**

- Validate that the existing mapping (10k for update/implement-add, 15k for fix-debug/other, etc.) is aligned with the latest statistics (global avg utilization ~0.52).
- Adjust descriptions in CLAUDE.md and implement-next-roadmap-step.md to clarify that 10k is sufficient for most tasks, and higher budgets should be used only for large refactors or reviews.

### 2. Usage Analytics & Test Failure Observability

2.1 **Improve MCP tests output for failures**

- In `execute_pre_commit_checks` / tests adapter, ensure that when tests fail:
  - `results.tests.errors` (or equivalent field) contains at least:
    - Fully-qualified test names of failing tests.
    - Assertion messages and 1–2 lines of traceback context.
- Add unit tests in `tests/tools/test_execute_pre_commit_checks.py` (or equivalent) to assert that a synthetic failing test populates this structured error payload.

2.2 **Surface failing tests in usage analytics when relevant**

- Optionally extend usage analytics tools (or a thin wrapper) so that **commit/test workflows** can quickly retrieve the last failing test names from a structured field, without parsing huge raw logs.
- Keep this opt-in and read-only (no schema change for usage events required).

2.3 **Document fallback strategy for agents when test output is truncated**

- Update commit.md and fix-tests.md with a short section:
  - When `execute_pre_commit_checks(checks=["tests"])` reports failures but the structured error array is empty or truncated, agents should:
    - Prefer a dedicated `/cortex/fix-tests` or `/cortex/diagnose-tests` command rather than guessing.
    - Ask the user for a local `pytest` snippet when absolutely necessary.

### 3. Rules and Documentation Alignment

3.1 **Synapse rules for context defaults**

- Add or update a Synapse rule (e.g. `general/context-selection.mdc`) to encode:
  - High-value vs. low-value memory-bank files for default commit/test/fix-debug context.
  - Guidance to avoid auto-loading `projectBrief.md` and synthetic test files for those tasks.

3.2 **AGENTS.md and CLAUDE.md updates**

- Add a short subsection under the context workflow in CLAUDE.md and AGENTS.md:
  - Summarizing current context-effectiveness metrics.
  - Recommending the high-value default set per task type.
  - Emphasizing that `load_context` should be called at task start and that agents should use the statistics (when available) to reason about over/under-provisioning.

3.3 **Tests for rules/docs alignment**

- Add or extend tests that assert commit/fix-tests/implement prompts:
  - Mention the correct high-value file set.
  - Do not require `projectBrief.md` for commit/test/fix-debug flows.

## Success Criteria

- New end-of-session context statistics (after this plan is implemented) show:
  - Average token utilization at or above current levels for fix/debug and testing tasks.
  - No unnecessary inclusion of low-relevance files in default context for commit/test/fix-debug.
- MCP `execute_pre_commit_checks(checks=["tests"])` exposes failing test names and key messages in structured JSON when tests fail.
- CLAUDE.md, AGENTS.md, and Synapse rules clearly encode context defaults and observability patterns so future agents follow them consistently.
