"""Tests for file_language_router."""

from pathlib import Path

from cortex.core.constants import EXTENSION_SCRIPT_MAP, FILE_SIZE_EXCLUDED_FILENAMES
from cortex.tools.execution import file_language_router as flr


def test_route_files_groups_python_and_swift() -> None:
    mapped = flr.route_files([Path("a.py"), Path("b.swift")])
    assert mapped == {"python": [Path("a.py")], "swift": [Path("b.swift")]}


def test_route_files_omits_unknown_extension() -> None:
    assert flr.route_files([Path("x.js"), Path("y.py")]) == {"python": [Path("y.py")]}


def test_route_files_custom_extension_map() -> None:
    custom = {".py": "python", ".rs": "rust"}
    assert flr.route_files([Path("lib.rs")], extension_map=custom) == {
        "rust": [Path("lib.rs")]
    }


def test_collect_project_files_includes_tests_and_excludes_skip_dirs(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "Tests").mkdir()
    py_file = tmp_path / "src" / "mod.py"
    _ = py_file.write_text("# x\n", encoding="utf-8")
    swift_file = tmp_path / "Tests" / "T.swift"
    _ = swift_file.write_text("// x\n", encoding="utf-8")
    pycache = tmp_path / "src" / "__pycache__"
    pycache.mkdir()
    _ = (pycache / "x.py").write_text("", encoding="utf-8")

    collected = flr.collect_project_files(tmp_path)
    assert py_file.resolve() in collected
    assert swift_file.resolve() in collected
    assert not any("__pycache__" in p.parts for p in collected)


def test_collect_project_files_excludes_models_py_name(tmp_path: Path) -> None:
    root = tmp_path / "pkg"
    root.mkdir()
    models = root / "models.py"
    _ = models.write_text("x=1\n", encoding="utf-8")
    ok = root / "other.py"
    _ = ok.write_text("y=2\n", encoding="utf-8")
    out = flr.collect_project_files(tmp_path)
    assert models.resolve() not in out
    assert ok.resolve() in out


def test_parse_file_size_violations(tmp_path: Path) -> None:
    root = tmp_path
    text = (
        "❌ File size violations detected:\n\n"
        "  src/huge.py: 450 lines (max: 400, excess: 50)\n"
    )
    violations = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        text,
        root,
    )
    assert len(violations) == 1
    v = violations[0]
    assert v.file == "src/huge.py"
    assert v.lines == 450
    assert v.max_lines == 400
    assert v.excess == 50


def test_parse_python_function_lines(tmp_path: Path) -> None:
    root = tmp_path
    text = (
        "❌ Function length violations detected:\n\n"
        "  src/cortex/foo.py:\n"
        "    my_func() at line 42: 35 lines (max: 30, excess: 5)\n"
    )
    violations = (
        flr._parse_function_length_violations(  # pyright: ignore[reportPrivateUsage]
            text,
            root,
            "python",
        )
    )
    assert len(violations) == 1
    v = violations[0]
    assert v.file == "src/cortex/foo.py"
    assert v.function == "my_func"
    assert v.line == 42
    assert v.lines == 35
    assert v.max_lines == 30
    assert v.excess == 5


def test_parse_swift_function_lines(tmp_path: Path) -> None:
    root = tmp_path
    line = "  Sources/Foo/Bar.swift:42: myFunc() — 35 lines (max: 30, excess: 5)"
    violations = (
        flr._parse_function_length_violations(  # pyright: ignore[reportPrivateUsage]
            line,
            root,
            "swift",
        )
    )
    assert len(violations) == 1
    v = violations[0]
    assert v.file == "Sources/Foo/Bar.swift"
    assert v.function == "myFunc"
    assert v.line == 42


def test_run_quality_checks_no_matching_files(tmp_path: Path) -> None:
    _ = (tmp_path / "readme.txt").write_text("hi", encoding="utf-8")
    fs, fn = flr.run_quality_checks_for_all_languages(tmp_path)
    assert fs == []
    assert fn == []


def test_extension_script_map_has_expected_keys() -> None:
    assert ".py" in EXTENSION_SCRIPT_MAP
    assert ".swift" in EXTENSION_SCRIPT_MAP


def test_file_size_excluded_constant_matches_router(tmp_path: Path) -> None:
    assert "models.py" in FILE_SIZE_EXCLUDED_FILENAMES
    _ = (tmp_path / "models.py").write_text("x=1\n", encoding="utf-8")
    assert flr.collect_project_files(tmp_path) == []
