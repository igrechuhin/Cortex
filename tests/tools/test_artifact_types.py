"""Tests for fileable artifact type metadata mapping."""

from cortex.tools.artifacts.artifact_types import (
    ARTIFACT_TYPE_METADATA,
    ArtifactType,
    MemoryBankArtifactStorageSubdir,
    get_artifact_type_metadata,
)


def test_all_artifact_types_have_metadata_entries() -> None:
    for artifact_type in ArtifactType:
        assert artifact_type in ARTIFACT_TYPE_METADATA


def test_review_report_metadata_matches_plan_conventions() -> None:
    metadata = get_artifact_type_metadata(ArtifactType.REVIEW_REPORT)

    assert metadata.storage_subdir == MemoryBankArtifactStorageSubdir.REVIEWS
    assert metadata.filename_template == "review-{slug}-{date}.md"
    assert "{title}" in metadata.cross_reference_summary_template
    assert "{date}" in metadata.cross_reference_summary_template


def test_session_analysis_metadata_targets_analyses_directory() -> None:
    metadata = get_artifact_type_metadata(ArtifactType.SESSION_ANALYSIS)
    assert metadata.storage_subdir == MemoryBankArtifactStorageSubdir.ANALYSES
    assert metadata.filename_template.startswith("analysis-")
