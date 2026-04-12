"""Definitions for fileable memory-bank artifact types."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class ArtifactType(str, Enum):
    """Artifact classes that can be filed into the memory bank."""

    REVIEW_REPORT = "review_report"
    SESSION_ANALYSIS = "session_analysis"
    ARCHITECTURAL_FINDING = "architectural_finding"
    QUERY_RESULT = "query_result"


class MemoryBankArtifactStorageSubdir(str, Enum):
    """Subdirectory under ``.cortex/memory-bank`` for filed artifact markdown."""

    REVIEWS = "reviews"
    ANALYSES = "analyses"
    FINDINGS = "findings"
    QUERIES = "queries"


class ArtifactTypeMetadata(BaseModel):
    """Metadata and conventions for a fileable artifact type."""

    model_config = ConfigDict(frozen=True)

    artifact_type: ArtifactType
    storage_subdir: MemoryBankArtifactStorageSubdir
    filename_template: str
    cross_reference_summary_template: str


ARTIFACT_TYPE_METADATA: dict[ArtifactType, ArtifactTypeMetadata] = {
    ArtifactType.REVIEW_REPORT: ArtifactTypeMetadata(
        artifact_type=ArtifactType.REVIEW_REPORT,
        storage_subdir=MemoryBankArtifactStorageSubdir.REVIEWS,
        filename_template="review-{slug}-{date}.md",
        cross_reference_summary_template=(
            "Review report for {title} ({date}); key findings summarized."
        ),
    ),
    ArtifactType.SESSION_ANALYSIS: ArtifactTypeMetadata(
        artifact_type=ArtifactType.SESSION_ANALYSIS,
        storage_subdir=MemoryBankArtifactStorageSubdir.ANALYSES,
        filename_template="analysis-{slug}-{date}.md",
        cross_reference_summary_template=(
            "Session analysis for {title} ({date}); decisions and follow-ups recorded."
        ),
    ),
    ArtifactType.ARCHITECTURAL_FINDING: ArtifactTypeMetadata(
        artifact_type=ArtifactType.ARCHITECTURAL_FINDING,
        storage_subdir=MemoryBankArtifactStorageSubdir.FINDINGS,
        filename_template="finding-{slug}-{date}.md",
        cross_reference_summary_template=(
            "Architectural finding: {title} ({date}); constraints and recommendations."
        ),
    ),
    ArtifactType.QUERY_RESULT: ArtifactTypeMetadata(
        artifact_type=ArtifactType.QUERY_RESULT,
        storage_subdir=MemoryBankArtifactStorageSubdir.QUERIES,
        filename_template="query-{slug}-{date}.md",
        cross_reference_summary_template=(
            "Query result captured for {title} ({date}) for future reuse."
        ),
    ),
}


def get_artifact_type_metadata(artifact_type: ArtifactType) -> ArtifactTypeMetadata:
    """Return metadata for a supported artifact type."""

    return ARTIFACT_TYPE_METADATA[artifact_type]
