"""Unit tests for grading claims against a quality-gate frame."""

from __future__ import annotations

from cortex.core.models import ModelDict
from cortex.experience.claim_grading import (
    GradingFrame,
    frame_from_gate_result,
    grade_claims,
    verdict_counts,
)
from cortex.experience.claims import Verdict, parse_claims


def _grade(text: str, frame: GradingFrame) -> Verdict:
    return grade_claims(parse_claims(text), frame)[0].verdict


def _frame(**overrides: object) -> GradingFrame:
    base: dict[str, object] = {"passed": True}
    base.update(overrides)
    return GradingFrame.model_validate(base)


# --- gate clean ---------------------------------------------------------


def test_gate_clean_hits_on_passing_frame() -> None:
    assert _grade("gate clean", _frame(passed=True)) is Verdict.HIT


def test_gate_clean_misses_on_failing_frame() -> None:
    assert _grade("gate clean", _frame(passed=False)) is Verdict.MISS


# --- gate fails <check> -------------------------------------------------


def test_gate_fails_hits_when_named_check_failed() -> None:
    frame = _frame(
        passed=False,
        ran_checks=frozenset({"type_check"}),
        failed_checks=frozenset({"type_check"}),
    )
    assert _grade("gate fails type_check", frame) is Verdict.HIT


def test_gate_fails_misses_when_named_check_passed() -> None:
    frame = _frame(ran_checks=frozenset({"type_check"}))
    assert _grade("gate fails type_check", frame) is Verdict.MISS


def test_gate_fails_ungraded_when_check_did_not_run() -> None:
    assert _grade("gate fails type_check", _frame()) is Verdict.UNGRADED


# --- error gone <check>@<path> ------------------------------------------


def test_error_gone_hits_when_error_absent() -> None:
    frame = _frame(ran_checks=frozenset({"ruff"}), errors=[])
    assert _grade("error gone ruff@src/a.py", frame) is Verdict.HIT


def test_error_gone_misses_when_error_remains() -> None:
    frame = _frame(
        passed=False,
        ran_checks=frozenset({"ruff"}),
        failed_checks=frozenset({"ruff"}),
        errors=[{"file": "src/a.py", "check": "ruff", "message": "E501"}],
    )
    assert _grade("error gone ruff@src/a.py", frame) is Verdict.MISS


def test_error_gone_ungraded_when_check_did_not_run() -> None:
    assert _grade("error gone ruff@src/a.py", _frame()) is Verdict.UNGRADED


def test_error_gone_ungraded_when_failing_check_reports_no_file_rows() -> None:
    # The gate summarises failures per check ("<ruff>"), never per file, so a
    # failing check carries no evidence about one specific path.
    frame = _frame(
        passed=False,
        ran_checks=frozenset({"ruff"}),
        failed_checks=frozenset({"ruff"}),
        errors=[{"file": "<ruff>", "check": "ruff", "message": "3 errors"}],
    )
    assert _grade("error gone ruff@src/a.py", frame) is Verdict.UNGRADED


# --- test <nodeid> passes | fails ---------------------------------------

_PASS_OUTPUT = "tests/t.py::test_x PASSED\n"
_FAIL_OUTPUT = "FAILED tests/t.py::test_x - AssertionError\n"


def test_test_passes_hits_on_passing_output() -> None:
    frame = _frame(test_output=_PASS_OUTPUT)
    assert _grade("test tests/t.py::test_x passes", frame) is Verdict.HIT


def test_test_passes_misses_on_failing_output() -> None:
    frame = _frame(passed=False, test_output=_FAIL_OUTPUT)
    assert _grade("test tests/t.py::test_x passes", frame) is Verdict.MISS


def test_test_fails_hits_on_failing_output() -> None:
    frame = _frame(passed=False, test_output=_FAIL_OUTPUT)
    assert _grade("test tests/t.py::test_x fails", frame) is Verdict.HIT


def test_test_ungraded_when_node_absent_from_output() -> None:
    frame = _frame(test_output="tests/other.py::test_y PASSED")
    assert _grade("test tests/t.py::test_x passes", frame) is Verdict.UNGRADED


def test_test_ungraded_when_no_test_output_at_all() -> None:
    assert _grade("test tests/t.py::test_x passes", _frame()) is Verdict.UNGRADED


def test_test_node_named_error_is_not_read_as_a_failure() -> None:
    # Regression: scanning the whole line made every test whose name contains
    # "error" grade as failed.
    frame = _frame(test_output="tests/t.py::test_error_gone PASSED")
    assert _grade("test tests/t.py::test_error_gone passes", frame) is Verdict.HIT


# --- coverage >= <pct> --------------------------------------------------


def test_coverage_hits_at_or_above_threshold() -> None:
    assert _grade("coverage >= 90", _frame(coverage_pct=91.0)) is Verdict.HIT


def test_coverage_misses_below_threshold() -> None:
    assert _grade("coverage >= 90", _frame(coverage_pct=89.9)) is Verdict.MISS


def test_coverage_ungraded_without_a_figure() -> None:
    assert _grade("coverage >= 90", _frame()) is Verdict.UNGRADED


# --- touches / noop <path> ----------------------------------------------


def test_touches_hits_when_path_changed() -> None:
    frame = _frame(changed_files=frozenset({"src/a.py"}))
    assert _grade("touches src/a.py", frame) is Verdict.HIT


def test_touches_misses_when_path_unchanged() -> None:
    frame = _frame(changed_files=frozenset({"src/b.py"}))
    assert _grade("touches src/a.py", frame) is Verdict.MISS


def test_noop_path_hits_when_path_unchanged() -> None:
    frame = _frame(changed_files=frozenset({"src/b.py"}))
    assert _grade("noop src/a.py", frame) is Verdict.HIT


def test_path_claim_ungraded_without_a_diff() -> None:
    assert _grade("touches src/a.py", _frame()) is Verdict.UNGRADED


# --- change / noop ------------------------------------------------------


def test_change_hits_when_diff_non_empty() -> None:
    frame = _frame(changed_files=frozenset({"src/a.py"}))
    assert _grade("change", frame) is Verdict.HIT


def test_noop_hits_on_empty_diff() -> None:
    assert _grade("noop", _frame(changed_files=frozenset[str]())) is Verdict.HIT


def test_free_text_grades_as_change() -> None:
    frame = _frame(changed_files=frozenset[str]())
    assert _grade("the retry loop stops double-counting", frame) is Verdict.MISS


def test_diff_claim_ungraded_without_a_diff() -> None:
    assert _grade("change", _frame()) is Verdict.UNGRADED


# --- compound + counting ------------------------------------------------


def test_compound_claim_grades_each_part_independently() -> None:
    # Arrange
    frame = _frame(passed=True, changed_files=frozenset({"src/a.py"}))

    # Act
    verdicts = grade_claims(
        parse_claims("gate clean; touches src/a.py; touches src/missing.py"), frame
    )

    # Assert
    assert [v.verdict for v in verdicts] == [
        Verdict.HIT,
        Verdict.HIT,
        Verdict.MISS,
    ]
    assert verdict_counts(verdicts) == {"HIT": 2, "MISS": 1, "UNGRADED": 0}


# --- frame assembly -----------------------------------------------------


def test_frame_from_failing_gate_result_extracts_checks_and_errors() -> None:
    # Arrange
    result: ModelDict = {
        "preflight_passed": False,
        "coverage": 0.93,
        "checks": [
            {"name": "type_check", "status": "failed", "message": "2 errors"},
            {"name": "format", "status": "passed"},
        ],
        "results": {"tests": {"output": "tests/t.py::test_x PASSED"}},
    }

    # Act
    frame = frame_from_gate_result(result, frozenset({"src/a.py"}))

    # Assert
    assert frame.passed is False
    assert frame.ran_checks == frozenset({"type_check", "format"})
    assert frame.failed_checks == frozenset({"type_check"})
    assert frame.coverage_pct == 93.0
    assert frame.test_output == "tests/t.py::test_x PASSED"
    assert [err.check for err in frame.errors] == ["type_check"]


def test_frame_accepts_string_checks_list_and_percent_coverage() -> None:
    # Arrange
    result: ModelDict = {
        "preflight_passed": True,
        "coverage": 94.5,
        "checks_performed": ["tests", "format"],
    }

    # Act
    frame = frame_from_gate_result(result, None)

    # Assert
    assert frame.ran_checks == frozenset({"tests", "format"})
    assert frame.failed_checks == frozenset()
    assert frame.coverage_pct == 94.5
    assert frame.changed_files is None
    assert frame.errors == []


def test_frame_ignores_bool_coverage_value() -> None:
    # Arrange
    result: ModelDict = {"preflight_passed": True, "coverage": False}

    # Act
    frame = frame_from_gate_result(result, None)

    # Assert
    assert frame.coverage_pct is None
