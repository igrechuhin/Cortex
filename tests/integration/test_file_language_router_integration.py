"""Integration tests: real Synapse scripts invoked via FILES env var."""

from pathlib import Path

import pytest

from cortex.tools.execution.file_language_router import (
    run_quality_checks_for_all_languages,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

_CONFIG_ENV_KEYS: tuple[str, ...] = (
    "MAX_FILE_LINES",
    "FILE_SIZE_WARN_LINES",
    "WARN_FILE_LINES",
    "MAX_FUNCTION_LINES",
    "SRC_DIR",
    "SOURCES_DIR",
)


def _clear_synapse_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _CONFIG_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.integration
def test_swift_file_size_violation_caught_via_files_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TradeWing scenario: a 401-line Swift file triggers a size violation."""
    _clear_synapse_config_env(monkeypatch)
    sources = tmp_path / "Sources" / "App"
    sources.mkdir(parents=True)
    big_file = sources / "BigFile.swift"
    _ = big_file.write_text("\n".join(["let x = 1"] * 401), encoding="utf-8")

    file_v, func_v = run_quality_checks_for_all_languages(_REPO_ROOT, files=[big_file])

    assert func_v == []
    assert len(file_v) == 1
    assert file_v[0].lines == 401
    assert file_v[0].excess == 1
    assert Path(file_v[0].file).suffix == ".swift"


@pytest.mark.integration
def test_swift_test_file_included_in_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests/ swift files must be included when explicitly passed."""
    _clear_synapse_config_env(monkeypatch)
    tests_dir = tmp_path / "Tests" / "AppTests"
    tests_dir.mkdir(parents=True)
    test_file = tests_dir / "BigTests.swift"
    _ = test_file.write_text("\n".join(["let x = 1"] * 401), encoding="utf-8")

    file_v, func_v = run_quality_checks_for_all_languages(_REPO_ROOT, files=[test_file])

    assert func_v == []
    assert len(file_v) == 1
    assert Path(file_v[0].file).suffix == ".swift"


@pytest.mark.integration
def test_python_file_size_violation_still_caught(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: Python file-size checks must still work via the dispatcher."""
    _clear_synapse_config_env(monkeypatch)
    src = tmp_path / "src" / "myapp"
    src.mkdir(parents=True)
    py_file = src / "big.py"
    _ = py_file.write_text("\n".join(["x = 1"] * 401), encoding="utf-8")

    file_v, func_v = run_quality_checks_for_all_languages(_REPO_ROOT, files=[py_file])

    assert func_v == []
    assert len(file_v) == 1
    assert Path(file_v[0].file).suffix == ".py"


@pytest.mark.integration
def test_mixed_language_repo_both_violations_caught(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mixed project: .py and .swift file-size violations both detected."""
    _clear_synapse_config_env(monkeypatch)
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "Sources" / "App").mkdir(parents=True)

    py_file = tmp_path / "src" / "pkg" / "big.py"
    swift_file = tmp_path / "Sources" / "App" / "Big.swift"
    _ = py_file.write_text("\n".join(["x = 1"] * 401), encoding="utf-8")
    _ = swift_file.write_text("\n".join(["let x = 1"] * 401), encoding="utf-8")

    file_v, func_v = run_quality_checks_for_all_languages(
        _REPO_ROOT, files=[py_file, swift_file]
    )

    assert func_v == []
    assert len(file_v) == 2
    extensions = {Path(v.file).suffix for v in file_v}
    assert extensions == {".py", ".swift"}


@pytest.mark.integration
def test_unknown_extension_silently_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_synapse_config_env(monkeypatch)
    unknown = tmp_path / "foo.js"
    _ = unknown.write_text("const x = 1;\n" * 500, encoding="utf-8")

    file_v, func_v = run_quality_checks_for_all_languages(_REPO_ROOT, files=[unknown])

    assert file_v == []
    assert func_v == []


@pytest.mark.integration
def test_clean_project_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_synapse_config_env(monkeypatch)
    (tmp_path / "src").mkdir()
    small_py = tmp_path / "src" / "small.py"
    _ = small_py.write_text("x = 1\n", encoding="utf-8")

    file_v, func_v = run_quality_checks_for_all_languages(_REPO_ROOT, files=[small_py])

    assert file_v == []
    assert func_v == []


@pytest.mark.integration
def test_swift_function_length_violation_caught(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Swift function-length check must fire via dispatcher."""
    _clear_synapse_config_env(monkeypatch)
    sources = tmp_path / "Sources" / "App"
    sources.mkdir(parents=True)

    lines: list[str] = ["struct Foo {", "    func longFunc() {"]
    lines += ["        let x = 1"] * 31
    lines += ["    }", "}"]
    swift_file = sources / "Foo.swift"
    _ = swift_file.write_text("\n".join(lines), encoding="utf-8")

    file_v, func_v = run_quality_checks_for_all_languages(
        _REPO_ROOT, files=[swift_file]
    )

    assert file_v == []
    assert any(v.function == "longFunc" for v in func_v)
