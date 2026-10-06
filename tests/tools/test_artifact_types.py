"""Tests for fileable artifact metadata and canonical directory resolution."""

from pathlib import Path

import pytest

from cortex.core.path_resolver import CortexResourceType
from cortex.tools.artifacts.artifact_types import (
    ARTIFACT_TYPE_METADATA,
    ArtifactType,
    get_artifact_directories,
    get_artifact_directory,
    get_artifact_type_metadata,
)


def test_all_artifact_types_have_metadata_entries() -> None:
    assert set(ARTIFACT_TYPE_METADATA) == set(ArtifactType)


def test_review_report_metadata_matches_plan_conventions() -> None:
    metadata = get_artifact_type_metadata(ArtifactType.REVIEW_REPORT)
    assert metadata.resource_type == CortexResourceType.REVIEWS
    assert metadata.filename_template == "review-{slug}-{date}.md"
    assert "{title}" in metadata.cross_reference_summary_template
    assert "{date}" in metadata.cross_reference_summary_template


def test_session_analysis_metadata_targets_analyses_directory() -> None:
    metadata = get_artifact_type_metadata(ArtifactType.SESSION_ANALYSIS)
    assert metadata.resource_type == CortexResourceType.ANALYSES
    assert metadata.filename_template.startswith("analysis-")


@pytest.mark.parametrize(
    ("artifact_type", "relative_directory"),
    [
        (ArtifactType.REVIEW_REPORT, "reviews"),
        (ArtifactType.SESSION_ANALYSIS, "analyses"),
        (ArtifactType.QUERY_RESULT, "queries"),
        (ArtifactType.ARCHITECTURAL_FINDING, "memory-bank/findings"),
    ],
)
def test_artifact_directory_resolves_without_creating_paths(
    tmp_path: Path, artifact_type: ArtifactType, relative_directory: str
) -> None:
    assert get_artifact_directory(tmp_path, artifact_type) == (
        tmp_path / ".cortex" / relative_directory
    )
    assert not (tmp_path / ".cortex").exists()


def test_artifact_directories_contains_exactly_three_canonical_report_dirs(
    tmp_path: Path,
) -> None:
    assert get_artifact_directories(tmp_path) == tuple(
        tmp_path / ".cortex" / directory
        for directory in ("reviews", "analyses", "queries")
    )
    assert not (tmp_path / ".cortex").exists()
