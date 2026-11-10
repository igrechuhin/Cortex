"""Selected quality gates validate sources without broad autofix."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.framework_adapters.selected_checks import selected_source_checks
from cortex.services.framework_adapters.swift_adapter import SwiftAdapter


def test_python_selected_checks_do_not_modify_sources(tmp_path: Path) -> None:
    unrelated = tmp_path / "unrelated.py"
    _ = unrelated.write_text("x=1\n")
    before = unrelated.read_bytes()
    adapter = PythonAdapter(str(tmp_path))
    completed = subprocess.CompletedProcess(["tool"], 0, "", "")
    with (
        patch("subprocess.run", return_value=completed) as run,
        patch.object(adapter, "fix_errors") as fix,
        patch.object(adapter, "format_code") as format_code,
    ):
        lint, formatting = selected_source_checks(adapter)
    commands = [call.args[0] for call in run.call_args_list]
    assert len(commands) == 3
    assert "--check" in commands[1]
    for command in (commands[0], commands[2]):
        assert "check" in command
        assert "--no-fix" in command
        assert "--no-fix-only" in command
    assert "--select" in commands[2]
    assert "I" in commands[2]
    assert all("--fix" not in command for command in commands)
    fix.assert_not_called()
    format_code.assert_not_called()
    assert lint.success and formatting.success
    assert unrelated.read_bytes() == before


def test_swift_selected_checks_lint_without_formatting(tmp_path: Path) -> None:
    unrelated = tmp_path / "unrelated.swift"
    _ = unrelated.write_text("let x=1\n")
    before = unrelated.read_bytes()
    _ = (tmp_path / "Package.swift").write_text("// swift-tools-version:5.9")
    adapter = SwiftAdapter(str(tmp_path))
    completed = subprocess.CompletedProcess(["swift"], 0, "", "")
    source_list = subprocess.CompletedProcess(["git"], 0, "unrelated.swift\x00", "")
    with (
        patch.object(adapter, "has_package_swift", return_value=True),
        patch("subprocess.run", side_effect=[completed, source_list, completed]) as run,
    ):
        lint, formatting = selected_source_checks(adapter)
    commands = [call.args[0] for call in run.call_args_list]
    assert commands == [
        ["swift", "build"],
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        ["swift", "format", "lint", "--strict", str(unrelated.resolve())],
    ]
    assert lint.success and formatting.success
    assert unrelated.read_bytes() == before


def test_selected_checks_keep_all_categories_after_failure(tmp_path: Path) -> None:
    adapter = PythonAdapter(str(tmp_path))
    failed = subprocess.CompletedProcess(["tool"], 1, "lint violation", "")
    with patch("subprocess.run", return_value=failed) as run:
        lint, formatting = selected_source_checks(adapter)
    assert run.call_count == 3
    assert not lint.success
    assert not formatting.success
    assert len(formatting.errors) == 2


def test_selected_checks_missing_tools_fail_closed(tmp_path: Path) -> None:
    adapter = PythonAdapter(str(tmp_path))
    with patch("subprocess.run", side_effect=FileNotFoundError("missing tool")):
        lint, formatting = selected_source_checks(adapter)
    assert not lint.success
    assert not formatting.success


def test_selected_checks_reject_xcode(tmp_path: Path) -> None:
    _ = (tmp_path / "Package.swift").write_text("// swift-tools-version:5.9")
    adapter = SwiftAdapter(str(tmp_path))
    with patch.object(adapter, "has_package_swift", return_value=False):
        with pytest.raises(ValueError, match="Swift Package Manager"):
            _ = selected_source_checks(adapter)


def test_swift_selected_format_excludes_build_checkouts(tmp_path: Path) -> None:
    source = tmp_path / "Main.swift"
    _ = source.write_text("let x = 1\n")
    vendor = tmp_path / ".build" / "checkouts" / "Vendor.swift"
    vendor.parent.mkdir(parents=True)
    _ = vendor.write_text("let x=1\n")
    _ = (tmp_path / "Package.swift").write_text("// swift-tools-version:5.9")
    adapter = SwiftAdapter(str(tmp_path))
    completed = subprocess.CompletedProcess(["swift"], 0, "", "")
    source_list = subprocess.CompletedProcess(
        ["git"], 0, "Main.swift\x00.build/checkouts/Vendor.swift\x00", ""
    )
    with (
        patch.object(adapter, "has_package_swift", return_value=True),
        patch("subprocess.run", side_effect=[completed, source_list, completed]) as run,
    ):
        _, formatting = selected_source_checks(adapter)
    assert formatting.success
    assert run.call_args.args[0] == [
        "swift",
        "format",
        "lint",
        "--strict",
        str(source.resolve()),
    ]
    assert vendor.read_text() == "let x=1\n"


def test_swift_selected_format_without_source_scope_fails(tmp_path: Path) -> None:
    _ = (tmp_path / "Package.swift").write_text("// swift-tools-version:5.9")
    adapter = SwiftAdapter(str(tmp_path))
    completed = subprocess.CompletedProcess(["swift"], 0, "", "")
    with (
        patch.object(adapter, "has_package_swift", return_value=True),
        patch("subprocess.run", return_value=completed) as run,
    ):
        _, formatting = selected_source_checks(adapter)
    assert not formatting.success
    assert run.call_count == 2


@pytest.mark.parametrize(
    "budget,override,expected",
    [(None, None, 300), (1800, None, 1800), (1800, "2400", 2400)],
)
def test_swift_selected_build_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    budget: int | None,
    override: str | None,
    expected: int,
) -> None:
    adapter = SwiftAdapter(str(tmp_path))
    monkeypatch.delenv("BUILD_TIMEOUT", raising=False)
    if override is not None:
        monkeypatch.setenv("BUILD_TIMEOUT", override)
    completed = subprocess.CompletedProcess(["swift"], 0, "", "")
    with (
        patch.object(adapter, "has_package_swift", return_value=True),
        patch("subprocess.run", return_value=completed) as run,
    ):
        lint, _ = selected_source_checks(adapter, timeout=budget)
    assert lint.success
    assert run.call_args_list[0].kwargs["timeout"] == expected


@pytest.mark.parametrize("override", ["0", "-1", "bad", "1.5", ""])
def test_swift_selected_invalid_budget_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, override: str
) -> None:
    adapter = SwiftAdapter(str(tmp_path))
    monkeypatch.setenv("BUILD_TIMEOUT", override)
    with (
        patch.object(adapter, "has_package_swift", return_value=True),
        patch("subprocess.run") as run,
    ):
        with pytest.raises(ValueError):
            _ = selected_source_checks(adapter, timeout=1800)
    run.assert_not_called()


def test_swift_selected_build_timeout_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = SwiftAdapter(str(tmp_path))
    monkeypatch.delenv("BUILD_TIMEOUT", raising=False)
    with (
        patch.object(adapter, "has_package_swift", return_value=True),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(["swift", "build"], 1800),
        ) as run,
    ):
        lint, formatting = selected_source_checks(adapter, timeout=1800)
    assert not lint.success
    assert lint.errors and "1800" in lint.output
    assert not formatting.success
    assert run.call_args_list[0].kwargs["timeout"] == 1800
