"""Swift ``swift test`` output interpretation and harness-failure diagnostics.

SwiftPM's ``swift test`` can exit non-zero even after ALL tests pass, due to
post-shutdown signals from the XCTest runner (most commonly SIGBUS on Apple
Silicon when the child's stdio is piped rather than attached to a TTY).
SwiftPM reports this as ``error: Exited with unexpected signal code N`` on
stderr after the test summary line.

This module is the single authoritative interpreter of ``swift test`` output:

1. :func:`interpret_swift_test_output` — returns a :class:`SwiftTestOutcome`
   classifying the run as ``passed`` / ``failed`` / ``harness_failure`` /
   ``unknown`` based on the **output**, not just the exit code.
2. :func:`build_swift_test_harness_errors` — decorates the gate-level error
   list when the harness crashed but tests themselves all passed.

The rationale for output-based classification: when XCTest emits
``Test Suite 'All tests' passed`` (legacy XCTest) or Swift Testing emits
``Test run with N tests ... passed`` (Swift Testing 6.0+), **the tests ran
to completion successfully**. Any non-zero exit afterwards is a harness /
teardown issue, not a test failure, and must not block the gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

# ---------------------------------------------------------------------------
# Output-based success markers
# ---------------------------------------------------------------------------

# Swift Testing (Swift 6.0+) end-of-run line. Tolerant to future format tweaks
# — matches the stable ``passed`` verb and the count prefix.
_SWIFT_TESTING_PASSED_RE = re.compile(
    r"Test run with\s+(?P<total>\d+)\s+tests?\b.*\bpassed\b",
    re.IGNORECASE | re.DOTALL,
)
_SWIFT_TESTING_FAILED_RE = re.compile(
    r"Test run with\s+(?P<total>\d+)\s+tests?\b.*\bfailed\b",
    re.IGNORECASE | re.DOTALL,
)

# XCTest legacy grand-total line: ``Test Suite 'All tests' passed at ...``.
# This is the ONLY authoritative XCTest "every test in every target passed"
# marker. Per-target suite summaries (e.g. ``Test Suite 'TargetATests' passed``)
# are deliberately NOT trusted — a later target may crash mid-run before
# emitting its own summary, leaving the earlier success line stale.
_XCTEST_ALL_TESTS_PASSED_RE = re.compile(
    r"Test Suite '(?:All tests|Selected tests)' passed",
    re.IGNORECASE,
)

# SwiftPM's post-run error line when the test bundle crashes after reporting
# success. This is the only stderr marker that SwiftPM emits for teardown
# signals — the numeric code varies (10 = SIGBUS on Darwin, 11 = SIGSEGV).
_SPM_UNEXPECTED_SIGNAL_RE = re.compile(
    r"error:\s+Exited with unexpected signal code\s+(?P<sig>\d+)",
    re.IGNORECASE,
)


class SwiftTestStatus(StrEnum):
    """Authoritative classification of a ``swift test`` run."""

    PASSED = "passed"
    FAILED = "failed"
    HARNESS_FAILURE = "harness_failure"


@dataclass(frozen=True)
class SwiftTestOutcome:
    """Result of interpreting ``swift test`` stdout + stderr + returncode.

    Attributes:
        status: :class:`SwiftTestStatus` — ``PASSED`` takes precedence over a
            non-zero returncode when the output proves all tests completed.
        diagnostic: Short human-readable summary (category + hint) used in the
            gate error list and in the comprehensive test log.
        teardown_signal: When the harness crashed after success, the signal
            number SwiftPM reported (``10`` = SIGBUS, ``11`` = SIGSEGV, ...).
            ``None`` when no such marker was found.
        tests_reported: Total tests parsed from the summary line, if present.
    """

    status: SwiftTestStatus
    diagnostic: str
    teardown_signal: int | None = None
    tests_reported: int | None = None


def interpret_swift_test_output(
    stdout: str,
    stderr: str,
    returncode: int,
) -> SwiftTestOutcome:
    """Return an authoritative outcome from ``swift test`` output.

    The output trumps the exit code: if the test summary line shows all tests
    passed but the process exited non-zero, this is a post-success harness
    crash (common on Apple Silicon when stdio is piped), and the outcome is
    ``PASSED`` + a ``HARNESS_FAILURE``-flavoured diagnostic attached.

    Priority order:
    1. Explicit ``Test run ... failed`` / XCTest failure marker → ``FAILED``.
    2. Explicit ``Test run ... passed`` / XCTest all-tests-passed → ``PASSED``
       (regardless of returncode; teardown signal noted in ``diagnostic``).
    3. Non-zero returncode with no success marker → ``HARNESS_FAILURE``.
    4. Zero returncode with no markers → ``PASSED`` (short/filtered runs,
       e.g. ``swift test --list-tests`` or empty ``--filter`` matches, emit
       no summary line but the zero exit is trustworthy).
    """
    combined = f"{stdout}\n{stderr}"
    failed = _failed_outcome_if_any(combined)
    if failed is not None:
        return failed
    passed = _passed_outcome_if_any(combined, stderr, returncode)
    if passed is not None:
        return passed
    if returncode != 0:
        return SwiftTestOutcome(
            status=SwiftTestStatus.HARNESS_FAILURE,
            diagnostic=(
                f"swift test exited {returncode} with no success marker in "
                "output — likely a build/link failure or mid-run crash"
            ),
        )
    return SwiftTestOutcome(
        status=SwiftTestStatus.PASSED,
        diagnostic="swift test exited 0 (no summary line parsed)",
    )


def _failed_outcome_if_any(combined: str) -> SwiftTestOutcome | None:
    """Return a FAILED outcome when Swift Testing reports a failed run."""
    fail_m = _SWIFT_TESTING_FAILED_RE.search(combined)
    if fail_m is None:
        return None
    total = int(fail_m.group("total"))
    return SwiftTestOutcome(
        status=SwiftTestStatus.FAILED,
        diagnostic=f"Swift Testing reported {total} tests with failures",
        tests_reported=total,
    )


def _passed_outcome_if_any(
    combined: str,
    stderr: str,
    returncode: int,
) -> SwiftTestOutcome | None:
    """Return a PASSED outcome when an authoritative success marker is present."""
    passed_swift_testing = _SWIFT_TESTING_PASSED_RE.search(combined)
    passed_xctest = _XCTEST_ALL_TESTS_PASSED_RE.search(combined)
    if not (passed_swift_testing or passed_xctest):
        return None
    signal_m = _SPM_UNEXPECTED_SIGNAL_RE.search(stderr)
    signal_n = int(signal_m.group("sig")) if signal_m else None
    total = int(passed_swift_testing.group("total")) if passed_swift_testing else None
    diag = "all tests passed"
    if returncode != 0 or signal_n is not None:
        signal_suffix = f" (post-run signal {signal_n})" if signal_n else ""
        diag = (
            f"all tests passed but test harness exited {returncode}"
            f"{signal_suffix} — treating as success"
        )
    return SwiftTestOutcome(
        status=SwiftTestStatus.PASSED,
        diagnostic=diag,
        teardown_signal=signal_n,
        tests_reported=total,
    )


# ---------------------------------------------------------------------------
# Stderr tail + harness-error formatting (existing API, kept stable)
# ---------------------------------------------------------------------------


def stderr_tail(stderr: str, max_chars: int = 2000) -> str:
    """Return the last ``max_chars`` characters of ``stderr`` for diagnostics."""
    if not stderr:
        return ""
    if len(stderr) <= max_chars:
        return stderr
    return stderr[-max_chars:]


def build_swift_test_harness_errors(
    output: str,
    returncode: int,
    stderr_tail_text: str,
) -> list[str]:
    """Build diagnostic errors when swift test exited non-zero with no assertion failures.

    Used only when :func:`interpret_swift_test_output` classifies the outcome
    as ``HARNESS_FAILURE`` — i.e. no success marker was found and the process
    exited non-zero. Surfaces the classified category plus the last few lines
    of stderr so fix-path agents can route.
    """
    outcome = interpret_swift_test_output(output, stderr_tail_text, returncode)
    prefix = outcome.diagnostic
    if stderr_tail_text:
        lines = [line.strip() for line in stderr_tail_text.splitlines() if line.strip()]
        tail_lines = lines[-5:]
        if tail_lines:
            return [prefix + " — " + " | ".join(tail_lines)]
    return [prefix]
