"""
Models for parse_file_links tool results.
"""

from __future__ import annotations

from pydantic import Field

from .models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)


class LinkLocation(StrictBaseModel):
    """Location of a link in a file."""

    line: int
    column: int


class LinkSummary(StrictBaseModel):
    """Summary statistics for parsed links."""

    markdown_links: int
    transclusions: int
    total: int
    unique_files: int


class ParsedMarkdownLink(StrictBaseModel):
    """Parsed markdown link information."""

    text: str = Field(..., description="Link text")
    target: str = Field(..., description="Link target path or URL")
    line: int = Field(..., ge=1, description="Line number")
    column: int = Field(default=1, ge=1, description="Column number")
    is_external: bool = Field(default=False, description="Whether link is external")


class ParsedTransclusion(StrictBaseModel):
    """Parsed transclusion reference."""

    target: str = Field(..., description="Transclusion target path")
    line: int = Field(..., ge=1, description="Line number")
    section: str | None = Field(default=None, description="Target section if specified")
    full_syntax: str = Field(..., description="Full transclusion syntax")


class ParseFileLinksResult(ToolResultBase):
    """Result of parse_file_links operation."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    file: str
    summary: LinkSummary
    markdown_links: list[ParsedMarkdownLink] = Field(
        default_factory=lambda: list[ParsedMarkdownLink]()
    )
    transclusions: list[ParsedTransclusion] = Field(
        default_factory=lambda: list[ParsedTransclusion]()
    )


class ParseFileLinksErrorResult(ErrorResultBase):
    """Error result for parse_file_links operations."""

    file: str | None = None


ParseFileLinksResultUnion = ParseFileLinksResult | ParseFileLinksErrorResult
