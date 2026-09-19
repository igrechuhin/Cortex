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


def test_render_recall_summary_falls_back_to_header_and_omission_note() -> None:
    # Arrange: header fits but the first (long) match line does not.
    matches = [
        _match(task_id=f"t{i}", spec=f"task number {i} with a fairly long description")
        for i in range(10)
    ]
    result = RecallResult(goal="fix types", matches=matches)

    # Act
    text = render_recall_summary(result, budget_chars=120)

    # Assert
    assert (
        text == "Prior experience (goal-similar tasks):\n… 10 matches omitted (budget)"
    )


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
    marker = "\n… 3 matches omitted (budget)"
    # The omission marker is part of the budget, not appended after it, so the
    # budget must cover header + two match lines + the marker. This previously
    # reserved nothing for the marker and overran the caller's cap.
    budget = len(header) + (len(line) + 1) * 2 + len(marker)

    # Act
    text = render_recall_summary(result, budget_chars=budget)

    # Assert
    assert text is not None
    assert text == "\n".join([header, line, line]) + marker
    assert len(text) <= budget


def test_render_recall_summary_budget_too_small_for_header_returns_none() -> None:
    # Arrange: budget is smaller than the pinned header itself, so there is
    # nothing useful to emit — never a raw char slice of the header.
    result = RecallResult(goal="fix types", matches=[_match()])

    # Act
    text = render_recall_summary(result, budget_chars=10)

    # Assert
    assert text is None


def test_render_recall_summary_never_exceeds_budget_at_any_size() -> None:
    # Arrange: the omission marker is part of the budget, not appended after
    # it. Sweeping every budget around the boundaries catches the off-by-one
    # where the marker pushed the block past the caller's cap.
    result = RecallResult(
        goal="fix types",
        matches=[
            _match(task_id=f"t{index}", spec=f"task {'x' * index} number {index}")
            for index in range(6)
        ],
    )

    # Act / Assert
    for budget in range(0, 400):
        text = render_recall_summary(result, budget_chars=budget)
        if text is None:
            continue
        assert len(text) <= budget, f"overran budget {budget}: {len(text)} chars"
        assert text.startswith("Prior experience (goal-similar tasks):")


def test_render_recall_summary_marker_is_on_its_own_line() -> None:
    # Arrange: a budget that fits the header plus some matches but not all.
    result = RecallResult(
        goal="fix types",
        matches=[_match(task_id=f"t{index}") for index in range(6)],
    )

    # Act
    text = render_recall_summary(result, budget_chars=260)

    # Assert: the marker must not be glued onto the last match line.
    assert text is not None
    lines = text.split("\n")
    assert lines[-1].startswith("… ")
    assert "matches omitted (budget)" in lines[-1]
    assert all(line.startswith("- ") for line in lines[1:-1])
