"""Helpers for summarizing detached pre-commit runs.

This module reads result files written by the detached pre-commit worker and
returns a compact status summary suitable for MCP tools and prompts.
"""

from __future__ import annotations

import json
import time
from enum import StrEnum
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict

from cortex.core.context_logging import MCPContext
from cortex.core.models import ModelDict
from cortex.tools.execution.session_paths import session_dir

_RESULT_PREFIX = "pre_commit_result_"
_RESULT_SUFFIX = ".json"
_MAX_RUNNING_AGE_SECONDS = 1800.0


class PreCommitJobStatusEnum(StrEnum):
    """Lifecycle status of a detached pre-commit job."""

    NO_RUNS = "no_runs"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class PreCommitRunSummary(BaseModel):
    """Summary of the most recent detached pre-commit run."""

    model_config = ConfigDict(extra="forbid")

    status: PreCommitJobStatusEnum
    args_hash: str | None = None
    checks: list[str] | None = None
    preflight_passed: bool | None = None
    docs_phase_passed: bool | None = None
    coverage: float | None = None
    completed_at: float | None = None
    error: str | None = None
    log_path: str | None = None
    checks_summary: dict[str, bool] | None = None

    def to_summary_dict(self) -> ModelDict:
        """Convert summary to a JSON-serializable dict for MCP payloads."""
        return cast(ModelDict, self.model_dump(mode="json", exclude_none=True))


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


def _build_checks_summary(result_obj: dict[str, object]) -> dict[str, bool] | None:
    """Build a coarse per-category checks summary from a completed result object."""
    raw_results = result_obj.get("results")
    if not isinstance(raw_results, dict):
        return None
    results_dict = cast(dict[str, object], raw_results)
    summary: dict[str, bool] = {}
    for key in ("tests", "format", "type_check", "quality"):
        value = results_dict.get(key)
        if isinstance(value, dict):
            inner = cast(dict[str, object], value)
            success_value = inner.get("success")
            if isinstance(success_value, bool):
                summary[key] = success_value
    return summary or None


def _summarize_completed(
    data: dict[str, object], args_hash: str | None, log_path: str | None
) -> PreCommitRunSummary:
    """Build summary for a completed run."""
    raw_result = data.get("result")
    if not isinstance(raw_result, dict):
        return PreCommitRunSummary(
            status=PreCommitJobStatusEnum.ERROR,
            args_hash=args_hash,
            error="Completed worker result missing 'result' object",
        )
    result_obj = cast(dict[str, object], raw_result)
    preflight = result_obj.get("preflight_passed")
    docs_phase = result_obj.get("docs_phase_passed")
    coverage = result_obj.get("coverage")
    checks_summary = _build_checks_summary(result_obj)
    return PreCommitRunSummary(
        status=PreCommitJobStatusEnum.COMPLETED,
        args_hash=args_hash,
        checks=_extract_checks_list(result_obj),
        preflight_passed=bool(preflight) if preflight is not None else None,
        docs_phase_passed=bool(docs_phase) if docs_phase is not None else None,
        coverage=float(coverage) if isinstance(coverage, (int, float)) else None,
        completed_at=_extract_completed_at(data),
        log_path=log_path,
        checks_summary=checks_summary,
    )


def _summarize_timeout_status(
    data: dict[str, object],
    args_hash: str | None,
    log_path: str | None,
    default_message: str,
) -> PreCommitRunSummary:
    """Build summary for timeout-like statuses."""
    error_val = data.get("error")
    return PreCommitRunSummary(
        status=PreCommitJobStatusEnum.TIMEOUT,
        args_hash=args_hash,
        completed_at=_extract_completed_at(data),
        error=str(error_val) if error_val else default_message,
        log_path=log_path,
    )


def _summarize_running_status(
    data: dict[str, object],
    args_hash: str | None,
    log_path: str | None,
) -> PreCommitRunSummary:
    """Build summary for a running job, with timeout promotion."""
    error_val = data.get("error")
    started_at = data.get("started_at")
    if isinstance(started_at, (int, float)):
        age = time.time() - float(started_at)
        if age >= _MAX_RUNNING_AGE_SECONDS:
            return _summarize_timeout_status(
                data=data,
                args_hash=args_hash,
                log_path=log_path,
                default_message=(
                    "Pre-commit job exceeded maximum allowed duration "
                    f"of {_MAX_RUNNING_AGE_SECONDS:.0f}s"
                ),
            )
    return PreCommitRunSummary(
        status=PreCommitJobStatusEnum.RUNNING,
        args_hash=args_hash,
        error=str(error_val) if error_val else "",
        log_path=log_path,
    )


def _summarize_result_error_or_unknown(
    status_value: str,
    data: dict[str, object],
    args_hash: str | None,
    log_path: str | None,
) -> PreCommitRunSummary:
    """Build summary for error or unknown status."""
    error_val = data.get("error")
    if status_value == "error":
        msg = str(error_val) if error_val else "Detached worker reported error"
        return PreCommitRunSummary(
            status=PreCommitJobStatusEnum.ERROR,
            args_hash=args_hash,
            error=msg,
            log_path=log_path,
        )
    msg = str(error_val) if error_val else "Unknown detached worker status"
    return PreCommitRunSummary(
        status=PreCommitJobStatusEnum.UNKNOWN,
        args_hash=args_hash,
        error=msg,
        log_path=log_path,
    )


def _summarize_result(
    data: dict[str, object], args_hash: str | None, log_path: str | None
) -> PreCommitRunSummary:
    """Build a PreCommitRunSummary from detached result data."""
    status_value = str(data.get("status") or "unknown")
    if status_value == "queued":
        error_val = data.get("error")
        return PreCommitRunSummary(
            status=PreCommitJobStatusEnum.QUEUED,
            args_hash=args_hash,
            error=str(error_val) if error_val else None,
            log_path=log_path,
        )
    if status_value == "completed":
        return _summarize_completed(data, args_hash, log_path)
    if status_value == "timeout":
        return _summarize_timeout_status(
            data=data,
            args_hash=args_hash,
            log_path=log_path,
            default_message="Pre-commit job exceeded configured timeout",
        )
    if status_value == "running":
        return _summarize_running_status(data, args_hash, log_path)
    return _summarize_result_error_or_unknown(status_value, data, args_hash, log_path)


async def get_last_pre_commit_status_impl(
    project_root: Path,
    ctx: MCPContext | None,
) -> ModelDict:
    """Return summary of the most recent detached pre-commit run.

    This helper is used by the MCP tool to provide a lightweight way for agents
    to inspect the latest execute_pre_commit_checks run without starting a new
    run. It is safe to call frequently and returns quickly.
    """
    # Avoid unused-variable warning for ctx; reserved for future logging.
    _ = ctx
    sd = session_dir(project_root)
    result_files = _iter_result_files(sd)
    if not result_files:
        return PreCommitRunSummary(
            status=PreCommitJobStatusEnum.NO_RUNS
        ).to_summary_dict()
    latest = result_files[0]
    data = _load_result(latest)
    if data is None:
        return PreCommitRunSummary(
            status=PreCommitJobStatusEnum.ERROR,
            error=f"Failed to read or parse result file: {latest.name}",
        ).to_summary_dict()
    args_hash: str | None = None
    name = latest.name
    if name.startswith(_RESULT_PREFIX) and name.endswith(_RESULT_SUFFIX):
        args_hash = name[len(_RESULT_PREFIX) : -len(_RESULT_SUFFIX)]
    log_path: str | None = None
    if args_hash is not None:
        log_path = str(sd / f"pre_commit_worker_{args_hash}.log")
    summary = _summarize_result(data, args_hash=args_hash, log_path=log_path)
    return summary.to_summary_dict()


async def get_pre_commit_status_impl(
    project_root: Path,
    job_id: str,
    ctx: MCPContext | None,
) -> ModelDict:
    """Return summary of a specific detached pre-commit job by job_id."""
    _ = ctx
    sd = session_dir(project_root)
    path = sd / f"{_RESULT_PREFIX}{job_id}{_RESULT_SUFFIX}"
    if not path.exists():
        return PreCommitRunSummary(
            status=PreCommitJobStatusEnum.NO_RUNS, args_hash=job_id
        ).to_summary_dict()
    data = _load_result(path)
    if data is None:
        return PreCommitRunSummary(
            status=PreCommitJobStatusEnum.ERROR,
            args_hash=job_id,
            error=f"Failed to read or parse result file: {path.name}",
        ).to_summary_dict()
    log_path = str(sd / f"pre_commit_worker_{job_id}.log")
    summary = _summarize_result(data, args_hash=job_id, log_path=log_path)
    return summary.to_summary_dict()
