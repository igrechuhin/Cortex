---
title: Pre-commit MCP heartbeat — dot message instead of fake N/K progress
component: execution
work_type: feature
status: DONE
priority: Medium
created: 2026-04-04
depends_on: []
---

## Goal

Replace the synthetic `tick/total` (e.g. 1…500 of 500) heartbeat in `execute_pre_commit_checks` with **honest liveness signaling**: each ping **adds one dot** to an MCP progress **message**, capped so payloads stay bounded. Avoid implying a meaningful fraction of work when the heartbeat is only keepalive.

## Context

- Today `_heartbeat_loop` in `src/cortex/tools/execution/pre_commit_tools_run_helpers.py` calls `report_progress_safe(ctx, float(tick), float(total))` with a fixed `total = 500` and incrementing `tick` so Cursor sees numeric activity during long subprocess phases (pytest collection, typecheck, etc.).
- That **N/K is not semantically tied** to real progress; it can be misread as fractional completion.
- FastMCP `Context.report_progress(progress, total, message=None)` supports an optional **`message`** (forwarded to `send_progress_notification`). Cortex `report_progress_safe` currently **does not** expose `message`.
- **Risk**: Some hosts may weight **numeric** progress more than `message` for timeouts. The implementation should preserve **monotonic numeric change** if manual verification shows message-only updates are insufficient (e.g. keep increasing `progress` with `total=None`, plus dot `message`).

## Implementation steps

## Step 1 — Extend `report_progress_safe` to forward `message`

- In `src/cortex/core/context_logging.py`, add an optional keyword parameter `message: str | None = None` (default `None`).
- Pass it through to `await ctx.report_progress(progress, total, message=message)` when `ctx` is not `None`.
- Update the docstring to describe `message` as optional client-visible status text (short, safe).
- Add `# AI:` comment only if the choice between keyword-only vs positional needs rationale (e.g. why optional third channel).

**Verification checklist**

| What to search for | Search scope | Files to re-read |
|--------------------|--------------|------------------|
| `report_progress_safe` definition and call into `report_progress` | `src/cortex/core/context_logging.py` | Same file |
| Callers assuming only two arguments | `rg report_progress_safe` repo `src/` `tests/` | Any changed callers |

## Step 2 — Unit tests for `report_progress_safe` with `message`

- In `tests/unit/test_context_logging.py`, add a test that a mock context’s `report_progress` receives `message="..."` when provided.
- Extend or mirror existing tests that assert `total=None` behavior still works with `message`.

**Verification checklist**

| What to search for | Search scope | Files to re-read |
|--------------------|--------------|------------------|
| `test_report_progress_safe` | `tests/unit/test_context_logging.py` | Same file |

## Step 3 — Heartbeat loop: one dot per ping, capped

- In `src/cortex/tools/execution/pre_commit_tools_run_helpers.py`, update `_heartbeat_loop`:
  - Maintain an integer **dot count**; each interval increment by 1, **cap** at a constant (reuse **500** to match prior max ticks, or introduce a named constant e.g. `_HEARTBEAT_MAX_DOTS` next to `_HEARTBEAT_INTERVAL_SECONDS`).
  - Build `message = "." * dot_count` (or append one `"."` per tick up to cap — equivalent).
  - Call `report_progress_safe` with:
    - **Recommended default**: `progress=float(dot_count)`, `total=None`, `message=message` so numeric progress still increases without a misleading denominator; **document** in `# AI:` that `total=None` avoids fake completion semantics while preserving monotonic numbers for strict clients.
    - **Fallback** (only if Step 5 proves insufficient): keep a separate monotonic counter or alternate numeric strategy as documented in Step 5.
  - Update the function docstring to describe dot-based message + cap + why numeric progress may still be present.

**Verification checklist**

| What to search for | Search scope | Files to re-read |
|--------------------|--------------|------------------|
| `_heartbeat_loop` | `pre_commit_tools_run_helpers.py` | Same file |
| `_HEARTBEAT_INTERVAL_SECONDS` | Same module | Same file |

## Step 4 — Integration-style or focused test for heartbeat signaling (optional but preferred)

- If there is no existing test hook for `_heartbeat_loop`, add a **small** unit test that runs the loop for a few iterations with a fast `interval` (patch `asyncio.sleep` to no-op or immediate) and asserts `report_progress_safe` (mocked) receives **increasing dot lengths** and **respects cap**.
- Prefer testing via a thin wrapper or mocking `report_progress_safe` at the module under test to avoid flakiness.

**Verification checklist**

| What to search for | Search scope | Files to re-read |
|--------------------|--------------|------------------|
| `pre_commit_tools_run_helpers` tests | `tests/unit/test_pre_commit_tools.py` or new test file | Chosen test module |

## Step 5 — Manual smoke / host behavior note

- Manually run a long `execute_pre_commit_checks` path in Cursor (or document for the implementer): confirm **no premature -32000 / connection closed** during a deliberately slow phase.
- If message-only or `total=None` breaks keepalive, apply the documented fallback (adjust numeric fields while keeping dot `message`).

**Verification checklist**

| What to search for | Search scope | Files to re-read |
|--------------------|--------------|------------------|
| Troubleshooting / timeout docs mentioning heartbeat | `docs/` | Update only if a one-line note is needed; avoid doc expansion unless required |

## Step 6 — Docs touch (minimal)

- If `docs/development/logging-guidelines.md` documents `report_progress_safe` as two-argument only, add one line for optional `message`.

**Verification checklist**

| What to search for | Search scope | Files to re-read |
|--------------------|--------------|------------------|
| `report_progress_safe` | `docs/development/logging-guidelines.md` | Same file |

## Dependencies

- FastMCP / MCP SDK in use already supports `message` on `report_progress` (verified in environment).

## Success criteria

- Heartbeat no longer reports a **fixed fake total** (e.g. 500) as if it were work units; user-visible signaling is **dot accumulation** with a **hard cap**.
- `report_progress_safe` supports optional `message` with tests; existing callers unchanged in behavior when `message` is omitted.
- Quality gate passes after implementation (`run_quality_gate()` in an MCP-enabled session).
- New/changed lines maintain project typing rules (no `Any`; optional params typed explicitly).

## Testing strategy (95% coverage target)

- **Unit**: `report_progress_safe` with and without `message`; connection-error swallowing unchanged for progress path.
- **Unit**: heartbeat dot length monotonicity and cap (mocked time/sleep).
- **Regression**: existing `execute_pre_commit_checks` tests in `tests/unit/test_pre_commit_tools.py` remain green.
- Aim for **≥95% coverage on touched modules** per project testing standards; do not skip tests without a justified ticket.
