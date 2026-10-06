"""Definitions and canonical directories for fileable artifacts."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from cortex.core.path_resolver import CortexResourceType, get_cortex_path


class ArtifactType(str, Enum):
    """Artifact classes that can be filed into Cortex."""

    REVIEW_REPORT = "review_report"
    SESSION_ANALYSIS = "session_analysis"
    ARCHITECTURAL_FINDING = "architectural_finding"
    QUERY_RESULT = "query_result"


class ArtifactTypeMetadata(BaseModel):
    """Metadata and conventions for a fileable artifact type."""

    model_config = ConfigDict(frozen=True)

    artifact_type: ArtifactType
    resource_type: CortexResourceType
    filename_template: str
    cross_reference_summary_template: str


ARTIFACT_TYPE_METADATA: dict[ArtifactType, ArtifactTypeMetadata] = {
    ArtifactType.REVIEW_REPORT: ArtifactTypeMetadata(
        artifact_type=ArtifactType.REVIEW_REPORT,
        resource_type=CortexResourceType.REVIEWS,
        filename_template="review-{slug}-{date}.md",
        cross_reference_summary_template=(
            "Review report for {title} ({date}); key findings summarized."
        ),
    ),
    ArtifactType.SESSION_ANALYSIS: ArtifactTypeMetadata(
        artifact_type=ArtifactType.SESSION_ANALYSIS,
        resource_type=CortexResourceType.ANALYSES,
        filename_template="analysis-{slug}-{date}.md",
        cross_reference_summary_template=(
            "Session analysis for {title} ({date}); decisions and follow-ups recorded."
        ),
    ),
    ArtifactType.ARCHITECTURAL_FINDING: ArtifactTypeMetadata(
        artifact_type=ArtifactType.ARCHITECTURAL_FINDING,
        resource_type=CortexResourceType.MEMORY_BANK,
        filename_template="finding-{slug}-{date}.md",
        cross_reference_summary_template=(
            "Architectural finding: {title} ({date}); constraints and recommendations."
        ),
    ),
    ArtifactType.QUERY_RESULT: ArtifactTypeMetadata(
        artifact_type=ArtifactType.QUERY_RESULT,
        resource_type=CortexResourceType.QUERIES,
        filename_template="query-{slug}-{date}.md",
        cross_reference_summary_template=(
            "Query result captured for {title} ({date}) for future reuse."
        ),
    ),
}


def get_artifact_type_metadata(artifact_type: ArtifactType) -> ArtifactTypeMetadata:
    """Return metadata for a supported artifact type."""

    return ARTIFACT_TYPE_METADATA[artifact_type]


def get_artifact_directory(project_root: Path, artifact_type: ArtifactType) -> Path:
    """Resolve an artifact destination without creating directories."""
    directory = get_cortex_path(
        project_root, get_artifact_type_metadata(artifact_type).resource_type
    )
    if artifact_type == ArtifactType.ARCHITECTURAL_FINDING:
        return directory / "findings"
    return directory


def get_artifact_directories(project_root: Path) -> tuple[Path, ...]:
    """Return only the canonical review, analysis, and query directories."""
    return tuple(
        get_artifact_directory(project_root, artifact_type)
        for artifact_type in (
            ArtifactType.REVIEW_REPORT,
            ArtifactType.SESSION_ANALYSIS,
            ArtifactType.QUERY_RESULT,
        )
    )
