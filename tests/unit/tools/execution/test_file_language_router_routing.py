"""Unit tests for route_files() and collect_project_files()."""

from __future__ import annotations

from pathlib import Path

from cortex.core.constants import EXTENSION_SCRIPT_MAP
from cortex.tools.execution.file_language_router import (
    collect_project_files,
    route_files,
)

# ---------------------------------------------------------------------------
# route_files()
# ---------------------------------------------------------------------------


def test_route_files_groups_py_files_under_python() -> None:
    files = [Path("a.py"), Path("b.py"), Path("c.swift")]
    result = route_files(files)
    assert result["python"] == [Path("a.py"), Path("b.py")]


def test_route_files_groups_swift_files_under_swift() -> None:
    files = [Path("a.swift"), Path("b.swift")]
    assert route_files(files) == {"swift": [Path("a.swift"), Path("b.swift")]}


def test_route_files_skips_unknown_extensions() -> None:
    assert route_files([Path("a.elm"), Path("b.ex"), Path("c.dart")]) == {}


def test_route_files_mixed_language_repo() -> None:
    result = route_files([Path("a.py"), Path("b.swift"), Path("c.rs")])
    assert set(result.keys()) == {"python", "swift", "rust"}
    assert result["python"] == [Path("a.py")]
    assert result["swift"] == [Path("b.swift")]
    assert result["rust"] == [Path("c.rs")]


def test_route_files_empty_list() -> None:
    assert route_files([]) == {}


def test_route_files_uses_extension_map_override() -> None:
    result = route_files(
        [Path("a.ts"), Path("b.py")], extension_map={".ts": "typescript"}
    )
    assert result == {"typescript": [Path("a.ts")]}


def test_extension_script_map_is_sane() -> None:
    assert ".py" in EXTENSION_SCRIPT_MAP
    assert ".swift" in EXTENSION_SCRIPT_MAP
    assert EXTENSION_SCRIPT_MAP[".go"] == "go"
    assert EXTENSION_SCRIPT_MAP[".rs"] == "rust"
    assert EXTENSION_SCRIPT_MAP[".java"] == "java"
    assert EXTENSION_SCRIPT_MAP[".kt"] == "kotlin"
    assert EXTENSION_SCRIPT_MAP[".kts"] == "kotlin"
    assert EXTENSION_SCRIPT_MAP[".cs"] == "csharp"
    assert EXTENSION_SCRIPT_MAP[".ts"] == "typescript"
    assert EXTENSION_SCRIPT_MAP[".tsx"] == "typescript"
    assert EXTENSION_SCRIPT_MAP[".js"] == "javascript"
    assert EXTENSION_SCRIPT_MAP[".jsx"] == "javascript"


# ---------------------------------------------------------------------------
# collect_project_files()
# ---------------------------------------------------------------------------


def test_collect_project_files_includes_py_and_swift(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    _ = (tmp_path / "src" / "foo.py").write_text("pass", encoding="utf-8")
    (tmp_path / "Sources").mkdir()
    _ = (tmp_path / "Sources" / "Bar.swift").write_text("// swift", encoding="utf-8")

    names = {f.name for f in collect_project_files(tmp_path)}
    assert "foo.py" in names
    assert "Bar.swift" in names


def test_collect_project_files_includes_supported_non_native_extensions(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "Main.java").write_text("class Main {}", encoding="utf-8")
    _ = (tmp_path / "Api.kt").write_text("fun main() {}", encoding="utf-8")
    _ = (tmp_path / "Program.cs").write_text("class Program {}", encoding="utf-8")
    _ = (tmp_path / "main.go").write_text("package main", encoding="utf-8")
    _ = (tmp_path / "lib.rs").write_text("fn main() {}", encoding="utf-8")
    _ = (tmp_path / "index.ts").write_text("export {}", encoding="utf-8")
    _ = (tmp_path / "index.js").write_text("console.log(1)", encoding="utf-8")

    names = {f.name for f in collect_project_files(tmp_path)}
    assert {
        "Main.java",
        "Api.kt",
        "Program.cs",
        "main.go",
        "lib.rs",
        "index.ts",
        "index.js",
    } <= names


def test_collect_project_files_excludes_pycache(tmp_path: Path) -> None:
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    _ = (cache / "compiled.pyc").write_text("", encoding="utf-8")
    assert not any("__pycache__" in str(f) for f in collect_project_files(tmp_path))


def test_collect_project_files_excludes_swift_test_files(tmp_path: Path) -> None:
    # Repo-wide scan: Tests/ is excluded; tests can still be checked when passed
    # explicitly via run_quality_checks_for_all_languages(files=[...]).
    (tmp_path / "Tests").mkdir()
    _ = (tmp_path / "Tests" / "FooTests.swift").write_text("// test", encoding="utf-8")
    assert not any(f.name == "FooTests.swift" for f in collect_project_files(tmp_path))


def test_collect_project_files_excludes_lowercase_tests_dir(tmp_path: Path) -> None:
    # Repo-wide scan: tests/ is excluded; explicit file lists still include them.
    (tmp_path / "tests").mkdir()
    _ = (tmp_path / "tests" / "conftest.py").write_text("", encoding="utf-8")
    assert not any(f.name == "conftest.py" for f in collect_project_files(tmp_path))


def test_collect_project_files_excludes_python_test_files(tmp_path: Path) -> None:
    # Repo-wide scan: tests are excluded.
    (tmp_path / "tests").mkdir()
    _ = (tmp_path / "tests" / "test_foo.py").write_text("x = 1", encoding="utf-8")
    assert not any(f.name == "test_foo.py" for f in collect_project_files(tmp_path))


def test_collect_project_files_includes_dispatcher_excluded_py_files(
    tmp_path: Path,
) -> None:
    # SIG-4 regression guard: FUNCTION_LENGTH_EXCLUDED_PATHS files must still
    # appear in the collected file list so file-size checks can catch them.
    (tmp_path / "src" / "cortex" / "tools" / "plans").mkdir(parents=True)
    plan = tmp_path / "src" / "cortex" / "tools" / "plans" / "plan.py"
    _ = plan.write_text("x = 1", encoding="utf-8")
    assert any(f.name == "plan.py" for f in collect_project_files(tmp_path))


def test_collect_project_files_excludes_dot_git(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    _ = (tmp_path / ".git" / "config").write_text("", encoding="utf-8")
    assert not any(".git" in str(f) for f in collect_project_files(tmp_path))


def test_collect_project_files_excludes_models_py(tmp_path: Path) -> None:
    _ = (tmp_path / "models.py").write_text("class M: pass", encoding="utf-8")
    assert not any(f.name == "models.py" for f in collect_project_files(tmp_path))


def test_collect_project_files_returns_sorted_paths(tmp_path: Path) -> None:
    for name in ["z.py", "a.py", "m.swift"]:
        _ = (tmp_path / name).write_text("", encoding="utf-8")
    result = collect_project_files(tmp_path)
    assert result == sorted(result)


def test_collect_project_files_excludes_node_modules(tmp_path: Path) -> None:
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    _ = (nm / "index.js").write_text("", encoding="utf-8")
    assert not any("node_modules" in str(f) for f in collect_project_files(tmp_path))
