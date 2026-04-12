"""Session brief building for session_start.

Extracted from session_start_tools to keep file size under 400 lines.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, cast

from cortex.core.constants import MemoryBankFile
from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_utils import find_clarification_markers
from cortex.managers.types import ManagersDict
from cortex.tools.logging.session_context import ensure_trace_id_persisted
from cortex.tools.models_base import ToolResultStatus
from cortex.tools.plans.plan_graph import build_plan_graph_surface_bundle
from cortex.tools.session.brief_extraction_helpers import (
    extract_focus_and_completed,
    generate_session_suggestions,
)
from cortex.tools.session.brief_helpers import brief_from_suggestions_and_context
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
from cortex.tools.session.registry import list_concurrent_sessions
from cortex.tools.session.start_models import (
    BriefInputs as _BriefInputs,
)
from cortex.tools.session.start_models import (
    SessionBriefContextKwargs,
)
from cortex.tools.session.wiki_status import compute_wiki_status

# Bound string fields so session_start tool JSON stays compact and clients cannot choke on
# oversized payloads (mitigates JSONDecodeError / truncation when composing composite tools).
_MAX_SESSION_BRIEF_CONCURRENT_TASK_CHARS = 512
_MAX_SESSION_BRIEF_CURRENT_FOCUS_CHARS = 20000
_MAX_SESSION_BRIEF_LINE_CHARS = 1000
_MAX_SESSION_BRIEF_SUGGESTION_CHARS = 800
_MAX_SESSION_BRIEF_PLAN_GRAPH_SUMMARY_CHARS = 500
_MAX_SESSION_BRIEF_PLAN_GRAPH_ASCII_CHARS = 2500


def _plan_graph_brief_fields(project_root: Path) -> tuple[str | None, str | None]:
    """READY/BLOCKED summary and truncated edge list for session orientation."""
    plans_dir = get_cortex_path(project_root, CortexResourceType.PLANS)
    bundle = build_plan_graph_surface_bundle(
        plans_dir, include_archive=False, max_ascii_edges=10
    )
    if bundle is None:
        return None, None
    summary = str(bundle["plan_graph_summary"])
    ascii_edges = str(bundle["plan_graph_ascii_edges"])
    return summary, ascii_edges


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


async def _load_gate_feedback_summary_safe(project_root: Path) -> str | None:
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


def _truncate_for_brief_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1] + "…"


def _truncate_optional(value: str | None, max_chars: int) -> str | None:
    if value is None:
        return None
    return _truncate_for_brief_text(value, max_chars)


def _constitution_notice_if_missing(project_root: Path) -> str | None:
    from cortex.core.path_resolver import get_constitution_path

    if get_constitution_path(project_root).is_file():
        return None
    return (
        "No constitution.md found. Run manage_file(operation='init_constitution') "
        "to create one."
    )


def _cap_concurrent_session_tasks(
    sessions: list[ConcurrentSession],
) -> list[ConcurrentSession]:
    return [
        ConcurrentSession(
            agent_role=s.agent_role,
            task=_truncate_for_brief_text(
                s.task, _MAX_SESSION_BRIEF_CONCURRENT_TASK_CHARS
            ),
            started=s.started,
            session_id=s.session_id,
        )
        for s in sessions
    ]


def _session_brief_cap_core_fields(brief: SessionBrief, line: int) -> dict[str, object]:
    return {
        "current_focus": _truncate_for_brief_text(
            brief.current_focus, _MAX_SESSION_BRIEF_CURRENT_FOCUS_CHARS
        ),
        "recent_completed": [
            _truncate_for_brief_text(x, line) for x in brief.recent_completed
        ],
        "next_work_item": _truncate_optional(brief.next_work_item, line),
        "next_work_plan_path": _truncate_optional(brief.next_work_plan_path, line),
        "session_suggestions": [
            _truncate_for_brief_text(s, _MAX_SESSION_BRIEF_SUGGESTION_CHARS)
            for s in brief.session_suggestions
        ],
        "concurrent_sessions": _cap_concurrent_session_tasks(brief.concurrent_sessions),
        "locked_tasks": [_truncate_for_brief_text(t, line) for t in brief.locked_tasks],
        "mcp_health_message": _truncate_optional(brief.mcp_health_message, line),
        "gate_feedback_summary": _truncate_optional(brief.gate_feedback_summary, line),
        "clarification_summary": _truncate_optional(brief.clarification_summary, line),
        "constitution_notice": _truncate_optional(brief.constitution_notice, line),
        "primary_session_goal": _truncate_optional(brief.primary_session_goal, line),
        "session_goal_drift_hint": _truncate_optional(
            brief.session_goal_drift_hint, line
        ),
        "plan_graph_summary": _truncate_optional(
            brief.plan_graph_summary, _MAX_SESSION_BRIEF_PLAN_GRAPH_SUMMARY_CHARS
        ),
        "plan_graph_ascii_edges": _truncate_optional(
            brief.plan_graph_ascii_edges, _MAX_SESSION_BRIEF_PLAN_GRAPH_ASCII_CHARS
        ),
    }


def _session_brief_cap_workflow_fields(
    brief: SessionBrief, line: int
) -> dict[str, object]:
    return {
        "workflow_schema_description": _truncate_optional(
            brief.workflow_schema_description, line
        ),
        "workflow_phases": [
            _truncate_for_brief_text(p, line) for p in brief.workflow_phases[:50]
        ],
    }


def _session_brief_cap_update(brief: SessionBrief) -> dict[str, object]:
    """Build ``model_copy(update=...)`` for capped string fields."""
    line = _MAX_SESSION_BRIEF_LINE_CHARS
    merged = _session_brief_cap_core_fields(brief, line)
    merged.update(_session_brief_cap_workflow_fields(brief, line))
    return merged


def cap_session_brief_payload(brief: SessionBrief) -> SessionBrief:
    """Cap long strings in the brief before MCP serialization."""
    return brief.model_copy(update=_session_brief_cap_update(brief))


async def _read_memory_bank_file(
    fs_manager: FileSystemManager, file_name: str
) -> tuple[str | None, str | None]:
    """Read a memory bank file. Returns (content, error_message)."""
    file_path: Path = fs_manager.memory_bank_dir / file_name
    if not file_path.exists():
        return None, f"{file_name} not found"
    content: str
    content, _ = await fs_manager.read_file(file_path)
    return content, None


async def _extract_project_name(fs_manager: FileSystemManager) -> str:
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


async def _load_concurrency_info(
    project_root: Path,
) -> tuple[list[ConcurrentSession], list[str]]:
    """Load concurrent sessions and locked tasks in parallel."""
    concurrent_sessions, locked_tasks = await asyncio.gather(
        _load_concurrent_sessions_safe(project_root),
        _load_locked_tasks_safe(project_root),
    )
    return concurrent_sessions, locked_tasks


def _is_active_plan(plan_content: str) -> bool:
    header = plan_content[:800]
    return "status: COMPLETE" not in header and "status: COMPLETED" not in header


def _format_clarification_summary(plan_count: int, blocking_count: int) -> str:
    return (
        f"{plan_count} plans have unresolved clarifications "
        f"({blocking_count} blocking)."
    )


def _scan_plan_file_for_clarifications(plan_path: Path) -> tuple[int, int]:
    content = plan_path.read_text(encoding="utf-8")
    if not _is_active_plan(content):
        return 0, 0
    markers = find_clarification_markers(content)
    if not markers:
        return 0, 0
    blocking = sum(1 for marker in markers if marker.blocking)
    return 1, blocking


def _compute_clarification_summary(project_root: Path) -> str | None:
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
    return _format_clarification_summary(plans_with_markers, blocking_markers)


def _compute_suggestions_and_create_brief(inp: _BriefInputs) -> SessionBrief:
    """Compute suggestions and build SessionBrief."""
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
    )


def _assemble_session_brief(inp: _BriefInputs) -> SessionBrief:
    """Assemble session brief from collected components.

    Includes ``session_scope`` (single-goal discipline) via ``brief_helpers`` assembly.
    """
    return _compute_suggestions_and_create_brief(inp)


def _brief_inputs_core_mapping(
    c: "_BriefComponents",
    next_work_item: str | None,
    next_work_plan_path: str | None,
    git_status: GitStatusSummary | None,
    mcp_healthy: bool,
    mcp_health_message: str | None,
) -> dict[str, object]:
    """Identity, health, and MCP fields for ``BriefInputs``."""
    return {
        "project_name": c.project_name,
        "current_focus": c.current_focus,
        "recent_completed": c.recent_completed,
        "next_work_item": next_work_item,
        "next_work_plan_path": next_work_plan_path,
        "health": c.health,
        "git_status": git_status,
        "last_handoff": c.last_handoff,
        "concurrent_sessions": c.concurrent_sessions,
        "locked_tasks": c.locked_tasks,
        "mcp_healthy": mcp_healthy,
        "mcp_health_message": mcp_health_message,
    }


def _brief_inputs_tail_mapping(c: "_BriefComponents") -> dict[str, object]:
    """Workflow, progress, and plan-graph fields for ``BriefInputs``."""
    return {
        "gate_feedback_summary": c.gate_feedback_summary,
        "clarification_summary": c.clarification_summary,
        "constitution_notice": c.constitution_notice,
        "progress_content": c.progress_content,
        "roadmap_content": c.roadmap_content,
        "workflow_schema": c.workflow_schema,
        "workflow_schema_description": c.workflow_schema_description,
        "workflow_phases": list(c.workflow_phases or []),
        "workflow_schema_warning": c.workflow_schema_warning,
        "plan_graph_summary": c.plan_graph_summary,
        "plan_graph_ascii_edges": c.plan_graph_ascii_edges,
        "wiki_status": c.wiki_status,
        "project_root": c.project_root,
    }


def _brief_inputs_mapping(
    c: "_BriefComponents",
    next_work_item: str | None,
    next_work_plan_path: str | None,
    git_status: GitStatusSummary | None,
    mcp_healthy: bool,
    mcp_health_message: str | None,
) -> dict[str, object]:
    """Assemble kwargs for ``BriefInputs`` without exceeding per-function line limits."""
    return {
        **_brief_inputs_core_mapping(
            c,
            next_work_item,
            next_work_plan_path,
            git_status,
            mcp_healthy,
            mcp_health_message,
        ),
        **_brief_inputs_tail_mapping(c),
    }


def _brief_inputs_from_components(
    c: "_BriefComponents",
    next_work_item: str | None,
    next_work_plan_path: str | None,
    git_status: GitStatusSummary | None,
    mcp_healthy: bool,
    mcp_health_message: str | None,
) -> _BriefInputs:
    """Build ``BriefInputs`` from gathered components and caller git/MCP fields."""
    return _BriefInputs.model_validate(
        _brief_inputs_mapping(
            c,
            next_work_item,
            next_work_plan_path,
            git_status,
            mcp_healthy,
            mcp_health_message,
        )
    )


def _assemble_brief_from_components(
    c: "_BriefComponents",
    next_work_item: str | None,
    next_work_plan_path: str | None,
    git_status: GitStatusSummary | None,
    mcp_healthy: bool,
    mcp_health_message: str | None,
) -> SessionBrief:
    """Unpack gathered components into ``_assemble_session_brief``."""
    inp = _brief_inputs_from_components(
        c,
        next_work_item,
        next_work_plan_path,
        git_status,
        mcp_healthy,
        mcp_health_message,
    )
    return _assemble_session_brief(inp)


_BriefAsyncResult = tuple[
    SessionHealthSummary,
    str,
    SessionHandoff | None,
    list[ConcurrentSession],
    list[str],
    str | None,
]


@dataclass(frozen=True)
class _LoadedAsyncBundle:
    """Unpacked ``_BriefAsyncResult`` tuple passed into brief component assembly."""

    health: SessionHealthSummary
    project_name: str
    last_handoff: SessionHandoff | None
    concurrent_sessions: list[ConcurrentSession]
    locked_tasks: list[str]
    gate_feedback_summary: str | None


class _WorkflowBriefFields(NamedTuple):
    """Workflow schema + plan-graph lines for ``_BriefComponents``."""

    workflow_schema: str
    workflow_schema_description: str
    workflow_phases: list[str]
    workflow_schema_warning: str | None
    plan_graph_summary: str | None
    plan_graph_ascii_edges: str | None


@dataclass(frozen=True)
class _BriefAssemblyParams:
    """Arguments for ``_brief_components_from_loaded_bundle`` (single param for line limits)."""

    current_focus: str
    recent_completed: list[str]
    loaded: _LoadedAsyncBundle
    progress_content: str | None
    roadmap_content: str
    constitution_notice: str | None
    project_root: Path
    workflow: _WorkflowBriefFields


async def _load_brief_async(
    managers: ManagersDict,
    project_root: Path,
    fs_manager: FileSystemManager,
) -> _BriefAsyncResult:
    """Load health, project name, handoff, and concurrency for brief in parallel."""
    from cortex.tools.memory.compaction_operations import read_handoff

    health, project_name, last_handoff, concurrency, gate_feedback = (
        await asyncio.gather(
            calculate_health_summary(managers, project_root),
            _extract_project_name(fs_manager),
            read_handoff(project_root, fs_manager),
            _load_concurrency_info(project_root),
            _load_gate_feedback_summary_safe(project_root),
        )
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


def _brief_components_from_async_load(
    current_focus: str,
    recent_completed: list[str],
    loaded: _BriefAsyncResult,
    progress_content: str | None,
    roadmap_content: str,
    constitution_notice: str | None,
    project_root: Path,
) -> _BriefComponents:
    """Build ``_BriefComponents`` from focus tuple and parallel-load results."""
    return _assemble_brief_components(
        current_focus,
        recent_completed,
        loaded,
        progress_content,
        roadmap_content,
        constitution_notice,
        project_root,
    )


def _workflow_fields_and_plan_graph(project_root: Path) -> _WorkflowBriefFields:
    """Load workflow schema fields plus plan-graph summary lines for the brief."""
    wn, wd, wp, ww = load_workflow_brief_fields(project_root)
    pg_summary, pg_ascii = _plan_graph_brief_fields(project_root)
    return _WorkflowBriefFields(wn, wd, wp, ww, pg_summary, pg_ascii)


def _brief_components_from_loaded_bundle(
    params: _BriefAssemblyParams,
) -> _BriefComponents:
    loaded = params.loaded
    workflow = params.workflow
    project_root = params.project_root
    return _BriefComponents(
        current_focus=params.current_focus,
        recent_completed=params.recent_completed,
        health=loaded.health,
        project_name=loaded.project_name,
        last_handoff=loaded.last_handoff,
        concurrent_sessions=loaded.concurrent_sessions,
        locked_tasks=loaded.locked_tasks,
        gate_feedback_summary=loaded.gate_feedback_summary,
        clarification_summary=_compute_clarification_summary(project_root),
        constitution_notice=params.constitution_notice,
        progress_content=params.progress_content or "",
        roadmap_content=params.roadmap_content,
        workflow_schema=workflow.workflow_schema,
        workflow_schema_description=workflow.workflow_schema_description,
        workflow_phases=workflow.workflow_phases,
        workflow_schema_warning=workflow.workflow_schema_warning,
        plan_graph_summary=workflow.plan_graph_summary,
        plan_graph_ascii_edges=workflow.plan_graph_ascii_edges,
        project_root=project_root,
        wiki_status=compute_wiki_status(project_root),
    )


def _brief_components_after_loaded_unpack(
    current_focus: str,
    recent_completed: list[str],
    loaded: _LoadedAsyncBundle,
    progress_content: str | None,
    roadmap_content: str,
    constitution_notice: str | None,
    project_root: Path,
) -> _BriefComponents:
    workflow = _workflow_fields_and_plan_graph(project_root)
    return _brief_components_from_loaded_bundle(
        _BriefAssemblyParams(
            current_focus=current_focus,
            recent_completed=recent_completed,
            loaded=loaded,
            progress_content=progress_content,
            roadmap_content=roadmap_content,
            constitution_notice=constitution_notice,
            project_root=project_root,
            workflow=workflow,
        )
    )


def _assemble_brief_components(
    current_focus: str,
    recent_completed: list[str],
    loaded: _BriefAsyncResult,
    progress_content: str | None,
    roadmap_content: str,
    constitution_notice: str | None,
    project_root: Path,
) -> _BriefComponents:
    h, pn, lh, cs, lt, gf = loaded
    bundle = _LoadedAsyncBundle(h, pn, lh, cs, lt, gf)
    return _brief_components_after_loaded_unpack(
        current_focus,
        recent_completed,
        bundle,
        progress_content,
        roadmap_content,
        constitution_notice,
        project_root,
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
    """Gather components needed to build a session brief (caller provides git/next)."""
    current_focus, recent_completed = extract_focus_and_completed(
        active_context_content
    )
    loaded, progress_tuple = await asyncio.gather(
        _load_brief_async(managers, project_root, fs_manager),
        _read_memory_bank_file(fs_manager, MemoryBankFile.PROGRESS),
    )
    progress_content, _ = progress_tuple
    constitution_notice = _constitution_notice_if_missing(project_root)
    return _brief_components_from_async_load(
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
    """Build session brief from extracted information (caller provides git/next).

    Every successful brief includes ``session_scope`` prompting one primary goal per session.
    """
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
    assembled = _assemble_brief_from_components(
        c,
        next_work_item,
        next_work_plan_path,
        git_status,
        mcp_healthy,
        mcp_health_message,
    )
    return cap_session_brief_payload(assembled)


async def load_memory_bank_files(
    fs_manager: FileSystemManager,
) -> tuple[str, str] | SessionStartErrorResult:
    """Load activeContext.md and roadmap.md in parallel. Returns tuple or error."""
    (active_content, active_err), (roadmap_content, roadmap_err) = await asyncio.gather(
        _read_memory_bank_file(fs_manager, MemoryBankFile.ACTIVE_CONTEXT),
        _read_memory_bank_file(fs_manager, MemoryBankFile.ROADMAP),
    )
    if active_err:
        return SessionStartErrorResult(status=ToolResultStatus.ERROR, error=active_err)
    if roadmap_err:
        return SessionStartErrorResult(status=ToolResultStatus.ERROR, error=roadmap_err)
    assert active_content is not None and roadmap_content is not None
    return active_content, roadmap_content
