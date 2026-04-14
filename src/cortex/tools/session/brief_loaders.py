"""Session brief loading and safe-read helpers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

from cortex.core.constants import MemoryBankFile
from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_utils import find_clarification_markers
from cortex.tools.logging.session_context import ensure_trace_id_persisted
from cortex.tools.plans.plan_graph import build_plan_graph_surface_bundle
from cortex.tools.session.brief_extraction_helpers import generate_session_suggestions
from cortex.tools.session.brief_helpers import brief_from_suggestions_and_context
from cortex.tools.session.models import (
    ConcurrentSession,
    GitStatusSummary,
    SessionBrief,
)
from cortex.tools.session.registry import list_concurrent_sessions
from cortex.tools.session.start_models import BriefInputs as _BriefInputs
from cortex.tools.session.start_models import SessionBriefContextKwargs


def _format_gate_feedback_summary(payload: dict[str, object]) -> str | None:
    """Build a one-line gate feedback summary from handoff payload."""
    summary_raw = payload.get("summary")
    if not isinstance(summary_raw, str):
        return None
    summary = summary_raw.strip()
    if not summary:
        return None
    top_files_raw = payload.get("top_files")
    if not isinstance(top_files_raw, list):
        return summary
    top_files: list[str] = []
    top_files_items = cast(list[object], top_files_raw)
    for item in top_files_items:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if cleaned:
            top_files.append(cleaned)
    if not top_files:
        return summary
    return f"{summary} Top files: {', '.join(top_files[:5])}"


async def load_gate_feedback_summary_safe(project_root: Path) -> str | None:
    """Load gate feedback summary from implement pipeline handoff if present."""
    import logging

    from cortex.tools.session.pipeline_handoff import pipeline_handoff

    logger = logging.getLogger(__name__)
    try:
        raw = await pipeline_handoff(
            operation="read",
            pipeline="implement",
            phase="gate_feedback",
            ctx=None,
        )
    except Exception as e:
        logger.debug("Failed to read gate feedback handoff: %s", e)
        return None
    try:
        parsed: object = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    payload = cast(dict[str, object], parsed)
    if payload.get("status") in {"not_found", "error"}:
        return None
    return _format_gate_feedback_summary(payload)


def constitution_notice_if_missing(project_root: Path) -> str | None:
    from cortex.core.path_resolver import get_constitution_path

    if get_constitution_path(project_root).is_file():
        return None
    return (
        "No constitution.md found. Run manage_file(operation='init_constitution') "
        "to create one."
    )


async def read_memory_bank_file(
    fs_manager: FileSystemManager, file_name: str
) -> tuple[str | None, str | None]:
    """Read a memory bank file. Returns (content, error_message)."""
    file_path: Path = fs_manager.memory_bank_dir / file_name
    if not file_path.exists():
        return None, f"{file_name} not found"
    content: str
    content, _ = await fs_manager.read_file(file_path)
    return content, None


async def extract_project_name(fs_manager: FileSystemManager) -> str:
    """Extract project name from projectBrief.md or return default."""
    project_name: str = "Cortex"
    project_brief_path: Path = fs_manager.memory_bank_dir / MemoryBankFile.PROJECT_BRIEF
    if project_brief_path.exists():
        project_brief_content: str
        project_brief_content, _ = await fs_manager.read_file(project_brief_path)
        first_line: str = (
            project_brief_content.split("\n")[0] if project_brief_content else ""
        )
        if first_line.startswith("#"):
            project_name = first_line.replace("#", "").strip()
    return project_name


async def _load_concurrent_sessions_safe(
    project_root: Path,
) -> list[ConcurrentSession]:
    """Load concurrent sessions, returning empty list on error."""
    import logging

    logger = logging.getLogger(__name__)
    try:
        return await list_concurrent_sessions(project_root, exclude_current=True)
    except Exception as e:
        logger.debug("Failed to load concurrent sessions: %s", e)
        return []


async def _load_locked_tasks_safe(project_root: Path) -> list[str]:
    """Load locked task titles, returning empty list on error."""
    import logging

    from cortex.tools.session.task_locking import list_active_locks

    logger = logging.getLogger(__name__)
    try:
        locks = await list_active_locks(project_root)
        return [lock.task_title for lock in locks]
    except Exception as e:
        logger.debug("Failed to load locked tasks: %s", e)
        return []


async def load_concurrency_info(
    project_root: Path,
) -> tuple[list[ConcurrentSession], list[str]]:
    """Load concurrent sessions and locked tasks in parallel."""
    concurrent_sessions, locked_tasks = await asyncio.gather(
        _load_concurrent_sessions_safe(project_root),
        _load_locked_tasks_safe(project_root),
    )
    return concurrent_sessions, locked_tasks


def plan_graph_brief_fields(project_root: Path) -> tuple[str | None, str | None]:
    plans_dir = get_cortex_path(project_root, CortexResourceType.PLANS)
    bundle = build_plan_graph_surface_bundle(
        plans_dir, include_archive=False, max_ascii_edges=10
    )
    if bundle is None:
        return None, None
    summary = str(bundle["plan_graph_summary"])
    ascii_edges = str(bundle["plan_graph_ascii_edges"])
    return summary, ascii_edges


def _is_active_plan(plan_content: str) -> bool:
    header = plan_content[:800]
    return "status: COMPLETE" not in header and "status: COMPLETED" not in header


def _scan_plan_file_for_clarifications(plan_path: Path) -> tuple[int, int]:
    content = plan_path.read_text(encoding="utf-8")
    if not _is_active_plan(content):
        return 0, 0
    markers = find_clarification_markers(content)
    if not markers:
        return 0, 0
    blocking = sum(1 for marker in markers if marker.blocking)
    return 1, blocking


def compute_clarification_summary(project_root: Path) -> str | None:
    plans_dir = get_cortex_path(project_root, CortexResourceType.PLANS)
    if not plans_dir.exists():
        return None
    plans_with_markers = 0
    blocking_markers = 0
    for plan_path in sorted(plans_dir.glob("*.md")):
        plan_count, blocking = _scan_plan_file_for_clarifications(plan_path)
        plans_with_markers += plan_count
        blocking_markers += blocking
    if plans_with_markers == 0:
        return None
    return f"{plans_with_markers} plans have unresolved clarifications ({blocking_markers} blocking)."


def _session_brief_context(inp: _BriefInputs) -> SessionBriefContextKwargs:
    return SessionBriefContextKwargs(
        project_name=inp.project_name,
        current_focus=inp.current_focus,
        recent_completed=inp.recent_completed,
        next_work_item=inp.next_work_item,
        next_work_plan_path=inp.next_work_plan_path,
        health=inp.health,
        git_status=inp.git_status,
        last_handoff=inp.last_handoff,
        concurrent_sessions=inp.concurrent_sessions,
        locked_tasks=inp.locked_tasks,
        mcp_healthy=inp.mcp_healthy,
        mcp_health_message=inp.mcp_health_message,
        gate_feedback_summary=inp.gate_feedback_summary,
        clarification_summary=inp.clarification_summary,
        constitution_notice=inp.constitution_notice,
        workflow_schema=inp.workflow_schema,
        workflow_schema_description=inp.workflow_schema_description,
        workflow_phases=inp.workflow_phases,
        plan_graph_summary=inp.plan_graph_summary,
        plan_graph_ascii_edges=inp.plan_graph_ascii_edges,
        wiki_status=inp.wiki_status,
        memory_type_counts=inp.memory_type_counts,
    )


def _assemble_session_brief(inp: _BriefInputs) -> SessionBrief:
    trace_id = ensure_trace_id_persisted()
    context = _session_brief_context(inp)
    suggestions = generate_session_suggestions(
        inp.health,
        inp.git_status,
        inp.next_work_item,
        inp.locked_tasks,
        inp.concurrent_sessions,
        mcp_healthy=inp.mcp_healthy,
        progress_content=inp.progress_content,
        roadmap_content=inp.roadmap_content,
        wiki_status=inp.wiki_status,
        project_root=inp.project_root,
    )
    if inp.workflow_schema_warning:
        suggestions = [*suggestions, inp.workflow_schema_warning]
    brief = brief_from_suggestions_and_context(suggestions, context)
    return brief.model_copy(update={"trace_id": trace_id})


def _brief_inputs_core(
    data: dict[str, object],
    next_work_item: str | None,
    next_work_plan_path: str | None,
    git_status: GitStatusSummary | None,
    mcp_healthy: bool,
    mcp_health_message: str | None,
) -> dict[str, object]:
    return {
        "project_name": data["project_name"],
        "current_focus": data["current_focus"],
        "recent_completed": data["recent_completed"],
        "next_work_item": next_work_item,
        "next_work_plan_path": next_work_plan_path,
        "health": data["health"],
        "git_status": git_status,
        "last_handoff": data["last_handoff"],
        "concurrent_sessions": data["concurrent_sessions"],
        "locked_tasks": data["locked_tasks"],
        "mcp_healthy": mcp_healthy,
        "mcp_health_message": mcp_health_message,
    }


def _brief_inputs_tail(data: dict[str, object]) -> dict[str, object]:
    return {
        "gate_feedback_summary": data["gate_feedback_summary"],
        "clarification_summary": data["clarification_summary"],
        "constitution_notice": data["constitution_notice"],
        "progress_content": data["progress_content"],
        "roadmap_content": data["roadmap_content"],
        "workflow_schema": data["workflow_schema"],
        "workflow_schema_description": data["workflow_schema_description"],
        "workflow_phases": list(cast(list[str] | None, data["workflow_phases"]) or []),
        "workflow_schema_warning": data["workflow_schema_warning"],
        "plan_graph_summary": data["plan_graph_summary"],
        "plan_graph_ascii_edges": data["plan_graph_ascii_edges"],
        "wiki_status": data["wiki_status"],
        "memory_type_counts": data["memory_type_counts"],
        "project_root": data["project_root"],
    }


def _brief_inputs_mapping(
    c: object,
    next_work_item: str | None,
    next_work_plan_path: str | None,
    git_status: GitStatusSummary | None,
    mcp_healthy: bool,
    mcp_health_message: str | None,
) -> dict[str, object]:
    data = cast(dict[str, object], c.__dict__)
    return {
        **_brief_inputs_core(
            data,
            next_work_item,
            next_work_plan_path,
            git_status,
            mcp_healthy,
            mcp_health_message,
        ),
        **_brief_inputs_tail(data),
    }


def assemble_brief_from_components(
    c: object,
    next_work_item: str | None,
    next_work_plan_path: str | None,
    git_status: GitStatusSummary | None,
    mcp_healthy: bool,
    mcp_health_message: str | None,
) -> SessionBrief:
    inp = _BriefInputs.model_validate(
        _brief_inputs_mapping(
            c,
            next_work_item,
            next_work_plan_path,
            git_status,
            mcp_healthy,
            mcp_health_message,
        )
    )
    return _assemble_session_brief(inp)
