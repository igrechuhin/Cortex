# Per-File Language Quality Gate - Implementation Plan v1

**Date Created**: 26-03-29
**Last Updated**: 26-03-29
**Status**: Ready for Implementation
**Priority**: P1 (Blocker — quality gate silently skips non-Python files)
**Estimated Time**: 4-6 hours
**Dependencies**: None
**Related Plans**: Migration: Language-Agnostic Rules and Scripts Scaffolding

## Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Root Cause](#root-cause)
- [Current Architecture](#current-architecture)
- [Target Architecture](#target-architecture)
- [Implementation Files](#implementation-files)
- [Technical Implementation Details](#technical-implementation-details)
- [Test Plan](#test-plan)
- [Success Criteria](#success-criteria)
- [Implementation Steps](#implementation-steps)
- [Risk Mitigation](#risk-mitigation)
- [Status Tracking](#status-tracking)

---

## Overview

The Cortex MCP commit pipeline silently passes for non-Python files because all quality
gate checks are hard-wired to Python. The fix is per-file language dispatch: each file is
checked by the script that understands its extension, regardless of what other languages
exist in the same project. This handles pure-Swift, pure-Python, and mixed-language repos
uniformly.

---

## Problem Statement

When the Cortex commit pipeline ran on TradeWing (a Swift project), it passed the quality
gate. The TradeWing CI (`quality.yml`) subsequently found **190 file-size violations** in
the same commit. The discrepancy:

1. `execute_quality()` (in `pre_commit_pipeline_quality.py`) only runs file-size and
   function-length checks when `language == "python"`. For Swift projects the checks are
   simply skipped.
2. Even if the synapse scripts were invoked, `check_file_sizes.py` (Swift variant) scans
   `Sources/` and skips `Tests/`, so test-file violations would still be missed.

Result: the commit pipeline reports green while the actual project has violations.
This is a **silent false-positive**.

---

## Root Cause

### The `language == "python"` guard (primary bug)

```python
# src/cortex/tools/execution/pre_commit_pipeline_quality.py  line 69
if language == "python":
    file_violations = check_file_sizes(project_root)
    func_violations = check_function_lengths(project_root)
```

This guard must be removed. File-size and function-length rules apply to every supported
language; only the **implementation** (AST parser vs. regex) is language-specific.

### Script-level directory scanning (secondary bug)

Both Swift synapse scripts scan a fixed directory (`Sources/` by default) and exclude
`Tests/`. The dispatcher must be able to pass an explicit file list so test files are also
checked, and so the scripts can be used against any subset of changed files.

---

## Current Architecture

```
execute_quality(adapter, language)
  ├── adapter.lint_code()                  ← always runs
  └── if language == "python":             ← GUARD — Swift projects skip this branch
       ├── check_file_sizes(project_root)  ← scans src/**/*.py via Python AST
       └── check_function_lengths(project_root)
```

**Script invocation today (format/lint checks via synapse):**
```
run_synapse_script(project_root, language, script_name, check_type)
  → subprocess([python_bin, script_path], cwd=project_root)
  # FILES env var is NOT passed — scripts scan fixed directories
```

---

## Target Architecture

```
execute_quality(adapter, language)
  ├── adapter.lint_code()                  ← unchanged
  └── run_quality_checks_for_all_languages(project_root)
        └── FileLanguageRouter.route_and_run(project_root)
              ├── collect all source files (src/**/* or project-root/**/* for Swift)
              ├── group by extension → { ".py": [...], ".swift": [...] }
              └── for each group:
                    run_synapse_script_with_files(script="check_file_sizes.py",   files=group)
                    run_synapse_script_with_files(script="check_function_lengths.py", files=group)
              → merge → list[FileSizeViolation] + list[FunctionLengthViolation]
```

The synapse scripts gain a **`FILES` environment variable** interface:
- When `FILES` is set: check exactly those files (newline-separated absolute paths).
- When `FILES` is absent: existing directory-scan fallback (backwards compatibility).

---

## Implementation Files

### Files to Create

| File | Purpose |
|------|---------|
| `src/cortex/tools/execution/file_language_router.py` | Route files by extension; invoke scripts; merge results |
| `tests/unit/tools/execution/test_file_language_router.py` | Unit tests for routing and merging |
| `tests/integration/test_file_language_router_integration.py` | Integration tests: real synapse scripts via FILES env |

### Files to Modify

| File | Change |
|------|--------|
| `src/cortex/tools/execution/pre_commit_pipeline_quality.py` | Remove `if language == "python"` guard; call router |
| `src/cortex/core/constants.py` | Add `EXTENSION_SCRIPT_MAP` |
| `.cortex/synapse/scripts/swift/check_file_sizes.py` | Accept `FILES` env var; fallback includes `Tests/` |
| `.cortex/synapse/scripts/swift/check_function_lengths.py` | Accept `FILES` env var; fallback includes `Tests/` |
| `.cortex/synapse/scripts/python/check_file_sizes.py` | Accept `FILES` env var (interface parity) |
| `.cortex/synapse/scripts/python/check_function_lengths.py` | Accept `FILES` env var (interface parity) |

---

## Technical Implementation Details

### Step 1 — `EXTENSION_SCRIPT_MAP` in `constants.py`

Add after the existing quality constants (around line 38):

```python
# Maps file extension to synapse script subdirectory.
# Each entry enables per-file quality checks for that language.
EXTENSION_SCRIPT_MAP: dict[str, str] = {
    ".py":    "python",
    ".swift": "swift",
}
```

**Why a `dict[str, str]` and not a tuple?** Extensions are looked up per file; a dict is
O(1). The value is the `language` directory name under `synapse/scripts/`.

---

### Step 2 — `file_language_router.py`

**Full module spec** — keep each function under 30 lines; file under 400 lines.

```
src/cortex/tools/execution/file_language_router.py
```

#### Public API

```python
def route_files(
    files: list[Path],
    extension_map: dict[str, str] | None = None,
) -> dict[str, list[Path]]:
    """Group files by their language directory.

    Args:
        files:         Absolute paths to check.
        extension_map: Override for EXTENSION_SCRIPT_MAP (for testing).

    Returns:
        Mapping of language dir (e.g. "python", "swift") → file list.
        Files with unknown extensions are silently omitted.
    """
```

```python
def collect_project_files(project_root: Path) -> list[Path]:
    """Return all checkable source files under project_root.

    Skips:
      - __pycache__ directories
      - test_* named files  (test directories are NOT skipped)
      - FILE_SIZE_EXCLUDED_FILENAMES (e.g. models.py)
      - .git, node_modules, .venv, build, dist directories

    Returns:
        Sorted list of absolute Paths.
    """
```

```python
def run_quality_checks_for_all_languages(
    project_root: Path,
    files: list[Path] | None = None,
) -> tuple[list[FileSizeViolation], list[FunctionLengthViolation]]:
    """Dispatch quality checks to per-language synapse scripts.

    Args:
        project_root: Root of the project being checked.
        files:        Explicit file list; if None, collects from project_root.

    Returns:
        (file_size_violations, function_length_violations) merged across all languages.
    """
```

#### Internal helpers (all private, prefixed `_`)

```python
def _files_env_value(files: list[Path]) -> str:
    """Return newline-separated absolute paths for FILES env var."""
    return "\n".join(str(f) for f in files)

def _run_script_with_files(
    project_root: Path,
    language: str,
    script_name: str,
    files: list[Path],
) -> CheckResult:
    """Run a synapse script with FILES env var set."""
    # Builds on _execute_synapse_script_subprocess from pre_commit_synapse.py
    # Adds env={"FILES": _files_env_value(files)} to subprocess.run

def _parse_file_size_violations(
    output: str,
    project_root: Path,
) -> list[FileSizeViolation]:
    """Parse check_file_sizes.py stderr output into FileSizeViolation objects."""
    # Format: "  path/to/file.swift: 450 lines (max: 400, excess: 50)"

def _parse_function_length_violations(
    output: str,
    project_root: Path,
    language: str,
) -> list[FunctionLengthViolation]:
    """Parse check_function_lengths.py stderr output into FunctionLengthViolation objects."""
    # Python format: "    func_name() at line 42: 35 lines (max: 30, excess: 5)"
    # Swift format:  "  rel/path.swift:42: func_name() — 35 lines (max: 30, excess: 5)"
```

#### Violation output format reference (exact strings from scripts)

**Python `check_file_sizes.py` stderr:**
```
❌ File size violations detected:

  src/cortex/foo.py: 450 lines (max: 400, excess: 50)

Total violations: 1 file(s) exceed 400 lines
```

**Python `check_function_lengths.py` stderr:**
```
❌ Function length violations detected:

  src/cortex/foo.py:
    my_func() at line 42: 35 lines (max: 30, excess: 5)
```

**Swift `check_file_sizes.py` stderr:**
```
❌ File size violations detected:

  Sources/Foo/Bar.swift: 450 lines (max: 400, excess: 50)

Total violations: 1 file(s) exceed 400 lines
```

**Swift `check_function_lengths.py` stderr:**
```
❌ Function length violations detected:

  Sources/Foo/Bar.swift:42: myFunc() — 35 lines (max: 30, excess: 5)

Total violations: 1 function(s) exceed 30 lines
```

> **Parsing note**: The router parses these strings into structured
> `FileSizeViolation` / `FunctionLengthViolation` objects using regex so the caller
> receives typed data. If a line doesn't match, it is silently skipped (unknown
> format — forward-compatible).

---

### Step 3 — Modify `pre_commit_pipeline_quality.py`

Remove the Python-only guard and delegate to the router:

```python
# BEFORE (lines 68-71):
file_violations: list[FileSizeViolation] = []
func_violations: list[FunctionLengthViolation] = []
if language == "python":
    file_violations = check_file_sizes(project_root)
    func_violations = check_function_lengths(project_root)

# AFTER:
file_violations, func_violations = run_quality_checks_for_all_languages(project_root)
```

Remove the now-unused imports (`check_file_sizes`, `check_function_lengths`,
`check_function_lengths_in_file`) if they are no longer used elsewhere in the file.

> **Note**: `check_file_sizes` and `check_function_lengths` (Python-only helpers) remain
> in `pre_commit_helpers_quality.py` — they are still used by the existing tests and may
> be useful for the Python synapse scripts. Do **not** delete them.

---

### Step 4 — Update synapse scripts to accept `FILES` env var

**Same pattern for all four scripts.** Shown here for Swift `check_file_sizes.py`;
apply identically to the other three.

In each script's `main()` function, replace the fixed directory glob with:

```python
import os

def _get_files_from_env(project_root: Path) -> list[Path] | None:
    """Return explicit file list from FILES env var, or None if not set."""
    files_env = os.environ.get("FILES")
    if not files_env:
        return None
    return [Path(p) for p in files_env.strip().splitlines() if p]

# In main():
files_from_env = _get_files_from_env(project_root)
if files_from_env is not None:
    # Dispatcher mode: check exactly these files
    swift_files = [f for f in files_from_env if f.suffix == ".swift"]
else:
    # Standalone fallback: scan Sources/ AND Tests/
    swift_files = sorted(sources_dir.rglob("*.swift"))
    # Remove exclusion of "Tests" in path — test files must be checked
```

**Swift `check_file_sizes.py` changes:**
- Add `_get_files_from_env()` helper.
- In `main()`: use env files when `FILES` is set, else scan `Sources/` **and** `Tests/`.
- Remove `if "Tests" in path.parts: return True` from `is_excluded()` (keep generated-file exclusion).

**Swift `check_function_lengths.py` changes:**
- Same `_get_files_from_env()` helper.
- In `main()`: use env files when `FILES` is set, else scan `Sources/` **and** `Tests/`.
- Remove `if "Tests" in swift_file.parts: continue` from the directory-scan loop.

**Python `check_file_sizes.py` changes:**
- Add `_get_files_from_env()` helper.
- In `main()`: when `FILES` is set, use that list directly; skip the `find_src_directory()` call.
- Existing exclusions (models.py, test_*) still apply in directory-scan fallback.

**Python `check_function_lengths.py` changes:**
- Same `_get_files_from_env()` helper.
- In `main()`: when `FILES` is set, use that list directly; skip `find_src_directory()`.
- Existing exclusions still apply in directory-scan fallback.

> **Interface contract**: When `FILES` is set, scripts check **exactly** those files.
> Directory-scan exclusions (models.py, test_*) are only applied in fallback mode.
> The dispatcher is responsible for any filtering before passing files.

---

## Test Plan

### Unit tests — `tests/unit/tools/execution/test_file_language_router.py`

All tests follow the **AAA pattern** (Arrange / Act / Assert). Use `pytest`, `tmp_path`,
and `unittest.mock`. No real synapse scripts are invoked in unit tests.

#### Group 1: `route_files()`

```python
def test_route_files_groups_py_files_under_python() -> None:
    # Arrange
    files = [Path("a.py"), Path("b.py"), Path("c.swift")]
    # Act
    result = route_files(files)
    # Assert
    assert result["python"] == [Path("a.py"), Path("b.py")]

def test_route_files_groups_swift_files_under_swift() -> None:
    files = [Path("a.swift"), Path("b.swift")]
    result = route_files(files)
    assert result["swift"] == [Path("a.swift"), Path("b.swift")]

def test_route_files_skips_unknown_extensions() -> None:
    files = [Path("a.js"), Path("b.ts"), Path("c.go")]
    result = route_files(files)
    assert result == {}

def test_route_files_mixed_language_repo() -> None:
    files = [Path("a.py"), Path("b.swift"), Path("c.rs")]
    result = route_files(files)
    assert set(result.keys()) == {"python", "swift"}
    assert result["python"] == [Path("a.py")]
    assert result["swift"] == [Path("b.swift")]

def test_route_files_empty_list() -> None:
    assert route_files([]) == {}

def test_route_files_uses_extension_map_override() -> None:
    custom_map = {".ts": "typescript"}
    files = [Path("a.ts"), Path("b.py")]
    result = route_files(files, extension_map=custom_map)
    assert result == {"typescript": [Path("a.ts")]}
```

#### Group 2: `collect_project_files()`

```python
def test_collect_project_files_includes_py_and_swift(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("pass")
    (tmp_path / "Sources").mkdir()
    (tmp_path / "Sources" / "Bar.swift").write_text("// swift")
    result = collect_project_files(tmp_path)
    names = {f.name for f in result}
    assert "foo.py" in names
    assert "Bar.swift" in names

def test_collect_project_files_excludes_pycache(tmp_path) -> None:
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "foo.cpython-313.pyc").write_text("")
    result = collect_project_files(tmp_path)
    assert not any("__pycache__" in str(f) for f in result)

def test_collect_project_files_includes_test_files(tmp_path) -> None:
    # Test files MUST be included — this was the TradeWing bug
    (tmp_path / "Tests").mkdir()
    (tmp_path / "Tests" / "FooTests.swift").write_text("// test")
    result = collect_project_files(tmp_path)
    assert any(f.name == "FooTests.swift" for f in result)

def test_collect_project_files_excludes_dot_git(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("")
    result = collect_project_files(tmp_path)
    assert not any(".git" in str(f) for f in result)

def test_collect_project_files_excludes_models_py(tmp_path) -> None:
    (tmp_path / "models.py").write_text("class M: pass")
    result = collect_project_files(tmp_path)
    assert not any(f.name == "models.py" for f in result)

def test_collect_project_files_returns_sorted_paths(tmp_path) -> None:
    for name in ["z.py", "a.py", "m.swift"]:
        (tmp_path / name).write_text("")
    result = collect_project_files(tmp_path)
    assert result == sorted(result)
```

#### Group 3: `_parse_file_size_violations()`

```python
def test_parse_file_size_violations_python_format(tmp_path) -> None:
    output = (
        "❌ File size violations detected:\n\n"
        "  src/cortex/foo.py: 450 lines (max: 400, excess: 50)\n"
    )
    result = _parse_file_size_violations(output, tmp_path)
    assert len(result) == 1
    assert result[0].lines == 450
    assert result[0].max_lines == 400
    assert result[0].excess == 50

def test_parse_file_size_violations_swift_format(tmp_path) -> None:
    output = (
        "❌ File size violations detected:\n\n"
        "  Sources/Foo/Bar.swift: 450 lines (max: 400, excess: 50)\n"
    )
    result = _parse_file_size_violations(output, tmp_path)
    assert len(result) == 1
    assert result[0].file.endswith("Bar.swift")

def test_parse_file_size_violations_no_violations(tmp_path) -> None:
    output = "✅ All files within size limits (400 lines)\n"
    result = _parse_file_size_violations(output, tmp_path)
    assert result == []

def test_parse_file_size_violations_multiple(tmp_path) -> None:
    output = (
        "❌ File size violations detected:\n\n"
        "  src/a.py: 500 lines (max: 400, excess: 100)\n"
        "  src/b.py: 450 lines (max: 400, excess: 50)\n"
    )
    result = _parse_file_size_violations(output, tmp_path)
    assert len(result) == 2

def test_parse_file_size_violations_ignores_unrecognised_lines(tmp_path) -> None:
    output = "some unexpected line\nTotal violations: 0 file(s) exceed 400 lines\n"
    result = _parse_file_size_violations(output, tmp_path)
    assert result == []
```

#### Group 4: `_parse_function_length_violations()`

```python
def test_parse_function_length_violations_python_format(tmp_path) -> None:
    output = (
        "❌ Function length violations detected:\n\n"
        "  src/cortex/foo.py:\n"
        "    my_func() at line 42: 35 lines (max: 30, excess: 5)\n"
    )
    result = _parse_function_length_violations(output, tmp_path, language="python")
    assert len(result) == 1
    assert result[0].function == "my_func"
    assert result[0].line == 42
    assert result[0].lines == 35
    assert result[0].excess == 5

def test_parse_function_length_violations_swift_format(tmp_path) -> None:
    output = (
        "❌ Function length violations detected:\n\n"
        "  Sources/Foo/Bar.swift:42: myFunc() — 35 lines (max: 30, excess: 5)\n"
    )
    result = _parse_function_length_violations(output, tmp_path, language="swift")
    assert len(result) == 1
    assert result[0].function == "myFunc"

def test_parse_function_length_violations_no_violations(tmp_path) -> None:
    output = "✅ All functions within length limits (30 lines)\n"
    result = _parse_function_length_violations(output, tmp_path, language="python")
    assert result == []
```

#### Group 5: `run_quality_checks_for_all_languages()` (mocked scripts)

```python
def test_run_returns_empty_when_no_supported_files(tmp_path) -> None:
    (tmp_path / "foo.js").write_text("")
    file_v, func_v = run_quality_checks_for_all_languages(tmp_path)
    assert file_v == []
    assert func_v == []

@patch("cortex.tools.execution.file_language_router._run_script_with_files")
def test_run_invokes_both_scripts_per_language(mock_run, tmp_path) -> None:
    mock_run.return_value = CheckResult(
        check_type="test", success=True, output="✅", errors=[], warnings=[], files_modified=[]
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("x = 1")
    run_quality_checks_for_all_languages(tmp_path)
    calls = [c.args[2] for c in mock_run.call_args_list]  # script_name arg
    assert "check_file_sizes.py" in calls
    assert "check_function_lengths.py" in calls

@patch("cortex.tools.execution.file_language_router._run_script_with_files")
def test_run_merges_violations_from_multiple_languages(mock_run, tmp_path) -> None:
    py_size_output = "  src/foo.py: 450 lines (max: 400, excess: 50)"
    swift_size_output = "  Sources/Bar.swift: 410 lines (max: 400, excess: 10)"

    def side_effect(project_root, language, script_name, files):
        if language == "python" and "file_sizes" in script_name:
            return CheckResult(success=False, output=py_size_output, ...)
        if language == "swift" and "file_sizes" in script_name:
            return CheckResult(success=False, output=swift_size_output, ...)
        return CheckResult(success=True, output="✅", ...)

    mock_run.side_effect = side_effect
    # ... create py + swift files in tmp_path ...
    file_v, _ = run_quality_checks_for_all_languages(tmp_path)
    assert len(file_v) == 2

@patch("cortex.tools.execution.file_language_router._run_script_with_files")
def test_run_returns_violations_even_when_script_fails(mock_run, tmp_path) -> None:
    # Script exit code 1 = violations found; still parse output
    mock_run.return_value = CheckResult(
        success=False, output="  src/foo.py: 450 lines (max: 400, excess: 50)", ...
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("x = 1")
    file_v, _ = run_quality_checks_for_all_languages(tmp_path)
    assert len(file_v) >= 1
```

#### Group 6: `execute_quality()` regression tests

```python
def test_execute_quality_runs_for_swift_language(tmp_path) -> None:
    """Regression test: quality gate must NOT be skipped for Swift."""
    adapter = _make_mock_adapter(project_root=tmp_path, language="swift")
    with patch("...run_quality_checks_for_all_languages") as mock_router:
        mock_router.return_value = ([], [])
        result = execute_quality(adapter, "swift")
    mock_router.assert_called_once_with(tmp_path)
    assert result.success

def test_execute_quality_python_language_unchanged(tmp_path) -> None:
    """Regression: Python behavior must be identical to before."""
    adapter = _make_mock_adapter(project_root=tmp_path, language="python")
    with patch("...run_quality_checks_for_all_languages") as mock_router:
        mock_router.return_value = ([], [])
        result = execute_quality(adapter, "python")
    mock_router.assert_called_once()
    assert result.success

def test_execute_quality_fails_when_router_returns_violations(tmp_path) -> None:
    adapter = _make_mock_adapter(project_root=tmp_path, language="swift")
    violation = FileSizeViolation(file="Foo.swift", lines=450, max_lines=400, excess=50)
    with patch("...run_quality_checks_for_all_languages") as mock_router:
        mock_router.return_value = ([violation], [])
        result = execute_quality(adapter, "swift")
    assert not result.success
    assert len(result.file_size_violations) == 1
```

### Integration tests — `tests/integration/test_file_language_router_integration.py`

These tests exercise real synapse scripts via subprocess. Use `tmp_path` to create real
project trees.

```python
@pytest.mark.integration
def test_swift_file_size_violation_caught_via_files_env(tmp_path) -> None:
    """190-line TradeWing scenario: FILES env triggers Swift size check."""
    # Arrange: create a Swift file with 401 logical lines
    sources = tmp_path / "Sources" / "App"
    sources.mkdir(parents=True)
    swift_file = sources / "BigFile.swift"
    swift_file.write_text("\n".join(["let x = 1"] * 401))

    # Act
    file_v, _ = run_quality_checks_for_all_languages(tmp_path, files=[swift_file])

    # Assert
    assert len(file_v) == 1
    assert file_v[0].lines == 401
    assert file_v[0].excess == 1

@pytest.mark.integration
def test_swift_test_file_included_in_check(tmp_path) -> None:
    """Test files must be checked — this was the secondary TradeWing bug."""
    tests = tmp_path / "Tests" / "AppTests"
    tests.mkdir(parents=True)
    test_file = tests / "BigTests.swift"
    test_file.write_text("\n".join(["let x = 1"] * 401))

    file_v, _ = run_quality_checks_for_all_languages(tmp_path, files=[test_file])
    assert len(file_v) == 1

@pytest.mark.integration
def test_python_files_still_checked(tmp_path) -> None:
    """Regression: Python checks must still work after router change."""
    src = tmp_path / "src" / "myapp"
    src.mkdir(parents=True)
    py_file = src / "big.py"
    py_file.write_text("\n".join(["x = 1"] * 401))

    file_v, _ = run_quality_checks_for_all_languages(tmp_path, files=[py_file])
    assert len(file_v) == 1

@pytest.mark.integration
def test_mixed_language_repo_all_files_checked(tmp_path) -> None:
    """Mixed-language project: both .py and .swift violations detected."""
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "Sources" / "App").mkdir(parents=True)
    py_file = tmp_path / "src" / "pkg" / "big.py"
    swift_file = tmp_path / "Sources" / "App" / "Big.swift"
    py_file.write_text("\n".join(["x = 1"] * 401))
    swift_file.write_text("\n".join(["let x = 1"] * 401))

    file_v, _ = run_quality_checks_for_all_languages(
        tmp_path, files=[py_file, swift_file]
    )
    assert len(file_v) == 2
    extensions = {Path(v.file).suffix for v in file_v}
    assert ".py" in extensions
    assert ".swift" in extensions

@pytest.mark.integration
def test_unknown_extension_silently_skipped(tmp_path) -> None:
    (tmp_path / "foo.js").write_text("const x = 1;\n" * 500)
    file_v, func_v = run_quality_checks_for_all_languages(
        tmp_path, files=[tmp_path / "foo.js"]
    )
    assert file_v == []
    assert func_v == []

@pytest.mark.integration
def test_clean_project_passes(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "small.py").write_text("x = 1\n")
    file_v, func_v = run_quality_checks_for_all_languages(tmp_path)
    assert file_v == []
    assert func_v == []
```

### Synapse script unit tests

Add minimal tests to verify the `FILES` env-var interface without running the full router.
Place in `tests/unit/synapse/` (create dir if needed).

```python
# tests/unit/synapse/test_swift_check_file_sizes.py

def test_files_env_overrides_directory_scan(tmp_path, monkeypatch) -> None:
    """When FILES is set, script checks only those files."""
    big_file = tmp_path / "Big.swift"
    big_file.write_text("let x = 1\n" * 401)
    ignored = tmp_path / "Small.swift"
    ignored.write_text("// tiny\n")
    monkeypatch.setenv("FILES", str(big_file))
    result = subprocess.run(
        [sys.executable, str(SWIFT_CHECK_FILE_SIZES_PATH)],
        capture_output=True, text=True, cwd=tmp_path
    )
    assert result.returncode == 1
    assert "Big.swift" in result.stderr
    assert "Small.swift" not in result.stderr

def test_files_env_empty_passes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FILES", "")
    big_file = tmp_path / "Sources" / "Big.swift"
    big_file.parent.mkdir()
    big_file.write_text("let x = 1\n" * 401)
    # FILES="" → fallback scan; Sources/ scanned; violation found
    result = subprocess.run(
        [sys.executable, str(SWIFT_CHECK_FILE_SIZES_PATH)],
        capture_output=True, text=True, cwd=tmp_path
    )
    # Fallback should still find the violation
    assert result.returncode == 1
```

---

## Success Criteria

- [ ] `execute_quality()` calls `run_quality_checks_for_all_languages()` regardless of language
- [ ] Every `.swift` file (incl. `Tests/`) in a project is checked by the Swift scripts
- [ ] Every `.py` file in a project is checked by the Python scripts
- [ ] Mixed-language repos have all files checked by their respective scripts
- [ ] Unknown extensions are silently skipped (no false errors, no crash)
- [ ] Python behavior is identical to before the change (no regression)
- [ ] TradeWing scenario: a Swift file with 401 logical lines produces 1 `FileSizeViolation`
- [ ] Synapse scripts still work standalone (no `FILES` env = directory-scan fallback)
- [ ] All unit tests pass; no existing tests broken
- [ ] All integration tests pass
- [ ] `file_language_router.py` ≤ 400 lines; all functions ≤ 30 lines

---

## Implementation Steps

### Step 1 — Read current code (required before writing anything)

1. Read `src/cortex/tools/execution/pre_commit_pipeline_quality.py` in full.
2. Read `src/cortex/tools/execution/pre_commit_helpers_quality.py` in full.
3. Read `src/cortex/tools/execution/pre_commit_synapse.py` in full.
4. Read `src/cortex/core/constants.py` lines 1-60.
5. Read all four synapse scripts in full.
6. Read `src/cortex/tools/execution/pre_commit_helpers_models.py` for model definitions.

### Step 2 — Add `EXTENSION_SCRIPT_MAP` to `constants.py`

Add after `FILE_SIZE_EXCLUDED_FILENAMES` (line 31):

```python
EXTENSION_SCRIPT_MAP: dict[str, str] = {
    ".py":    "python",
    ".swift": "swift",
}
```

Update `__all__` if present.

### Step 3 — Create `file_language_router.py`

Write the full module as specified in [Technical Implementation Details](#technical-implementation-details).

Key correctness points:
- `_run_script_with_files()` must pass `FILES` as an environment variable to
  `subprocess.run()`. Merge it into the existing env: `env={**os.environ, "FILES": value}`.
- Parsers must handle both Python and Swift output formats (different line formats).
- `collect_project_files()` must **include** test files (no `test_*` exclusion in Swift;
  Python `test_*` naming exclusion stays in the directory-scan fallback inside the scripts).
- Return `([], [])` when no files match known extensions (not an error).

### Step 4 — Modify `pre_commit_pipeline_quality.py`

Replace the `if language == "python":` block with the router call. Update imports.

Exact diff:

```python
# Remove:
from cortex.tools.execution.pre_commit_helpers_quality import (
    check_file_sizes,
    check_function_lengths_in_file,
)

# Add:
from cortex.tools.execution.file_language_router import (
    run_quality_checks_for_all_languages,
)

# Remove _collect_violations_from_file() and check_function_lengths() functions
# if they are ONLY used by execute_quality() and not imported elsewhere.
# Check with grep before deleting.

# In execute_quality(), replace:
if language == "python":
    file_violations = check_file_sizes(project_root)
    func_violations = check_function_lengths(project_root)
# With:
file_violations, func_violations = run_quality_checks_for_all_languages(project_root)
```

### Step 5 — Update the four synapse scripts

For each of the four synapse scripts:
1. Add `import os` at the top (if not present).
2. Add `_get_files_from_env(project_root: Path) -> list[Path] | None` helper function.
3. In `main()`: replace/augment the directory-scan with the env-var branch.
4. For Swift scripts: remove `"Tests" in path.parts` exclusion from both the scan loop
   and `is_excluded()`.

Apply changes to:
- `.cortex/synapse/scripts/swift/check_file_sizes.py`
- `.cortex/synapse/scripts/swift/check_function_lengths.py`
- `.cortex/synapse/scripts/python/check_file_sizes.py`
- `.cortex/synapse/scripts/python/check_function_lengths.py`

### Step 6 — Write unit tests

Create `tests/unit/tools/execution/test_file_language_router.py` with all test groups
specified in the [Test Plan](#test-plan) section.

### Step 7 — Write integration tests

Create `tests/integration/test_file_language_router_integration.py` with the scenarios
specified in the [Test Plan](#test-plan) section.

Mark integration tests with `@pytest.mark.integration` so they can be run separately
from the unit suite.

### Step 8 — Validation

1. Run `run_quality_gate()` — must pass with zero regressions.
2. Manually simulate TradeWing:
   ```bash
   # Create temp dir with 401-line Swift file; run the full pipeline against it
   python -c "
   from pathlib import Path
   from cortex.tools.execution.file_language_router import run_quality_checks_for_all_languages
   import tempfile, os
   with tempfile.TemporaryDirectory() as d:
       root = Path(d)
       f = root / 'Sources' / 'App' / 'Big.swift'
       f.parent.mkdir(parents=True)
       f.write_text('let x = 1\n' * 401)
       violations, _ = run_quality_checks_for_all_languages(root)
       print(violations)
   "
   ```
3. Run full test suite to confirm no regressions.

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `FILES` env var not received by subprocess | Low | High | Integration test `test_files_env_overrides_directory_scan` catches this |
| Output format changes break parsers | Medium | Medium | Parsers skip unrecognised lines (forward-compatible); integration tests pin format |
| `pre_commit_pipeline_quality.py` grows past 400 lines | Low | Low | Router is a separate file; only 3 lines change in `execute_quality()` |
| Standalone synapse script usage breaks | Low | Medium | `FILES` is opt-in; directory scan remains default when env var absent |
| `collect_project_files()` too slow on large repos | Low | Low | Defer optimization; add `files` parameter for explicit override |
| Swift `Tests/` inclusion creates false positives | None | None | Test files are subject to the same size/length rules as production files |

---

## Status Tracking

- [ ] Not Started
- [ ] In Progress (Started: YY-MM-DD)
- [ ] Completed (Completed: YY-MM-DD)
- [ ] Blocked (Blocked by: [plan name])
