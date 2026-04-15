"""Pydantic models for plan roadmap registration."""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MemoryBankFile
from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.tools.models_base import ToolResultStatus


class RegisterPlanResult(BaseModel):
    """Result of registering a plan in roadmap."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID, validate_assignment=True, use_enum_values=True
    )

    status: ToolResultStatus = Field(description="Operation status")
    file_name: str = Field(
        description=f"File that was modified ({MemoryBankFile.ROADMAP})"
    )
    message: str = Field(description="Success or error message")
    line_inserted: int | None = Field(
        None, ge=1, description="Line number where entry was inserted"
    )
    section: str | None = Field(None, description="Section where entry was added")
    error: str | None = Field(None, description="Error message if status is error")
    parallel_steps_count: int | None = Field(
        default=None,
        ge=0,
        description="Parallel [P] steps when the plan file was validated (else null)",
    )
    sequential_steps_count: int | None = Field(
        default=None,
        ge=0,
        description="Sequential steps when the plan file was validated (else null)",
    )
