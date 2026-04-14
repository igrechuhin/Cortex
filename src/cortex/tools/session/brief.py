"""Session brief building for session_start."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from cortex.core.constants import MemoryBankFile
from cortex.core.file_system import FileSystemManager
from cortex.managers.types import ManagersDict
from cortex.tools.models_base import ToolResultStatus
from cortex.tools.session.brief_cap import (
    cap_session_brief_payload as _cap_session_brief_payload,
)
from cortex.tools.session.brief_extraction_helpers import extract_focus_and_completed
from cortex.tools.session.brief_loaders import (
    assemble_brief_from_components,
    compute_clarification_summary,
    constitution_notice_if_missing,
    extract_project_name,
    load_concurrency_info,
    load_gate_feedback_summary_safe,
    plan_graph_brief_fields,
    read_memory_bank_file,
)
from cortex.tools.session.brief_workflow import load_workflow_brief_fields
from cortex.tools.session.health import calculate_health_summary
from cortex.tools.session.models import (
    ConcurrentSession,
    GitStatusSummary,
    SessionBrief,
    SessionHandoff,
    SessionHealthSummary,
    SessionStartErrorResult,
    WikiStatusSummary,
)
from cortex.tools.session.wiki_status import compute_wiki_status

__all__ = ["build_session_brief", "cap_session_brief_payload", "load_memory_bank_files"]

_BriefAsyncResult = tuple[
    SessionHealthSummary,
    str,
    SessionHandoff | None,
    list[ConcurrentSession],
    list[str],
    str | None,
]


class _WorkflowBriefFields(NamedTuple):
    workflow_schema: str
    workflow_schema_description: str
    workflow_phases: list[str]
    workflow_schema_warning: str | None
    plan_graph_summary: str | None
    plan_graph_ascii_edges: str | None


@dataclass
class _BriefComponents:
    current_focus: str
    recent_completed: list[str]
    health: SessionHealthSummary
    project_name: str
    last_handoff: SessionHandoff | None
    concurrent_sessions: list[ConcurrentSession]
    locked_tasks: list[str]
    gate_feedback_summary: str | None
    clarification_summary: str | None
    project_root: Path
    wiki_status: WikiStatusSummary
    constitution_notice: str | None = None
    progress_content: str = ""
    roadmap_content: str = ""
    workflow_schema: str = "default"
    workflow_schema_description: str = ""
    workflow_phases: list[str] | None = None
    workflow_schema_warning: str | None = None
    plan_graph_summary: str | None = None
    plan_graph_ascii_edges: str | None = None


async def _load_brief_async(
    managers: ManagersDict,
    project_root: Path,
    fs_manager: FileSystemManager,
) -> _BriefAsyncResult:
    from cortex.tools.memory.compaction_operations import read_handoff

    (
        health,
        project_name,
        last_handoff,
        concurrency,
        gate_feedback,
    ) = await asyncio.gather(
        calculate_health_summary(managers, project_root),
        extract_project_name(fs_manager),
        read_handoff(project_root, fs_manager),
        load_concurrency_info(project_root),
        load_gate_feedback_summary_safe(project_root),
    )
    concurrent_sessions, locked_tasks = concurrency
    return (
        health,
        project_name,
        last_handoff,
        concurrent_sessions,
        locked_tasks,
        gate_feedback,
    )


def _workflow_fields_and_plan_graph(project_root: Path) -> _WorkflowBriefFields:
    wn, wd, wp, ww = load_workflow_brief_fields(project_root)
    pg_summary, pg_ascii = plan_graph_brief_fields(project_root)
    return _WorkflowBriefFields(wn, wd, wp, ww, pg_summary, pg_ascii)


def _typed_loaded_fields(
    loaded: _BriefAsyncResult,
) -> tuple[
    SessionHealthSummary,
    str,
    SessionHandoff | None,
    list[ConcurrentSession],
    list[str],
    str | None,
]:
    return loaded


def _workflow_component_fields(project_root: Path) -> tuple[
    str,
    str,
    list[str],
    str | None,
    str | None,
    str | None,
]:
    workflow = _workflow_fields_and_plan_graph(project_root)
    return (
        workflow.workflow_schema,
        workflow.workflow_schema_description,
        workflow.workflow_phases,
        workflow.workflow_schema_warning,
        workflow.plan_graph_summary,
        workflow.plan_graph_ascii_edges,
    )


def _brief_base_components(
    loaded: _BriefAsyncResult,
) -> tuple[
    SessionHealthSummary,
    str,
    SessionHandoff | None,
    list[ConcurrentSession],
    list[str],
    str | None,
]:
    return _typed_loaded_fields(loaded)


def _brief_workflow_fields(project_root: Path) -> tuple[
    str,
    str,
    list[str],
    str | None,
    str | None,
    str | None,
]:
    return _workflow_component_fields(project_root)


def _build_brief_components(
    current_focus: str,
    recent_completed: list[str],
    loaded: _BriefAsyncResult,
    progress_content: str | None,
    roadmap_content: str,
    constitution_notice: str | None,
    project_root: Path,
) -> _BriefComponents:
    core = _brief_base_components(loaded)
    workflow = _brief_workflow_fields(project_root)
    return _BriefComponents(
        current_focus,
        recent_completed,
        *core,
        compute_clarification_summary(project_root),
        project_root,
        compute_wiki_status(project_root),
        constitution_notice,
        progress_content or "",
        roadmap_content,
        *workflow,
    )


async def _gather_brief_components(
    active_context_content: str,
    managers: ManagersDict,
    project_root: Path,
    fs_manager: FileSystemManager,
    git_status: GitStatusSummary | None,
    next_work_item: str | None,
    next_work_plan_path: str | None,
    roadmap_content: str = "",
) -> _BriefComponents:
    del git_status, next_work_item, next_work_plan_path
    current_focus, recent_completed = extract_focus_and_completed(
        active_context_content
    )
    loaded, progress_tuple = await asyncio.gather(
        _load_brief_async(managers, project_root, fs_manager),
        read_memory_bank_file(fs_manager, MemoryBankFile.PROGRESS),
    )
    progress_content, _ = progress_tuple
    constitution_notice = constitution_notice_if_missing(project_root)
    return _build_brief_components(
        current_focus,
        recent_completed,
        loaded,
        progress_content,
        roadmap_content,
        constitution_notice,
        project_root,
    )


async def build_session_brief(
    active_context_content: str,
    managers: ManagersDict,
    project_root: Path,
    fs_manager: FileSystemManager,
    git_status: GitStatusSummary | None,
    next_work_item: str | None,
    next_work_plan_path: str | None,
    mcp_healthy: bool = True,
    mcp_health_message: str | None = None,
    roadmap_content: str = "",
) -> SessionBrief:
    c = await _gather_brief_components(
        active_context_content,
        managers,
        project_root,
        fs_manager,
        git_status,
        next_work_item,
        next_work_plan_path,
        roadmap_content=roadmap_content,
    )
    assembled = assemble_brief_from_components(
        c,
        next_work_item,
        next_work_plan_path,
        git_status,
        mcp_healthy,
        mcp_health_message,
    )
    return _cap_session_brief_payload(assembled)


def cap_session_brief_payload(brief: SessionBrief) -> SessionBrief:
    """Backward-compatible export for tests importing from session.brief."""
    return _cap_session_brief_payload(brief)


async def load_memory_bank_files(
    fs_manager: FileSystemManager,
) -> tuple[str, str] | SessionStartErrorResult:
    (active_content, active_err), (roadmap_content, roadmap_err) = await asyncio.gather(
        read_memory_bank_file(fs_manager, MemoryBankFile.ACTIVE_CONTEXT),
        read_memory_bank_file(fs_manager, MemoryBankFile.ROADMAP),
    )
    if active_err:
        return SessionStartErrorResult(status=ToolResultStatus.ERROR, error=active_err)
    if roadmap_err:
        return SessionStartErrorResult(status=ToolResultStatus.ERROR, error=roadmap_err)
    assert active_content is not None and roadmap_content is not None
    return active_content, roadmap_content
