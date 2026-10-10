"""Consumer-behavior tests for ``SwiftAdapter.run_tests`` result shaping.

Split from ``tests/unit/test_swift_adapter.py`` to keep that module under
the 400-logical-line file-size limit. These tests pin what the quality-gate
consumer observes from a ``swift test`` invocation: pass/fail verdict, test
counts, error diagnostics (harness and compile failures), and post-run
teardown-signal warnings.
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.services.framework_adapters.swift_adapter import SwiftAdapter


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


class TestSwiftAdapterRunTestsDiagnostics:
    """run_tests verdict, count, and diagnostics behavior seen by consumers."""

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
    def test_run_tests_compile_failure_reports_zero_tests_and_compiler_errors(
        self, mock_run: MagicMock
    ) -> None:
        """REV-2026-10-02-33: a compile/harness failure ran ZERO tests.

        Pre-fix failure mode: ``swift test`` dying on a COMPILE failure
        (rc=1, ``error:`` diagnostics, no test-run rollup) was reported as a
        fabricated single failed test (tests_run=1, tests_passed=0,
        tests_failed=1, pass_rate=0.0) with only a generic harness message.
        The stage must report zero counts, a compile-failure classification,
        and the actual compiler error lines as error context.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "Package.swift").write_text(
                "// swift-tools-version:5.9"
            )
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stdout = (
                b"Building for testing...\n"
                b"/Sources/App/Main.swift:12:5: error: cannot find 'foo' in scope\n"
            )
            mock_proc.stderr = b"error: fatalError\n"
            mock_run.return_value = mock_proc
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()
            assert result.success is False
            assert result.tests_run == 0
            assert result.tests_passed == 0
            assert result.tests_failed == 0
            assert result.pass_rate == 0.0
            joined = " | ".join(result.errors)
            assert "build/compile errors" in joined
            assert "zero tests ran" in joined
            assert (
                "/Sources/App/Main.swift:12:5: error: cannot find 'foo' in scope"
                in (joined)
            )
            assert "error: fatalError" in joined

    @patch("cortex.services.framework_adapters.swift_adapter.subprocess.run")
    def test_run_tests_failing_rollup_counts_unchanged(
        self, mock_run: MagicMock
    ) -> None:
        """Genuine failing log with a real rollup: counts unchanged by the fix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _ = (root / "Package.swift").write_text("// swift-tools-version:5.9")
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stdout = (
                b"Executed 17 tests, with 2 failures (2 unexpected)\n"
                b"\xe2\x9c\x98 Test run with 534 tests failed after 0.5 seconds.\n"
            )
            mock_proc.stderr = b""
            mock_run.return_value = mock_proc
            adapter = SwiftAdapter(str(tmpdir))
            result = adapter.run_tests()
            assert result.success is False
            assert result.tests_failed == 2
            assert result.tests_passed == 15
            assert result.tests_run == 17
            assert any("534 tests with failures" in e for e in result.errors)

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
