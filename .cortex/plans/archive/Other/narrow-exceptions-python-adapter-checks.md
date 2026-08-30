---
title: "Narrow exceptions in python_adapter_checks.py"
component: framework_adapters
work_type: fix
status: PENDING
priority: High
created: 2026-03-22
depends_on: []
---

## Goal

Replace five broad `except Exception` blocks in `python_adapter_checks.py` with layered narrow exception handling, mirroring the pattern already established in `python_adapter.py`. This closes **REV-2026-03-22-4** and unblocks Error Handling and Rules Compliance from their 8/10 plateau.

## Context

All three code reviews (2026-03-22T20-26, T20-27, T20-28) flag the same five locations:

- `python_adapter_checks.py:32` — `run_black_formatting`
- `python_adapter_checks.py:61` — `run_ruff_import_sorting`
- `python_adapter_checks.py:95` — `type_check_via_script`
- `python_adapter_checks.py:122` — `type_check_pyright_only`
- `python_adapter_checks.py:208` — `run_ruff_fix`

`python_adapter.py` already uses: `subprocess.TimeoutExpired` → `(OSError, subprocess.SubprocessError)` → labeled `Exception` with "Unexpected … error: " prefix. The checks module must match.

## Implementation Steps

## Step 1: Read and understand current state

**Verification Checklist**:

- What to search for: `except Exception` in `python_adapter_checks.py`
- Search scope: `src/cortex/services/framework_adapters/python_adapter_checks.py`
- Files to re-read: `python_adapter.py:260–310` for the reference pattern

## Step 2: Apply narrow exception pattern to format helpers (lines ~32, ~61)

In `run_black_formatting` and `run_ruff_import_sorting`, replace:

```python
except Exception as e:
    errors.append(f"Black formatting error: {e}")
```

With:

```python
except subprocess.TimeoutExpired as e:
    errors.append(f"Black formatting timed out: {e}")
except (OSError, subprocess.SubprocessError) as e:
    errors.append(f"Black formatting error: {e}")
except Exception as e:
    errors.append(f"Unexpected black error: {e}")
```

Apply the same triple-layer to `run_ruff_import_sorting` (line ~61), with "ruff import sorting" prefix.

**Verification Checklist**:

- What to search for: `except subprocess.TimeoutExpired` in lines 25–70
- Search scope: `python_adapter_checks.py`
- Files to re-read: updated file after edit

## Step 3: Apply narrow exception pattern to type-check helpers (lines ~95, ~122)

In `type_check_via_script` and `type_check_pyright_only`, replace the broad catch with:

```python
except subprocess.TimeoutExpired as e:
    return _type_check_result(False, str(e), [f"Type-check timed out: {e}"])
except (OSError, subprocess.SubprocessError) as e:
    return _type_check_result(False, str(e), [str(e)])
except Exception as e:
    return _type_check_result(
        False,
        str(e),
        [f"Unexpected type-check runner error: {e}"],
    )
```

For `type_check_pyright_only` (line ~122), use `CheckResult(...)` constructor in each handler (matching the existing return type).

**Verification Checklist**:

- What to search for: `except subprocess.TimeoutExpired` in lines 85–130
- Search scope: `python_adapter_checks.py`
- Files to re-read: `tests/unit/test_python_adapter.py` to confirm test patterns for timeout branch

## Step 4: Apply narrow exception pattern to run_ruff_fix (line ~208)

```python
except (OSError, subprocess.SubprocessError) as e:
    return _create_lint_error_result(str(e))
except Exception as e:
    return _create_lint_error_result(f"Unexpected ruff fix error: {e}")
```

**Verification Checklist**:

- What to search for: `except` in lines 200–220
- Search scope: `python_adapter_checks.py`
- Files to re-read: updated file

## Step 5: Write/update tests

Add test cases in `tests/unit/test_python_adapter_checks.py` (create if missing) or extend `test_python_adapter.py`:

- `TimeoutExpired` is surfaced with "timed out" label
- `OSError` routes to operational handler
- Unexpected exception routes to "Unexpected … error" handler

**Verification Checklist**:

- What to search for: test functions covering `run_black_formatting`, `type_check_via_script`, `run_ruff_fix`
- Search scope: `tests/unit/`
- Files to re-read: `tests/unit/test_python_adapter.py`

## Step 6: Run quality gate

Call `run_quality_gate()` (zero-arg). Gate must pass with 0 errors, 0 type warnings, 0 function/file length violations.

**Verification Checklist**:

- Gate output: `file_size_violations: []`, `function_length_violations: []`, tests pass ≥5389, coverage ≥90%

## Dependencies

- None (self-contained to `python_adapter_checks.py` and its tests)

## Success Criteria

1. Zero `except Exception` blocks remaining in `python_adapter_checks.py` (all replaced with layered handling)
2. `REV-2026-03-22-4` marked RESOLVED in next review
3. Error Handling and Rules Compliance scores eligible to advance beyond 8
4. Quality gate passes with no regressions

## Testing Strategy (95% coverage target)

- Unit tests for each handler branch: `TimeoutExpired`, `OSError`, and unexpected `Exception` for all five functions
- Existing passing tests must not regress
- Parametrize where helpers share structure to keep test file ≤400 lines
