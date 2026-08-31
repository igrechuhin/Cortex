"""The predictions line reaches the session brief and stays within its cap."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.experience.claim_grading import GradingFrame, grade_claims
from cortex.experience.claims import parse_claims
from cortex.experience.predictions import record_prediction, record_verdicts
from cortex.tools.session.brief_cap import cap_session_brief_payload
from cortex.tools.session.models import (
    SessionBrief,
    SessionHealthSummary,
    TokenBudgetStatus,
)
from cortex.tools.session.predictions_brief import merge_predictions_into_brief


def _brief() -> SessionBrief:
    health = SessionHealthSummary(
        file_count=0, total_tokens=0, token_budget_status=TokenBudgetStatus.HEALTHY
    )
    return SessionBrief(
        project_name="Cortex",
        health=health,
        next_work_item=None,
        next_work_plan_path=None,
        git_status=None,
        last_handoff=None,
    )


@pytest.fixture(autouse=True)
def _session(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_SESSION_ID", "briefsess")


def test_brief_is_unchanged_without_predictions(tmp_path: Path) -> None:
    # Arrange / Act
    merged = merge_predictions_into_brief(_brief(), tmp_path)

    # Assert
    assert merged.predictions is None


def test_brief_reports_open_claim_count(tmp_path: Path) -> None:
    # Arrange
    _ = record_prediction(
        tmp_path, "briefsess", parse_claims("gate clean; touches src/a.py")
    )

    # Act
    merged = merge_predictions_into_brief(_brief(), tmp_path)

    # Assert
    assert merged.predictions is not None
    assert "2 open claim(s)" in merged.predictions


def test_brief_reports_recent_misses(tmp_path: Path) -> None:
    # Arrange
    claims = parse_claims("gate clean")
    verdicts = grade_claims(claims, GradingFrame(passed=False))
    _ = record_verdicts(tmp_path, "briefsess", verdicts)

    # Act
    merged = merge_predictions_into_brief(_brief(), tmp_path)

    # Assert
    assert merged.predictions is not None
    assert "recent misses: gate clean" in merged.predictions


def test_predictions_line_is_capped(tmp_path: Path) -> None:
    # Arrange
    brief = _brief().model_copy(update={"predictions": "x" * 5000})

    # Act
    capped = cap_session_brief_payload(brief)

    # Assert
    assert capped.predictions is not None
    assert len(capped.predictions) <= 400


def test_brief_survives_a_broken_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    def _boom(*args: object, **kwargs: object) -> str:
        raise OSError("no session id")

    monkeypatch.setattr(
        "cortex.tools.session.pipeline_handoff_io.get_session_id", _boom
    )

    # Act
    merged = merge_predictions_into_brief(_brief(), tmp_path)

    # Assert
    assert merged.predictions is None


def test_brief_counts_free_text_claims(tmp_path: Path) -> None:
    # Arrange
    _ = record_prediction(
        tmp_path, "briefsess", parse_claims("gate clean; the loop stops retrying")
    )

    # Act
    merged = merge_predictions_into_brief(_brief(), tmp_path)

    # Assert
    assert merged.predictions is not None
    assert "1 free-text" in merged.predictions
