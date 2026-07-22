"""Unit tests for recall summary rendering and budget truncation (AAA)."""

from __future__ import annotations

from cortex.experience.recall_models import RecallResult, TaskRecallMatch
from cortex.experience.recall_render import render_recall_summary


def _match(**overrides: object) -> TaskRecallMatch:
    defaults: dict[str, object] = {
        "task_id": "t1",
        "spec": "fix pyright type errors",
        "similarity": 0.82,
        "best_fitness": 1.0,
        "best_fitness_label": "quality-gate",
        "dead_end_label": None,
    }
    defaults.update(overrides)
    return TaskRecallMatch.model_validate(defaults)


def test_recall_result_matches_defaults_to_empty_list_when_omitted() -> None:
    # Act
    result = RecallResult(goal="fix types")

    # Assert
    assert result.matches == []


def test_render_recall_summary_includes_header_and_match_details() -> None:
    # Arrange
    result = RecallResult(goal="fix types", matches=[_match()])

    # Act
    text = render_recall_summary(result, budget_chars=500)

    # Assert
    assert text is not None
    assert "Prior experience" in text
    assert "fix pyright type errors" in text
    assert "0.82" in text
    assert "best outcome fitness=1.00 [quality-gate]" in text


def test_render_recall_summary_includes_dead_end_when_present() -> None:
    # Arrange
    result = RecallResult(
        goal="fix types", matches=[_match(dead_end_label="markdown-lint-retry")]
    )

    # Act
    text = render_recall_summary(result, budget_chars=500)

    # Assert
    assert text is not None
    assert "dead end: markdown-lint-retry" in text


def test_render_recall_summary_no_matches_returns_none() -> None:
    # Arrange
    result = RecallResult(goal="fix types", matches=[])

    # Act
    text = render_recall_summary(result, budget_chars=500)

    # Assert
    assert text is None


def test_render_recall_summary_zero_budget_returns_none() -> None:
    # Arrange
    result = RecallResult(goal="fix types", matches=[_match()])

    # Act
    text = render_recall_summary(result, budget_chars=0)

    # Assert
    assert text is None


def test_render_recall_summary_truncates_to_whole_lines_within_budget() -> None:
    # Arrange
    matches = [
        _match(task_id=f"t{i}", spec=f"task number {i} with a fairly long description")
        for i in range(10)
    ]
    result = RecallResult(goal="fix types", matches=matches)

    # Act
    text = render_recall_summary(result, budget_chars=120)

    # Assert
    assert text is not None
    assert len(text) <= 121  # allows the trailing ellipsis char
    assert text.endswith("…")


def test_render_recall_summary_truncates_to_multiple_whole_lines() -> None:
    # Arrange: five identical short matches so line lengths are uniform.
    matches = [
        _match(task_id=f"t{i}", spec="task", best_fitness=None, dead_end_label=None)
        for i in range(5)
    ]
    result = RecallResult(goal="fix types", matches=matches)
    full = render_recall_summary(result, budget_chars=100_000)
    assert full is not None
    header, line, *_ = full.split("\n")
    # Budget exactly fits header + two match lines (matches the truncation
    # loop's running-length accounting), leaving no room for a third line.
    budget = len(header) + (len(line) + 1) * 2

    # Act
    text = render_recall_summary(result, budget_chars=budget)

    # Assert
    assert text == "\n".join([header, line, line]) + "…"


def test_render_recall_summary_budget_too_small_for_one_line_hard_truncates() -> None:
    # Arrange
    result = RecallResult(goal="fix types", matches=[_match()])

    # Act
    text = render_recall_summary(result, budget_chars=10)

    # Assert
    assert text is not None
    assert len(text) == 10
    assert text.endswith("…")
