# Step 7 of 8 — Write unit tests for file_language_router.py

**Series**: Per-File Language Quality Gate
**Date Created**: 26-03-29
**Status**: Ready for Implementation
**Depends on**: `swift-qg-s6-python-scripts-files-env.plan.md` (all production code must be in place)
**Next step**: `swift-qg-s8-integration-tests.plan.md`

---

## Goal

Create `tests/unit/tools/execution/test_file_language_router.py` covering all public
functions and critical private helpers of `file_language_router.py`.

No real synapse scripts are invoked — all subprocess calls are mocked.

---

## Files to Read First

1. `src/cortex/tools/execution/file_language_router.py` — full implementation
2. `src/cortex/tools/execution/pre_commit_helpers_models.py` — `FileSizeViolation`, `FunctionLengthViolation`, `CheckResult`
3. `tests/unit/tools/execution/` — list existing files to confirm path conventions
4. Any existing `conftest.py` in `tests/unit/` or `tests/` — check for shared fixtures

---

## File to Create

`tests/unit/tools/execution/test_file_language_router.py`

---

## Test Groups and Cases

All tests: AAA pattern. Use `pytest`, `tmp_path`, `unittest.mock.patch`.

### Group 1 — `route_files()`

```python
def test_route_files_groups_py_files_under_python() -> None:
    files = [Path("a.py"), Path("b.py"), Path("c.swift")]
    result = route_files(files)
    assert result["python"] == [Path("a.py"), Path("b.py")]

def test_route_files_groups_swift_files_under_swift() -> None:
    files = [Path("a.swift"), Path("b.swift")]
    assert route_files(files) == {"swift": [Path("a.swift"), Path("b.swift")]}

def test_route_files_skips_unknown_extensions() -> None:
    assert route_files([Path("a.js"), Path("b.ts"), Path("c.go")]) == {}

def test_route_files_mixed_language_repo() -> None:
    result = route_files([Path("a.py"), Path("b.swift"), Path("c.rs")])
    assert set(result.keys()) == {"python", "swift"}
    assert result["python"] == [Path("a.py")]
    assert result["swift"] == [Path("b.swift")]

def test_route_files_empty_list() -> None:
    assert route_files([]) == {}

def test_route_files_uses_extension_map_override() -> None:
    result = route_files([Path("a.ts"), Path("b.py")], extension_map={".ts": "typescript"})
    assert result == {"typescript": [Path("a.ts")]}
```

### Group 2 — `collect_project_files()`

```python
def test_collect_project_files_includes_py_and_swift(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("pass")
    (tmp_path / "Sources").mkdir()
    (tmp_path / "Sources" / "Bar.swift").write_text("// swift")
    names = {f.name for f in collect_project_files(tmp_path)}
    assert "foo.py" in names
    assert "Bar.swift" in names

def test_collect_project_files_excludes_pycache(tmp_path) -> None:
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "compiled.pyc").write_text("")
    assert not any("__pycache__" in str(f) for f in collect_project_files(tmp_path))

def test_collect_project_files_includes_test_files(tmp_path) -> None:
    # CRITICAL: test files must NOT be excluded — this was the TradeWing bug
    (tmp_path / "Tests").mkdir()
    (tmp_path / "Tests" / "FooTests.swift").write_text("// test")
    assert any(f.name == "FooTests.swift" for f in collect_project_files(tmp_path))

def test_collect_project_files_excludes_dot_git(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("")
    assert not any(".git" in str(f) for f in collect_project_files(tmp_path))

def test_collect_project_files_excludes_models_py(tmp_path) -> None:
    (tmp_path / "models.py").write_text("class M: pass")
    assert not any(f.name == "models.py" for f in collect_project_files(tmp_path))

def test_collect_project_files_returns_sorted_paths(tmp_path) -> None:
    for name in ["z.py", "a.py", "m.swift"]:
        (tmp_path / name).write_text("")
    result = collect_project_files(tmp_path)
    assert result == sorted(result)

def test_collect_project_files_excludes_node_modules(tmp_path) -> None:
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("")
    assert not any("node_modules" in str(f) for f in collect_project_files(tmp_path))
```

### Group 3 — `_parse_file_size_violations()`

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
    output = "  Sources/Foo/Bar.swift: 450 lines (max: 400, excess: 50)\n"
    result = _parse_file_size_violations(output, tmp_path)
    assert len(result) == 1
    assert result[0].file.endswith("Bar.swift")
    assert result[0].lines == 450

def test_parse_file_size_violations_no_violations(tmp_path) -> None:
    assert _parse_file_size_violations("✅ All files within size limits (400 lines)\n", tmp_path) == []

def test_parse_file_size_violations_multiple(tmp_path) -> None:
    output = (
        "  src/a.py: 500 lines (max: 400, excess: 100)\n"
        "  src/b.py: 450 lines (max: 400, excess: 50)\n"
    )
    assert len(_parse_file_size_violations(output, tmp_path)) == 2

def test_parse_file_size_violations_ignores_unrecognised_lines(tmp_path) -> None:
    output = "some unexpected line\nTotal violations: 0 file(s) exceed 400 lines\n"
    assert _parse_file_size_violations(output, tmp_path) == []

def test_parse_file_size_violations_excess_consistent(tmp_path) -> None:
    output = "  src/foo.py: 450 lines (max: 400, excess: 50)\n"
    result = _parse_file_size_violations(output, tmp_path)
    v = result[0]
    assert v.excess == v.lines - v.max_lines
```

### Group 4 — `_parse_function_length_violations()`

```python
def test_parse_function_length_violations_python_format(tmp_path) -> None:
    output = (
        "  src/cortex/foo.py:\n"
        "    my_func() at line 42: 35 lines (max: 30, excess: 5)\n"
    )
    result = _parse_function_length_violations(output, tmp_path, language="python")
    assert len(result) == 1
    v = result[0]
    assert v.function == "my_func"
    assert v.line == 42
    assert v.lines == 35
    assert v.max_lines == 30
    assert v.excess == 5

def test_parse_function_length_violations_swift_format(tmp_path) -> None:
    output = "  Sources/Foo/Bar.swift:42: myFunc() — 35 lines (max: 30, excess: 5)\n"
    result = _parse_function_length_violations(output, tmp_path, language="swift")
    assert len(result) == 1
    assert result[0].function == "myFunc"
    assert result[0].line == 42

def test_parse_function_length_violations_no_violations(tmp_path) -> None:
    output = "✅ All functions within length limits (30 lines)\n"
    assert _parse_function_length_violations(output, tmp_path, language="python") == []

def test_parse_function_length_violations_multiple_python(tmp_path) -> None:
    output = (
        "  src/foo.py:\n"
        "    func_a() at line 10: 35 lines (max: 30, excess: 5)\n"
        "    func_b() at line 50: 40 lines (max: 30, excess: 10)\n"
    )
    result = _parse_function_length_violations(output, tmp_path, language="python")
    assert len(result) == 2
    assert {v.function for v in result} == {"func_a", "func_b"}
```

### Group 5 — `run_quality_checks_for_all_languages()` (mocked scripts)

```python
def test_run_returns_empty_when_no_supported_files(tmp_path) -> None:
    (tmp_path / "foo.js").write_text("")
    file_v, func_v = run_quality_checks_for_all_languages(tmp_path)
    assert file_v == []
    assert func_v == []

@patch("cortex.tools.execution.file_language_router._run_script_with_files")
def test_run_invokes_check_file_sizes_and_check_function_lengths(mock_run, tmp_path) -> None:
    mock_run.return_value = CheckResult(
        check_type="test", success=True, output="✅", errors=[], warnings=[], files_modified=[]
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("x = 1")
    run_quality_checks_for_all_languages(tmp_path)
    script_names = {c.args[2] for c in mock_run.call_args_list}
    assert "check_file_sizes.py" in script_names
    assert "check_function_lengths.py" in script_names

@patch("cortex.tools.execution.file_language_router._run_script_with_files")
def test_run_returns_violations_parsed_from_script_output(mock_run, tmp_path) -> None:
    output = "  src/foo.py: 450 lines (max: 400, excess: 50)\n"
    mock_run.return_value = CheckResult(
        check_type="test", success=False, output=output, errors=[], warnings=[], files_modified=[]
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("x = 1")
    file_v, _ = run_quality_checks_for_all_languages(tmp_path)
    assert len(file_v) >= 1

@patch("cortex.tools.execution.file_language_router._run_script_with_files")
def test_run_merges_violations_across_languages(mock_run, tmp_path) -> None:
    py_output = "  src/foo.py: 450 lines (max: 400, excess: 50)\n"
    swift_output = "  Sources/Bar.swift: 410 lines (max: 400, excess: 10)\n"

    def side_effect(project_root, language, script_name, files):
        if language == "python" and "file_sizes" in script_name:
            return CheckResult(check_type="t", success=False, output=py_output,
                               errors=[], warnings=[], files_modified=[])
        if language == "swift" and "file_sizes" in script_name:
            return CheckResult(check_type="t", success=False, output=swift_output,
                               errors=[], warnings=[], files_modified=[])
        return CheckResult(check_type="t", success=True, output="✅",
                           errors=[], warnings=[], files_modified=[])

    mock_run.side_effect = side_effect
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("x = 1")
    (tmp_path / "Sources").mkdir()
    (tmp_path / "Sources" / "Bar.swift").write_text("// x")
    file_v, _ = run_quality_checks_for_all_languages(tmp_path)
    assert len(file_v) == 2

def test_run_accepts_explicit_files_list(tmp_path) -> None:
    """Explicit files= parameter bypasses collect_project_files."""
    with patch("cortex.tools.execution.file_language_router._run_script_with_files") as mock_run:
        mock_run.return_value = CheckResult(
            check_type="t", success=True, output="✅", errors=[], warnings=[], files_modified=[]
        )
        explicit = [tmp_path / "Foo.swift"]
        run_quality_checks_for_all_languages(tmp_path, files=explicit)
    # _run_script_with_files should be called with swift language
    calls = mock_run.call_args_list
    assert any(c.args[1] == "swift" for c in calls)
```

### Group 6 — `execute_quality()` regression tests

```python
# Import execute_quality from pre_commit_pipeline_quality

def _make_mock_adapter(project_root: Path) -> MagicMock:
    adapter = MagicMock()
    adapter.project_root = project_root
    adapter.lint_code.return_value = CheckResult(
        check_type="lint", success=True, output="ok", errors=[], warnings=[], files_modified=[]
    )
    return adapter

def test_execute_quality_calls_router_for_swift(tmp_path) -> None:
    """Regression: quality gate must NOT be skipped for Swift projects."""
    adapter = _make_mock_adapter(tmp_path)
    with patch(
        "cortex.tools.execution.pre_commit_pipeline_quality.run_quality_checks_for_all_languages"
    ) as mock_router:
        mock_router.return_value = ([], [])
        result = execute_quality(adapter, "swift")
    mock_router.assert_called_once_with(tmp_path)
    assert result.success

def test_execute_quality_calls_router_for_python(tmp_path) -> None:
    """Regression: Python projects still go through the router."""
    adapter = _make_mock_adapter(tmp_path)
    with patch(
        "cortex.tools.execution.pre_commit_pipeline_quality.run_quality_checks_for_all_languages"
    ) as mock_router:
        mock_router.return_value = ([], [])
        execute_quality(adapter, "python")
    mock_router.assert_called_once_with(tmp_path)

def test_execute_quality_fails_on_file_size_violation(tmp_path) -> None:
    adapter = _make_mock_adapter(tmp_path)
    violation = FileSizeViolation(file="Foo.swift", lines=450, max_lines=400, excess=50)
    with patch(
        "cortex.tools.execution.pre_commit_pipeline_quality.run_quality_checks_for_all_languages",
        return_value=([violation], []),
    ):
        result = execute_quality(adapter, "swift")
    assert not result.success
    assert len(result.file_size_violations) == 1
    assert result.file_size_violations[0].file == "Foo.swift"
```

---

## Success Criteria

- [ ] All test groups present in the file
- [ ] Tests pass with `pytest tests/unit/tools/execution/test_file_language_router.py`
- [ ] No real subprocess/synapse invocations in unit tests (all mocked)
- [ ] Group 2 `test_collect_project_files_includes_test_files` confirms Tests/ is included
- [ ] Group 6 `test_execute_quality_calls_router_for_swift` confirms the guard is gone
- [ ] File follows AAA pattern throughout
- [ ] No `Any` type; 100% type hints in test helpers
