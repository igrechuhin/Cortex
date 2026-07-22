"""Tests for .cortex/session.yaml and workflow_schema defaults."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_session_config import (
    load_project_session_config,
    project_session_config_path,
    validate_schema_fork_name,
)
from cortex.core.session_config import read_session_config


def test_load_project_session_config_missing(tmp_path: Path) -> None:
    cfg = load_project_session_config(tmp_path)
    assert cfg.workflow_schema == "default"


def test_load_project_session_config_experience_recall_defaults(
    tmp_path: Path,
) -> None:
    # Act
    cfg = load_project_session_config(tmp_path)

    # Assert
    assert cfg.experience_recall_enabled is True
    assert cfg.experience_recall_k == 3
    assert cfg.experience_recall_similarity_threshold == 0.35
    assert cfg.experience_recall_budget_chars == 600


def test_load_project_session_config_experience_recall_overrides(
    tmp_path: Path,
) -> None:
    # Arrange
    cortex = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
    cortex.mkdir(parents=True)
    path = project_session_config_path(tmp_path)
    _ = path.write_text(
        yaml.safe_dump(
            {
                "experience_recall_enabled": False,
                "experience_recall_k": 5,
                "experience_recall_similarity_threshold": 0.5,
                "experience_recall_budget_chars": 100,
            }
        ),
        encoding="utf-8",
    )

    # Act
    cfg = load_project_session_config(tmp_path)

    # Assert
    assert cfg.experience_recall_enabled is False
    assert cfg.experience_recall_k == 5
    assert cfg.experience_recall_similarity_threshold == 0.5
    assert cfg.experience_recall_budget_chars == 100


def test_load_project_session_config_from_yaml(tmp_path: Path) -> None:
    cortex = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
    cortex.mkdir(parents=True)
    path = project_session_config_path(tmp_path)
    _ = path.write_text(
        yaml.safe_dump({"workflow_schema": "fast-path"}), encoding="utf-8"
    )
    cfg = load_project_session_config(tmp_path)
    assert cfg.workflow_schema == "fast-path"


def test_load_project_session_config_preserves_extra_keys_for_workflow_conditions(
    tmp_path: Path,
) -> None:
    """Unknown session.yaml keys are kept for schema ``condition`` evaluation."""
    cortex = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
    cortex.mkdir(parents=True)
    path = project_session_config_path(tmp_path)
    _ = path.write_text(
        yaml.safe_dump(
            {"workflow_schema": "data-science", "eda_required": True},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    cfg = load_project_session_config(tmp_path)
    assert cfg.workflow_schema == "data-science"
    dumped = cfg.model_dump(mode="python")
    assert dumped.get("eda_required") is True


def test_read_session_config_merges_workflow_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cortex = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
    session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
    cortex.mkdir(parents=True)
    session_dir.mkdir(parents=True)
    _ = project_session_config_path(tmp_path).write_text(
        yaml.safe_dump({"workflow_schema": "compliance"}), encoding="utf-8"
    )
    task_path = session_dir / "current-task.json"
    _ = task_path.write_text(json.dumps({"task_description": "x"}), encoding="utf-8")
    monkeypatch.setattr(
        "cortex.core.session_config.get_current_project_root", lambda: tmp_path
    )
    cfg = read_session_config()
    assert cfg.get("workflow_schema") == "compliance"
    assert cfg.get("task_description") == "x"


def test_validate_schema_fork_name() -> None:
    assert validate_schema_fork_name("") is not None
    assert validate_schema_fork_name("no_underscore") is not None
    assert validate_schema_fork_name("-bad") is not None
    assert validate_schema_fork_name("ok-1") is None
