"""Private models for the session_start tool."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from cortex.core.models import DictLikeModel
from cortex.tools.session.models import (
    ConcurrentSession,
    GitStatusSummary,
    SessionHandoff,
    SessionHealthSummary,
    WikiStatusSummary,
)


class SessionBriefContextKwargs(DictLikeModel):
    """Typed kwargs for building SessionBrief from suggestions and context."""

    project_name: str
    current_focus: str
    recent_completed: list[str]
    next_work_item: str | None
    next_work_plan_path: str | None
    health: SessionHealthSummary
    git_status: GitStatusSummary | None
    last_handoff: SessionHandoff | None
    concurrent_sessions: list[ConcurrentSession]
    locked_tasks: list[str]
    mcp_healthy: bool
    mcp_health_message: str | None
    gate_feedback_summary: str | None
    clarification_summary: str | None = None
    constitution_notice: str | None = None
    workflow_schema: str = "default"
    workflow_schema_description: str = ""
    workflow_phases: list[str] = []
    plan_graph_summary: str | None = None
    plan_graph_ascii_edges: str | None = None
    wiki_status: WikiStatusSummary = Field(default_factory=WikiStatusSummary)
    memory_type_counts: dict[str, int] = Field(default_factory=dict)


class BriefInputs(DictLikeModel):
    """Input bundle for _compute_suggestions_and_create_brief."""

    project_name: str
    current_focus: str
    recent_completed: list[str]
    next_work_item: str | None
    next_work_plan_path: str | None
    health: SessionHealthSummary
    git_status: GitStatusSummary | None
    last_handoff: SessionHandoff | None
    concurrent_sessions: list[ConcurrentSession]
    locked_tasks: list[str]
    mcp_healthy: bool
    mcp_health_message: str | None
    gate_feedback_summary: str | None
    clarification_summary: str | None = None
    constitution_notice: str | None = None
    workflow_schema: str = "default"
    workflow_schema_description: str = ""
    workflow_phases: list[str] = []
    workflow_schema_warning: str | None = None
    plan_graph_summary: str | None = None
    plan_graph_ascii_edges: str | None = None
    wiki_status: WikiStatusSummary = Field(default_factory=WikiStatusSummary)
    project_root: Path
    progress_content: str = ""
    roadmap_content: str = ""
    memory_type_counts: dict[str, int] = Field(default_factory=dict)
