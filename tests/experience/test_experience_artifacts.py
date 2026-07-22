"""Unit tests for artifact-reference persistence helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.experience.artifacts import (
    ARTIFACTS_DIR_RELATIVE_POSIX,
    ArtifactRefError,
    load_artifact,
    store_artifact,
    validate_artifact_ref,
)


def test_store_and_load_artifact_round_trip(tmp_path: Path) -> None:
    # Arrange
    content = '{"preflight_passed": true}'

    # Act
    ref = store_artifact(tmp_path, "quality-gate", content)

    # Assert
    assert ref.startswith(f"{ARTIFACTS_DIR_RELATIVE_POSIX}/quality-gate-")
    assert load_artifact(tmp_path, ref) == content


def test_store_artifact_unique_refs_for_same_name(tmp_path: Path) -> None:
    # Arrange / Act
    first = store_artifact(tmp_path, "gate", "a")
    second = store_artifact(tmp_path, "gate", "b")

    # Assert
    assert first != second
    assert load_artifact(tmp_path, first) == "a"
    assert load_artifact(tmp_path, second) == "b"


def test_store_artifact_sanitizes_hostile_names(tmp_path: Path) -> None:
    # Arrange / Act
    ref = store_artifact(tmp_path, "../../etc/passwd", "x")

    # Assert
    validate_artifact_ref(ref)
    assert ".." not in ref
    assert load_artifact(tmp_path, ref) == "x"


def test_store_artifact_empty_name_falls_back(tmp_path: Path) -> None:
    # Arrange / Act
    ref = store_artifact(tmp_path, "///", "y")

    # Assert
    assert f"{ARTIFACTS_DIR_RELATIVE_POSIX}/artifact-" in ref


def test_load_artifact_rejects_ref_outside_artifacts_dir(tmp_path: Path) -> None:
    # Arrange / Act / Assert
    with pytest.raises(ArtifactRefError):
        _ = load_artifact(tmp_path, ".cortex/memory-bank/roadmap.md")


def test_load_artifact_rejects_traversal_ref(tmp_path: Path) -> None:
    # Arrange / Act / Assert
    with pytest.raises(ArtifactRefError):
        _ = load_artifact(tmp_path, f"{ARTIFACTS_DIR_RELATIVE_POSIX}/../secret.json")
