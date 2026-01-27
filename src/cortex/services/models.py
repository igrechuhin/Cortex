"""
Pydantic models for services module.

This module contains Pydantic models for service operations,
migrated from legacy dict-based shapes for better validation.
"""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import DictLikeModel

# ============================================================================
# Base Model
# ============================================================================


class ServiceBaseModel(BaseModel):
    """Base model for service types with strict validation."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )


# ============================================================================
# Language Detection Models (from language_detector.py)
# ============================================================================


class LanguageInfoModel(DictLikeModel):
    """Language detection result."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )

    language: str = Field(..., description="Detected language")
    test_framework: str | None = Field(None, description="Test framework if detected")
    formatter: str | None = Field(None, description="Code formatter if detected")
    linter: str | None = Field(None, description="Linter if detected")
    type_checker: str | None = Field(None, description="Type checker if detected")
    build_tool: str | None = Field(None, description="Build tool if detected")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Detection confidence 0-1"
    )


# ============================================================================
# Framework Adapter Models (from framework_adapters/base.py)
# ============================================================================


class CheckResultModel(DictLikeModel):
    """Result of a single check operation."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )

    check_type: str = Field(..., description="Type of check performed")
    success: bool = Field(..., description="Whether check succeeded")
    output: str = Field(..., description="Check output")
    errors: list[str] = Field(default_factory=list, description="Error messages")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    files_modified: list[str] = Field(
        default_factory=list, description="Files modified"
    )


class TestResultModel(ServiceBaseModel):
    """Test execution result."""

    success: bool = Field(..., description="Whether tests passed")
    tests_run: int = Field(..., ge=0, description="Number of tests run")
    tests_passed: int = Field(..., ge=0, description="Number of tests passed")
    tests_failed: int = Field(..., ge=0, description="Number of tests failed")
    pass_rate: float = Field(..., ge=0.0, le=1.0, description="Pass rate 0-1")
    coverage: float | None = Field(None, ge=0.0, le=1.0, description="Coverage 0-1")
    output: str = Field(..., description="Test output")
    errors: list[str] = Field(default_factory=list, description="Error messages")
