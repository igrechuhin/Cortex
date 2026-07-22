"""Tests for vector-seeded recall merged into SessionBrief (AAA pattern)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_session_config import project_session_config_path
from cortex.experience.embedding_index_core import EmbeddingIndexCore
from cortex.experience.embedding_models import TaskEmbeddingRecord
from cortex.experience.encoder import HashingEncoder
from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
    ExperienceTask,
)
from cortex.experience.recorder import experience_db_path
from cortex.experience.store_core import ExperienceStoreCore
from cortex.tools.models import SessionHealthSummary
from cortex.tools.session.experience_recall_brief import (
    load_experience_recall_summary_safe,
    merge_experience_recall_into_brief,
)
from cortex.tools.session.models import SessionBrief, TokenBudgetStatus

_GOAL = "fix pyright type errors in the retrieval module"


def _minimal_brief(**overrides: object) -> SessionBrief:
    defaults: dict[str, object] = {
        "project_name": "Proj",
        "current_focus": "",
        "recent_completed": [],
        "next_work_item": None,
        "next_work_plan_path": None,
        "health": SessionHealthSummary(
            file_count=1, total_tokens=1, token_budget_status=TokenBudgetStatus.HEALTHY
        ),
        "git_status": None,
        "session_suggestions": [],
        "last_handoff": None,
        "concurrent_sessions": [],
        "locked_tasks": [],
        "mcp_healthy": True,
        "mcp_health_message": None,
    }
    defaults.update(overrides)
    return SessionBrief.model_validate(defaults)


def _disable_recall(project_root: Path) -> None:
    cortex_dir = get_cortex_path(project_root, CortexResourceType.CORTEX_DIR)
    cortex_dir.mkdir(parents=True, exist_ok=True)
    path = project_session_config_path(project_root)
    _ = path.write_text(
        yaml.safe_dump({"experience_recall_enabled": False}), encoding="utf-8"
    )


def _seed_matching_task(project_root: Path) -> None:
    db_path = experience_db_path(project_root)
    core = ExperienceStoreCore(db_path)
    index = EmbeddingIndexCore(db_path)
    encoder = HashingEncoder()
    task = core.create_task(ExperienceTask(id="task-1", spec=_GOAL))
    _ = index.upsert(
        TaskEmbeddingRecord(
            task_id=task.id,
            vector=encoder.encode(_GOAL),
            dim=encoder.dim,
            encoder_version=encoder.version,
        )
    )
    session = core.create_session(
        ExperienceSession(task_id=task.id, algorithm="commit", owner="sess")
    )
    _ = core.append_node(
        ExperienceNode(
            session_id=session.id,
            status=ExperienceNodeStatus.COMPLETED,
            label="quality-gate",
            fitness=1.0,
            step_number=1,
        )
    )


@pytest.mark.asyncio
async def test_load_experience_recall_summary_safe_no_store_returns_none(
    tmp_path: Path,
) -> None:
    # Act
    summary = await load_experience_recall_summary_safe(tmp_path, _GOAL)

    # Assert
    assert summary is None


@pytest.mark.asyncio
async def test_load_experience_recall_summary_safe_disabled_returns_none(
    tmp_path: Path,
) -> None:
    # Arrange
    _disable_recall(tmp_path)
    _seed_matching_task(tmp_path)

    # Act
    summary = await load_experience_recall_summary_safe(tmp_path, _GOAL)

    # Assert
    assert summary is None


@pytest.mark.asyncio
async def test_load_experience_recall_summary_safe_finds_matching_task(
    tmp_path: Path,
) -> None:
    # Arrange
    _seed_matching_task(tmp_path)

    # Act
    summary = await load_experience_recall_summary_safe(tmp_path, _GOAL)

    # Assert
    assert summary is not None
    assert "Prior experience" in summary


@pytest.mark.asyncio
async def test_merge_experience_recall_into_brief_no_goal_returns_unchanged(
    tmp_path: Path,
) -> None:
    # Arrange
    brief = _minimal_brief(current_focus="", primary_session_goal=None)
    _seed_matching_task(tmp_path)

    # Act
    merged = await merge_experience_recall_into_brief(brief, tmp_path)

    # Assert
    assert merged.experience_recall_summary is None


@pytest.mark.asyncio
async def test_merge_experience_recall_into_brief_attaches_summary(
    tmp_path: Path,
) -> None:
    # Arrange
    brief = _minimal_brief(primary_session_goal=_GOAL)
    _seed_matching_task(tmp_path)

    # Act
    merged = await merge_experience_recall_into_brief(brief, tmp_path)

    # Assert
    assert merged.experience_recall_summary is not None
    assert "Prior experience" in merged.experience_recall_summary


@pytest.mark.asyncio
async def test_merge_experience_recall_into_brief_falls_back_to_current_focus(
    tmp_path: Path,
) -> None:
    # Arrange
    brief = _minimal_brief(current_focus=_GOAL, primary_session_goal=None)
    _seed_matching_task(tmp_path)

    # Act
    merged = await merge_experience_recall_into_brief(brief, tmp_path)

    # Assert
    assert merged.experience_recall_summary is not None
