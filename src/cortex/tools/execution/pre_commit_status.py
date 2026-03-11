"""Helpers for summarizing detached pre-commit runs.

This module reads result files written by the detached pre-commit worker and
returns a compact status summary suitable for MCP tools and prompts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from cortex.core.context_logging import MCPContext

_RESULT_PREFIX = "pre_commit_result_"
_RESULT_SUFFIX = ".json"


@dataclass
class PreCommitRunSummary:
    """Summary of the most recent detached pre-commit run."""

    status: str
    args_hash: str | None = None
    checks: list[str] | None = None
    preflight_passed: bool | None = None
    docs_phase_passed: bool | None = None
    coverage: float | None = None
    completed_at: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to a JSON-serializable dict."""
        out: dict[str, Any] = {
            "status": self.status,
        }
        if self.args_hash is not None:
            out["args_hash"] = self.args_hash
        if self.checks is not None:
            out["checks"] = self.checks
        if self.preflight_passed is not None:
            out["preflight_passed"] = self.preflight_passed
        if self.docs_phase_passed is not None:
            out["docs_phase_passed"] = self.docs_phase_passed
        if self.coverage is not None:
            out["coverage"] = self.coverage
        if self.completed_at is not None:
            out["completed_at"] = self.completed_at
        if self.error is not None:
            out["error"] = self.error
        return out


def _session_dir(project_root: Path) -> Path:
    """Return session directory for result files."""
    d = project_root / ".cortex" / ".session"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _iter_result_files(session_dir: Path) -> list[Path]:
    """Return list of result files under the session directory."""
    if not session_dir.exists():
        return []
    return sorted(
        [
            p
            for p in session_dir.iterdir()
            if p.is_file()
            and p.name.startswith(_RESULT_PREFIX)
            and p.name.endswith(_RESULT_SUFFIX)
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _load_result(path: Path) -> dict[str, object] | None:
    """Load a detached result JSON file."""
    try:
        text = path.read_text()
    except OSError:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return cast(dict[str, object], data)


def _extract_checks_list(result_obj: dict[str, object]) -> list[str] | None:
    """Extract checks list from a completed result object."""
    checks = result_obj.get("checks") or result_obj.get("checks_performed")
    if not isinstance(checks, list):
        return None
    return [str(item) for item in cast(list[object], checks)]


def _extract_completed_at(data: dict[str, object]) -> float | None:
    """Extract completed_at timestamp from result data."""
    completed_at = data.get("completed_at")
    if isinstance(completed_at, (int, float)):
        return float(completed_at)
    return None


def _summarize_completed(
    data: dict[str, object], args_hash: str | None
) -> PreCommitRunSummary:
    """Build summary for a completed run."""
    raw_result = data.get("result")
    if not isinstance(raw_result, dict):
        return PreCommitRunSummary(
            status="error",
            args_hash=args_hash,
            error="Completed worker result missing 'result' object",
        )
    result_obj = cast(dict[str, object], raw_result)
    preflight = result_obj.get("preflight_passed")
    docs_phase = result_obj.get("docs_phase_passed")
    coverage = result_obj.get("coverage")
    return PreCommitRunSummary(
        status="completed",
        args_hash=args_hash,
        checks=_extract_checks_list(result_obj),
        preflight_passed=bool(preflight) if preflight is not None else None,
        docs_phase_passed=bool(docs_phase) if docs_phase is not None else None,
        coverage=float(coverage) if isinstance(coverage, (int, float)) else None,
        completed_at=_extract_completed_at(data),
    )


def _summarize_result(
    data: dict[str, object], args_hash: str | None
) -> PreCommitRunSummary:
    """Build a PreCommitRunSummary from detached result data."""
    status_value = str(data.get("status") or "unknown")
    if status_value == "completed":
        return _summarize_completed(data, args_hash)
    error_val = data.get("error")
    if status_value == "running":
        return PreCommitRunSummary(
            status="running",
            args_hash=args_hash,
            error=str(error_val) if error_val else "",
        )
    if status_value == "error":
        return PreCommitRunSummary(
            status="error",
            args_hash=args_hash,
            error=str(error_val) if error_val else "Detached worker reported error",
        )
    return PreCommitRunSummary(
        status="unknown",
        args_hash=args_hash,
        error=str(error_val) if error_val else "Unknown detached worker status",
    )


async def get_last_pre_commit_status_impl(
    project_root: Path,
    ctx: MCPContext | None,
) -> dict[str, Any]:
    """Return summary of the most recent detached pre-commit run.

    This helper is used by the MCP tool to provide a lightweight way for agents
    to inspect the latest execute_pre_commit_checks run without starting a new
    run. It is safe to call frequently and returns quickly.
    """
    # Avoid unused-variable warning for ctx; reserved for future logging.
    _ = ctx
    session_dir = _session_dir(project_root)
    result_files = _iter_result_files(session_dir)
    if not result_files:
        return PreCommitRunSummary(status="no_runs").to_dict()
    latest = result_files[0]
    data = _load_result(latest)
    if data is None:
        return PreCommitRunSummary(
            status="error",
            error=f"Failed to read or parse result file: {latest.name}",
        ).to_dict()
    args_hash: str | None = None
    name = latest.name
    if name.startswith(_RESULT_PREFIX) and name.endswith(_RESULT_SUFFIX):
        args_hash = name[len(_RESULT_PREFIX) : -len(_RESULT_SUFFIX)]
    summary = _summarize_result(data, args_hash=args_hash)
    return summary.to_dict()


async def get_pre_commit_status_impl(
    project_root: Path,
    job_id: str,
    ctx: MCPContext | None,
) -> dict[str, Any]:
    """Return summary of a specific detached pre-commit job by job_id."""
    _ = ctx
    session_dir = _session_dir(project_root)
    path = session_dir / f"{_RESULT_PREFIX}{job_id}{_RESULT_SUFFIX}"
    if not path.exists():
        return PreCommitRunSummary(status="no_runs", args_hash=job_id).to_dict()
    data = _load_result(path)
    if data is None:
        return PreCommitRunSummary(
            status="error",
            args_hash=job_id,
            error=f"Failed to read or parse result file: {path.name}",
        ).to_dict()
    summary = _summarize_result(data, args_hash=job_id)
    return summary.to_dict()
