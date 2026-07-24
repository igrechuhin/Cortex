"""Pipeline handoff tool — structured inter-phase communication via session files.

Each pipeline run (commit, implement, …) creates a session-scoped subfolder
under .cortex/.session/{session_id}/ and exchanges structured JSON between
pipeline phases through that folder.

## Simplified API (4 operations)

    pipeline_handoff(operation="init",  pipeline="commit")
    pipeline_handoff(operation="write", pipeline="commit", phase="checks",
                     data='{"status": "passed", "coverage": 0.94}')
    pipeline_handoff(operation="read",  pipeline="commit", phase="checks")
    pipeline_handoff(operation="read",  pipeline="commit")  # full state
    pipeline_handoff(operation="clear", pipeline="commit")

Legacy operation names (write_task, read_task, write_result, read_state) are
mapped to the simplified API automatically.

## Files on disk

.cortex/.session/{session_id}/{pipeline}/
    pipeline.json             — cumulative state updated after each write
    {phase}-result.json       — per-phase data
"""

from __future__ import annotations

import asyncio
import json
from enum import StrEnum
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import OperationStatus
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.server import mcp
from cortex.tools.logging.instrumentation import emit_pipeline_handoff_log

from .pipeline_handoff_analytics import (
    op_fitness_by_task_type,
    op_preference_pairs,
    op_repeated_failures,
    op_write_failure_evals,
)
from .pipeline_handoff_io import (
    extract_routing_keys,
    op_clear,
    op_init,
    op_mark_running,
    op_read_log,
    op_read_state,
    op_read_task,
    op_rollback,
    op_snapshot,
    op_status,
    op_write_result,
    op_write_task,
)
from .pipeline_handoff_resume import op_resume
from .pipeline_handoff_rule_provenance import (
    dispatch as dispatch_rule_provenance,
)
from .pipeline_handoff_session import get_session_id
from .pipeline_handoff_validation import validate_phase, validate_pipeline

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


class PipelineHandoffOperation(StrEnum):
    """Supported pipeline_handoff operations (canonical + legacy aliases)."""

    INIT = "init"
    WRITE = "write"
    READ = "read"
    READ_LOG = "read_log"
    STATUS = "status"
    MARK_RUNNING = "mark_running"
    CLEAR = "clear"
    SNAPSHOT = "snapshot"
    ROLLBACK = "rollback"
    RESUME = "resume"
    PREFERENCE_PAIRS = "preference_pairs"
    REPEATED_FAILURES = "repeated_failures"
    FITNESS_BY_TASK_TYPE = "fitness_by_task_type"
    WRITE_FAILURE_EVALS = "write_failure_evals"
    RECORD_RULE_PROVENANCE = "record_rule_provenance"
    REFRESH_RULE_MATCHES = "refresh_rule_matches"
    RULE_EVIDENCE = "rule_evidence"
    PRUNING_CANDIDATES = "pruning_candidates"
    WRITE_TASK = "write_task"
    READ_TASK = "read_task"
    WRITE_RESULT = "write_result"
    READ_STATE = "read_state"


_OPS_NEED_PHASE = frozenset(
    {
        PipelineHandoffOperation.WRITE_TASK.value,
        PipelineHandoffOperation.READ_TASK.value,
        PipelineHandoffOperation.WRITE_RESULT.value,
        PipelineHandoffOperation.WRITE.value,
        PipelineHandoffOperation.MARK_RUNNING.value,
    }
)


def _resolve_zero_arg_defaults(
    operation: str,
    pipeline: str,
    phase: str | None,
) -> tuple[str, str, str | None]:
    """Fall back to session config when an MCP client strips all tool arguments.

    Some MCP client bridges send {} for every tool call, leaving all parameters
    at their declared defaults.  Detect this by checking whether both
    ``operation`` and ``pipeline`` are still at their default values, then read
    ``operation``, ``pipeline``, and ``phase`` from the session config file
    written by the orchestrator prompt before it called this tool.

    If session config is absent or incomplete the original values are returned
    unchanged, so unaffected callers see no behavior change.
    """
    if operation != PipelineHandoffOperation.READ_STATE.value or pipeline != "default":
        # At least one arg was explicitly set — not a zero-arg call.
        return operation, pipeline, phase

    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    resolved_op = str(cfg.get("operation", operation))
    resolved_pipeline = str(cfg.get("pipeline", pipeline))
    resolved_phase = phase or (
        str(cfg.get("phase")) if isinstance(cfg.get("phase"), str) else phase
    )
    return resolved_op, resolved_pipeline, resolved_phase


def _coerce_data(data: object) -> str | None:
    """Normalize data to a JSON string regardless of what the LLM sent.

    Some MCP client agents may send data as a native JSON object (dict) even though the
    MCP schema declares str | None.  Accept both: if already a string, use it
    as-is; if a dict/list/scalar, serialise it; if None/empty, return None.
    """
    if data is None:
        return None
    if isinstance(data, str):
        return data if data.strip() else None
    return json.dumps(data)


def _unknown_op_error(operation: str) -> str:
    return json.dumps(
        {
            "status": OperationStatus.ERROR.value,
            "error": (
                f"Unknown operation '{operation}'. "
                "Use: init, write, read, read_log, status, mark_running, clear, "
                "snapshot, rollback, resume, preference_pairs, repeated_failures, "
                "fitness_by_task_type, write_failure_evals, record_rule_provenance, "
                "refresh_rule_matches, rule_evidence, pruning_candidates "
                "(aliases: write_task, read_task, write_result, read_state)"
            ),
        },
        indent=2,
    )


def _phase_required_error(operation: str) -> str:
    return json.dumps(
        {
            "status": OperationStatus.ERROR.value,
            "error": f"phase is required for {operation}",
        },
        indent=2,
    )


def _snapshot_paths_required_error() -> str:
    return json.dumps(
        {
            "status": OperationStatus.ERROR.value,
            "error": "paths is required for snapshot",
        },
        indent=2,
    )


def _rollback_snapshot_id_required_error() -> str:
    return json.dumps(
        {
            "status": OperationStatus.ERROR.value,
            "error": "snapshot_id is required for rollback",
        },
        indent=2,
    )


def _extract_snapshot_paths(data_str: str | None) -> list[str]:
    if not data_str:
        return []
    try:
        parsed = json.loads(data_str)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, dict):
        return []
    parsed_dict = cast(dict[str, object], parsed)
    paths = parsed_dict.get("paths")
    if not isinstance(paths, list):
        return []
    raw_paths = cast(list[object], paths)
    return [path for path in raw_paths if isinstance(path, str) and path]


def _extract_session_id(data_str: str | None) -> str | None:
    if not data_str:
        return None
    try:
        parsed = json.loads(data_str)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    parsed_dict = cast(dict[str, object], parsed)
    session_id = parsed_dict.get("session_id")
    return session_id if isinstance(session_id, str) and session_id else None


def _extract_snapshot_id(data_str: str | None) -> str | None:
    if not data_str:
        return None
    try:
        parsed = json.loads(data_str)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    parsed_dict = cast(dict[str, object], parsed)
    snapshot_id = parsed_dict.get("snapshot_id")
    return snapshot_id if isinstance(snapshot_id, str) and snapshot_id else None


def _dispatch_read(project_root: Path, pipeline: str, phase: str | None) -> str:
    ph = phase or ""
    return (
        op_read_task(project_root, pipeline, ph)
        if phase
        else op_read_state(project_root, pipeline)
    )


def _dispatch_snapshot_or_rollback(
    project_root: Path, operation: str, data_str: str | None
) -> str:
    if operation == PipelineHandoffOperation.SNAPSHOT.value:
        snapshot_paths = _extract_snapshot_paths(data_str)
        if not snapshot_paths:
            return _snapshot_paths_required_error()
        return op_snapshot(project_root, snapshot_paths)
    snapshot_id = _extract_snapshot_id(data_str)
    if snapshot_id is None:
        return _rollback_snapshot_id_required_error()
    return op_rollback(project_root, snapshot_id)


def _dispatch_simple_operation(
    project_root: Path, pipeline: str, operation: str, phase: str | None = None
) -> str | None:
    if operation == PipelineHandoffOperation.READ_STATE.value:
        return op_read_state(project_root, pipeline)
    if operation == PipelineHandoffOperation.READ_LOG.value:
        return op_read_log(project_root, pipeline)
    if operation == PipelineHandoffOperation.STATUS.value:
        return op_status(project_root, pipeline)
    if operation == PipelineHandoffOperation.CLEAR.value:
        # AI: a phase-scoped clear (e.g. gate_feedback) must only drop that
        # one phase, never the whole live pipeline — see op_clear docstring.
        return op_clear(project_root, pipeline, phase)
    if operation == PipelineHandoffOperation.RESUME.value:
        return op_resume(project_root, pipeline)
    return None


def _dispatch_analytics_operation(
    project_root: Path, operation: str, data_str: str | None
) -> str | None:
    """Route the 4 graph-analytics operations (Gap 1: coverage-checked queries)."""
    if operation == PipelineHandoffOperation.FITNESS_BY_TASK_TYPE.value:
        return op_fitness_by_task_type(project_root)
    if operation not in (
        PipelineHandoffOperation.PREFERENCE_PAIRS.value,
        PipelineHandoffOperation.REPEATED_FAILURES.value,
        PipelineHandoffOperation.WRITE_FAILURE_EVALS.value,
    ):
        return None
    session_id = _extract_session_id(data_str) or get_session_id(project_root)
    if operation == PipelineHandoffOperation.PREFERENCE_PAIRS.value:
        return op_preference_pairs(project_root, session_id)
    if operation == PipelineHandoffOperation.REPEATED_FAILURES.value:
        return op_repeated_failures(project_root, session_id)
    return op_write_failure_evals(project_root, session_id)


_RULE_PROVENANCE_OPS = frozenset(
    {
        PipelineHandoffOperation.RECORD_RULE_PROVENANCE.value,
        PipelineHandoffOperation.REFRESH_RULE_MATCHES.value,
        PipelineHandoffOperation.RULE_EVIDENCE.value,
        PipelineHandoffOperation.PRUNING_CANDIDATES.value,
    }
)


def _dispatch_rule_provenance_operation(
    project_root: Path, operation: str, data_str: str | None
) -> str | None:
    """Route the 4 rule-provenance operations (plan: synapse-rule-provenance)."""
    if operation not in _RULE_PROVENANCE_OPS:
        return None
    session_id = _extract_session_id(data_str) or get_session_id(project_root)
    return dispatch_rule_provenance(project_root, operation, session_id, data_str)


def _dispatch_phase_bound_operation(
    project_root: Path, operation: str, pipeline: str, phase: str, data_str: str | None
) -> str | None:
    if operation == PipelineHandoffOperation.WRITE_TASK.value:
        return op_write_task(project_root, pipeline, phase, data_str)
    if operation in (
        PipelineHandoffOperation.WRITE_RESULT.value,
        PipelineHandoffOperation.WRITE.value,
    ):
        return op_write_result(project_root, pipeline, phase, data_str)
    if operation == PipelineHandoffOperation.READ_TASK.value:
        return op_read_task(project_root, pipeline, phase)
    if operation == PipelineHandoffOperation.MARK_RUNNING.value:
        return op_mark_running(project_root, pipeline, phase)
    return None


def _dispatch_query_operation(
    project_root: Path,
    operation: str,
    pipeline: str,
    data_str: str | None,
    phase: str | None = None,
) -> str | None:
    """Try each non-phase-bound dispatcher in turn; None if none match."""
    for query_result in (
        _dispatch_analytics_operation(project_root, operation, data_str),
        _dispatch_rule_provenance_operation(project_root, operation, data_str),
        _dispatch_simple_operation(project_root, pipeline, operation, phase),
    ):
        if query_result is not None:
            return query_result
    return None


def _dispatch_sync(
    project_root: Path,
    operation: str,
    pipeline: str,
    phase: str | None,
    data_str: str | None,
) -> str:
    """Route operation to the correct handler. Call after resolving project root.

    Simplified API (preferred):
        init, write (needs phase), read (phase optional), clear
    Legacy operations (still supported):
        write_task, read_task, write_result, read_state
    """
    if operation in _OPS_NEED_PHASE and not phase:
        return _phase_required_error(operation)
    if operation == PipelineHandoffOperation.INIT.value:
        return op_init(project_root, pipeline, data_str)
    resolved_phase = phase or ""
    phase_result = _dispatch_phase_bound_operation(
        project_root, operation, pipeline, resolved_phase, data_str
    )
    if phase_result is not None:
        return phase_result
    query_result = _dispatch_query_operation(
        project_root, operation, pipeline, data_str, phase
    )
    if query_result is not None:
        return query_result
    if operation == PipelineHandoffOperation.READ.value:
        return _dispatch_read(project_root, pipeline, phase)
    if operation in (
        PipelineHandoffOperation.SNAPSHOT.value,
        PipelineHandoffOperation.ROLLBACK.value,
    ):
        return _dispatch_snapshot_or_rollback(project_root, operation, data_str)
    return _unknown_op_error(operation)


async def _dispatch(
    operation: str,
    pipeline: str,
    phase: str | None,
    data: object,
    ctx: MCPContext | None,
) -> str:
    data_str = _coerce_data(data)

    # Extract routing overrides embedded in the data payload.
    # Agents write {"operation":"write","phase":"select","pipeline":"implement",...payload...}
    # to current-task.json so routing + payload travel in one write instead of two.
    routing, data_str = extract_routing_keys(data_str)
    if routing.get("op"):
        operation = routing["op"]
    if routing.get("phase"):
        phase = routing["phase"]
    if routing.get("pipeline"):
        pipeline = routing["pipeline"]

    # When an MCP client strips all args and no routing keys were in data, recover
    # operation/pipeline/phase from the session config file.
    operation, pipeline, phase = _resolve_zero_arg_defaults(operation, pipeline, phase)

    # Validate tokens before any filesystem path construction.
    pipeline_error = validate_pipeline(pipeline)
    if pipeline_error is not None:
        return pipeline_error
    if phase is not None:
        phase_error = validate_phase(phase)
        if phase_error is not None:
            return phase_error

    root = await get_or_resolve_project_root(ctx)
    project_root = Path(root)
    # Offload all blocking filesystem operations in _dispatch_sync.
    out = await asyncio.to_thread(
        _dispatch_sync, project_root, operation, pipeline, phase, data_str
    )
    emit_pipeline_handoff_log(operation, pipeline, phase)
    return out


# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations=safe_write_annotations("Pipeline Handoff (Inter-Agent State)"),
    output_schema=None,
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def pipeline_handoff(
    operation: str = PipelineHandoffOperation.READ_STATE.value,
    pipeline: str = "default",
    phase: str | None = None,
    data: object = None,
    paths: list[str] | None = None,
    snapshot_id: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Structured inter-agent communication for pipeline workflows.

    USE WHEN: Orchestrators need to exchange structured data between pipeline
    phases. Each phase writes its output; the next phase reads it. All data
    persists in .cortex/.session/{id}/{pipeline}/.

    WORKFLOW (simplified):
    1. pipeline_handoff(operation="init", pipeline="commit")
    2. pipeline_handoff(operation="write", pipeline="commit", phase="preflight",
         data='{"status":"complete","snapshot_ref":"abc123"}')
    3. pipeline_handoff(operation="read", pipeline="commit", phase="preflight")
         → reads phase data
    4. pipeline_handoff(operation="read", pipeline="commit")
         → reads full pipeline state (all phases)
    5. pipeline_handoff(operation="clear", pipeline="commit")

    EXAMPLES:
    - pipeline_handoff(operation="init", pipeline="commit")
    - pipeline_handoff(operation="write", pipeline="commit", phase="checks",
        data='{"status":"passed","coverage":0.94}')
    - pipeline_handoff(operation="read", pipeline="commit", phase="checks")
    - pipeline_handoff(operation="read", pipeline="commit")
    - pipeline_handoff(operation="clear", pipeline="commit")

    Legacy aliases (write_task, read_task, write_result, read_state) still work.

    RETURNS: JSON with {status, ...} for write ops; JSON file content for reads.

    Args:
        operation: init | write | read | read_log | status | mark_running
            | clear | snapshot | rollback | resume | preference_pairs
            | repeated_failures | fitness_by_task_type | write_failure_evals
            | record_rule_provenance | refresh_rule_matches | rule_evidence
            | pruning_candidates
            (legacy: write_task, read_task,
            write_result, read_state)
            resume: returns a ResumePlan for an interrupted run of the
            pipeline — completed phases to skip, frontier phase, and
            whether continuation is allowed (failed frontier => fix path).
            preference_pairs / repeated_failures: coverage-checked graph
            queries for the analyze-session step — pass
            data={"session_id": "..."} (falls back to the active pipeline
            session id when omitted). Returns {"status":"no_coverage"} when
            the experience store is absent, or {"coverage": false} when the
            store has no nodes for that session — both mean the caller
            should fall back to transcript scraping.
            fitness_by_task_type: store-wide fitness aggregation (no
            session_id). Same coverage-check contract.
            write_failure_evals: computes preference_pairs for the session
            and upserts evidence-linked entries into
            .cortex/evals/tasks/failure_based_evals.json.
            record_rule_provenance / refresh_rule_matches / rule_evidence /
            pruning_candidates: rule-evidence-citation API (plan
            synapse-rule-provenance) — pass data={"rule_id","failure_class",
            "session_id","pair_ids"} to record, {"session_id"} to refresh,
            {"rule_id"} to read evidence, {"window_days"} (default 90) to
            list pruning candidates.
        pipeline: Pipeline name (e.g. "commit", "implement"). Default: "default".
        phase: Phase name (e.g. "preflight", "checks"). Required for write.
            For read: if given, reads that phase; if omitted, reads full state.
        data: Payload for write and init. Accepts JSON string or native object.
            When the JSON includes free-text fields such as `context` or
            `summary`, write compact technical prose (see cortex://rules,
            Agent-Internal Communication): no filler or hedging; keep file
            paths and error messages verbatim.
        paths: Paths to snapshot for operation="snapshot". Can be passed via
            this argument or via data={"paths":[...]} for arg-stripping clients.
        snapshot_id: Snapshot id for operation="rollback". Can be passed via
            this argument or via data={"snapshot_id":"..."}.
        ctx: MCP context (auto-provided).
    """
    await log_client(
        ctx,
        "debug",
        f"pipeline_handoff({operation}/{pipeline}/{phase})",
        logger_name=__name__,
    )
    payload = data
    if (
        operation == PipelineHandoffOperation.SNAPSHOT.value
        and payload is None
        and paths is not None
    ):
        payload = {"paths": paths}
    if (
        operation == PipelineHandoffOperation.ROLLBACK.value
        and payload is None
        and snapshot_id is not None
    ):
        payload = {"snapshot_id": snapshot_id}
    return await _dispatch(
        operation, pipeline, phase, payload, ctx
    )  # data coerced inside _dispatch
