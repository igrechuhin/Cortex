---
title: "Narrow broad exception handlers in markdown_lint_core.py"
component: tools/files
work_type: fix
status: PENDING
priority: Medium
created: 2026-03-21
depends_on: []
---

## Goal

Replace the three broad `except Exception` catches in `markdown_lint_core.py` with specific exception types to prevent silent bug masking and improve diagnostics.

## Context

- **Cortex review REV-2026-03-21-1** (Medium severity): Lines 108, 147, and 447 use `except Exception`.
- **Codex review finding #8**: Broad exception handling in critical paths hides actionable failure modes.
- Project rules require narrow exceptions with structured logging.

## Implementation Steps

### Step 1: Narrow `_run_git_command` exception (line ~108)

Replace `except Exception as e` with `except (subprocess.SubprocessError, OSError, ValueError) as e`.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `except Exception` in `_run_git_command` | `markdown_lint_core.py` | Lines 100-115 |
| subprocess error types used elsewhere | `src/cortex/tools/` | Similar subprocess wrappers |

### Step 2: Narrow `_calculate_file_hash` exception (line ~147)

Replace `except Exception:` with `except (OSError, UnicodeDecodeError):`. These are the concrete failure modes for file reads.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `_calculate_file_hash` | `markdown_lint_core.py` | Lines 140-155 |

### Step 3: Narrow cache-update wrapper exception (line ~447)

Replace `except Exception as e:` with `except (OSError, ValueError, KeyError) as e:` or the specific exceptions the cache logic can raise.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Cache update logic | `markdown_lint_core.py` | Lines 440-455 |

### Step 4: Add tests for exception propagation

Add tests verifying that unexpected exception types (e.g., `TypeError`, `RuntimeError`) propagate rather than being silently caught.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Tests for markdown_lint_core exceptions | `tests/` | Existing markdown lint tests |

## Dependencies

- None.

## Success Criteria

- Zero `except Exception` in `markdown_lint_core.py`.
- Unexpected exceptions propagate to callers.
- Existing tests pass; new tests cover propagation.
- Quality gate passes.

## Testing Strategy

- Unit tests with mocked subprocess/file I/O raising specific and unexpected exceptions.
- AAA pattern; verify expected exceptions are caught and unexpected ones propagate.
- Target: 95% coverage maintained.
