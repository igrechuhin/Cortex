"""Pydantic models for usage analytics (Phase 29, Phase 50).

Extracted from usage_analytics.py for Phase 9.1 file size compliance.
"""

from pydantic import BaseModel, ConfigDict

from cortex.core.pydantic_extra import EXTRA_ALLOW


class UsageEventPayload(BaseModel):
    """Looser wire model for usage events returned to external callers.

    This sits at the communication boundary (JSON returned by the MCP tool).
    Internally we still use the strict `ToolUsageEvent` model; this payload
    only enforces a stable subset of fields and allows additional data via
    Pydantic's ``extra='allow'`` configuration.
    """

    model_config = ConfigDict(extra=EXTRA_ALLOW)

    id: str
    tool_name: str | None = None
    result_summary: str | None = None


class UsageEventsResponse(BaseModel):
    """Pydantic response model for usage events lookup."""

    status: str
    project_root: str
    events: list[UsageEventPayload]
    missing_ids: list[str]


class UsageSearchResultEntry(BaseModel):
    """Pydantic model for compact search result entries."""

    id: str
    tool_name: str
    timestamp: str
    duration_ms: float
    success: bool
    error_type: str | None
    handler_kind: str


class SearchUsageResponse(BaseModel):
    """Pydantic response model for search_usage results."""

    status: str
    project_root: str
    results: list[UsageSearchResultEntry]
    total: int


class UsageTimelineEntry(BaseModel):
    """Pydantic model for compact usage timeline entries.

    NOTE: This model is part of the canonical Pydantic v2 usage pattern for
    usage analytics. Its schema is documented in the tech context Pydantic v2
    section and the Python Pydantic v2 rule; keep fields stable for external
    callers and update docs/tests together with any changes.
    """

    id: str
    tool_name: str
    timestamp: str
    duration_ms: float
    success: bool
    error_type: str | None
    handler_kind: str
