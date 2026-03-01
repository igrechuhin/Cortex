"""Pydantic models for plan roadmap registration."""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MemoryBankFile


class RegisterPlanResult(BaseModel):
    """Result of registering a plan in roadmap."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    file_name: str = Field(
        description=f"File that was modified ({MemoryBankFile.ROADMAP})"
    )
    message: str = Field(description="Success or error message")
    line_inserted: int | None = Field(
        None, ge=1, description="Line number where entry was inserted"
    )
    section: str | None = Field(None, description="Section where entry was added")
    error: str | None = Field(None, description="Error message if status is error")
