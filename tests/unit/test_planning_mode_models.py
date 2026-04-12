"""Tests for planning mode enums and PlanSection model."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from cortex.core.models import PlanningMode, PlanSection, PlanSectionStatus


def test_planning_mode_values() -> None:
    assert PlanningMode.FAST_FORWARD.value == "ff"
    assert PlanningMode.STEP_BY_STEP.value == "step"


def test_plan_section_status_values() -> None:
    assert PlanSectionStatus.PENDING.value == "pending"
    assert PlanSectionStatus.APPROVED.value == "approved"


def test_plan_section_round_trip() -> None:
    when = datetime(2026, 4, 12, 12, 0, tzinfo=UTC)
    section = PlanSection(
        name="goal",
        status=PlanSectionStatus.APPROVED,
        content="## Goal\n\nShip modes.",
        approved_at=when,
    )
    dumped = section.model_dump(mode="json")
    assert dumped["name"] == "goal"
    assert dumped["status"] == "approved"
    restored = PlanSection.model_validate(dumped)
    assert restored.approved_at == when


def test_plan_section_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        _ = PlanSection.model_validate(
            {
                "name": "x",
                "status": "draft",
                "content": "",
                "extra_field": "no",
            }
        )
