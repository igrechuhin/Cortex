"""Tests for :mod:`cortex.services.framework_adapters.swift_test_diagnostics`.

Exercises the ``swift test`` harness-failure classification path added to
surface the real failure reason (linker error, compile error, crash, signal)
when the subprocess exits non-zero but XCTest reported zero assertion failures.
The default ``Test execution failed`` message hides this information and causes
the fix-path agents to loop without a route.
"""

from __future__ import annotations

from cortex.services.framework_adapters.swift_test_diagnostics import (
    build_swift_test_harness_errors,
    classify_swift_test_failure,
    stderr_tail,
)


class TestClassifySwiftTestFailure:
    def test_signal_returncode_maps_to_signal_label(self) -> None:
        # POSIX convention: returncode == -N means terminated by signal N.
        assert classify_swift_test_failure("", -11) == "signal 11"

    def test_linker_failure_detected_from_output(self) -> None:
        output = "ld: symbol(s) not found for architecture arm64\nlinker command failed"
        assert classify_swift_test_failure(output, 1) == "linker failure"

    def test_undefined_symbol_counts_as_linker_failure(self) -> None:
        output = "Undefined symbol: _OBJC_CLASS_$_FooBar"
        assert classify_swift_test_failure(output, 1) == "linker failure"

    def test_compile_error_detected_from_swift_error(self) -> None:
        output = "/path/to/file.swift:42:10: error: cannot find 'foo' in scope"
        assert classify_swift_test_failure(output, 1) == "compile error"

    def test_fatal_error_detected(self) -> None:
        output = "Swift runtime failure: fatal error: unexpectedly found nil"
        assert classify_swift_test_failure(output, 134) == "fatal error / crash"

    def test_unknown_failure_defaults_to_harness_failure(self) -> None:
        assert classify_swift_test_failure("some unrelated output", 1) == (
            "harness failure"
        )

    def test_returncode_zero_still_classifies_when_called(self) -> None:
        # Not a normal call path (caller only invokes this for !=0), but the
        # classifier must not crash or return an empty label.
        label = classify_swift_test_failure("", 0)
        assert isinstance(label, str) and label


class TestStderrTail:
    def test_short_stderr_returned_verbatim(self) -> None:
        assert stderr_tail("hello") == "hello"

    def test_empty_stderr_returns_empty_string(self) -> None:
        assert stderr_tail("") == ""

    def test_stderr_longer_than_limit_is_tail_truncated(self) -> None:
        text = "x" * 3000
        tail = stderr_tail(text, max_chars=1000)
        assert len(tail) == 1000
        assert tail == "x" * 1000

    def test_custom_max_chars_respected(self) -> None:
        assert stderr_tail("abcdef", max_chars=3) == "def"


class TestBuildSwiftTestHarnessErrors:
    def test_linker_error_includes_classification_and_tail(self) -> None:
        output = "ld: symbol(s) not found\nlinker command failed"
        errors = build_swift_test_harness_errors(
            output, 1, "ld: symbol(s) not found for architecture arm64"
        )
        assert len(errors) == 1
        assert "swift test exited 1" in errors[0]
        assert "linker failure" in errors[0]
        assert "symbol(s) not found" in errors[0]

    def test_empty_stderr_still_produces_classified_message(self) -> None:
        errors = build_swift_test_harness_errors("fatal error: crashed", 134, "")
        assert len(errors) == 1
        assert "swift test exited 134" in errors[0]
        assert "fatal error / crash" in errors[0]

    def test_signal_returncode_reported_with_signal_label(self) -> None:
        errors = build_swift_test_harness_errors(
            "", -11, "Process terminated due to SIGSEGV"
        )
        assert len(errors) == 1
        assert "swift test exited -11" in errors[0]
        assert "signal 11" in errors[0]
        assert "SIGSEGV" in errors[0]

    def test_multiline_stderr_tail_limited_to_last_five_lines(self) -> None:
        # Eight lines — only the last five should appear in the joined summary.
        stderr = "\n".join(f"line{i}" for i in range(8))
        errors = build_swift_test_harness_errors("compile error: .swift:", 1, stderr)
        assert len(errors) == 1
        msg = errors[0]
        # line3..line7 are the last five; line0/line1/line2 must be absent.
        assert "line3" in msg
        assert "line7" in msg
        assert "line0" not in msg
