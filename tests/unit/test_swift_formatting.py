"""Project formatter selection, pin enforcement, and scope regression tests."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.services.framework_adapters.swift_formatting import run_swift_format


@pytest.mark.parametrize("check", [True, False])
@pytest.mark.parametrize("package", [True, False])
def test_swift_formatting_honors_project_pin(
    tmp_path: Path, check: bool, package: bool
) -> None:
    source = tmp_path / "Main.swift"
    _ = source.write_text("let x=1\n")
    _ = (tmp_path / ".swiftformat").write_text("--indent 4\n")
    _ = (tmp_path / "swiftformat.version").write_text("0.62.1\n")
    if package:
        _ = (tmp_path / "Package.swift").write_text("// swift-tools-version:5.9")
    responses = [
        subprocess.CompletedProcess([], 0, "Main.swift\x00", ""),
        subprocess.CompletedProcess([], 0, "0.62.1\n", ""),
        subprocess.CompletedProcess([], 0, "", ""),
    ]
    with patch("subprocess.run", side_effect=responses) as run:
        result = (
            run_swift_format(tmp_path, check=True)
            if check
            else SwiftAdapter(str(tmp_path)).format_code()
        )
    assert result.success
    command = run.call_args.args[0]
    assert command[0] == "swiftformat"
    assert ("--lint" in command) is check
    assert command[-1] == str(source.resolve())
    assert "--config" in command
    assert run.call_args_list[1].args[0] == ["swiftformat", "--version"]
    assert source.read_text() == "let x=1\n"


@pytest.mark.parametrize("check", [True, False])
@pytest.mark.parametrize("version", ["0.61.0", "", "0.62.10"])
def test_swift_formatting_pin_mismatch_fails_without_fallback(
    tmp_path: Path, check: bool, version: str
) -> None:
    _ = (tmp_path / "Main.swift").write_text("let x=1\n")
    _ = (tmp_path / "swiftformat.version").write_text("0.62.1")
    with patch(
        "subprocess.run",
        side_effect=[
            subprocess.CompletedProcess([], 0, "Main.swift\x00", ""),
            subprocess.CompletedProcess([], 0, version, ""),
        ],
    ) as run:
        result = run_swift_format(tmp_path, check=check)
    assert not result.success
    assert "version mismatch" in result.output
    assert run.call_count == 2


@pytest.mark.parametrize("check", [True, False])
def test_swift_formatting_missing_binary_fails(tmp_path: Path, check: bool) -> None:
    _ = (tmp_path / "Main.swift").write_text("let x=1\n")
    _ = (tmp_path / ".swiftformat").write_text("")
    with patch(
        "subprocess.run",
        side_effect=[
            subprocess.CompletedProcess([], 0, "Main.swift\x00", ""),
            FileNotFoundError("swiftformat missing"),
        ],
    ) as run:
        result = run_swift_format(tmp_path, check=check)
    assert not result.success
    assert "swiftformat missing" in result.output
    assert run.call_count == 2


def test_swift_formatting_rejects_escaping_source(tmp_path: Path) -> None:
    with patch(
        "subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, "../Outside.swift\x00", ""),
    ) as run:
        result = run_swift_format(tmp_path, check=False)
    assert not result.success
    assert "outside the project" in result.output
    assert run.call_count == 1


@pytest.mark.parametrize("check", [True, False])
def test_swift_formatting_batches_only_owned_files(tmp_path: Path, check: bool) -> None:
    names = [f"Source{i}.swift" for i in range(101)]
    for name in names:
        _ = (tmp_path / name).write_text("let x=1\n")
    _ = (tmp_path / ".swiftformat").write_text("")
    vendor = tmp_path / ".build" / "checkouts" / "Vendor.swift"
    vendor.parent.mkdir(parents=True)
    _ = vendor.write_text("let x=1\n")
    with patch(
        "subprocess.run",
        side_effect=[
            subprocess.CompletedProcess(
                [], 0, "\x00".join([*names, ".build/checkouts/Vendor.swift"]), ""
            ),
            subprocess.CompletedProcess([], 1, "violation", ""),
            subprocess.CompletedProcess([], 0, "", ""),
        ],
    ) as run:
        result = run_swift_format(tmp_path, check=check)
    assert not result.success
    assert run.call_count == 3
    commands = [call.args[0] for call in run.call_args_list[1:]]
    sources = [arg for command in commands for arg in command if arg.endswith(".swift")]
    assert len(sources) == 101
    assert str(vendor) not in sources
    assert vendor.read_text() == "let x=1\n"


@pytest.mark.parametrize("conflict", [True, False])
def test_swift_formatting_invalid_configuration_fails(
    tmp_path: Path, conflict: bool
) -> None:
    _ = (tmp_path / "Main.swift").write_text("let x=1\n")
    _ = (tmp_path / "swiftformat.version").write_text("invalid")
    if conflict:
        _ = (tmp_path / ".swift-format").write_text("{}")
    with patch(
        "subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, "Main.swift\x00", ""),
    ) as run:
        result = run_swift_format(tmp_path, check=False)
    assert not result.success
    assert run.call_count == 1


@pytest.mark.parametrize("apple", [True, False])
def test_swift_formatting_unpinned_defaults(tmp_path: Path, apple: bool) -> None:
    _ = (tmp_path / "Main.swift").write_text("let x=1\n")
    if apple:
        _ = (tmp_path / ".swift-format").write_text("{}")
    with patch(
        "subprocess.run",
        side_effect=[
            subprocess.CompletedProcess([], 0, "Main.swift\x00", ""),
            subprocess.CompletedProcess([], 0, "", ""),
        ],
    ) as run:
        result = run_swift_format(tmp_path, check=False)
    assert result.success
    expected = ["swift", "format", "--in-place"] if apple else ["swiftformat"]
    assert run.call_args.args[0] == [
        *expected,
        str((tmp_path / "Main.swift").resolve()),
    ]
