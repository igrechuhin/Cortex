---
title: "Fix broad exception handling and subprocess log fd comment"
component: tools
work_type: fix
status: PENDING
priority: high
created: 2026-03-22
depends_on: []
sources:
  - "code-review-report-2026-03-22T11-58.md (REV-2026-03-22-1, REV-2026-03-22-2)"
  - "Codex audit: Codebase Complexity / Exception-Handling Debt (Medium)"
---

## Goal

Resolve two open code-review items (REV-2026-03-22-1 and REV-2026-03-22-2) and reduce the broader exception-handling debt in MCP tool entrypoints. Narrow or document broad `except Exception` clauses so failures are not silently swallowed, and add the missing subprocess log fd comment to prevent future confusion.

## Context

- **REV-2026-03-22-2** (`project_root_resolver.py:94-98`): `_fetch_roots_path` catches all exceptions after a `TimeoutError` guard with a bare `except Exception`. The fallback is intentional but the exception surface is undocumented — maintainers cannot tell which MCP SDK or transport errors are expected vs. which are bugs.
- **REV-2026-03-22-1** (`pre_commit_detached.py:138-148`): `_spawn_detached_process` opens a log file with `with open(log_file, "w") as lf:` and passes `lf` to `Popen`. On Unix the child inherits the fd after the parent's `with` block closes its handle. No comment explains this behaviour.
- **Codex audit**: Broader pattern — large multi-responsibility handlers and broad `except Exception` in core MCP request paths increase debugging difficulty and regression risk. `tools/__init__.py` uses heavy side-effect imports that make the registration surface brittle.

## Implementation Steps

### Step 1 — Document `_fetch_roots_path` exception catch

1. Read `src/cortex/core/project_root_resolver.py` lines 87–99.
2. Add a one-line comment above the `except Exception` block:

   ```python
   # MCP transport/client implementations may raise varied exceptions
   # (e.g. McpError, ConnectionError, RuntimeError); fall back to
   # get_project_root() for all of them.
   except Exception as e:
   ```

3. Optionally, if the MCP SDK exposes specific exception base types, narrow the catch to those types — check `mcp` package exports first.

#### Verification Checklist — Step 1

| What to check | Search scope | Files to re-read |
|---|---|---|
| Comment present, no trailing spaces | `project_root_resolver.py:87-99` | `src/cortex/core/project_root_resolver.py` |
| Pyright still passes (no narrowing errors) | `uv run pyright src/` | — |
| REV-2026-03-22-2 closed in review tracker | `code-review-report-2026-03-22T11-58.md` | — |

### Step 2 — Add subprocess fd comment to `_spawn_detached_process`

1. Read `src/cortex/tools/execution/pre_commit_detached.py` lines 130–155.
2. Inside `_spawn_detached_process`, immediately after `with open(log_file, "w") as lf:`, add:

   ```python
   # On Unix the child process inherits the fd after the parent's
   # `with` block closes its own handle; this is intentional so
   # stdout/stderr are captured in the detached log file.
   ```

3. Confirm no line-length violations (Black 88 col).

#### Verification Checklist — Step 2

| What to check | Search scope | Files to re-read |
|---|---|---|
| Comment present and correctly placed | `pre_commit_detached.py:138-148` | `src/cortex/tools/execution/pre_commit_detached.py` |
| Black format passes | `uv run black --check src/` | — |
| REV-2026-03-22-1 closed in review tracker | `code-review-report-2026-03-22T11-58.md` | — |

### Step 3 — Audit MCP entrypoints for bare `except Exception`

1. Grep `src/cortex/tools/` for `except Exception` patterns.
2. For each hit, classify:
   - **Intentional fallback** (like `_fetch_roots_path`): add documentation comment per Step 1 pattern.
   - **Accidental broad catch**: narrow to specific exception types or raise domain exception.
3. Do NOT change behaviour — only add comments or narrow types.

#### Verification Checklist — Step 3

| What to check | Search scope | Files to re-read |
|---|---|---|
| All `except Exception` in tools/ have comment or are narrowed | `src/cortex/tools/**/*.py` | Each modified file |
| No new Pyright errors | `uv run pyright src/` | — |
| Tests still pass | `run_quality_gate()` | — |

### Step 4 — Evaluate `tools/__init__.py` import side-effects

1. Read `src/cortex/tools/__init__.py`.
2. Identify side-effect imports (module-level code with observable external effects at import time).
3. If any registration code runs at import time and could be deferred, file a follow-up Refactoring plan — do NOT refactor in this fix plan.
4. Document findings in `activeContext.md` under a new entry.

#### Verification Checklist — Step 4

| What to check | Search scope | Files to re-read |
|---|---|---|
| Side-effect import inventory documented | `src/cortex/tools/__init__.py` | `.cortex/memory-bank/activeContext.md` |
| No source changes made in this step | `git diff src/cortex/tools/__init__.py` | — |

### Step 5 — Run quality gate and update memory bank

1. Call `run_quality_gate()` — must pass with zero errors.
2. Update `activeContext.md` — add completed entry for this plan.
3. Update `progress.md` — mark REV-2026-03-22-1 and REV-2026-03-22-2 RESOLVED.

## Dependencies

- None (self-contained to `src/cortex/core/` and `src/cortex/tools/execution/`).

## Success Criteria

- REV-2026-03-22-1 and REV-2026-03-22-2 marked RESOLVED in the review issue tracker.
- All `except Exception` clauses in MCP tool entrypoints either documented or narrowed.
- `run_quality_gate()` passes: zero errors, all tests green, coverage ≥ 91%.
- No new Pyright warnings introduced.

## Testing Strategy (95% coverage target)

- Existing `tests/unit/test_project_root_resolver.py` covers the `list_roots` exception fallback — re-run to confirm no regression.
- Add one unit test in `test_project_root_resolver.py`: assert that a generic `RuntimeError` from `list_roots` still results in `get_project_root(None)` being called (covers the documented exception surface).
- Existing `pre_commit_detached` tests cover `_spawn_detached_process` behaviour — re-run to confirm no regression from comment-only change.
- New tests for any narrowed `except` clauses must cover both the specific exception type and a fallback path.
