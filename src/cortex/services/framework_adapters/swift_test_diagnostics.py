"""Swift ``swift test`` output interpretation and harness-failure diagnostics.

SwiftPM's ``swift test`` can exit non-zero even after ALL tests pass, due to
post-shutdown signals from the XCTest runner (most commonly SIGBUS on Apple
Silicon when the child's stdio is piped rather than attached to a TTY).
SwiftPM reports this as ``error: Exited with unexpected signal code N`` on
stderr after the test summary line.

This module is the single authoritative interpreter of ``swift test`` output:

1. :func:`interpret_swift_test_output` — returns a :class:`SwiftTestOutcome`
   classifying the run as ``passed`` / ``failed`` / ``compile_failure`` /
   ``harness_failure`` based on the **output**, not just the exit code.
2. :func:`build_swift_test_harness_errors` — decorates the gate-level error
   list when the harness crashed but tests themselves all passed.

SwiftPM may emit multiple independent grand totals. A completed runner's
output does not prove that later runners passed. The sole nonzero-exit
exception is the known SwiftPM SIGBUS teardown signature on complete output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

# ---------------------------------------------------------------------------
# Output-based success markers
# ---------------------------------------------------------------------------

# AI: Treat only the verb immediately after the counts as the result. Other
# lines (including passing test names) can contain either status word.
_SWIFT_TESTING_RUN_PREFIX = (
    r"^[ \t]*(?:[^\w\s][ \t]+)?"
    r"Test run with[ \t]+(?P<total>\d+)[ \t]+tests?"
    r"(?:[ \t]+in[ \t]+\d+[ \t]+suites?)?[ \t]+"
)
_SWIFT_TESTING_PASSED_RE = re.compile(
    _SWIFT_TESTING_RUN_PREFIX + r"passed\b[^\r\n]*",
    re.IGNORECASE | re.MULTILINE,
)
_SWIFT_TESTING_FAILED_RE = re.compile(
    _SWIFT_TESTING_RUN_PREFIX + r"failed\b",
    re.IGNORECASE | re.MULTILINE,
)

# SwiftPM's post-run error line when the test bundle crashes after reporting
# success. Only the documented SwiftPM/Darwin SIGBUS case is accepted.
_SPM_UNEXPECTED_SIGNAL_RE = re.compile(
    r"error:\s+Exited with unexpected signal code\s+(?P<sig>\d+)",
    re.IGNORECASE,
)


_XCTEST_COUNT = (
    r"^[ \t]*Executed[ \t]+(?P<total>\d+)[ \t]+tests?,[ \t]+"
    r"with[ \t]+(?P<failed>\d+)[ \t]+failures?\b"
)
_FLAGS = re.IGNORECASE | re.MULTILINE
_XCTEST_SUMMARY_RE = re.compile(_XCTEST_COUNT, _FLAGS)
_XCTEST_ROOT = r"^[ \t]*Test Suite '(?:All tests|Selected tests)' "
_XCTEST_GRAND_TOTAL_RE = re.compile(
    _XCTEST_ROOT + r"(?:passed|failed)\b[^\r\n]*\r?\n" + _XCTEST_COUNT, _FLAGS
)
_XCTEST_STARTED_RE = re.compile(_XCTEST_ROOT + r"started\b", _FLAGS)
_XCTEST_FAILED_RE = re.compile(r"^[ \t]*Test Suite '[^\r\n]+' failed\b", _FLAGS)
_SWIFT_STARTED_RE = re.compile(r"^[ \t]*(?:[^\w\s][ \t]+)?Test run started\.", _FLAGS)
_KNOWN_ISSUE_COUNT_RE = re.compile(r"[ \t]with[ \t]+(\d+)[ \t]+known issues?\b")


def extract_swift_test_counts(output: str) -> tuple[int, int]:
    """Aggregate independent Swift Testing and XCTest grand totals."""
    swift_passed = sum(
        int(m.group("total")) for m in _SWIFT_TESTING_PASSED_RE.finditer(output)
    )
    xctest_runs = list(_XCTEST_GRAND_TOTAL_RE.finditer(output))
    if xctest_runs:
        passed = sum(
            max(int(m.group("total")) - int(m.group("failed")), 0) for m in xctest_runs
        )
        return swift_passed + passed, sum(int(m.group("failed")) for m in xctest_runs)
    # AI: Unframed XCTest rows can overlap, so only use a single partial count
    # when no authoritative run totals are available.
    partial = list(_XCTEST_SUMMARY_RE.finditer(output))
    if not partial:
        return swift_passed, 0
    if swift_passed:
        return swift_passed, max(int(m.group("failed")) for m in partial)
    last = partial[-1]
    failed = int(last.group("failed"))
    return max(int(last.group("total")) - failed, 0), failed


class SwiftTestStatus(StrEnum):
    """Authoritative classification of a ``swift test`` run."""

    PASSED = "passed"
    FAILED = "failed"
    HARNESS_FAILURE = "harness_failure"
    COMPILE_FAILURE = "compile_failure"


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
        compiler_errors: Distinct ``error:`` diagnostic lines captured from the
            output when the run died on build/compile errors before any test
            executed. Empty for every other classification.
        known_issues: Non-failing issues explicitly declared by Swift Testing.
    """

    status: SwiftTestStatus
    diagnostic: str
    teardown_signal: int | None = None
    tests_reported: int | None = None
    compiler_errors: tuple[str, ...] = ()
    known_issues: int = 0


def interpret_swift_test_output(
    stdout: str,
    stderr: str,
    returncode: int,
) -> SwiftTestOutcome:
    """Classify explicit failures, complete runner output, and the process exit."""
    combined = f"{stdout}\n{stderr}"
    failed = _failed_outcome_if_any(combined)
    if failed is not None:
        return failed
    if _has_unclosed_runner(stdout) or _has_unclosed_runner(stderr):
        return SwiftTestOutcome(
            SwiftTestStatus.HARNESS_FAILURE,
            f"swift test exited {returncode} with an incomplete test run",
        )
    passed = _passed_outcome_if_any(combined, stderr, returncode)
    if passed is not None:
        return passed
    if returncode == 0 and _SPM_UNEXPECTED_SIGNAL_RE.search(stderr):
        return SwiftTestOutcome(
            SwiftTestStatus.HARNESS_FAILURE,
            "swift test reported an unexpected signal despite exiting 0",
        )
    return _no_marker_outcome(returncode, combined)


def _no_marker_outcome(returncode: int, combined: str) -> SwiftTestOutcome:
    """Classify a run whose output contained no success/failure summary marker."""
    if returncode == 0:
        return SwiftTestOutcome(
            status=SwiftTestStatus.PASSED,
            diagnostic="swift test exited 0 (no summary line parsed)",
        )
    compiler_errors = extract_compiler_error_lines(combined)
    if compiler_errors:
        return SwiftTestOutcome(
            status=SwiftTestStatus.COMPILE_FAILURE,
            diagnostic=(
                f"swift test exited {returncode} on build/compile errors "
                "— zero tests ran"
            ),
            compiler_errors=compiler_errors,
        )
    return SwiftTestOutcome(
        status=SwiftTestStatus.HARNESS_FAILURE,
        diagnostic=(
            f"swift test exited {returncode} with no success marker in "
            "output — likely a build/link failure or mid-run crash"
        ),
    )


def _failed_outcome_if_any(combined: str) -> SwiftTestOutcome | None:
    """Any explicit test failure wins over another runner's passing summary."""
    fail_m = _SWIFT_TESTING_FAILED_RE.search(combined)
    if fail_m is not None:
        total = int(fail_m.group("total"))
        return SwiftTestOutcome(
            SwiftTestStatus.FAILED,
            f"Swift Testing reported {total} tests with failures",
            tests_reported=total,
        )
    if _XCTEST_FAILED_RE.search(combined) or any(
        int(m.group("failed")) > 0 for m in _XCTEST_SUMMARY_RE.finditer(combined)
    ):
        return SwiftTestOutcome(SwiftTestStatus.FAILED, "XCTest reported test failures")
    return None


def _has_unclosed_runner(output: str) -> bool:
    """Do not treat a final start marker as covered by a preceding summary."""
    for started, completed in (
        (_SWIFT_STARTED_RE, _SWIFT_TESTING_PASSED_RE),
        (_XCTEST_STARTED_RE, _XCTEST_GRAND_TOTAL_RE),
    ):
        starts = list(started.finditer(output))
        ends = list(completed.finditer(output))
        if starts and (
            len(starts) > len(ends) or starts[-1].start() > ends[-1].start()
        ):
            return True
    return False


def _passed_outcome_if_any(
    combined: str,
    stderr: str,
    returncode: int,
) -> SwiftTestOutcome | None:
    """Return a PASSED outcome when an authoritative success marker is present."""
    swift_runs = list(_SWIFT_TESTING_PASSED_RE.finditer(combined))
    xctest_runs = list(_XCTEST_GRAND_TOTAL_RE.finditer(combined))
    if not (swift_runs or xctest_runs):
        return None
    signal_m = _SPM_UNEXPECTED_SIGNAL_RE.search(stderr)
    signal_n = int(signal_m.group("sig")) if signal_m else None
    passed, _ = extract_swift_test_counts(combined)
    if returncode != 0 or signal_n is not None:
        if not _is_proven_teardown(returncode, signal_n, swift_runs + xctest_runs):
            return None
        if extract_compiler_error_lines(combined):
            return None
    known_issues = sum(
        int(n) for m in swift_runs for n in _KNOWN_ISSUE_COUNT_RE.findall(m.group(0))
    )
    return SwiftTestOutcome(
        status=SwiftTestStatus.PASSED,
        diagnostic=_success_diagnostic(returncode, signal_n, known_issues),
        teardown_signal=signal_n,
        tests_reported=passed,
        known_issues=known_issues,
    )


def _success_diagnostic(returncode: int, signal: int | None, known_issues: int) -> str:
    diagnostic = "all tests passed"
    if signal is not None:
        diagnostic += (
            f" but test harness exited {returncode}"
            f" (post-run signal {signal}) — treating as success"
        )
    if known_issues:
        noun = "issue" if known_issues == 1 else "issues"
        diagnostic += f" ({known_issues} known {noun})"
    return diagnostic


def _is_proven_teardown(
    returncode: int, signal: int | None, completed: list[re.Match[str]]
) -> bool:
    # AI: In a multi-run transcript, a signal cannot be attributed to a
    # previously completed nonempty run just because its summary is present.
    return (
        returncode == 1
        and signal == 10
        and sum(int(m.group("total")) > 0 for m in completed) == 1
    )


def extract_compiler_error_lines(output: str, max_lines: int = 5) -> tuple[str, ...]:
    """Return up to ``max_lines`` distinct compiler/SPM ``error:`` diagnostic lines.

    Lines are stripped and de-duplicated in first-seen order. The SwiftPM
    post-run signal marker (``error: Exited with unexpected signal code N``)
    is excluded — it classifies a teardown crash, not a compile diagnostic.
    """
    seen: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or "error:" not in line.lower():
            continue
        if _SPM_UNEXPECTED_SIGNAL_RE.search(line):
            continue
        if line not in seen:
            seen.append(line)
        if len(seen) >= max_lines:
            break
    return tuple(seen)


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
    if outcome.compiler_errors:
        return [prefix + " — " + " | ".join(outcome.compiler_errors)]
    if stderr_tail_text:
        lines = [line.strip() for line in stderr_tail_text.splitlines() if line.strip()]
        tail_lines = lines[-5:]
        if tail_lines:
            return [prefix + " — " + " | ".join(tail_lines)]
    return [prefix]
