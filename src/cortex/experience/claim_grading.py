"""Grade open claims against the next quality-gate result.

A :class:`GradingFrame` is the "next frame" a claim can be contradicted by: a
quality-gate result plus the set of files the working tree changed. Every
grader returns ``UNGRADED`` rather than a silent pass when the frame carries no
evidence for its claim.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

from pydantic import BaseModel, Field

from cortex.experience.claims import Claim, ClaimKind, ClaimVerdict, Verdict

__all__ = [
    "FrameError",
    "GradingFrame",
    "frame_from_gate_result",
    "grade_claims",
    "verdict_counts",
]


class FrameError(BaseModel):
    """One gate error row, flattened out of ``GateFeedback``."""

    file: str
    check: str
    message: str = ""


class GradingFrame(BaseModel):
    """Evidence available to grade a claim after one quality-gate run."""

    passed: bool
    errors: list[FrameError] = Field(default_factory=list[FrameError])
    ran_checks: frozenset[str] = Field(default_factory=frozenset)
    failed_checks: frozenset[str] = Field(default_factory=frozenset)
    coverage_pct: float | None = None
    test_output: str | None = None
    changed_files: frozenset[str] | None = None


def _check_names(result: Mapping[str, object]) -> tuple[frozenset[str], frozenset[str]]:
    """Return (ran, failed) check names from either payload shape."""
    ran: set[str] = set()
    failed: set[str] = set()
    raw = result.get("checks") or result.get("checks_performed")
    for item in cast(list[object], raw if isinstance(raw, list) else []):
        if isinstance(item, str):
            ran.add(item.lower())
        elif isinstance(item, dict):
            entry = cast(dict[str, object], item)
            name = str(entry.get("name", "")).lower()
            if not name:
                continue
            ran.add(name)
            if str(entry.get("status", "")).lower() in {"failed", "error"}:
                failed.add(name)
    return frozenset(ran), frozenset(failed)


def _coverage_pct(result: Mapping[str, object]) -> float | None:
    raw = result.get("coverage")
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        return None
    value = float(raw)
    # AI: the gate reports coverage as a 0..1 fraction; claims are written in percent.
    return value * 100.0 if value <= 1.0 else value


def _test_output(result: Mapping[str, object]) -> str | None:
    results = result.get("results")
    if not isinstance(results, dict):
        return None
    tests = cast(dict[str, object], results).get("tests")
    if not isinstance(tests, dict):
        return None
    parts = [
        str(value)
        for key, value in cast(dict[str, object], tests).items()
        if key in {"output", "stdout", "stderr", "message"} and value
    ]
    return "\n".join(parts) or None


def frame_from_gate_result(
    result: Mapping[str, object], changed_files: frozenset[str] | None
) -> GradingFrame:
    """Assemble the grading frame from a quality-gate result and a diff."""
    # AI: imported lazily — cortex.tools imports gate_hook, which imports this module.
    from cortex.tools.session.gate_feedback import feedback_from_quality_result

    feedback = feedback_from_quality_result(result)
    ran, failed = _check_names(result)
    return GradingFrame(
        passed=bool(result.get("preflight_passed")),
        errors=(
            [
                FrameError(file=err.file, check=err.check, message=err.message)
                for err in feedback.errors
            ]
            if feedback is not None
            else []
        ),
        ran_checks=ran,
        failed_checks=failed,
        coverage_pct=_coverage_pct(result),
        test_output=_test_output(result),
        changed_files=changed_files,
    )


def _verdict(hit: bool) -> Verdict:
    return Verdict.HIT if hit else Verdict.MISS


def _grade_gate_clean(claim: Claim, frame: GradingFrame) -> tuple[Verdict, str]:
    del claim
    return _verdict(frame.passed), f"preflight_passed={frame.passed}"


def _grade_gate_fails(claim: Claim, frame: GradingFrame) -> tuple[Verdict, str]:
    name = claim.target.lower()
    if name not in frame.ran_checks:
        return Verdict.UNGRADED, f"check {claim.target!r} did not run"
    failed = name in frame.failed_checks
    return _verdict(failed), f"check {claim.target!r} failed={failed}"


def _grade_error_gone(claim: Claim, frame: GradingFrame) -> tuple[Verdict, str]:
    check, _, path = claim.target.partition("@")
    lowered = check.lower()
    if lowered not in frame.ran_checks:
        return Verdict.UNGRADED, f"check {check!r} did not run"
    if lowered not in frame.failed_checks:
        return Verdict.HIT, f"check {check!r} passed, so no error remains"
    matching = [
        err for err in frame.errors if err.check.lower() == lowered and path in err.file
    ]
    if matching:
        return Verdict.MISS, f"{len(matching)} error(s) still name {path}"
    # AI: the gate reports failures per check, not per file. A failing check with
    # no path-bearing row cannot decide this claim — say so instead of passing it.
    return Verdict.UNGRADED, f"check {check!r} failed but reported no per-file rows"


def _test_outcome(nodeid: str, output: str | None) -> bool | None:
    if not output:
        return None
    statuses: set[str] = set()
    for line in output.splitlines():
        if nodeid not in line:
            continue
        # AI: strip the node id before scanning for status words — a test named
        # test_error_gone would otherwise make every one of its lines read FAILED.
        rest = line.replace(nodeid, " ").upper()
        statuses.update(word for word in ("FAILED", "ERROR", "PASSED") if word in rest)
    if not statuses:
        return None
    return not statuses & {"FAILED", "ERROR"}


def _grade_test(claim: Claim, frame: GradingFrame) -> tuple[Verdict, str]:
    outcome = _test_outcome(claim.target, frame.test_output)
    if outcome is None:
        return Verdict.UNGRADED, f"no test outcome for {claim.target!r} in frame"
    want_pass = claim.kind is ClaimKind.TEST_PASSES
    return _verdict(outcome is want_pass), f"{claim.target} passed={outcome}"


def _grade_coverage(claim: Claim, frame: GradingFrame) -> tuple[Verdict, str]:
    if frame.coverage_pct is None or claim.threshold is None:
        return Verdict.UNGRADED, "frame carried no coverage figure"
    return (
        _verdict(frame.coverage_pct >= claim.threshold),
        f"coverage={frame.coverage_pct:.2f}% threshold={claim.threshold:.2f}%",
    )


def _path_changed(target: str, changed: frozenset[str]) -> bool:
    return any(item == target or item.endswith(f"/{target}") for item in changed)


def _grade_path(claim: Claim, frame: GradingFrame) -> tuple[Verdict, str]:
    if frame.changed_files is None:
        return Verdict.UNGRADED, "frame carried no diff"
    touched = _path_changed(claim.target, frame.changed_files)
    want_touched = claim.kind is ClaimKind.TOUCHES
    return _verdict(touched is want_touched), f"{claim.target} changed={touched}"


def _grade_diff(claim: Claim, frame: GradingFrame) -> tuple[Verdict, str]:
    if frame.changed_files is None:
        return Verdict.UNGRADED, "frame carried no diff"
    changed = bool(frame.changed_files)
    want_changed = claim.kind is ClaimKind.CHANGE
    return (
        _verdict(changed is want_changed),
        f"{len(frame.changed_files)} file(s) changed",
    )


_GRADERS: dict[ClaimKind, Callable[[Claim, GradingFrame], tuple[Verdict, str]]] = {
    ClaimKind.GATE_CLEAN: _grade_gate_clean,
    ClaimKind.GATE_FAILS: _grade_gate_fails,
    ClaimKind.ERROR_GONE: _grade_error_gone,
    ClaimKind.TEST_PASSES: _grade_test,
    ClaimKind.TEST_FAILS: _grade_test,
    ClaimKind.COVERAGE_AT_LEAST: _grade_coverage,
    ClaimKind.TOUCHES: _grade_path,
    ClaimKind.NOOP_PATH: _grade_path,
    ClaimKind.CHANGE: _grade_diff,
    ClaimKind.NOOP: _grade_diff,
}


def grade_claims(claims: list[Claim], frame: GradingFrame) -> list[ClaimVerdict]:
    """Grade every claim independently against the frame."""
    graded: list[ClaimVerdict] = []
    for claim in claims:
        verdict, evidence = _GRADERS[claim.kind](claim, frame)
        graded.append(ClaimVerdict(claim=claim, verdict=verdict, evidence=evidence))
    return graded


def verdict_counts(verdicts: list[ClaimVerdict]) -> dict[str, int]:
    """Count verdicts by name (``HIT``/``MISS``/``UNGRADED``)."""
    counts = {member.value: 0 for member in Verdict}
    for item in verdicts:
        counts[item.verdict.value] += 1
    return counts
