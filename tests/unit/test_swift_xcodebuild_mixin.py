"""Tests for xcodebuild ``-skip-testing:`` wiring (SwiftXcodebuildMixin)."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.services.framework_adapters.swift_adapter import SwiftAdapter

_PASSED_STDOUT = b"Test run with 3 tests in 1 suite passed after 1.0s"
_SCHEME_LIST_STDOUT = "Schemes:\n    App-Dev\n    App-Prod\n\n"


def _xcodebuild_side_effect(captured: dict[str, list[str]]):
    """Return a subprocess.run side_effect dispatching on the xcodebuild subcommand."""

    def side_effect(
        cmd: list[str] | str | bytes,
        *args: object,
        **kwargs: object,
    ) -> subprocess.CompletedProcess[object]:
        assert isinstance(cmd, list)
        if cmd[0] == "xcrun":
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )
        if cmd[0] == "xcodebuild" and "-list" in cmd:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=_SCHEME_LIST_STDOUT, stderr=""
            )
        if cmd[0] == "xcodebuild" and "build-for-testing" in cmd:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=b"", stderr=b""
            )
        if cmd[0] == "xcodebuild" and "test-without-building" in cmd:
            captured["test_args"] = [str(part) for part in cmd]
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=_PASSED_STDOUT, stderr=b""
            )
        raise AssertionError(f"unexpected subprocess.run call: {cmd!r}")

    return side_effect


def _make_xcodeproj(tmpdir: str) -> None:
    (Path(tmpdir) / "App.xcodeproj").mkdir()


def _write_skip_testing_config(tmpdir: str) -> None:
    """Write .cortex/config/swift_test.json with two skip_testing identifiers."""
    cfg_dir = Path(tmpdir) / ".cortex" / "config"
    cfg_dir.mkdir(parents=True)
    _ = (cfg_dir / "swift_test.json").write_text(
        json.dumps(
            {
                "skip_testing": [
                    "SampleTests/LiveNetworkIntegrationTests",
                    "SampleTests/AnotherSlowSuite/testFoo",
                ]
            }
        ),
        encoding="utf-8",
    )


def _assert_skip_testing_flags_precede_action(args: list[str]) -> None:
    """Assert both -skip-testing: flags are present and precede the test action."""
    assert "-skip-testing:SampleTests/LiveNetworkIntegrationTests" in args
    assert "-skip-testing:SampleTests/AnotherSlowSuite/testFoo" in args
    action_index = args.index("test-without-building")
    assert (
        args.index("-skip-testing:SampleTests/LiveNetworkIntegrationTests")
        < action_index
    )
    assert (
        args.index("-skip-testing:SampleTests/AnotherSlowSuite/testFoo") < action_index
    )


@patch("cortex.services.framework_adapters.swift_xcodebuild_mixin.subprocess.run")
def test_run_tests_passes_configured_skip_testing_flags(mock_run: MagicMock) -> None:
    """Identifiers from .cortex/config/swift_test.json become -skip-testing: flags."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _make_xcodeproj(tmpdir)
        _write_skip_testing_config(tmpdir)
        captured: dict[str, list[str]] = {}
        mock_run.side_effect = _xcodebuild_side_effect(captured)

        adapter = SwiftAdapter(tmpdir)
        result = adapter.run_tests()

        assert result.success is True
        _assert_skip_testing_flags_precede_action(captured["test_args"])


@patch("cortex.services.framework_adapters.swift_xcodebuild_mixin.subprocess.run")
def test_run_tests_omits_skip_testing_flags_when_unconfigured(
    mock_run: MagicMock,
) -> None:
    """No swift_test.json present → xcodebuild argv has no -skip-testing: flags."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _make_xcodeproj(tmpdir)
        captured: dict[str, list[str]] = {}
        mock_run.side_effect = _xcodebuild_side_effect(captured)

        adapter = SwiftAdapter(tmpdir)
        result = adapter.run_tests()

        assert result.success is True
        args = captured["test_args"]
        assert not any(part.startswith("-skip-testing:") for part in args)
