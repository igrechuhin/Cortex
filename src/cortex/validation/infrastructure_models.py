"""Infrastructure validation models.

These models were originally defined in `validation.models` and are now
grouped here by domain (infrastructure) as part of Phase 81.
"""

from enum import Enum
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import JsonValue, ModelDict, OperationStatus, RiskLevel


class CheckTypeInfrastructure(str, Enum):
    """Check type for infrastructure validation."""

    INFRASTRUCTURE = "infrastructure"


class JobStepModel(BaseModel):
    """A single step in a CI/CD job configuration.

    This model replaces `ModelDict` for job step definitions.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    name: str = Field(..., description="Step name")
    run: str | None = Field(default=None, description="Command to run")
    uses: str | None = Field(default=None, description="Action to use")


class JobConfigModel(BaseModel):
    """CI/CD job configuration.

    This model replaces `ModelDict` for job configuration.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    name: str | None = Field(default=None, description="Job name")
    steps: list[JobStepModel] = Field(
        default_factory=lambda: list[JobStepModel](),
        description="Job steps",
    )

    @classmethod
    def from_dict(cls, data: ModelDict) -> "JobConfigModel":
        """Create JobConfigModel from a dictionary.

        Args:
            data: Dictionary with job configuration

        Returns:
            JobConfigModel instance
        """
        steps_data_raw = data.get("steps", [])
        steps_data: list[JsonValue] = (
            cast(list[JsonValue], steps_data_raw)
            if isinstance(steps_data_raw, list)
            else []
        )
        steps = [
            JobStepModel.model_validate(step)
            for step in steps_data
            if isinstance(step, dict)
        ]
        return cls.model_validate({**data, "steps": steps})


class InfrastructureIssueModel(BaseModel):
    """Infrastructure validation issue."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    type: str = Field(description="Issue type")
    severity: RiskLevel = Field(description="Issue severity")
    description: str = Field(description="Issue description")
    location: str = Field(description="Issue location")
    suggestion: str = Field(description="Suggested fix")
    ci_check: str | None = Field(None, description="Related CI check")
    missing_in_commit: bool = Field(
        description="Whether missing in commit prompt",
    )


class InfrastructureValidationResultModel(BaseModel):
    """Infrastructure validation result."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: OperationStatus = Field(description="Validation status")
    check_type: CheckTypeInfrastructure = Field(description="Type of check")
    checks_performed: dict[str, bool] = Field(
        default_factory=dict,
        description="Checks performed and results",
    )
    issues_found: list[InfrastructureIssueModel] = Field(
        default_factory=lambda: list[InfrastructureIssueModel](),
        description="Issues found",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations",
    )


__all__ = [
    "CheckTypeInfrastructure",
    "JobConfigModel",
    "JobStepModel",
    "InfrastructureIssueModel",
    "InfrastructureValidationResultModel",
]
