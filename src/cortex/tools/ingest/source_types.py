"""Source typing for memory-bank ingest (external content staging)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SourceType(StrEnum):
    """How raw content was obtained before ingest."""

    MARKDOWN_FILE = "markdown_file"
    TEXT = "text"
    URL = "url"


class IngestSource(BaseModel):
    """Validated ingest payload used by the ingest tool and tests."""

    model_config = ConfigDict(extra="forbid")

    type: SourceType = Field(description="Source classification")
    content: str = Field(min_length=1, description="Raw source body")
    title: str = Field(
        min_length=1, description="Human-readable title for slugging and summaries"
    )
    tags: list[str] | None = Field(
        default=None, description="Optional tags for downstream prompts"
    )
