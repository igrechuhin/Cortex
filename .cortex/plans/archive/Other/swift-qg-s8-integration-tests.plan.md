# Step 8 of 8 — Write integration tests + validate end-to-end

**Series**: Per-File Language Quality Gate
**Date Created**: 26-03-29
**Status**: Ready for Implementation
**Depends on**: `swift-qg-s7-unit-tests.plan.md` (all production code + unit tests must pass)
**Next step**: none (final step)

---

## Goal

1. Create `tests/integration/test_file_language_router_integration.py` — exercises
   real synapse scripts via subprocess with the `FILES` env var.
2. Create `tests/unit/synapse/test_swift_check_file_sizes_files_env.py` — verifies the
   `FILES` env-var interface of the Swift file-size script in isolation.
3. Run the full test suite and confirm zero regressions.

These tests form the regression net: if the `FILES` interface or the parsing breaks in
the future, these tests catch it before merging.

---

## Files to Read First

1. `src/cortex/tools/execution/file_language_router.py` — public API
2. `.cortex/synapse/scripts/swift/check_file_sizes.py` — confirm `FILES` interface added in Step 4
3. `.cortex/synapse/scripts/python/check_file_sizes.py` — confirm `FILES` interface added in Step 6
4. `tests/integration/` — list existing files; check for `conftest.py` or `pytest.ini` marks
5. `tests/unit/synapse/` — check if directory exists; look for `__init__.py` or `conftest.py`

---

## Files to Create

| File | Purpose |
|------|---------|
| `tests/integration/test_file_language_router_integration.py` | End-to-end tests via real synapse scripts |
| `tests/unit/synapse/test_swift_check_file_sizes_files_env.py` | Isolated script interface test |

---

## Integration Tests

Mark all tests `@pytest.mark.integration`.

```python
# tests/integration/test_file_language_router_integration.py
"""Integration tests: real synapse scripts invoked via FILES env var."""

import pytest
from pathlib import Path
from cortex.tools.execution.file_language_router import run_quality_checks_for_all_languages


@pytest.mark.integration
def test_swift_file_size_violation_caught_via_files_env(tmp_path: Path) -> None:
    """TradeWing scenario: a 401-line Swift file triggers a size violation."""
    # Arrange
    sources = tmp_path / "Sources" / "App"
    sources.mkdir(parents=True)
    big_file = sources / "BigFile.swift"
    big_file.write_text("\n".join(["let x = 1"] * 401))

    # Act
    file_v, _ = run_quality_checks_for_all_languages(tmp_path, files=[big_file])

    # Assert
    assert len(file_v) == 1
    assert file_v[0].lines == 401
    assert file_v[0].excess == 1


@pytest.mark.integration
def test_swift_test_file_included_in_check(tmp_path: Path) -> None:
    """Tests/ directory files must be checked — secondary TradeWing bug."""
    tests = tmp_path / "Tests" / "AppTests"
    tests.mkdir(parents=True)
    test_file = tests / "BigTests.swift"
    test_file.write_text("\n".join(["let x = 1"] * 401))

    file_v, _ = run_quality_checks_for_all_languages(tmp_path, files=[test_file])
    assert len(file_v) == 1


@pytest.mark.integration
def test_python_file_size_violation_still_caught(tmp_path: Path) -> None:
    """Regression: Python size checks must work after the router change."""
    src = tmp_path / "src" / "myapp"
    src.mkdir(parents=True)
    py_file = src / "big.py"
    py_file.write_text("\n".join(["x = 1"] * 401))

    file_v, _ = run_quality_checks_for_all_languages(tmp_path, files=[py_file])
    assert len(file_v) == 1


@pytest.mark.integration
def test_mixed_language_repo_both_violations_caught(tmp_path: Path) -> None:
    """Mixed project: .py and .swift violations both detected."""
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
def test_unknown_extension_silently_skipped(tmp_path: Path) -> None:
    js_file = tmp_path / "foo.js"
    js_file.write_text("const x = 1;\n" * 500)
    file_v, func_v = run_quality_checks_for_all_languages(tmp_path, files=[js_file])
    assert file_v == []
    assert func_v == []


@pytest.mark.integration
def test_clean_project_passes(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "small.py").write_text("x = 1\n")
    file_v, func_v = run_quality_checks_for_all_languages(tmp_path)
    assert file_v == []
    assert func_v == []


@pytest.mark.integration
def test_swift_function_length_violation_caught(tmp_path: Path) -> None:
    """Swift function-length check must fire via dispatcher."""
    sources = tmp_path / "Sources" / "App"
    sources.mkdir(parents=True)
    # Write a Swift file with a 31-line function body
    lines = ["struct Foo {", "    func longFunc() {"]
    lines += ["        let x = 1"] * 31
    lines += ["    }", "}"]
    swift_file = sources / "Foo.swift"
    swift_file.write_text("\n".join(lines))

    _, func_v = run_quality_checks_for_all_languages(tmp_path, files=[swift_file])
    assert len(func_v) >= 1
    assert func_v[0].function == "longFunc"
```

---

## Isolated Script Tests

```python
# tests/unit/synapse/test_swift_check_file_sizes_files_env.py
"""Unit tests for the FILES env var interface of swift/check_file_sizes.py."""

import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parents[3] / ".cortex" / "synapse" / "scripts" / "swift" / "check_file_sizes.py"


def test_files_env_checks_only_specified_file(tmp_path: Path, monkeypatch) -> None:
    """When FILES is set, script ignores all other files."""
    big = tmp_path / "Big.swift"
    big.write_text("let x = 1\n" * 401)
    small = tmp_path / "Small.swift"
    small.write_text("// tiny\n")

    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env={**__import__("os").environ, "FILES": str(big)},
    )
    assert result.returncode == 1
    assert "Big.swift" in result.stderr
    assert "Small.swift" not in result.stderr


def test_files_env_absent_scans_sources_dir(tmp_path: Path) -> None:
    """When FILES is not set, script falls back to Sources/ scan."""
    sources = tmp_path / "Sources"
    sources.mkdir()
    big = sources / "Big.swift"
    big.write_text("let x = 1\n" * 401)

    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 1
    assert "Big.swift" in result.stderr


def test_files_env_includes_tests_dir_in_fallback(tmp_path: Path) -> None:
    """Fallback scan includes Tests/ — secondary TradeWing bug regression."""
    sources = tmp_path / "Sources"
    sources.mkdir()
    (sources / "Ok.swift").write_text("// fine\n")
    tests = tmp_path / "Tests"
    tests.mkdir()
    big_test = tests / "BigTest.swift"
    big_test.write_text("let x = 1\n" * 401)

    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 1
    assert "BigTest.swift" in result.stderr


def test_files_env_empty_string_uses_fallback(tmp_path: Path) -> None:
    """FILES='' is treated as unset; fallback scan is used."""
    sources = tmp_path / "Sources"
    sources.mkdir()
    big = sources / "Big.swift"
    big.write_text("let x = 1\n" * 401)

    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env={**__import__("os").environ, "FILES": ""},
    )
    assert result.returncode == 1
```

---

## Validation Steps (run after tests pass)

1. `run_quality_gate()` — must pass with zero errors.
2. Manual TradeWing simulation:

   ```python
   from pathlib import Path
   from cortex.tools.execution.file_language_router import run_quality_checks_for_all_languages
   import tempfile

   with tempfile.TemporaryDirectory() as d:
       root = Path(d)
       f = root / "Sources" / "App" / "Big.swift"
       f.parent.mkdir(parents=True)
       f.write_text("let x = 1\n" * 401)
       violations, _ = run_quality_checks_for_all_languages(root)
       print(violations)  # must print 1 FileSizeViolation
   ```

3. Confirm `run_quality_gate()` still passes on the Cortex repo itself
   (Python-only project — must be zero regressions).

---

## Success Criteria

- [ ] `tests/integration/test_file_language_router_integration.py` created with all 7 tests
- [ ] `tests/unit/synapse/test_swift_check_file_sizes_files_env.py` created with all 4 tests
- [ ] All integration tests pass
- [ ] All synapse unit tests pass
- [ ] TradeWing simulation produces exactly 1 `FileSizeViolation` for a 401-line Swift file
- [ ] `run_quality_gate()` passes on Cortex repo (zero Python regressions)
- [ ] Full test suite passes with no newly broken tests
