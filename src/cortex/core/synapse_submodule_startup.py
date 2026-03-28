"""Best-effort Synapse submodule sync before MCP server listens (non-fatal).

Runs ``git submodule update --init --recursive`` from the detected project root
when safe: not opted out, superproject is a git checkout, and ``.cortex/synapse``
has no local changes. Failures and timeouts are logged; the server still starts.
"""

from __future__ import annotations

import logging
import os
import subprocess
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.execution.pre_commit_submodule_guard import (
    submodule_path_has_local_changes,
)

logger = logging.getLogger(__name__)

DEFAULT_UPDATE_TIMEOUT = 300.0
DEFAULT_PORCELAIN_TIMEOUT = 60.0


class SynapseStartupSyncOutcome(StrEnum):
    """Result category for MCP startup Synapse submodule sync."""

    SKIPPED_OPT_OUT = "skipped_opt_out"
    SKIPPED_NOT_GIT_ROOT = "skipped_not_git_root"
    SKIPPED_DIRTY_WORKTREE = "skipped_dirty_worktree"
    SUCCESS = "success"
    GIT_ERROR = "git_error"
    GIT_TIMEOUT = "git_timeout"


class SynapseStartupSyncResult(BaseModel):
    """Structured outcome of startup submodule sync."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: SynapseStartupSyncOutcome
    detail: str = Field(default="")


def _env_opt_out() -> bool:
    raw = os.environ.get("CORTEX_SKIP_SYNAPSE_UPDATE", "").strip().lower()
    return raw in ("1", "true", "yes")


def _skipped_opt_out() -> SynapseStartupSyncResult:
    logger.info(
        "MCP startup: skipping Synapse submodule sync (CORTEX_SKIP_SYNAPSE_UPDATE is set)"
    )
    return SynapseStartupSyncResult(outcome=SynapseStartupSyncOutcome.SKIPPED_OPT_OUT)


def _skipped_not_git(root: Path) -> SynapseStartupSyncResult:
    logger.debug(
        "MCP startup: skipping Synapse submodule sync (not a git checkout: %s)",
        root,
    )
    return SynapseStartupSyncResult(
        outcome=SynapseStartupSyncOutcome.SKIPPED_NOT_GIT_ROOT,
        detail=str(root),
    )


def _skipped_dirty(synapse_abs: Path) -> SynapseStartupSyncResult:
    logger.warning(
        "MCP startup: skipping Synapse submodule sync — %s has local changes (commit, stash, or discard to avoid data loss). Manual: git submodule update --init --recursive from repo root.",
        synapse_abs,
    )
    return SynapseStartupSyncResult(
        outcome=SynapseStartupSyncOutcome.SKIPPED_DIRTY_WORKTREE,
        detail=str(synapse_abs),
    )


def _submodule_update_result_from_proc(
    proc: subprocess.CompletedProcess[str],
) -> SynapseStartupSyncResult:
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:800]
        logger.warning(
            "MCP startup: Synapse submodule sync failed (rc=%s, non-fatal): %s",
            proc.returncode,
            err or "(no output)",
        )
        return SynapseStartupSyncResult(
            outcome=SynapseStartupSyncOutcome.GIT_ERROR,
            detail=err,
        )

    logger.info(
        "MCP startup: Synapse submodule sync completed (git submodule update --init --recursive)"
    )
    return SynapseStartupSyncResult(outcome=SynapseStartupSyncOutcome.SUCCESS)


def _run_git_submodule_update(
    root: Path, update_timeout: float
) -> SynapseStartupSyncResult:
    cmd = [
        "git",
        "-C",
        str(root),
        "submodule",
        "update",
        "--init",
        "--recursive",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=update_timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "MCP startup: Synapse submodule sync timed out after %ss (non-fatal; server continues). Command: %s",
            update_timeout,
            " ".join(cmd),
        )
        return SynapseStartupSyncResult(
            outcome=SynapseStartupSyncOutcome.GIT_TIMEOUT,
            detail=f"timeout_after_{update_timeout}s",
        )

    return _submodule_update_result_from_proc(proc)


def try_sync_synapse_submodule_at_mcp_startup(
    project_root: Path,
    *,
    update_timeout: float = DEFAULT_UPDATE_TIMEOUT,
    porcelain_timeout: float = DEFAULT_PORCELAIN_TIMEOUT,
) -> SynapseStartupSyncResult:
    """Run submodule update when policy allows; never raises for git failures."""
    if _env_opt_out():
        return _skipped_opt_out()

    root = project_root.resolve()
    if not (root / ".git").exists():
        return _skipped_not_git(root)

    synapse_abs = get_cortex_path(root, CortexResourceType.SYNAPSE).resolve()
    if submodule_path_has_local_changes(synapse_abs, timeout=porcelain_timeout):
        return _skipped_dirty(synapse_abs)

    return _run_git_submodule_update(root, update_timeout)


__all__ = [
    "DEFAULT_PORCELAIN_TIMEOUT",
    "DEFAULT_UPDATE_TIMEOUT",
    "SynapseStartupSyncOutcome",
    "SynapseStartupSyncResult",
    "try_sync_synapse_submodule_at_mcp_startup",
]
