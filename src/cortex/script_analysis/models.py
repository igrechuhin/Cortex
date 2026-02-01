"""Pydantic models for script analysis results."""

from pydantic import BaseModel, Field


class UseCaseExtraction(BaseModel):
    """Extracted use case from a captured script."""

    use_case_label: str = Field(
        ..., description="Short label for the use case (e.g. 'format Python files')"
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords inferred from content and context",
    )


class GapAnalysis(BaseModel):
    """Gap analysis comparing a script to existing tools/scripts."""

    existing_tool_names: list[str] = Field(
        default_factory=list,
        description="Existing MCP tools that may overlap",
    )
    existing_script_names: list[str] = Field(
        default_factory=list,
        description="Existing Synapse scripts that may overlap",
    )
    gap_reason: str = Field(
        ...,
        description="Why this script represents a gap (or that it is covered)",
    )
    is_gap: bool = Field(
        ...,
        description="True if no existing tool/script adequately covers the use case",
    )


class SimilarityPair(BaseModel):
    """Pair of script IDs with a similarity score."""

    script_id_1: str = Field(..., description="First script capture ID")
    script_id_2: str = Field(..., description="Second script capture ID")
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity between 0 and 1",
    )


class ScriptAnalysisResult(BaseModel):
    """Full analysis result for a single captured script."""

    script_id: str = Field(..., description="Script capture ID")
    use_case: UseCaseExtraction = Field(
        ...,
        description="Extracted use case",
    )
    gap: GapAnalysis = Field(..., description="Gap analysis vs existing tooling")
    reusability_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Estimated reusability (0-1)",
    )
    promotion_potential: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Overall promotion potential (0-1)",
    )
