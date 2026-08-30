---
title: "Test and harden parse_type_errors in python_adapter_parsing"
component: framework_adapters
work_type: fix
status: PENDING
priority: Medium
created: 2026-03-22
depends_on: []
covers:
  - REV-2026-03-22-2
---

## Plan: Test and Harden parse_type_errors in python_adapter_parsing

### Goal

Add a dedicated `TestParseTypeErrors` test class for `parse_type_errors` in
`python_adapter_parsing.py` (currently has zero direct unit tests), and optionally
tighten the line-matching heuristic to better match pyright's actual output format and
reduce false positives.

### Context

**REV-2026-03-22-2 — Missing tests and fragile heuristic (all 3 review reports):**

`src/cortex/services/framework_adapters/python_adapter_parsing.py:240–246` contains:

```python
def parse_type_errors(output: str) -> list[str]:
    """Parse pyright output for type errors."""
    errors: list[str] = []
    for line in output.split("\n"):
        if "error" in line.lower() and "warning" not in line.lower():
            errors.append(line.strip())
    return errors
```

Issues:

1. **No direct unit tests.** `test_python_adapter_parsing.py` has test classes for
   `TestParseLintErrors`, `TestBuildTestErrors`, `TestParseCoverage`,
   `TestParseTestCounts`, `TestParsePytestOutput`, and `TestMergeSkipTrendWarnings` —
   but nothing for `parse_type_errors`. Any future refactor could silently break it.

2. **Substring heuristic is fragile.** `"error" in line.lower()` matches lines like:
   - `"Traceback (most recent call last):  error in internal function"` — false positive
   - `"0 errors, 2 warnings"` — false positive (the summary line pyright always emits)
   - A line with `"error"` in a string literal in the source snippet printed by pyright

   Pyright's real diagnostic lines follow the format:
   `<path>:<line>:<col> - error: <message> (reportXxx)`
   A regex anchored to this pattern would be strictly more precise.

3. The `"warning" not in line.lower()` guard is insufficient — the summary line
   `"0 errors, 0 warnings"` contains neither "warning" in the suppressable sense nor
   a real path reference, yet it would be captured as a false positive.

### Implementation Steps

#### Step 1 — Write `TestParseTypeErrors` test class

**File:** `tests/unit/test_python_adapter_parsing.py`

Insert a new test class after the existing `TestParseLintErrors` class. The class must
cover at minimum:

| Test name | Input | Expected |
|---|---|---|
| `test_captures_pyright_error_line` | `"src/foo.py:10:5 - error: Name 'x' is not defined (reportUndefinedVariable)"` | `["src/foo.py:10:5 - error: Name 'x' is not defined (reportUndefinedVariable)"]` |
| `test_ignores_warning_lines` | `"src/foo.py:10:5 - warning: something"` | `[]` |
| `test_ignores_summary_line` | `"0 errors, 0 warnings"` | `[]` (if heuristic is tightened) or document current behavior |
| `test_ignores_empty_input` | `""` | `[]` |
| `test_multiple_errors` | multiline pyright output with 2 error lines + 1 warning | list of 2 error strings only |
| `test_does_not_capture_informational_lines` | `"Pyright (1.1.x)"` header line | `[]` |
| `test_error_in_string_literal_context` | line containing `"error"` only in a printed snippet | document expected behavior and whether false positive occurs |

The last test (`test_error_in_string_literal_context`) may document a known limitation
rather than assert correctness if the heuristic is kept. If the regex is tightened,
the assertion should be `[]`.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `class TestParseTypeErrors` present | `tests/unit/test_python_adapter_parsing.py` | full file |
| All 7 test methods inside the class | grep `def test_` inside class | same |
| No import added to test file that was already there | top 20 lines of test file | same |

---

#### Step 2 — Optionally tighten the matching regex in `parse_type_errors`

**File:** `src/cortex/services/framework_adapters/python_adapter_parsing.py`
**Location:** lines 240–246

This step is optional but recommended. If implemented, replace the substring heuristic
with a regex that matches pyright's canonical diagnostic line format:

```text
<path>:<line>:<col> - error: <message>
```

Regex pattern (no trailing anchor to tolerate the `(reportXxx)` suffix):

```python
import re
_PYRIGHT_ERROR_RE = re.compile(r".+:\d+:\d+ - error:", re.IGNORECASE)
```

Then the function body becomes:

```python
def parse_type_errors(output: str) -> list[str]:
    """Parse pyright output for type errors."""
    return [
        line.strip()
        for line in output.split("\n")
        if _PYRIGHT_ERROR_RE.search(line)
    ]
```

**Decision gate for implementer:** If pyright output samples confirm the format above,
proceed with the regex. If uncertain, keep the heuristic and document the limitation
in a code comment — in that case Step 2 tests should document expected behavior for
the ambiguous cases rather than assert strict correctness.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `_PYRIGHT_ERROR_RE` or comment about known limitation | `python_adapter_parsing.py:240–250` | same |
| `parse_type_errors` returns list, not generator | same | same |
| `import re` at top if regex path chosen | `python_adapter_parsing.py:1–15` | same |

---

#### Step 3 — Run quality gate and confirm no regressions

After writing tests (and optionally tightening the regex), run:

- `run_quality_gate()` — must pass with zero new violations.
- Confirm `TestParseTypeErrors` tests all pass.
- Confirm existing `TestParseLintErrors` and other existing test classes still pass.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `run_quality_gate()` output shows PASS | MCP tool output | N/A |
| No ruff/pyright violations introduced | same | N/A |
| Coverage on `parse_type_errors` ≥ 95% | coverage report | N/A |

---

### Dependencies

- No upstream dependency.
- Independent of Plan A (exception handling), Plan C (preflight URL), Plan D (docs).

### Success Criteria

1. `TestParseTypeErrors` class exists in `tests/unit/test_python_adapter_parsing.py`
   with at minimum 7 test methods.
2. All tests pass with `run_quality_gate()`.
3. Coverage on `python_adapter_parsing.py:parse_type_errors` reaches 95%+.
4. If the regex tightening is applied, the summary line (`"0 errors, 0 warnings"`)
   no longer produces a false positive.
5. Test Coverage score: maintained at 8/10 or improved; no regression.

### Testing Strategy

- **Coverage target:** 95% on `parse_type_errors`.
- **Pattern:** AAA (Arrange-Act-Assert) for every test method.
- **No mocking required** — `parse_type_errors` is a pure function; use plain
  string inputs.
- **Real pyright output samples:** Use verbatim pyright diagnostic lines as test
  inputs where possible. Example canonical lines:
  - `"src/cortex/core/session.py:42:9 - error: Cannot access attribute 'x' (reportAttributeAccessIssue)"`
  - `"0 errors, 0 warnings, 0 informations"`
  - `"  /path/to/file.py:1:1 - error: Import could not be resolved (reportMissingModuleSource)"`
- **Edge cases:** empty string, string with no newlines, string with only whitespace
  lines, mixed error/warning/info lines.
