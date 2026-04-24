"""Tests for :mod:`cortex.services.framework_adapters.swift_test_diagnostics`.

The diagnostics module is the single authoritative interpreter of
``swift test`` output. The gate's pass/fail decision must NOT follow the
exit code — SwiftPM exits non-zero on post-run harness signals (SIGBUS from
XCTest teardown on Apple Silicon under piped stdio) even when every test
passed. These tests lock in the output-based classification so a regression
would re-break TradeWing's coverage gate.
"""

from __future__ import annotations

from cortex.services.framework_adapters.swift_test_diagnostics import (
    SwiftTestStatus,
    build_swift_test_harness_errors,
    interpret_swift_test_output,
    stderr_tail,
)


class TestInterpretSwiftTestOutputPassed:
    def test_swift_testing_success_line_overrides_nonzero_returncode(self) -> None:
        """Swift Testing summary ``Test run with N tests ... passed`` trumps rc=1.

        This is the exact TradeWing failure shape: rc=1 with SIGBUS on stderr
        but 534 tests passed — must classify as PASSED so coverage runs.
        """
        stdout = "✔ Test run with 534 tests in 69 suites passed after 0.515 seconds.\n"
        stderr = (
            "Build complete! (0.55s)\nerror: Exited with unexpected signal code 10\n"
        )
        outcome = interpret_swift_test_output(stdout, stderr, returncode=1)
        assert outcome.status is SwiftTestStatus.PASSED
        assert outcome.teardown_signal == 10
        assert outcome.tests_reported == 534
        assert "all tests passed" in outcome.diagnostic
        assert "treating as success" in outcome.diagnostic

    def test_xctest_all_tests_passed_overrides_nonzero_returncode(self) -> None:
        stdout = (
            "Test Suite 'All tests' passed at 2026-04-23 21:12:30.080\n"
            "Executed 300 tests, with 0 failures (0 unexpected) in 0.4 seconds\n"
        )
        outcome = interpret_swift_test_output(stdout, "", returncode=1)
        assert outcome.status is SwiftTestStatus.PASSED

    def test_per_target_suite_passed_is_NOT_treated_as_grand_total(self) -> None:
        """Individual target summaries must NOT mark a non-zero run as passed.

        Regression guard: when TargetB crashes mid-run before emitting its own
        summary, TargetA's earlier ``Test Suite 'TargetATests' passed`` line
        would become a false-positive grand total under a lax regex.
        """
        stdout = (
            "Test Suite 'TargetATests' passed\n"
            "\t Executed 86 tests, with 0 failures (0 unexpected) in 1.0 seconds\n"
            "Segmentation fault: 11\n"
        )
        outcome = interpret_swift_test_output(stdout, "", returncode=1)
        assert outcome.status is SwiftTestStatus.HARNESS_FAILURE

    def test_clean_pass_with_zero_returncode_has_no_harness_caveat(self) -> None:
        stdout = "✔ Test run with 100 tests in 10 suites passed after 2.0 seconds.\n"
        outcome = interpret_swift_test_output(stdout, "", returncode=0)
        assert outcome.status is SwiftTestStatus.PASSED
        assert outcome.teardown_signal is None
        assert outcome.diagnostic == "all tests passed"


class TestInterpretSwiftTestOutputFailed:
    def test_swift_testing_failure_line_classified_as_failed(self) -> None:
        stdout = "✘ Test run with 534 tests failed after 0.5 seconds.\n"
        outcome = interpret_swift_test_output(stdout, "", returncode=1)
        assert outcome.status is SwiftTestStatus.FAILED
        assert outcome.tests_reported == 534

    def test_failed_line_takes_priority_over_passed_line_in_mixed_output(self) -> None:
        # A failed test run should always win over a stale passed line
        # from an earlier phase of the same output.
        stdout = (
            "Test run with 10 tests passed after 0.1 seconds.\n"
            "Test run with 534 tests failed after 0.5 seconds.\n"
        )
        outcome = interpret_swift_test_output(stdout, "", returncode=1)
        assert outcome.status is SwiftTestStatus.FAILED


class TestInterpretSwiftTestOutputHarnessFailure:
    def test_nonzero_with_no_success_marker_is_harness_failure(self) -> None:
        stderr = "ld: symbol(s) not found\nlinker command failed"
        outcome = interpret_swift_test_output("", stderr, returncode=1)
        assert outcome.status is SwiftTestStatus.HARNESS_FAILURE
        assert "swift test exited 1" in outcome.diagnostic

    def test_negative_returncode_with_no_success_marker_is_harness_failure(
        self,
    ) -> None:
        outcome = interpret_swift_test_output("", "", returncode=-11)
        assert outcome.status is SwiftTestStatus.HARNESS_FAILURE


class TestInterpretSwiftTestOutputBareZeroExit:
    def test_zero_returncode_with_no_markers_trusts_exit_code_as_passed(self) -> None:
        """rc=0 with no summary line (e.g. --list-tests, filtered run with no
        matches) must not block the gate — trust the exit code."""
        outcome = interpret_swift_test_output("", "", returncode=0)
        assert outcome.status is SwiftTestStatus.PASSED
        assert "no summary line parsed" in outcome.diagnostic


class TestStderrTail:
    def test_short_stderr_returned_verbatim(self) -> None:
        assert stderr_tail("hello") == "hello"

    def test_empty_stderr_returns_empty_string(self) -> None:
        assert stderr_tail("") == ""

    def test_stderr_longer_than_limit_is_tail_truncated(self) -> None:
        text = "x" * 3000
        assert stderr_tail(text, max_chars=1000) == "x" * 1000


class TestBuildSwiftTestHarnessErrors:
    def test_passed_outcome_yields_no_harness_error(self) -> None:
        """When tests passed (exit nonzero due to teardown), no harness error."""
        stdout = "✔ Test run with 534 tests passed after 0.5 seconds.\n"
        stderr = "error: Exited with unexpected signal code 10\n"
        errors = build_swift_test_harness_errors(stdout, 1, stderr)
        # Call path: when outcome is PASSED, diagnostic text still surfaces
        # but the caller (SwiftAdapter._build_swift_test_errors) gates on
        # tests_ok — so what matters here is that the string references the
        # success, not a linker/compile failure.
        assert any("all tests passed" in e for e in errors)
        assert not any("linker" in e.lower() for e in errors)

    def test_harness_failure_includes_stderr_tail(self) -> None:
        errors = build_swift_test_harness_errors(
            "", 1, "ld: symbol(s) not found for architecture arm64"
        )
        assert len(errors) == 1
        assert "swift test exited 1" in errors[0]
        assert "symbol(s) not found" in errors[0]
