"""
Models for fix_markdown_lint tool results.
"""

from __future__ import annotations

from pydantic import Field

from .models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)


class FileResult(StrictBaseModel):
    """Result for a single file processing."""

    file: str
    fixed: bool
    errors: list[str] = Field(default_factory=list)
    error_message: str | None = None


class FixMarkdownLintResult(ToolResultBase):
    """Result of markdown lint fixing operation."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    files_processed: int
    files_fixed: int
    files_unchanged: int
    files_with_errors: int
    results: list[FileResult] = Field(default_factory=lambda: list[FileResult]())
    error_message: str | None = None


class FixMarkdownLintErrorResult(ErrorResultBase):
    """Error result for fix_markdown_lint operations."""


FixMarkdownLintResultUnion = FixMarkdownLintResult | FixMarkdownLintErrorResult
