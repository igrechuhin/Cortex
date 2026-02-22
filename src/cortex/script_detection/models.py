"""Pydantic models for script capture records."""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class PromotionStatus(str, Enum):
    """Status in the promotion pipeline."""

    PENDING = "pending"
    ANALYZED = "analyzed"
    PROMOTED = "promoted"
    REJECTED = "rejected"


class ScriptCaptureRecord(BaseModel):
    """A single captured session-generated script with metadata."""

    script_id: str = Field(..., description="Unique identifier for the capture")
    timestamp: str = Field(..., description="ISO timestamp when captured")
    task_description: str = Field(
        ..., description="Description of task that required the script"
    )
    script_path: str = Field(..., description="Relative or absolute path to the script")
    script_content: str = Field(..., description="Full script content")
    script_type: str = Field(
        default="python", description="Language: python, shell, javascript, etc."
    )
    purpose: str = Field(
        default="utility",
        description="Category: utility, analysis, transformation, etc.",
    )
    usage_context: str | None = Field(
        default=None,
        description="When and why this script was created",
    )
    promotion_status: PromotionStatus = Field(
        default=PromotionStatus.PENDING,
        description="Status in the promotion pipeline",
    )
    agent_session: str | None = Field(
        default=None, description="Session identifier if available"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Declared dependencies"
    )

    def to_storage_dict(self) -> dict[str, object]:
        """Serialize for JSON storage (Pydantic model_dump)."""
        return self.model_dump()

    @classmethod
    def from_storage_dict(cls, data: dict[str, object]) -> "ScriptCaptureRecord":
        """Deserialize from JSON storage."""
        return cls.model_validate(data)


def make_timestamp_utc() -> str:
    """Return current UTC time as ISO format string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
