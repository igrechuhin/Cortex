"""
Base Pydantic models and shared types for MCP tool return types.

This module provides StrictBaseModel, ToolResultBase, ErrorResultBase, and
ConfigValue type aliases. All domain-specific model modules (context_models,
validation_result_models, refactoring_result_models, session.models,
evaluation_models) import from here to avoid circular imports.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import JsonDict


class ToolResultStatus(str, Enum):
    """Status for tool result responses."""

    SUCCESS = "success"
    ERROR = "error"


# ConfigValue type for configuration values - supports primitive and nested structures.
# This type union is designed to support the dynamic nature of configuration systems
# while maintaining some type safety.
ConfigValuePrimitive = str | int | float | bool | None
ConfigValueList = list[str] | list[int] | list[float] | list[bool]
ConfigValueDict = JsonDict
ConfigValue = ConfigValuePrimitive | ConfigValueList | ConfigValueDict


class StrictBaseModel(BaseModel):
    """Strict base model with maximum Pydantic validation.

    All models should inherit from this or ToolResultBase to ensure:
    - No extra fields allowed (extra = "forbid")
    - Validation on assignment (validate_assignment = True)
    - Validation of default values (validate_default = True)
    - Strict type checking (strict = True)
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
        strict=True,
    )


class ToolResultBase(StrictBaseModel):
    """Base class for all tool results with common status and error handling."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
        use_enum_values=True,
        strict=True,
        json_schema_extra={
            "examples": [
                {"status": "success"},
                {"status": "error", "error": "Operation failed"},
            ]
        },
    )


class ErrorResultBase(ToolResultBase):
    """Base class for error responses."""

    status: ToolResultStatus = Field(default=ToolResultStatus.ERROR)
    error: str = Field(..., min_length=1, description="Error message")
    error_type: str | None = Field(
        default=None, description="Type/class name of the error"
    )
