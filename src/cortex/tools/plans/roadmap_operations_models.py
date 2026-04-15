"""
Models for roadmap and memory-bank write operations (add/remove roadmap entry,
remove section, append progress, append activeContext).
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from cortex.core.constants import MemoryBankFile
from cortex.core.models import OperationStatus
from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.tools.models_base import StrictBaseModel


class AddRoadmapEntryResult(StrictBaseModel):
    """Result of adding a roadmap entry."""

    status: OperationStatus = Field(description="Operation status")
    file_name: str = Field(description="File that was modified")
    message: str = Field(description="Success or error message")
    line_inserted: int | None = Field(
        None, ge=1, description="Line number where entry was inserted"
    )
    section: str | None = Field(None, description="Section where entry was added")
    error: str | None = Field(None, description="Error message if status is error")

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)


class RemoveRoadmapEntryResult(StrictBaseModel):
    """Result of removing a single roadmap entry (bullet line)."""

    status: OperationStatus = Field(description="Operation status")
    file_name: str = Field(description="File that was modified")
    message: str = Field(description="Success or error message")
    line_removed: int | None = Field(
        None, ge=1, description="1-based line number that was removed"
    )
    error: str | None = Field(None, description="Error message if status is error")

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)


class RemoveRoadmapSectionResult(StrictBaseModel):
    """Result of removing a roadmap section by heading."""

    status: OperationStatus = Field(description="Operation status")
    file_name: str = Field(description="File that was modified")
    message: str = Field(description="Success or error message")
    section_heading: str | None = Field(
        None, description="Heading text that was matched and removed"
    )
    lines_removed: int | None = Field(
        None, ge=0, description="Number of lines removed (header and content)"
    )
    error: str | None = Field(None, description="Error message if status is error")

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)


class AppendProgressEntryResult(StrictBaseModel):
    """Result of appending a single entry to progress.md."""

    status: OperationStatus = Field(description="Operation status")
    file_name: str = Field(
        description=f"File that was modified ({MemoryBankFile.PROGRESS})"
    )
    message: str = Field(description="Success or error message")
    line_inserted: int | None = Field(
        None, ge=1, description="1-based line number where entry was inserted"
    )
    error: str | None = Field(None, description="Error message if status is error")

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)


class AppendActiveContextEntryResult(StrictBaseModel):
    """Result of appending a single completed entry to activeContext.md."""

    status: OperationStatus = Field(description="Operation status")
    file_name: str = Field(
        description=f"File that was modified ({MemoryBankFile.ACTIVE_CONTEXT})"
    )
    message: str = Field(description="Success or error message")
    line_inserted: int | None = Field(
        None, ge=1, description="1-based line number where entry was inserted"
    )
    error: str | None = Field(None, description="Error message if status is error")

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)
