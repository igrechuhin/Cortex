"""Link validation and link graph result models for validate_links and get_link_graph tools."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BeforeValidator, Field

from cortex.tools.models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)
from cortex.tools.validation.result_models import (
    LinkGraphFormat,
    ValidateLinksMode,
)


def _coerce_str_enum[E: Enum](v: str | Enum, enum_cls: type[E]) -> E:
    """Coerce string to enum for Pydantic."""
    if isinstance(v, enum_cls):
        return v
    return enum_cls(v)


_StatusField = Annotated[
    ToolResultStatus,
    BeforeValidator(lambda x: _coerce_str_enum(x, ToolResultStatus)),
]
_LinksModeField = Annotated[
    ValidateLinksMode,
    BeforeValidator(lambda x: _coerce_str_enum(x, ValidateLinksMode)),
]
_LinkGraphFormatField = Annotated[
    LinkGraphFormat,
    BeforeValidator(lambda x: _coerce_str_enum(x, LinkGraphFormat)),
]


class LinkValidationError(StrictBaseModel):
    """Validation error for a broken link."""

    file: str
    line: int
    link_type: str
    target: str
    error: str
    suggestion: str
    section: str | None = None


class LinkValidationWarning(StrictBaseModel):
    """Validation warning for a non-critical issue."""

    file: str
    line: int
    link_type: str
    target: str
    warning: str
    suggestion: str
    section: str | None = None
    available_sections: list[str] | None = None


class ValidateLinksSingleFileResult(ToolResultBase):
    """Result of validate_links operation for single file (success)."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    mode: _LinksModeField = Field(default=ValidateLinksMode.SINGLE_FILE)
    file: str
    files_checked: int = 1
    total_links: int
    valid_links: int
    broken_links: int
    warnings: int
    validation_errors: list[LinkValidationError]
    validation_warnings: list[LinkValidationWarning]


class ValidateLinksAllFilesResult(ToolResultBase):
    """Result of validate_links operation for all files (success)."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    mode: _LinksModeField = Field(default=ValidateLinksMode.ALL_FILES)
    files_checked: int
    total_links: int
    valid_links: int
    broken_links: int
    warnings: int
    validation_errors: list[LinkValidationError]
    validation_warnings: list[LinkValidationWarning]
    report: str


class ValidateLinksErrorResult(ErrorResultBase):
    """Error result for validate_links operations."""

    mode: str | None = None
    files_checked: int | None = None


ValidateLinksResultUnion = (
    ValidateLinksSingleFileResult
    | ValidateLinksAllFilesResult
    | ValidateLinksErrorResult
)


class LinkGraphNode(StrictBaseModel):
    """Node in the link graph."""

    id: str
    type: str = "file"
    exists: bool


class LinkGraphEdge(StrictBaseModel):
    """Edge in the link graph."""

    source: str
    target: str
    type: str
    line: int


class LinkGraphSummary(StrictBaseModel):
    """Summary statistics for the link graph."""

    total_files: int
    total_links: int
    reference_links: int
    transclusion_links: int
    has_cycles: bool
    cycle_count: int


class GetLinkGraphJsonResult(ToolResultBase):
    """Result of get_link_graph operation in JSON format (success)."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    format: _LinkGraphFormatField = Field(default=LinkGraphFormat.JSON)
    nodes: list[LinkGraphNode]
    edges: list[LinkGraphEdge]
    cycles: list[list[str]]
    summary: LinkGraphSummary


class GetLinkGraphMermaidResult(ToolResultBase):
    """Result of get_link_graph operation in Mermaid format (success)."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    format: _LinkGraphFormatField = Field(default=LinkGraphFormat.MERMAID)
    diagram: str
    cycles: list[list[str]]


class GetLinkGraphErrorResult(ErrorResultBase):
    """Error result for get_link_graph operations."""

    format: str | None = None


GetLinkGraphResultUnion = (
    GetLinkGraphJsonResult | GetLinkGraphMermaidResult | GetLinkGraphErrorResult
)
