"""Validation configuration and schema-related models."""

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from cortex.core.constants import (
    DEFAULT_TOKEN_BUDGET,
    MIN_SECTION_LENGTH_CHARS,
    QUALITY_WEIGHT_COMPLETENESS,
    QUALITY_WEIGHT_CONSISTENCY,
    QUALITY_WEIGHT_EFFICIENCY,
    QUALITY_WEIGHT_FRESHNESS,
    QUALITY_WEIGHT_STRUCTURE,
    SIMILARITY_THRESHOLD_DUPLICATE,
)


class TokenBudgetConfigModel(BaseModel):
    """Token budget configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    max_total_tokens: int = Field(
        default=DEFAULT_TOKEN_BUDGET,
        ge=1,
        description="Maximum total tokens allowed",
    )
    warn_at_percentage: float = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
        description="Warning threshold percentage (0-100)",
    )
    per_file_max: int = Field(
        default=15000,
        ge=1,
        description="Maximum tokens per file",
    )
    per_file_warn: int = Field(
        default=12000,
        ge=1,
        description="Warning threshold per file",
    )


class DuplicationConfigModel(BaseModel):
    """Duplication detection configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = Field(
        default=True,
        description="Whether duplication detection is enabled",
    )
    threshold: float = Field(
        default=SIMILARITY_THRESHOLD_DUPLICATE,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for duplicate detection (0.0-1.0)",
    )
    min_length: int = Field(
        default=MIN_SECTION_LENGTH_CHARS,
        ge=0,
        description="Minimum section length in characters",
    )
    suggest_transclusion: bool = Field(
        default=True,
        description="Whether to suggest transclusion for duplicates",
    )


class FileSchemaModel(BaseModel):
    """Schema definition for a single Memory Bank file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    required_sections: list[str] = Field(
        default_factory=list,
        description="Required sections for the file",
    )
    recommended_sections: list[str] = Field(
        default_factory=list,
        description="Recommended sections for the file",
    )
    heading_level: int = Field(
        default=2,
        ge=1,
        le=6,
        description="Expected heading level",
    )
    max_nesting: int = Field(
        default=3,
        ge=1,
        le=6,
        description="Maximum nesting depth",
    )


class SchemasConfigModel(BaseModel):
    """Schema validation configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enforce_required_sections: bool = Field(
        default=True,
        description="Whether to enforce required sections",
    )
    enforce_section_order: bool = Field(
        default=False,
        description="Whether to enforce section order",
    )
    custom_schemas: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Custom schema definitions by file name",
    )


class QualityWeightsModel(BaseModel):
    """Quality score weight configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    completeness: float = Field(
        default=QUALITY_WEIGHT_COMPLETENESS,
        ge=0.0,
        le=1.0,
        description="Weight for completeness (0.0-1.0)",
    )
    consistency: float = Field(
        default=QUALITY_WEIGHT_CONSISTENCY,
        ge=0.0,
        le=1.0,
        description="Weight for consistency (0.0-1.0)",
    )
    freshness: float = Field(
        default=QUALITY_WEIGHT_FRESHNESS,
        ge=0.0,
        le=1.0,
        description="Weight for freshness (0.0-1.0)",
    )
    structure: float = Field(
        default=QUALITY_WEIGHT_STRUCTURE,
        ge=0.0,
        le=1.0,
        description="Weight for structure (0.0-1.0)",
    )
    token_efficiency: float = Field(
        default=QUALITY_WEIGHT_EFFICIENCY,
        ge=0.0,
        le=1.0,
        description="Weight for token efficiency (0.0-1.0)",
    )


class QualityConfigModel(BaseModel):
    """Quality metrics configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    minimum_score: float = Field(
        default=70.0,
        ge=0.0,
        le=100.0,
        description="Minimum acceptable quality score",
    )
    fail_below: float = Field(
        default=50.0,
        ge=0.0,
        le=100.0,
        description="Score below which validation fails",
    )
    weights: QualityWeightsModel = Field(
        default_factory=QualityWeightsModel,
        description="Quality score weights",
    )


class ValidationConfigModel(BaseModel):
    """Complete validation configuration."""

    # NOTE: Allow extra keys so users/tests can store experimental settings.
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    enabled: str | StrictBool = Field(
        default=True,
        description=(
            "Whether validation is enabled (may be invalid when loaded "
            "from user config)"
        ),
    )
    auto_validate_on_write: bool = Field(
        default=True,
        description="Whether to auto-validate on write",
    )
    strict_mode: bool = Field(
        default=False,
        description="Whether to use strict validation mode",
    )
    token_budget: TokenBudgetConfigModel = Field(
        default_factory=TokenBudgetConfigModel,
        description="Token budget configuration",
    )
    duplication: DuplicationConfigModel = Field(
        default_factory=DuplicationConfigModel,
        description="Duplication detection configuration",
    )
    schemas: SchemasConfigModel = Field(
        default_factory=SchemasConfigModel,
        description="Schema validation configuration",
    )
    quality: QualityConfigModel = Field(
        default_factory=QualityConfigModel,
        description="Quality metrics configuration",
    )
