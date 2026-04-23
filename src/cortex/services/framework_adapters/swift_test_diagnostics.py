"""Swift ``swift test`` harness-failure diagnostics.

Used by :class:`SwiftAdapter` when ``swift test`` exits non-zero but XCTest
reported 0 assertion failures — the generic ``Test execution failed`` message
hides the real cause (linker error, target crash, signal). These helpers
classify the failure and surface a stderr tail so downstream fix-path agents
can route intelligently instead of looping on a generic error.
"""

from __future__ import annotations

# Classifies non-zero ``swift test`` exits that parsed 0 assertion failures.
_SWIFT_LINKER_HINTS = (
    "undefined symbol",
    "linker command failed",
    "ld: symbol(s) not found",
    "duplicate symbol",
)
_SWIFT_COMPILE_HINTS = (
    ".swift:",
    "cannot find ",
    "missing argument",
)


def classify_swift_test_failure(output: str, returncode: int) -> str:
    """Classify a non-zero ``swift test`` exit into a short category label.

    Used by the gate to surface *why* the test harness failed when no
    assertion count was reported (the default ``Test execution failed``
    message hides the real cause — link error, crash, or signal).
    """
    if returncode < 0:
        return f"signal {-returncode}"
    lowered = output.lower()
    for hint in _SWIFT_LINKER_HINTS:
        if hint in lowered:
            return "linker failure"
    if any(hint in lowered for hint in _SWIFT_COMPILE_HINTS) and "error:" in lowered:
        return "compile error"
    if "fatal error:" in lowered:
        return "fatal error / crash"
    return "harness failure"


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
    """Build diagnostic errors when swift test exited non-zero but parsed 0 failures."""
    classification = classify_swift_test_failure(output, returncode)
    prefix = f"swift test exited {returncode} ({classification})"
    if stderr_tail_text:
        lines = [line.strip() for line in stderr_tail_text.splitlines() if line.strip()]
        tail_lines = lines[-5:]
        if tail_lines:
            return [prefix + " — " + " | ".join(tail_lines)]
    return [prefix]
