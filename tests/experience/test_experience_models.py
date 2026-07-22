"""Unit tests for experience-store Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
    ExperienceTask,
    new_experience_id,
)


def test_new_experience_id_is_unique_hex() -> None:
    # Arrange / Act
    first = new_experience_id()
    second = new_experience_id()

    # Assert
    assert first != second
    assert len(first) == 32


def test_experience_task_defaults_populate_id_and_created_at() -> None:
    # Arrange / Act
    task = ExperienceTask(spec="pipeline:commit")

    # Assert
    assert task.id
    assert task.created_at
    assert task.success_metric is None


def test_experience_task_rejects_empty_spec() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError):
        _ = ExperienceTask(spec="")


def test_experience_session_requires_task_id_and_algorithm() -> None:
    # Arrange / Act
    session = ExperienceSession(task_id="t1", algorithm="commit", owner="sess")

    # Assert
    assert session.task_id == "t1"
    assert session.algorithm == "commit"
    with pytest.raises(ValidationError):
        _ = ExperienceSession(task_id="", algorithm="commit")


def test_experience_node_defaults_and_status_enum() -> None:
    # Arrange / Act
    node = ExperienceNode(session_id="s1")

    # Assert
    assert node.status is ExperienceNodeStatus.RUNNING
    assert node.step_number == 1
    assert node.parent_id is None
    assert node.fitness is None


def test_experience_node_rejects_nonpositive_step_number() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError):
        _ = ExperienceNode(session_id="s1", step_number=0)


def test_experience_node_rejects_empty_session_id() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError):
        _ = ExperienceNode(session_id="")
