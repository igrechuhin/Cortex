---
title: "Narrow broad exception handling in PythonAdapter test execution"
component: framework_adapters
work_type: bug-fix
status: PENDING
priority: medium
created: 2026-03-22
depends_on: []
covers:
  - REV-2026-03-22-1
  - REV-2026-03-22-CACHE
---

## Plan: Narrow Broad Exception Handling in PythonAdapter Test Execution

### Goal

Replace two broad `except Exception as e:` clauses in `python_adapter.py` with narrow,
specific exception types so that subprocess failures surface their real cause instead of
being silently swallowed. Additionally add a debug-level log when the cache write in
`python_adapter_parsing.py` fails so operators can diagnose cache permission issues.

### Context

Two error-handling issues identified across all three code-review reports (T18-16,
T18-17, T18-27):

**REV-2026-03-22-1 — Broad catch in test execution methods:**

- `src/cortex/services/framework_adapters/python_adapter.py:257`
  `except Exception as e:` in `_execute_test_command_streaming`
- `src/cortex/services/framework_adapters/python_adapter.py:281`
  `except Exception as e:` in `_execute_test_command`
- Both convert any unexpected error (including programming mistakes, import errors,
  `MemoryError`, etc.) into a generic `TestResult(success=False)` with no diagnostic
  detail beyond `str(e)`. A narrow catch of `(OSError, subprocess.SubprocessError)`
  covers the real failure modes; a fallback broad catch with a more descriptive message
  should remain as a last resort.

**REV-2026-03-22-CACHE — Silent cache write failure:**

- `src/cortex/services/framework_adapters/python_adapter_parsing.py:97–98`
  `except OSError: pass` in `_persist_skipped_count_cache`
- Cache write failures are invisible to operators. Adding a `logging.debug()`
  (or `logging.warning()`) call lets operators diagnose file-permission issues in
  restricted environments without changing the best-effort semantics.

### Implementation Steps

#### Step 1 — Narrow exception catch in `_execute_test_command_streaming`

**File:** `src/cortex/services/framework_adapters/python_adapter.py`
**Location:** line 257 (the `except Exception as e:` following the
`except subprocess.TimeoutExpired:` clause inside `_execute_test_command_streaming`)

Replace:

```python
except Exception as e:
    return self._create_error_result(str(e))
```

With:

```python
except (OSError, subprocess.SubprocessError) as e:
    return self._create_error_result(str(e))
except Exception as e:
    return self._create_error_result(
        f"Unexpected error during streaming test execution: {e}"
    )
```

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `except Exception` remaining in `_execute_test_command_streaming` | `python_adapter.py` | `python_adapter.py:240–260` |
| `except (OSError, subprocess.SubprocessError)` present | `python_adapter.py` | same |
| No import added twice | top of `python_adapter.py` | `python_adapter.py:1–20` |

---

#### Step 2 — Narrow exception catch in `_execute_test_command`

**File:** `src/cortex/services/framework_adapters/python_adapter.py`
**Location:** line 281 (the `except Exception as e:` inside `_execute_test_command`)

Replace:

```python
except Exception as e:
    return self._create_error_result(str(e))
```

With:

```python
except (OSError, subprocess.SubprocessError) as e:
    return self._create_error_result(str(e))
except Exception as e:
    return self._create_error_result(
        f"Unexpected error during test execution: {e}"
    )
```

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `except Exception` remaining in `_execute_test_command` | `python_adapter.py` | `python_adapter.py:260–285` |
| `except (OSError, subprocess.SubprocessError)` present | `python_adapter.py` | same |

---

#### Step 3 — Add diagnostic log in `_persist_skipped_count_cache`

**File:** `src/cortex/services/framework_adapters/python_adapter_parsing.py`
**Location:** lines 91–98, function `_persist_skipped_count_cache`

Add a `logging` import (if not already present) and replace:

```python
except OSError:
    pass
```

With:

```python
except OSError as exc:
    logging.debug("Cache write failed for %s: %s", cache_path, exc)
```

The severity should be `debug` (not `warning`) because cache write failure does not
affect correctness — it only means the skip-trend comparison will be skipped next run.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `import logging` present | `python_adapter_parsing.py` top | `python_adapter_parsing.py:1–15` |
| `logging.debug(` in `_persist_skipped_count_cache` | `python_adapter_parsing.py:91–100` | same |
| `except OSError: pass` no longer present | `python_adapter_parsing.py` | same |

---

#### Step 4 — Add / update unit tests for the narrowed exception paths

**File:** `tests/unit/test_python_adapter.py`

Add test cases that exercise the new narrow and fallback catch branches:

1. `test_execute_test_command_oserror` — mock `subprocess.run` to raise `OSError`;
   assert result has `success=False` and `errors` is non-empty.
2. `test_execute_test_command_unexpected_error` — mock `subprocess.run` to raise
   `ValueError`; assert result has `success=False` and the error message contains
   `"Unexpected error"`.
3. `test_execute_test_command_streaming_oserror` — same pattern for the streaming path;
   mock the streaming subprocess creation to raise `OSError`.
4. `test_execute_test_command_streaming_unexpected_error` — mock to raise `RuntimeError`.

**File:** `tests/unit/test_python_adapter_parsing.py`

Add to the `TestMergeSkipTrendWarnings` class (or a new class
`TestPersistSkippedCountCache`):

5. `test_cache_write_failure_logs_debug` — mock `Path.write_text` to raise `OSError`;
   assert `logging.debug` is called with a message containing the cache path.
6. `test_cache_write_failure_does_not_raise` — same setup; assert the function returns
   normally without propagating the exception.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `test_execute_test_command_oserror` present | `tests/unit/test_python_adapter.py` | full file |
| `test_cache_write_failure_logs_debug` present | `tests/unit/test_python_adapter_parsing.py` | full file |
| All 6 new tests pass via quality gate | run `run_quality_gate()` | N/A |

---

### Dependencies

- No upstream plan dependency.
- Does not interact with Plan B (parse_type_errors), Plan C (preflight URL), or Plan D
  (docs). Safe to implement independently.

### Success Criteria

1. `except (OSError, subprocess.SubprocessError)` replaces `except Exception` as the
   primary catch in both `_execute_test_command` and `_execute_test_command_streaming`.
2. A final broad `except Exception` remains as a last-resort with a descriptive message
   prefix.
3. `_persist_skipped_count_cache` logs at `debug` level on `OSError` instead of silently
   passing.
4. All new unit tests pass.
5. `run_quality_gate()` passes (zero ruff/pyright/black violations introduced).
6. Test coverage on `python_adapter.py` and `python_adapter_parsing.py` does not
   decrease from baseline.
7. Error Handling score target: 8/10 (up from 7/10 per review reports).

### Testing Strategy

- **Coverage target:** 95% on the two changed functions.
- **Pattern:** Arrange-Act-Assert (AAA) for each test.
- **Mocking strategy:** `unittest.mock.patch` / `monkeypatch` on `subprocess.run` and
  `subprocess.Popen` for the subprocess exception tests; `unittest.mock.patch.object`
  on `Path.write_text` for the cache test; `caplog` fixture at `DEBUG` level for the
  logging assertion.
- **No integration tests needed** — all interactions are with stdlib subprocess and
  filesystem; mocking is sufficient.
- **Regression guard:** Keep existing passing tests unchanged; the new tests are purely
  additive.
