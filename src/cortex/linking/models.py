"""
Pydantic models for linking module.

This module contains Pydantic models for link parsing, transclusion,
and link validation operations.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Base Model
# ============================================================================


class LinkingBaseModel(BaseModel):
    """Base model for linking types with strict validation."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )


# ============================================================================
# Link Parser Models
# ============================================================================


class MarkdownLinkModel(LinkingBaseModel):
    """Parsed markdown link."""

    text: str = Field(..., description="Link text")
    target: str = Field(..., description="Link target path or URL")
    line_number: int = Field(..., ge=1, description="Line number in source file")
    column: int = Field(default=1, ge=1, description="Column number")
    is_external: bool = Field(default=False, description="Whether link is external URL")


class TransclusionModel(LinkingBaseModel):
    """Parsed transclusion reference."""

    target: str = Field(..., description="Transclusion target path")
    line_number: int = Field(..., ge=1, description="Line number in source file")
    section: str | None = Field(default=None, description="Target section if specified")
    full_syntax: str = Field(..., description="Full transclusion syntax")


# ============================================================================
# Link Parser Internal Models (for parse_file result)
# ============================================================================


class ParsedFileLinks(LinkingBaseModel):
    """Result of parsing file for links and transclusions."""

    markdown_links: list[MarkdownLinkModel] = Field(
        default_factory=lambda: list[MarkdownLinkModel](),
        description="Parsed markdown links",
    )
    transclusions: list[TransclusionModel] = Field(
        default_factory=lambda: list[TransclusionModel](),
        description="Parsed transclusion references",
    )


# ============================================================================
# Unified Link Model (for validation)
# ============================================================================


class UnifiedLinkModel(LinkingBaseModel):
    """Unified link representation for validation.

    Represents either a markdown link or transclusion in a common format
    for validation purposes.
    """

    target: str = Field(..., description="Link target path")
    line: int = Field(..., ge=1, description="Line number in source file")
    type: Literal["markdown", "transclusion"] = Field(..., description="Link type")
    section: str | None = Field(default=None, description="Target section if specified")
    text: str | None = Field(
        default=None, description="Link text (markdown links only)"
    )


# ============================================================================
# Link Validation Internal Models
# ============================================================================


class BrokenLinkDetail(LinkingBaseModel):
    """Details about a broken link."""

    line: int = Field(..., ge=1, description="Line number")
    target: str = Field(..., description="Link target")
    section: str | None = Field(default=None, description="Section if specified")
    type: Literal["markdown", "transclusion"] = Field(..., description="Link type")
    error: str = Field(..., description="Error message")
    suggestion: str = Field(..., description="Suggested fix")


class LinkWarningDetail(LinkingBaseModel):
    """Details about a link warning (e.g., missing section)."""

    line: int = Field(..., ge=1, description="Line number")
    target: str = Field(..., description="Link target")
    section: str = Field(..., description="Missing section")
    type: Literal["markdown", "transclusion"] = Field(..., description="Link type")
    warning: str = Field(..., description="Warning message")
    available_sections: list[str] = Field(
        default_factory=list, description="Available sections in target file"
    )
    suggestion: str = Field(..., description="Suggested fix")


class FileValidationResult(LinkingBaseModel):
    """Result of validating links in a single file."""

    file: str = Field(..., description="File name")
    valid_links: list[UnifiedLinkModel] = Field(
        default_factory=lambda: list[UnifiedLinkModel](), description="Valid links"
    )
    broken_links: list[BrokenLinkDetail] = Field(
        default_factory=lambda: list[BrokenLinkDetail](), description="Broken links"
    )
    warnings: list[LinkWarningDetail] = Field(
        default_factory=lambda: list[LinkWarningDetail](), description="Warnings"
    )


class ValidationStats(LinkingBaseModel):
    """Statistics for batch link validation."""

    files_checked: int = Field(default=0, ge=0, description="Number of files checked")
    total_links: int = Field(default=0, ge=0, description="Total links found")
    valid_links_count: int = Field(default=0, ge=0, description="Number of valid links")
    all_broken_links: list[BrokenLinkDetail] = Field(
        default_factory=lambda: list[BrokenLinkDetail](),
        description="All broken links across files",
    )
    all_warnings: list[LinkWarningDetail] = Field(
        default_factory=lambda: list[LinkWarningDetail](),
        description="All warnings across files",
    )
    by_file: dict[str, FileValidationResult] = Field(
        default_factory=dict, description="Results by file name"
    )


class BatchValidationResult(LinkingBaseModel):
    """Result of validating all links in Memory Bank."""

    files_checked: int = Field(..., ge=0, description="Number of files checked")
    total_links: int = Field(..., ge=0, description="Total links found")
    valid_links: int = Field(..., ge=0, description="Number of valid links")
    broken_links: int = Field(..., ge=0, description="Number of broken links")
    warnings: int = Field(..., ge=0, description="Number of warnings")
    validation_errors: list[BrokenLinkDetail] = Field(
        default_factory=lambda: list[BrokenLinkDetail](),
        description="Broken link details with file info",
    )
    validation_warnings: list[LinkWarningDetail] = Field(
        default_factory=lambda: list[LinkWarningDetail](),
        description="Warning details with file info",
    )
    by_file: dict[str, FileValidationResult] = Field(
        default_factory=dict, description="Validation results by file"
    )


# ============================================================================
# Transclusion Options Model
# ============================================================================


class TransclusionOptions(LinkingBaseModel):
    """Parsed transclusion options."""

    lines: int | None = Field(
        default=None, ge=1, description="Number of lines to include"
    )
    recursive: bool = Field(
        default=True, description="Whether to resolve nested transclusions"
    )


# ============================================================================
# Link Count Model
# ============================================================================


class LinkCountResult(LinkingBaseModel):
    """Count of different types of links."""

    markdown_links: int = Field(default=0, ge=0, description="Number of markdown links")
    transclusions: int = Field(default=0, ge=0, description="Number of transclusions")
    total: int = Field(default=0, ge=0, description="Total link count")
    unique_files: int = Field(
        default=0, ge=0, description="Number of unique files referenced"
    )


# ============================================================================
# Link Validation Models
# ============================================================================


class BrokenLinkInfo(LinkingBaseModel):
    """Information about a broken link."""

    target: str = Field(..., description="Link target")
    line_number: int = Field(..., ge=1, description="Line number")
    link_type: Literal["markdown", "transclusion"] = Field(
        ..., description="Type of link"
    )
    error: str = Field(..., description="Error description")
    suggestion: str | None = Field(default=None, description="Suggested fix")


class LinkValidationResult(LinkingBaseModel):
    """Result of validating links in a file."""

    valid: bool = Field(..., description="Whether all links are valid")
    total_links: int = Field(default=0, ge=0, description="Total links found")
    valid_links: int = Field(default=0, ge=0, description="Number of valid links")
    broken_links: list[BrokenLinkInfo] = Field(
        default_factory=lambda: list[BrokenLinkInfo](),
        description="Broken links found",
    )
    broken_transclusions: list[BrokenLinkInfo] = Field(
        default_factory=lambda: list[BrokenLinkInfo](),
        description="Broken transclusions found",
    )
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


# ============================================================================
# Transclusion Resolution Models
# ============================================================================


class TransclusionResolutionResult(LinkingBaseModel):
    """Result of resolving transclusions in content."""

    resolved_content: str = Field(
        ..., description="Content with transclusions resolved"
    )
    transclusions_resolved: int = Field(
        default=0, ge=0, description="Number of transclusions resolved"
    )
    files_included: list[str] = Field(
        default_factory=list, description="Files that were included"
    )
    cache_hits: int = Field(default=0, ge=0, description="Number of cache hits")
    errors: list[str] = Field(
        default_factory=list, description="Errors during resolution"
    )
