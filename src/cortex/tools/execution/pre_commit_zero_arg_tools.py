"""Zero-arg pre-commit MCP tools for the commit pipeline.

Extracted from ``pre_commit_tools.py`` to keep that module under the
file-length limit while preserving the public MCP surface:

- run_quality_gate: Phase A quality gate (used by commit orchestrator)
- run_quality_gate_fresh: Phase A final gate (Step 12)
- run_docs_gate: Phase B docs/memory validation
- fix_quality_issues: Auto-fix format/type/quality/markdown issues
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_COMPLEX,
    MCP_TOOL_TIMEOUT_VERY_COMPLEX,
)
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_annotations import external_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
    typed_mcp_tool,
)
from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.usage_context import (
    get_current_project_root,
    get_or_resolve_project_root,
)
from cortex.tools.execution.pre_commit_detached import clear_all_cached_results
from cortex.tools.execution.pre_commit_docs_memory_helpers import (
    run_docs_and_memory_bank_sync_impl,
)
from cortex.tools.execution.pre_commit_fix_quality import fix_quality_issues_impl
from cortex.tools.execution.pre_commit_phase_dispatch import (
    PreCommitPhase,
    phase_to_checks,
)

# Serializes all Phase-A spawns (run_quality_gate, run_quality_gate_fresh,
# fix_quality_issues). Concurrent Phase-A subprocess jobs crash the MCP server
# because they race on shared session files and stdout. One job at a time.
phase_a_lock = asyncio.Lock()


def _read_pipeline_phase_config(
    root: Path,
    pipeline: str,
    phase: str,
    defaults: dict[str, object],
) -> dict[str, object]:
    """Read config for a pipeline phase from its task file. Falls back to defaults.

    Reads .cortex/.session/{session_id}/{pipeline}/{phase}-task.json written by
    pipeline_handoff(operation="write_task"). This lets orchestrators pass params
    without the MCP bridge needing to forward arguments — the tool reads them from
    disk instead. Returns defaults for any key not present in the task file.
    """
    import os

    session_id = os.environ.get("CORTEX_SESSION_ID", "")
    if not session_id:
        return defaults
    session_root = get_cortex_path(root, CortexResourceType.SESSION)
    task_path = session_root / session_id / pipeline / f"{phase}-task.json"
    if not task_path.exists():
        return defaults
    try:
        data: object = json.loads(task_path.read_text())
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    merged = dict(defaults)
    # pyright can't infer key/value types from json.loads + dict checks.
    updates: dict[str, object] = {}
    for k, v in cast(dict[object, object], data).items():
        if isinstance(k, str) and k in defaults:
            updates[k] = v
    merged.update(updates)
    return merged


def _start_phase_a_job(
    root: Path,
    timeout: int,
    coverage_threshold: float,
    force_fresh: bool,
) -> ModelDict:
    """Start detached Phase A pre-commit job and return {job_id,status}."""
    from cortex.tools.execution.pre_commit_detached import start_pre_commit_job_impl

    checks = list(phase_to_checks(PreCommitPhase.A))
    job = start_pre_commit_job_impl(
        root,
        checks=checks,
        timeout=timeout,
        coverage_threshold=coverage_threshold,
        strict_mode=False,
        include_markdown_lint=True,
        force_fresh=force_fresh,
    )
    return cast(ModelDict, job)


def markdown_result_has_errors(md: dict[str, object]) -> bool:
    """Return True when the detached worker's markdown_result indicates failures."""
    files_err = md.get("files_with_errors", 0)
    try:
        if isinstance(files_err, (int, str)) and int(files_err) > 0:
            return True
    except (ValueError, TypeError):
        # Non-numeric string — treat as error signal.
        return True
    if str(md.get("status", "success")) == "error" and md.get("error") != "timeout":
        return True
    return False


async def poll_phase_a_result(
    root: Path,
    job_id: str,
    timeout: int,
    ctx: MCPContext | None,
) -> ModelDict:
    """Poll detached Phase A result envelope and return inner dict.

    The detached worker stores two top-level keys in the result envelope:
    ``result`` (language checks) and ``markdown_result`` (rumdl lint).
    This function merges them so that ``preflight_passed`` reflects
    **both** — preventing markdown-lint failures from being silently
    dropped before the commit orchestrator sees the quality-gate output.
    """
    from cortex.tools.execution.pre_commit_detached import poll_for_result

    rp = (
        get_cortex_path(root, CortexResourceType.SESSION)
        / f"pre_commit_result_{job_id}.json"
    )
    envelope = await poll_for_result(rp, ctx=ctx, timeout=float(timeout + 60))
    if envelope.get("status") != "completed":
        return cast(ModelDict, envelope)
    inner = envelope.get("result")
    if not isinstance(inner, dict):
        return cast(ModelDict, {"status": "error", "error": "Missing result key"})

    # Merge markdown lint result so callers see it and preflight_passed is correct.
    md_raw = envelope.get("markdown_result")
    if isinstance(md_raw, dict):
        md_result = cast(dict[str, object], md_raw)
        inner["markdown_result"] = md_result
        if markdown_result_has_errors(md_result):
            inner["preflight_passed"] = False

    return cast(ModelDict, inner)


async def _spawn_and_poll_phase_a(
    root: Path,
    timeout: int,
    coverage_threshold: float,
    force_fresh: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Spawn Phase A as a detached subprocess and poll with heartbeats.

    This keeps the MCP stdio connection alive by yielding to the event loop
    every 2 seconds (via asyncio.sleep in poll_for_result), allowing
    progress notifications to flow. Without this, long-running in-process
    checks block the event loop and Cursor drops the connection.

    Acquires ``phase_a_lock`` before spawning to prevent concurrent Phase-A
    jobs, which race on shared session files and crash the MCP server.
    """
    async with phase_a_lock:
        job = _start_phase_a_job(
            root,
            timeout=timeout,
            coverage_threshold=coverage_threshold,
            force_fresh=force_fresh,
        )
        job_id = str(job.get("job_id", ""))
        status = str(job.get("status", ""))
        if status == "error":
            return job
        return await poll_phase_a_result(root, job_id, timeout=timeout, ctx=ctx)


@typed_mcp_tool(
    annotations=external_annotations(
        "Run Quality Gate",
        read_only=False,
        destructive=False,
        idempotent=False,
    )
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)
async def run_quality_gate(
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Run Phase A quality gate end-to-end and return full result. Zero args required.

    USE WHEN: Running the commit pipeline Phase A quality gate. Spawns checks
    as a detached subprocess and polls with heartbeat progress notifications,
    keeping the MCP stdio connection alive during long runs (~90s).

    Config is read automatically from the pipeline session file written by
    pipeline_handoff(operation="write", pipeline="commit", phase="checks").
    Supported keys: coverage_threshold (float), test_timeout (int).

    EXAMPLES:
    - run_quality_gate() to run the full Phase A quality gate before commit.
    - run_quality_gate() inside the commit orchestrator instead of calling
      start_quality_job + get_quality_job_status manually when arguments
      cannot be passed through the MCP bridge.
    """
    root = get_current_project_root() or Path(await get_or_resolve_project_root(ctx))
    cfg = _read_pipeline_phase_config(
        root,
        "commit",
        "checks",
        {"coverage_threshold": 0.90, "test_timeout": 300},
    )
    return await _spawn_and_poll_phase_a(
        root,
        timeout=int(cfg["test_timeout"]),  # type: ignore[arg-type]
        coverage_threshold=float(cfg["coverage_threshold"]),  # type: ignore[arg-type]
        force_fresh=False,
        ctx=ctx,
    )


@typed_mcp_tool(
    annotations=external_annotations(
        "Run Quality Gate Fresh",
        read_only=False,
        destructive=False,
        idempotent=False,
    )
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)
async def run_quality_gate_fresh(
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Run Phase A quality gate with cache cleared (force_fresh). Zero args required.

    USE WHEN: Running the Step 12 final gate where a fresh run is mandatory after
    Phase B/C may have modified files. Clears all cached pre-commit results first,
    then spawns and polls Phase A with heartbeat progress.

    EXAMPLES:
    - run_quality_gate_fresh() in Step 12 of the commit pipeline when Phase B/C
      may have modified files since Phase A.
    - run_quality_gate_fresh() after manual fixes to ensure a clean, uncached
      quality gate run.
    """
    root = get_current_project_root() or Path(await get_or_resolve_project_root(ctx))
    return await _spawn_and_poll_phase_a(
        root,
        timeout=600,
        coverage_threshold=0.90,
        force_fresh=True,
        ctx=ctx,
    )


@typed_mcp_tool(
    annotations=external_annotations(
        "Run Docs Gate",
        read_only=False,
        destructive=False,
        idempotent=True,
    )
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def run_docs_gate(
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Run Phase B docs/memory-bank sync validation. Zero args required.

    USE WHEN: Validating that timestamps, roadmap_sync, and memory-bank files
    are consistent after documentation updates. Called by the commit-docs
    subagent as a zero-arg alternative to execute_pre_commit_checks(phase="B")
    (which Cursor's MCP bridge zero-args to Phase A, running tests instead).

    RETURNS: JSON with docs_phase_passed (bool), timestamps_result, and
    roadmap_sync_result. Does NOT run tests or code quality checks.

    EXAMPLES:
    - run_docs_gate() after updating memory-bank files via manage_file() in
      Phase B of the commit pipeline.
    - run_docs_gate() to re-check roadmap_sync and timestamps without
      re-running tests or other quality checks.
    """
    return await run_docs_and_memory_bank_sync_impl(ctx=ctx)


@typed_mcp_tool(
    annotations=external_annotations(
        "Fix Quality Issues",
        read_only=False,
        destructive=False,
        idempotent=False,
    )
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)
async def fix_quality_issues(
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Auto-fix formatting, linting, type errors, and markdown lint. Zero args required.

    USE WHEN: Phase A fails and automated fixes are needed before re-running checks.
    Called by commit-checks, commit-final-gate, and implement-code agents after
    preflight_passed=false. Runs fix_errors, format, type_check, and markdown auto-fix.

    EXAMPLES:
    - fix_quality_issues() immediately after a failing run_quality_gate() call
      to auto-fix formatting, linting, type, and markdown issues.
    - fix_quality_issues() inside implement-code or commit-checks agents on
      the fix path before re-running the quality gate.
    """
    root = get_current_project_root() or Path(await get_or_resolve_project_root(ctx))
    async with phase_a_lock:
        result_json = await fix_quality_issues_impl(
            root, include_untracked_markdown=True, ctx=ctx
        )
    _ = clear_all_cached_results(root)
    return cast(ModelDict, json.loads(result_json))
