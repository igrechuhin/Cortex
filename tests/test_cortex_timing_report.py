"""Regression tests for read-only timing report."""

import json

from scripts.cortex_timing_report import (
    TimingReport,
    phase_timings,
    render,
    swift_tests,
)


def test_checkpoint_repetitions_and_partial_events() -> None:
    """Ignore broken tails and distinguish unmatched checkpoints."""

    def event(time: float, operation: str, phase: str = "checks") -> str:
        args = {"operation": operation, "phase": phase, "data": {"status": "passed"}}
        data = {"tool": "pipeline_handoff", "args": args, "result": {"isError": False}}
        return json.dumps({"time": time, "kind": "mcp", "data": data})

    report = TimingReport()
    phase_timings(
        [event(1, "write"), event(2, "init"), event(7, "write"), '{"time":'], report
    )
    assert report.phases == [("checks", None), ("checks", 5)]
    output = render(report, 1)
    assert "checks ×2" in output
    assert "invalid event line 4" in output


def test_sort_individual_tests_without_summing_parallel_durations() -> None:
    """Recognize Swift Testing and XCTest but not summaries."""
    report = TimingReport(
        tests=swift_tests(
            [
                '✔ Test "rotation" passed after 249.368 seconds.',
                "Test Case '-[Suite short]' failed (1.002 seconds).",
                "✔ Test run with 2 tests passed after 250 seconds.",
            ]
        )
    )
    assert report.tests == [
        ('"rotation"', "passed", 249.368),
        ("-[Suite short]", "failed", 1.002),
    ]
    output = render(report, 1)
    assert "rotation" in output
    assert "short" not in output
    assert "not additive" in output
