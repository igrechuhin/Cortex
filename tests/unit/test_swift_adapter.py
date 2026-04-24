"""Tests for Swift framework adapter."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.services.framework_adapters.swift_coverage import merge_profraw_to_profdata


def _argv_contains(argv: list[str], needle: str) -> bool:
    return any(needle in str(part) for part in argv)


def _subprocess_swift_test_then_skip_coverage(
    test_stdout: bytes,
    test_returncode: int = 0,
):
    """``swift test`` succeeds; coverage collection aborts (no bin path)."""

    def _failed_proc() -> MagicMock:
        m = MagicMock()
        m.returncode = 1
        m.stdout = b""
        m.stderr = b"skip"
        return m

    def side_effect(
        cmd: list[str] | str | bytes,
        *args: object,
        **kwargs: object,
    ) -> MagicMock:
        if not isinstance(cmd, list) or not cmd:
            return _failed_proc()
        if cmd[0] == "swift" and "test" in cmd:
            m = MagicMock()
            m.returncode = test_returncode
            m.stdout = test_stdout
            m.stderr = b""
            return m
        return _failed_proc()

    return side_effect


def _seed_codecov_project(
    root: Path,
    *,
    count: int,
    covered: int,
) -> Path:
    _ = (root / "Package.swift").write_text("// swift-tools-version:5.9\n")
    bin_path = root / ".build" / "debug"
    codecov = bin_path / "codecov"
    codecov.mkdir(parents=True)
    _ = (codecov / "default.profdata").write_bytes(b"x")
    payload = {
        "data": [
            {
                "files": [
                    {
                        "filename": str(root / "Sources" / "App.swift"),
                        "summary": {"lines": {"count": count, "covered": covered}},
                    },
                ],
            },
        ],
    }
    _ = (codecov / "export.json").write_text(json.dumps(payload), encoding="utf-8")
    return bin_path


def _seed_codecov_project_app_and_pb(root: Path) -> Path:
    """Two source files: App.swift 90/100 lines, x.pb.swift 0/100 (dilutes global)."""
    _ = (root / "Package.swift").write_text("// swift-tools-version:5.9\n")
    bin_path = root / ".build" / "debug"
    codecov = bin_path / "codecov"
    codecov.mkdir(parents=True)
    _ = (codecov / "default.profdata").write_bytes(b"x")
    payload = {
        "data": [
            {
                "files": [
                    {
                        "filename": str(root / "Sources" / "App.swift"),
                        "summary": {"lines": {"count": 100, "covered": 90}},
                    },
                    {
                        "filename": str(root / "Sources" / "Generated" / "x.pb.swift"),
                        "summary": {"lines": {"count": 100, "covered": 0}},
                    },
                ],
            },
        ],
    }
    _ = (codecov / "export.json").write_text(json.dumps(payload), encoding="utf-8")
    return bin_path


def _write_swift_coverage_json(root: Path, patterns: list[str]) -> None:
    cfg_dir = root / ".cortex" / "config"
    cfg_dir.mkdir(parents=True)
    _ = (cfg_dir / "swift_coverage.json").write_text(
        json.dumps({"exclude_filename_regex_patterns": patterns}),
        encoding="utf-8",
    )


def _swift_test_and_bin_path_side_effect(bin_path: Path):
    def side_effect(
        cmd: list[str] | str | bytes,
        *args: object,
        **kwargs: object,
    ) -> MagicMock:
        assert isinstance(cmd, list)
        m = MagicMock()
        if cmd[:2] == ["swift", "test"]:
            m.returncode = 0
            m.stdout = b"\t Executed 1 tests, with 0 failures (0 unexpected) in 0.1 (0.1) seconds\n"
            m.stderr = b""
            return m
        if _argv_contains(cmd, "show-bin-path"):
            m.returncode = 0
            m.stdout = str(bin_path.resolve()).encode() + b"\n"
            m.stderr = b""
            return m
        raise AssertionError(f"unexpected subprocess: {cmd!r}")

    return side_effect


def _seed_llvm_cov_project(root: Path) -> Path:
    _ = (root / "Package.swift").write_text("// swift-tools-version:5.9\n")
    bin_path = root / ".build" / "debug"
    codecov = bin_path / "codecov"
    codecov.mkdir(parents=True)
    _ = (codecov / "default.profdata").write_bytes(b"x")
    xctest = bin_path / "DemoPackageTests.xctest"
    xctest.mkdir(parents=True)
    if sys.platform == "darwin":
        exe = xctest / "Contents" / "MacOS" / "DemoPackageTests"
        exe.parent.mkdir(parents=True)
    else:
        exe = xctest / "DemoPackageTests"
    _ = exe.write_bytes(b"")
    _ = exe.chmod(0o755)
    return bin_path


def _swift_test_bin_and_llvm_cov_side_effect(bin_path: Path, report: bytes):
    def side_effect(
        cmd: list[str] | str | bytes,
        *args: object,
        **kwargs: object,
    ) -> MagicMock:
        assert isinstance(cmd, list)
        m = MagicMock()
        if cmd[:2] == ["swift", "test"]:
            m.returncode = 0
            m.stdout = b"\t Executed 1 tests, with 0 failures (0 unexpected) in 0.1 (0.1) seconds\n"
            m.stderr = b""
            return m
        if _argv_contains(cmd, "show-bin-path"):
            m.returncode = 0
            m.stdout = str(bin_path.resolve()).encode() + b"\n"
            m.stderr = b""
            return m
        if cmd and cmd[0] in ("llvm-cov", "xcrun"):
            m.returncode = 0
            m.stdout = report
            m.stderr = b""
            return m
        raise AssertionError(f"unexpected subprocess: {cmd!r}")

    return side_effect


def _mock_process(stdout: bytes) -> MagicMock:
    process = MagicMock()
    process.returncode = 0
    process.stdout = stdout
    process.stderr = b""
    return process


def _swift_test_bin_and_llvm_cov_export_side_effect(
    bin_path: Path, export_json: bytes, export_call_seen: list[bool]
):
    def side_effect(
        cmd: list[str] | str | bytes,
        *args: object,
        **kwargs: object,
    ) -> MagicMock:
        assert isinstance(cmd, list)
        if cmd[:2] == ["swift", "test"]:
            return _mock_process(
                b"\t Executed 1 tests, with 0 failures (0 unexpected) in 0.1 (0.1) seconds\n"
            )
        if _argv_contains(cmd, "show-bin-path"):
            return _mock_process(str(bin_path.resolve()).encode() + b"\n")
        if cmd and cmd[0] in ("llvm-cov", "xcrun") and "export" in cmd:
            export_call_seen[0] = True
            return _mock_process(export_json)
        if cmd and cmd[0] in ("llvm-cov", "xcrun"):
            return _mock_process(b"Lines Missed Cover\nTOTAL 180 58 67.78%\n")
        raise AssertionError(f"unexpected subprocess: {cmd!r}")

    return side_effect


def _llvm_cov_export_payload() -> bytes:
    return json.dumps(
        {
            "data": [
                {
                    "files": [
                        {
                            "filename": "/src/App.swift",
                            "summary": {"lines": {"count": 100, "covered": 50}},
                        },
                        {
                            "filename": "/src/Helper.swift",
                            "summary": {"lines": {"count": 80, "covered": 72}},
                        },
                    ]
                }
            ]
        }
    ).encode()


class TestSwiftAdapter:
    """Test Swift framework adapter."""

    def test_init_with_project_root(self) -> None:
        """Adapter initializes with project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            assert adapter.project_root == Path(tmpdir)

    def test_init_without_project_root(self) -> None:
        """Adapter initializes with cwd when project_root is None."""
        adapter = SwiftAdapter()
        assert adapter.project_root == Path.cwd()

    def test_has_package_swift_true_when_package_swift_exists(self) -> None:
        """_has_package_swift returns True when Package.swift is present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            adapter = SwiftAdapter(str(tmpdir))
            assert adapter.has_package_swift() is True

    def test_has_package_swift_false_when_no_package_swift(self) -> None:
        """_has_package_swift returns False when Package.swift is absent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            assert adapter.has_package_swift() is False

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_returns_error_when_no_package_swift(
        self, mock_run: MagicMock
    ) -> None:
        """run_tests returns error when no Package.swift found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()
            mock_run.assert_not_called()
            assert result.success is False
            assert "Package.swift" in result.output

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_success_when_swift_test_exits_0(
        self, mock_run: MagicMock
    ) -> None:
        """run_tests returns success when swift test exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_run.side_effect = _subprocess_swift_test_then_skip_coverage(
                b"Test run: 3 passed", 0
            )

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is True
            call_args = mock_run.call_args_list[0][0][0]
            assert "swift" in call_args
            assert "test" in call_args
            assert "--enable-code-coverage" in call_args

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_disables_mlx_metal_by_default(self, mock_run: MagicMock) -> None:
        """swift test subprocess gets MLX_DISABLE_METAL=1 to avoid SIGBUS on Apple Silicon."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_run.side_effect = _subprocess_swift_test_then_skip_coverage(
                b"Test run: 1 passed", 0
            )
            adapter = SwiftAdapter(str(tmpdir))
            _ = adapter.run_tests()
            swift_test_kwargs = mock_run.call_args_list[0][1]
            env = swift_test_kwargs.get("env")
            assert env is not None, "swift test must run with an explicit env override"
            assert env.get("MLX_DISABLE_METAL") == "1"

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_honors_swift_test_allow_metal_opt_out(
        self, mock_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SWIFT_TEST_ALLOW_METAL=1 disables the MLX override for diagnostic runs."""
        monkeypatch.setenv("SWIFT_TEST_ALLOW_METAL", "1")
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_run.side_effect = _subprocess_swift_test_then_skip_coverage(
                b"Test run: 1 passed", 0
            )
            adapter = SwiftAdapter(str(tmpdir))
            _ = adapter.run_tests()
            swift_test_kwargs = mock_run.call_args_list[0][1]
            env = swift_test_kwargs.get("env")
            assert env is None or "MLX_DISABLE_METAL" not in env

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_tolerates_binary_output(self, mock_run: MagicMock) -> None:
        """run_tests does not crash when output contains non-UTF-8 bytes (e.g. PNG 0x89)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_run.side_effect = _subprocess_swift_test_then_skip_coverage(
                b"Test run: 1 passed\n" + bytes([0x89]) + b"PNG\r\n", 0
            )

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()  # must not raise UnicodeDecodeError

            assert result.success is True
            assert "\ufffd" in result.output or "Test run" in result.output

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_parses_xctest_summary_format(self, mock_run: MagicMock) -> None:
        """run_tests correctly parses XCTest 'Executed N tests, with M failures' format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            xctest_output = (
                b"Test Suite 'MyTests' passed at 2026-04-09.\n"
                b"\t Executed 7819 tests, with 0 failures (0 unexpected) in 120.0 (122.0) seconds\n"
            )
            mock_run.side_effect = _subprocess_swift_test_then_skip_coverage(
                xctest_output, 0
            )

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is True
            assert result.tests_run == 7819
            assert result.tests_failed == 0
            assert result.tests_passed == 7819
            assert result.pass_rate == 1.0

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_xctest_summary_nonzero_failures(
        self, mock_run: MagicMock
    ) -> None:
        """run_tests correctly extracts failure count from XCTest summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_result = MagicMock()
            mock_result.returncode = 1
            xctest_output = (
                b"Test Suite 'MyTests' failed at 2026-04-09.\n"
                b"\t Executed 100 tests, with 3 failures (0 unexpected) in 5.0 (5.1) seconds\n"
            )
            mock_result.stdout = xctest_output
            mock_result.stderr = b""
            mock_run.return_value = mock_result

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is False
            assert result.tests_run == 100
            assert result.tests_failed == 3
            assert result.tests_passed == 97

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_multi_target_uses_grand_total_summary_line(
        self, mock_run: MagicMock
    ) -> None:
        """Multi-target output: last 'Executed N' line (grand total) is used, not the first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            # Simulates two test targets (86 + 50) + grand total "All tests" (136).
            xctest_output = (
                b"Test Suite 'All tests' started\n"
                b"Test Suite 'TargetATests' passed\n"
                b"\t Executed 86 tests, with 0 failures (0 unexpected) in 1.0 (1.0) seconds\n"
                b"Test Suite 'TargetBTests' passed\n"
                b"\t Executed 50 tests, with 0 failures (0 unexpected) in 0.5 (0.5) seconds\n"
                b"Test Suite 'All tests' passed\n"
                b"\t Executed 136 tests, with 0 failures (0 unexpected) in 2.0 (2.0) seconds\n"
            )
            mock_run.side_effect = _subprocess_swift_test_then_skip_coverage(
                xctest_output, 0
            )

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.tests_run == 136
            assert result.tests_passed == 136
            assert result.tests_failed == 0

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_multi_target_partial_run_uses_last_visible_line(
        self, mock_run: MagicMock
    ) -> None:
        """Partial run (crash before grand total): last visible target summary is used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            # TargetA ran fine; TargetB crashed before its summary; grand total absent.
            xctest_output = (
                b"Test Suite 'TargetATests' passed\n"
                b"\t Executed 86 tests, with 0 failures (0 unexpected) in 1.0 (1.0) seconds\n"
                b"Segmentation fault: 11\n"
            )
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = xctest_output
            mock_result.stderr = b""
            mock_run.return_value = mock_result

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is False
            assert result.tests_run == 86
            assert result.tests_failed == 0

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_multi_target_tradewing_style_uses_final_aggregate(
        self, mock_run: MagicMock
    ) -> None:
        """TradeWing-style multi-target output uses the final 'All tests' aggregate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            # Mirrors TradeWing-style nested XCTest output where each target emits
            # its own summary before a final aggregate line for the full run.
            xctest_output = (
                b"Test Suite 'All tests' started at 2026-04-16 12:00:00.000\n"
                b"Test Suite 'TradeWingCoreTests.xctest' passed at 2026-04-16 12:00:05.000\n"
                b"\t Executed 86 tests, with 0 failures (0 unexpected) in 5.1 (5.2) seconds\n"
                b"Test Suite 'TradeWingAppTests.xctest' passed at 2026-04-16 12:00:08.000\n"
                b"\t Executed 50 tests, with 0 failures (0 unexpected) in 2.8 (2.9) seconds\n"
                b"Test Suite 'All tests' passed at 2026-04-16 12:00:08.100\n"
                b"\t Executed 136 tests, with 0 failures (0 unexpected) in 7.9 (8.1) seconds\n"
            )
            mock_run.side_effect = _subprocess_swift_test_then_skip_coverage(
                xctest_output, 0
            )

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()

            assert result.success is True
            assert result.tests_run == 136
            assert result.tests_passed == 136
            assert result.tests_failed == 0

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_timeout(self, mock_run: MagicMock) -> None:
        """run_tests returns failure when execution times out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_run.side_effect = subprocess.TimeoutExpired("swift", 30)

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests(timeout=30)

            assert result.success is False
            assert (
                "timeout" in result.output.lower()
                or "timed out" in result.output.lower()
            )

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """run_tests returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_run.side_effect = RuntimeError("swift not found")
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()
            assert result.success is False
            assert "swift not found" in result.output

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_surfaces_harness_failure_when_no_assertion_failures(
        self, mock_run: MagicMock
    ) -> None:
        """Non-zero exit with no success marker must surface a harness diagnostic
        that includes stderr tail — NOT the legacy 'Test execution failed'.

        This is the core it48/it49 blocker: TradeWing saw
        ``tests.success=false, tests_failed=0, coverage=null, errors=[
        "Test execution failed"]`` and had no path to diagnose it.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stdout = b""
            mock_proc.stderr = (
                b"ld: symbol(s) not found for architecture arm64\n"
                b"linker command failed with exit code 1"
            )
            mock_run.return_value = mock_proc
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()
            assert result.success is False
            assert result.tests_failed == 0
            joined = " | ".join(result.errors)
            assert "swift test exited 1" in joined
            assert "no success marker" in joined
            assert "symbol(s) not found" in joined
            assert "Test execution failed" not in joined

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_surfaces_stderr_when_signal_kills_target(
        self, mock_run: MagicMock
    ) -> None:
        """Negative returncode with no success marker surfaces a harness failure
        diagnostic that includes the stderr tail so ops can route quickly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_proc = MagicMock()
            mock_proc.returncode = -11
            mock_proc.stdout = b""
            mock_proc.stderr = b"Segmentation fault in test target"
            mock_run.return_value = mock_proc
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()
            assert result.success is False
            joined = " | ".join(result.errors)
            assert "swift test exited -11" in joined
            assert "Segmentation fault" in joined

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_treats_passed_test_run_line_as_success_despite_nonzero_exit(
        self, mock_run: MagicMock
    ) -> None:
        """CORE it49 FIX: when Swift Testing prints the final ``Test run with N
        tests ... passed`` line, the gate MUST treat the run as success even
        if SwiftPM exits non-zero (post-run SIGBUS during XCTest teardown on
        Apple Silicon under piped stdio, reported as ``error: Exited with
        unexpected signal code 10``). Without this, coverage can never be
        collected on TradeWing-style projects and ``/cortex/fix`` loops forever.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stdout = (
                b"\xe2\x9c\x94 Test run with 534 tests in 69 suites passed "
                b"after 0.515 seconds.\n"
            )
            mock_proc.stderr = (
                b"Build complete! (0.55s)\n"
                b"error: Exited with unexpected signal code 10\n"
            )
            mock_run.return_value = mock_proc
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()
            # Gate decision: coverage is None because we mocked swift test
            # but no codecov dir exists. The crucial point is that the
            # harness-failure error list is EMPTY (not "Test execution
            # failed") and the warnings include a teardown-signal note so
            # ops know what happened.
            assert result.errors == []
            assert any("post-run signal 10" in w for w in result.warnings)
            assert any("treated as success" in w for w in result.warnings)

    def test_format_code_returns_error_when_no_package_swift(self) -> None:
        """format_code returns error when no Package.swift."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.format_code()
            assert result.success is False
            assert result.check_type == "format"
            assert "Package.swift" in result.output

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_format_code_success_when_swift_format_exits_0(
        self, mock_run: MagicMock
    ) -> None:
        """format_code returns success when swift format exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = b""
            mock_result.stderr = b""
            mock_run.return_value = mock_result

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.format_code()

            assert result.check_type == "format"
            assert result.success is True
            call_args = mock_run.call_args[0][0]
            assert "swift" in call_args
            assert "format" in call_args

    def test_type_check_returns_error_when_no_package_swift(self) -> None:
        """type_check returns error when no Package.swift."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.type_check()
            assert result.success is False
            assert result.check_type == "type_check"
            assert "Package.swift" in result.output

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_type_check_success_when_swift_build_exits_0(
        self, mock_run: MagicMock
    ) -> None:
        """type_check returns success when swift build exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = b""
            mock_result.stderr = b""
            mock_run.return_value = mock_result

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.type_check()

            assert result.check_type == "type_check"
            assert result.success is True
            call_args = mock_run.call_args[0][0]
            assert "swift" in call_args
            assert "build" in call_args

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_fix_errors_delegates_to_format_code(self, mock_run: MagicMock) -> None:
        """fix_errors delegates to format_code when formatting requested."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = b""
            mock_result.stderr = b""
            mock_run.return_value = mock_result

            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["formatting"])

            assert result.check_type == "fix_errors"
            assert result.success is True

    def test_fix_errors_without_formatting_returns_success(self) -> None:
        """fix_errors returns success when error_types excludes formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.fix_errors(error_types=["linting"])
            assert result.check_type == "fix_errors"
            assert result.success is True
            assert result.errors == []

    def test_lint_code_returns_error_when_no_package_swift(self) -> None:
        """lint_code delegates to type_check; returns error when no Package.swift."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.lint_code()
            assert result.success is False
            assert result.check_type == "type_check"
            assert "Package.swift" in result.output

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_format_code_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """format_code returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_run.side_effect = RuntimeError("swift not found")
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.format_code()
            assert result.success is False
            assert result.check_type == "format"
            assert "swift not found" in result.output

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_type_check_returns_error_on_exception(self, mock_run: MagicMock) -> None:
        """type_check returns error result when subprocess raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_run.side_effect = RuntimeError("swift not found")
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.type_check()
            assert result.success is False
            assert result.check_type == "type_check"

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_collects_coverage_from_codecov_json(
        self, mock_run: MagicMock
    ) -> None:
        """Numeric coverage from SwiftPM JSON under codecov/ (no llvm-cov subprocess)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            bin_path = _seed_codecov_project(root, count=100, covered=95)
            mock_run.side_effect = _swift_test_and_bin_path_side_effect(bin_path)
            adapter = SwiftAdapter(str(root))
            result = adapter.run_tests(coverage_threshold=0.90)
            assert result.coverage == pytest.approx(0.95)  # type: ignore[unknown-member-type]
            assert result.success is True
            # Calls: swift test, bin-path for logging, bin-path for coverage.
            # The second bin-path call could be cached in future — for now
            # accept 3 to pin the observed behavior.
            assert mock_run.call_count == 3

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_fails_when_codecov_json_below_accept_min(
        self, mock_run: MagicMock
    ) -> None:
        """Coverage below 89.5% fails gate (parity with Python adapter semantics)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            bin_path = _seed_codecov_project(root, count=100, covered=89)
            mock_run.side_effect = _swift_test_and_bin_path_side_effect(bin_path)
            adapter = SwiftAdapter(str(root))
            result = adapter.run_tests(coverage_threshold=0.90)
            assert result.coverage == pytest.approx(0.89)  # type: ignore[unknown-member-type]
            assert result.success is False
            assert any("below" in e.lower() for e in result.errors)

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_warns_when_coverage_between_accept_min_and_threshold(
        self, mock_run: MagicMock
    ) -> None:
        """89.5%–90% yields success with warning (Python parity)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            bin_path = _seed_codecov_project(root, count=1000, covered=896)
            mock_run.side_effect = _swift_test_and_bin_path_side_effect(bin_path)
            adapter = SwiftAdapter(str(root))
            result = adapter.run_tests(coverage_threshold=0.90)
            assert result.coverage == pytest.approx(0.896)  # type: ignore[unknown-member-type]
            assert result.success is True
            assert result.warnings

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_uses_llvm_cov_when_json_missing(
        self, mock_run: MagicMock
    ) -> None:
        """llvm-cov report path supplies coverage when JSON is absent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            bin_path = _seed_llvm_cov_project(root)
            report = b"Lines Missed Cover\nTOTAL 10 1 90.00%\n"
            mock_run.side_effect = _swift_test_bin_and_llvm_cov_side_effect(
                bin_path, report
            )
            adapter = SwiftAdapter(str(root))
            result = adapter.run_tests(coverage_threshold=0.90)
            assert result.coverage == pytest.approx(0.90)  # type: ignore[unknown-member-type]
            assert result.success is True
            # Calls: swift test, bin-path for logging, bin-path for coverage,
            # llvm-cov export, llvm-cov report fallback.
            assert mock_run.call_count == 5

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_populates_coverage_gaps_via_llvm_cov_export(
        self, mock_run: MagicMock
    ) -> None:
        """When SwiftPM JSON absent, llvm-cov export supplies per-file coverage_gaps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            bin_path = _seed_llvm_cov_project(root)
            export_json = _llvm_cov_export_payload()
            export_call_seen: list[bool] = [False]
            mock_run.side_effect = _swift_test_bin_and_llvm_cov_export_side_effect(
                bin_path, export_json, export_call_seen
            )
            adapter = SwiftAdapter(str(root))
            result = adapter.run_tests(coverage_threshold=0.90)
            assert export_call_seen[0], "llvm-cov export was not called"
            assert len(result.coverage_gaps) == 2  # type: ignore[unknown-member-type]
            # App.swift has 50 uncovered lines — should be first (sorted desc)
            assert result.coverage_gaps[0].file == "/src/App.swift"  # type: ignore[unknown-member-type]
            assert result.coverage_gaps[0].lines_uncovered == 50  # type: ignore[unknown-member-type]

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    # AI: Fixture pairs covered App.swift with zero-covered *.pb.swift; JSON aggregate should fail the gate without excludes.
    def test_run_tests_codecov_json_includes_pb_without_swift_coverage_config(
        self, mock_run: MagicMock
    ) -> None:
        """Without config, generated *.pb.swift lines count toward the aggregate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            bin_path = _seed_codecov_project_app_and_pb(root)
            mock_run.side_effect = _swift_test_and_bin_path_side_effect(bin_path)
            adapter = SwiftAdapter(str(root))
            result = adapter.run_tests(coverage_threshold=0.90)
            assert result.coverage == pytest.approx(0.45)  # type: ignore[unknown-member-type]
            assert result.success is False

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    # AI: swift_coverage.json exclude patterns remove pb paths from codecov JSON so App-only coverage passes threshold.
    def test_run_tests_codecov_json_excludes_pb_with_swift_coverage_config(
        self, mock_run: MagicMock
    ) -> None:
        """``.cortex/config/swift_coverage.json`` drops matching paths from JSON totals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            _write_swift_coverage_json(root, [r"\.pb\.swift$"])
            bin_path = _seed_codecov_project_app_and_pb(root)
            mock_run.side_effect = _swift_test_and_bin_path_side_effect(bin_path)
            adapter = SwiftAdapter(str(root))
            result = adapter.run_tests(coverage_threshold=0.90)
            assert result.coverage == pytest.approx(0.90)  # type: ignore[unknown-member-type]
            assert result.success is True

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_llvm_cov_ignore_regex_includes_swift_coverage_config(
        self, mock_run: MagicMock
    ) -> None:
        """llvm-cov fallback receives combined regex including config patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            _write_swift_coverage_json(root, [r"\.pb\.swift$"])
            bin_path = _seed_llvm_cov_project(root)
            report = b"Lines Missed Cover\nTOTAL 10 1 90.00%\n"
            mock_run.side_effect = _swift_test_bin_and_llvm_cov_side_effect(
                bin_path, report
            )
            adapter = SwiftAdapter(str(root))
            _ = adapter.run_tests(coverage_threshold=0.90)
            llvm_calls = [
                c
                for c in mock_run.call_args_list
                if c[0]
                and isinstance(c[0][0], list)
                and c[0][0]
                and c[0][0][0] in ("llvm-cov", "xcrun")
            ]
            assert llvm_calls
            argv = llvm_calls[0][0][0]
            ignore_arg = next(str(a) for a in argv if "ignore-filename-regex" in str(a))
            assert r".pb" in ignore_arg or "pb.swift" in ignore_arg


class TestMergeProfrawToProfdata:
    """Unit tests for merge_profraw_to_profdata."""

    def test_returns_true_when_profdata_already_exists(self) -> None:
        """No subprocess call when default.profdata is already present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_path = Path(tmpdir) / "debug"
            codecov = bin_path / "codecov"
            codecov.mkdir(parents=True)
            _ = (codecov / "default.profdata").write_bytes(b"existing")
            result = merge_profraw_to_profdata(bin_path)
            assert result is True

    def test_returns_false_when_no_profraw_files_present(self) -> None:
        """Returns False immediately when there are no .profraw files to merge."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_path = Path(tmpdir) / "debug"
            codecov = bin_path / "codecov"
            codecov.mkdir(parents=True)
            result = merge_profraw_to_profdata(bin_path)
            assert result is False

    @patch("cortex.services.framework_adapters.swift_coverage.subprocess.run")
    def test_merges_profraw_files_into_profdata(self, mock_run: MagicMock) -> None:
        """Calls llvm-profdata merge and returns True when merge succeeds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_path = Path(tmpdir) / "debug"
            codecov = bin_path / "codecov"
            codecov.mkdir(parents=True)
            _ = (codecov / "XCTest_0.profraw").write_bytes(b"raw1")
            _ = (codecov / "SwiftTesting_0.profraw").write_bytes(b"raw2")
            profdata = codecov / "default.profdata"

            def _fake_merge(cmd: list[str], **kwargs: object) -> MagicMock:
                # Simulate a successful merge by writing the profdata file.
                _ = profdata.write_bytes(b"merged")
                m = MagicMock()
                m.returncode = 0
                m.stderr = b""
                return m

            mock_run.side_effect = _fake_merge
            result = merge_profraw_to_profdata(bin_path)
            assert result is True
            assert profdata.is_file()
            # Verify the merge command included both profraw files.
            call_args: list[str] = mock_run.call_args[0][0]
            assert any("profraw" in str(a) for a in call_args)
            assert str(profdata) in call_args

    @patch("cortex.services.framework_adapters.swift_coverage.subprocess.run")
    def test_returns_false_when_merge_subprocess_fails(
        self, mock_run: MagicMock
    ) -> None:
        """Returns False when llvm-profdata merge exits non-zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_path = Path(tmpdir) / "debug"
            codecov = bin_path / "codecov"
            codecov.mkdir(parents=True)
            _ = (codecov / "XCTest_0.profraw").write_bytes(b"raw")
            m = MagicMock()
            m.returncode = 1
            m.stderr = b"error merging"
            mock_run.return_value = m
            result = merge_profraw_to_profdata(bin_path)
            assert result is False

    @patch("cortex.services.framework_adapters.swift_adapter.merge_profraw_to_profdata")
    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_calls_merge_before_profdata_check(
        self, mock_run: MagicMock, mock_merge: MagicMock
    ) -> None:
        """run_tests invokes merge_profraw_to_profdata before checking profdata existence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            _ = (root / "Package.swift").write_text("// swift-tools-version:5.9\n")
            bin_path = root / ".build" / "debug"
            _ = (bin_path / "codecov").mkdir(parents=True)
            mock_merge.return_value = False
            mock_run.side_effect = _swift_test_and_bin_path_side_effect(bin_path)
            adapter = SwiftAdapter(str(root))
            result = adapter.run_tests()
            mock_merge.assert_called_once_with(bin_path, None)
            # No profdata → coverage not collected → coverage=None but tests pass.
            assert result.coverage is None
            assert result.success is True
