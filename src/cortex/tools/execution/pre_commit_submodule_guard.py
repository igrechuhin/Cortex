"""Block pre-commit / Phase A when git submodules are dirty or out of sync.

Ensures the parent repo does not record a gitlink while a submodule has
uncommitted work or its checkout disagrees with the superproject index.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from enum import StrEnum
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import ModelDict, OperationStatus
from cortex.services.framework_adapters.base import CheckResult
from cortex.tools.execution.pre_commit_helpers import ensure_json_serializable_for_mcp
from cortex.tools.execution.pre_commit_helpers_models import PreCommitResult
from cortex.tools.execution.pre_commit_helpers_remaining import (
    truncate_large_logs_in_data,
)

logger = logging.getLogger(__name__)

SUBMODULE_STATUS_LINE = re.compile(
    r"^([+\-U ])([0-9a-f]{4,40}) (.+)$",
    re.IGNORECASE,
)

REMEDIATION = (
    "Inside each listed submodule path, commit or discard local changes, then "
    "in the superproject run `git add <submodule-path>` so the gitlink matches "
    "the submodule commit you intend. If the submodule was advanced on purpose, "
    "stage the new gitlink before committing the parent."
)

SUBMODULE_INIT_REMEDIATION = "git submodule update --init --recursive"


class SubmoduleHygieneMode(StrEnum):
    """Execution context for submodule hygiene behavior."""

    COMMIT = "commit"
    FIX = "fix"


class SubmoduleHygieneCode(StrEnum):
    """Why the submodule failed the hygiene gate."""

    OUT_OF_SYNC = "out_of_sync"
    MERGE_CONFLICT = "merge_conflict"
    DIRTY_WORKTREE = "dirty_worktree"


class SubmoduleHygieneViolation(BaseModel):
    """One submodule hygiene failure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    code: SubmoduleHygieneCode


class SubmoduleHygieneReport(BaseModel):
    """Result of scanning the superproject for submodule issues."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    violations: tuple[SubmoduleHygieneViolation, ...] = Field(default_factory=tuple)


def _resolve_hygiene_mode(mode: SubmoduleHygieneMode | None) -> SubmoduleHygieneMode:
    """Resolve explicit mode first, then environment override, then default."""
    if mode is not None:
        return mode
    raw = os.environ.get("CORTEX_SUBMODULE_HYGIENE_MODE", "").strip().lower()
    if raw == SubmoduleHygieneMode.COMMIT.value:
        return SubmoduleHygieneMode.COMMIT
    if raw == SubmoduleHygieneMode.FIX.value:
        return SubmoduleHygieneMode.FIX
    # Default to FIX semantics: treat "dirty_worktree" as fixable/work-in-progress
    # rather than a blocker for quality/test execution. Still block the more
    # severe out-of-sync and merge-conflict states.
    return SubmoduleHygieneMode.FIX


def _filter_violations_for_mode(
    violations: tuple[SubmoduleHygieneViolation, ...],
    mode: SubmoduleHygieneMode,
) -> tuple[SubmoduleHygieneViolation, ...]:
    """Apply mode-specific filtering for gate-blocking violations."""
    if mode is SubmoduleHygieneMode.FIX:
        return tuple(
            v for v in violations if v.code is not SubmoduleHygieneCode.DIRTY_WORKTREE
        )
    return violations


def _parse_submodule_status_line(line: str) -> tuple[str, str] | None:
    """Parse one line of `git submodule status --recursive`; return (prefix, path)."""
    # Do not str.strip(): a clean submodule line begins with a space status marker.
    trimmed = line.rstrip("\n\r")
    if not trimmed:
        return None
    match = SUBMODULE_STATUS_LINE.match(trimmed)
    if not match:
        return None
    prefix, _sha, rest = match.groups()
    path = rest.split(" (", 1)[0].strip()
    if not path:
        return None
    return prefix, path


def _submodule_porcelain_non_empty(sub_abs: Path, timeout: float) -> bool:
    """True when the submodule has unstaged/untracked changes outside ignored noise paths."""
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(sub_abs),
                "status",
                "--porcelain",
                "--",
                ":/",
                ":(exclude).cache",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "submodule_hygiene: git status --porcelain timed out after %ss for %s",
            timeout,
            sub_abs,
        )
        return False
    return proc.returncode == 0 and bool(proc.stdout.strip())


def _git_submodule_status_text(project_root: Path, status_timeout: float) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(project_root), "submodule", "status", "--recursive"],
            capture_output=True,
            text=True,
            timeout=status_timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "submodule_hygiene: git submodule status timed out after %ss (root=%s)",
            status_timeout,
            project_root,
        )
        return None
    if proc.returncode == 0:
        return proc.stdout
    logger.warning(
        "submodule_hygiene: git submodule status failed (rc=%s): %s",
        proc.returncode,
        (proc.stderr or proc.stdout or "")[:500],
    )
    return None


def _maybe_dirty_worktree_violation(
    rel_path: str, project_root: Path, porcelain_timeout: float
) -> SubmoduleHygieneViolation | None:
    sub_abs = (project_root / rel_path).resolve()
    if not (sub_abs / ".git").exists():
        return None
    if not _submodule_porcelain_non_empty(sub_abs, porcelain_timeout):
        return None
    return SubmoduleHygieneViolation(
        path=rel_path, code=SubmoduleHygieneCode.DIRTY_WORKTREE
    )


def _append_violation_for_prefix(
    prefix: str,
    rel_path: str,
    project_root: Path,
    porcelain_timeout: float,
    violations: list[SubmoduleHygieneViolation],
) -> None:
    if prefix == "-":
        return
    if prefix == "U":
        v = SubmoduleHygieneViolation(
            path=rel_path, code=SubmoduleHygieneCode.MERGE_CONFLICT
        )
    elif prefix == "+":
        v = SubmoduleHygieneViolation(
            path=rel_path, code=SubmoduleHygieneCode.OUT_OF_SYNC
        )
    elif prefix != " ":
        return
    else:
        found = _maybe_dirty_worktree_violation(
            rel_path, project_root, porcelain_timeout
        )
        if found is None:
            return
        violations.append(found)
        return
    violations.append(v)


def _violations_from_submodule_status(
    status_text: str,
    project_root: Path,
    porcelain_timeout: float,
) -> tuple[SubmoduleHygieneViolation, ...]:
    violations: list[SubmoduleHygieneViolation] = []
    seen: set[str] = set()
    for line in status_text.splitlines():
        parsed = _parse_submodule_status_line(line)
        if parsed is None:
            continue
        prefix, rel_path = parsed
        if rel_path in seen:
            continue
        seen.add(rel_path)
        _append_violation_for_prefix(
            prefix, rel_path, project_root, porcelain_timeout, violations
        )
    return tuple(violations)


def scan_submodule_hygiene(
    project_root: Path,
    *,
    status_timeout: float = 120.0,
    porcelain_timeout: float = 60.0,
) -> SubmoduleHygieneReport:
    """Inspect submodules under project_root; empty report when skipped or clean."""
    if not (project_root / ".git").exists():
        return SubmoduleHygieneReport()
    text = _git_submodule_status_text(project_root, status_timeout)
    if text is None:
        return SubmoduleHygieneReport()
    return SubmoduleHygieneReport(
        violations=_violations_from_submodule_status(
            text, project_root, porcelain_timeout
        )
    )


def _violation_messages(report: SubmoduleHygieneReport) -> list[str]:
    lines: list[str] = []
    for v in report.violations:
        if v.code is SubmoduleHygieneCode.OUT_OF_SYNC:
            lines.append(
                f"{v.path}: submodule checkout differs from the index "
                + f"(stage the intended gitlink with `git add {v.path}`)."
            )
        elif v.code is SubmoduleHygieneCode.MERGE_CONFLICT:
            lines.append(
                f"{v.path}: submodule merge conflict — resolve before committing."
            )
        else:
            lines.append(
                f"{v.path}: uncommitted or untracked changes inside the submodule."
            )
    return lines


def _make_submodule_hygiene_check(messages: list[str], detail: str) -> CheckResult:
    """Build the submodule_hygiene CheckResult payload."""
    return CheckResult(
        check_type="submodule_hygiene",
        success=False,
        output=detail[:8000],
        errors=messages + [REMEDIATION],
    )


def _make_precommit_result(check: CheckResult, total_errors: int) -> PreCommitResult:
    """Build PreCommitResult wrapper for the hygiene failure."""
    return PreCommitResult(
        status=OperationStatus.ERROR,
        language=None,
        checks_performed=["submodule_hygiene"],
        results={"submodule_hygiene": check},
        total_errors=total_errors,
        total_warnings=0,
        success=False,
    )


def _finalize_precommit_block_response(
    result: PreCommitResult,
    *,
    effective_mode: SubmoduleHygieneMode,
    effective_violations: tuple[SubmoduleHygieneViolation, ...],
) -> ModelDict:
    """Attach remediation metadata for MCP /cortex/fix routing."""
    data = truncate_large_logs_in_data(result.model_dump(mode="json"))
    merged: dict[str, object] = dict(
        ensure_json_serializable_for_mcp(cast(ModelDict, data))
    )
    merged.update(
        {
            "remediation": SUBMODULE_INIT_REMEDIATION,
            "submodule_first_required": True,
            "submodule_hygiene_violations": [
                {"path": v.path, "code": v.code.value} for v in effective_violations
            ],
            "submodule_hygiene_mode": effective_mode.value,
        }
    )
    return cast(ModelDict, merged)


def _build_precommit_block_response(
    effective_mode: SubmoduleHygieneMode,
    effective_violations: tuple[SubmoduleHygieneViolation, ...],
) -> ModelDict:
    """Build the MCP pre-commit shaped response payload."""
    report = SubmoduleHygieneReport(violations=effective_violations)
    messages = _violation_messages(report)
    detail = " ".join(messages) + " " + REMEDIATION
    check = _make_submodule_hygiene_check(messages, detail)
    result = _make_precommit_result(check, len(effective_violations))
    return _finalize_precommit_block_response(
        result,
        effective_mode=effective_mode,
        effective_violations=effective_violations,
    )


def precommit_block_response(
    project_root: Path, *, mode: SubmoduleHygieneMode | None = None
) -> ModelDict | None:
    """If submodules are unsafe to commit against, return a PreCommit-shaped dict."""
    report = scan_submodule_hygiene(project_root)
    effective_mode = _resolve_hygiene_mode(mode)
    effective_violations = _filter_violations_for_mode(
        report.violations, effective_mode
    )
    if not effective_violations:
        return None
    return _build_precommit_block_response(effective_mode, effective_violations)


__all__ = [
    "REMEDIATION",
    "SUBMODULE_INIT_REMEDIATION",
    "SubmoduleHygieneMode",
    "SubmoduleHygieneCode",
    "SubmoduleHygieneReport",
    "SubmoduleHygieneViolation",
    "precommit_block_response",
    "scan_submodule_hygiene",
]
