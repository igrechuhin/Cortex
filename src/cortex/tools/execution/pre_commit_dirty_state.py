"""Dirty-state tracking for pre-commit pipeline optimization.

Tracks file fingerprints between Phase A and Step 12 to skip redundant
checks when no source files changed between phases.

Phase 89: Commit Pipeline Efficiency — Reduce Redundant Check Runs.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from cortex.tools.execution.pre_commit_fingerprint_store import (
    clear_phase_a_fingerprint,
    load_fingerprint_record,
    save_fingerprint_record,
)

logger = logging.getLogger(__name__)

# File extensions considered "source" for dirty-state tracking.
# Changes to these extensions invalidate the fingerprint.
_SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".java", ".swift", ".kt"}
)

# Extensions that do NOT invalidate source checks (docs, config, markdown).
_NON_SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".mdc", ".json", ".yaml", ".yml", ".toml", ".txt", ".cfg", ".ini"}
)

# Check names that depend on source file content (skip when source hash unchanged).
_SOURCE_DEPENDENT_CHECKS: frozenset[str] = frozenset(
    {
        "type_check",
        "tests",
        "format",
        "quality",
        "fix_errors",
        "synapse_format",
        "synapse_lint",
        "format_ci_parity",
    }
)


@dataclass(frozen=True)
class PipelineFingerprint:
    """Immutable fingerprint of file state at a point in time."""

    source_hash: str
    all_files_hash: str
    source_file_count: int
    total_file_count: int


@dataclass
class SkipDecision:
    """Decision on whether a check can be skipped."""

    can_skip: bool
    reason: str


@dataclass(frozen=True)
class CheckCleanResult:
    """Last known clean result metadata for a single check."""

    passed: bool
    step: str
    timestamp: str


def _bool_dict() -> dict[str, bool]:
    return {}


def _clean_result_dict() -> dict[str, CheckCleanResult]:
    return {}


def _parse_diff_lines(
    stdout: str,
    source_entries: list[str],
    all_entries: list[str],
) -> None:
    """Parse git diff/ls-files stdout into source_entries and all_entries."""
    for line in stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status, filepath = parts
            entry = f"{status}\t{filepath}"
        else:
            filepath = line.strip()
            entry = f"?\t{filepath}"
        all_entries.append(entry)
        if Path(filepath).suffix.lower() in _SOURCE_EXTENSIONS:
            source_entries.append(entry)


def _collect_entries_from_diff(
    project_root: Path,
    source_entries: list[str],
    all_entries: list[str],
) -> None:
    """Run git diff (cached and unstaged) and collect file entries."""
    for diff_args in (
        ["git", "diff", "--cached", "--name-status"],
        ["git", "diff", "--name-status"],
    ):
        try:
            result = subprocess.run(
                diff_args,
                capture_output=True,
                text=True,
                cwd=str(project_root),
                timeout=10,
            )
            if result.returncode == 0:
                _parse_diff_lines(result.stdout, source_entries, all_entries)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("git diff failed for dirty-state tracking")


def _collect_untracked(
    project_root: Path,
    source_entries: list[str],
    all_entries: list[str],
) -> None:
    """Run git ls-files --others and collect untracked file entries."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=10,
        )
        if result.returncode == 0:
            for filepath in result.stdout.strip().splitlines():
                if filepath:
                    entry = f"?\t{filepath}"
                    all_entries.append(entry)
                    if Path(filepath).suffix.lower() in _SOURCE_EXTENSIONS:
                        source_entries.append(entry)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git ls-files failed for dirty-state tracking")


def _hash_source_contents(project_root: Path, source_entries: list[str]) -> str:
    """Hash the names AND current bytes of every changed source file.

    Names alone are not enough: an autofix pass rewrites file contents while
    leaving the changed-file set identical, and a name-only hash would then
    skip the very tests meant to validate that rewrite.
    """
    digest = hashlib.sha256()
    for entry in source_entries:
        digest.update(entry.encode())
        digest.update(b"\0")
        # AI: rename entries are "R100\told\tnew" — the live path is the last field.
        path = project_root / entry.split("\t")[-1]
        try:
            digest.update(path.read_bytes())
        except OSError:
            # Deleted or unreadable: a stable marker still differs from content.
            digest.update(b"<unreadable>")
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def compute_git_file_hash(project_root: Path) -> PipelineFingerprint:
    """Compute fingerprint from git status of staged and modified files."""
    source_entries: list[str] = []
    all_entries: list[str] = []
    _collect_entries_from_diff(project_root, source_entries, all_entries)
    _collect_untracked(project_root, source_entries, all_entries)
    source_entries.sort()
    all_entries.sort()
    source_hash = _hash_source_contents(project_root, source_entries)
    all_hash = hashlib.sha256("\n".join(all_entries).encode()).hexdigest()[:16]
    return PipelineFingerprint(
        source_hash=source_hash,
        all_files_hash=all_hash,
        source_file_count=len(source_entries),
        total_file_count=len(all_entries),
    )


def save_phase_a_fingerprint(project_root: Path, fp: PipelineFingerprint) -> None:
    """Persist a Phase A fingerprint together with git HEAD and a timestamp."""
    save_fingerprint_record(
        project_root,
        source_hash=fp.source_hash,
        all_files_hash=fp.all_files_hash,
        source_file_count=fp.source_file_count,
        total_file_count=fp.total_file_count,
    )


def load_phase_a_fingerprint(project_root: Path) -> PipelineFingerprint | None:
    """Load a valid persisted Phase A fingerprint, or None when not trustworthy."""
    record = load_fingerprint_record(project_root)
    if record is None:
        return None
    return PipelineFingerprint(
        source_hash=record.source_hash,
        all_files_hash=record.all_files_hash,
        source_file_count=record.source_file_count,
        total_file_count=record.total_file_count,
    )


@dataclass
class PipelineDirtyTracker:
    """Tracks dirty state across pipeline phases.

    Singleton-like usage: one instance per pipeline run. After Phase A
    completes, call `record_phase_a()` to store the fingerprint. Before
    Step 12 checks, call `can_skip_check()` to determine if re-run is
    needed.
    """

    _instance: ClassVar[PipelineDirtyTracker | None] = None

    project_root: Path | None = None
    phase_a_fingerprint: PipelineFingerprint | None = None
    phase_a_passed: bool = False
    dirty_checks: dict[str, bool] = field(default_factory=_bool_dict)
    last_clean_results: dict[str, CheckCleanResult] = field(
        default_factory=_clean_result_dict
    )
    _active: bool = field(default=False, init=False)

    @classmethod
    def get_instance(cls) -> PipelineDirtyTracker:
        """Get or create the singleton tracker instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls, project_root: Path | None = None) -> None:
        """Reset the tracker and drop any persisted fingerprint."""
        root = project_root or (
            cls._instance.project_root if cls._instance is not None else None
        )
        if root is not None:
            clear_phase_a_fingerprint(root)
        cls._instance = None

    def record_phase_a(self, project_root: Path, passed: bool) -> None:
        """Record Phase A completion, compute fingerprint, and persist it."""
        self.project_root = project_root
        self.phase_a_passed = passed
        if passed:
            self.phase_a_fingerprint = compute_git_file_hash(project_root)
            self._active = True
            save_phase_a_fingerprint(project_root, self.phase_a_fingerprint)
            logger.info(
                "Phase A fingerprint recorded: source=%s, files=%d",
                self.phase_a_fingerprint.source_hash,
                self.phase_a_fingerprint.source_file_count,
            )
        else:
            self.phase_a_fingerprint = None
            self._active = False
            clear_phase_a_fingerprint(project_root)

    def ensure_loaded(self, project_root: Path) -> None:
        """Rehydrate the fingerprint from disk when this process has none.

        The Phase A gate records the fingerprint in the MCP server process,
        but the checks themselves run in a detached worker with a fresh
        interpreter. Without this the worker never sees Phase A's state.
        """
        if self.phase_a_fingerprint is not None:
            return
        persisted = load_phase_a_fingerprint(project_root)
        if persisted is None:
            return
        self.project_root = project_root
        self.phase_a_fingerprint = persisted
        self.phase_a_passed = True
        self._active = True

    def partition_skippable(
        self, check_names: Sequence[str]
    ) -> tuple[list[str], dict[str, str]]:
        """Split checks into (to_run, {skipped: reason}) using one git snapshot.

        Per-check, not all-or-nothing: an always-run check no longer drags the
        expensive source-dependent checks along with it.
        """
        if not self._active or self.phase_a_fingerprint is None:
            return list(check_names), {}
        if self.project_root is None:
            return list(check_names), {}
        current = compute_git_file_hash(self.project_root)
        to_run: list[str] = []
        skipped: dict[str, str] = {}
        for name in check_names:
            decision = self._decide(name, current)
            if decision.can_skip:
                skipped[name] = decision.reason
            else:
                to_run.append(name)
        return to_run, skipped

    def mark_dirty(self, check_name: str) -> None:
        """Mark a check as dirty, forcing it to re-run in final validation."""
        self.dirty_checks[check_name] = True

    def mark_clean(
        self,
        check_name: str,
        *,
        step: str,
        timestamp: str,
    ) -> None:
        """Mark a check as clean and record last clean result metadata."""
        self.dirty_checks[check_name] = False
        self.last_clean_results[check_name] = CheckCleanResult(
            passed=True,
            step=step,
            timestamp=timestamp,
        )

    def can_skip_check(self, check_name: str) -> SkipDecision:
        """Determine if a Step 12 check can be skipped."""
        if self.dirty_checks.get(check_name, False):
            return SkipDecision(
                False, "Check explicitly marked dirty in pipeline state"
            )
        if not self._active or self.phase_a_fingerprint is None:
            return SkipDecision(False, "No Phase A fingerprint recorded")
        if self.project_root is None:
            return SkipDecision(False, "No project root")

        return self._decide(check_name, compute_git_file_hash(self.project_root))

    def _decide(self, check_name: str, current: PipelineFingerprint) -> SkipDecision:
        """Decide skippability of one check against an already-computed snapshot."""
        if self.dirty_checks.get(check_name, False):
            return SkipDecision(
                False, "Check explicitly marked dirty in pipeline state"
            )
        if self.phase_a_fingerprint is None:
            return SkipDecision(False, "No Phase A fingerprint recorded")
        if check_name not in _SOURCE_DEPENDENT_CHECKS:
            return SkipDecision(False, f"Check '{check_name}' always re-runs")

        phase_a_hash = self.phase_a_fingerprint.source_hash[:8]
        current_hash = current.source_hash[:8]
        if current.source_hash == self.phase_a_fingerprint.source_hash:
            return SkipDecision(
                True, f"No source files changed since Phase A (hash={current_hash})"
            )
        return SkipDecision(
            False,
            f"Source files changed: Phase A={phase_a_hash}, current={current_hash}",
        )

    @property
    def is_active(self) -> bool:
        """Whether dirty tracking is active (Phase A was recorded)."""
        return self._active


def partition_skippable_checks(
    project_root: Path, check_names: Sequence[str]
) -> tuple[list[str], dict[str, str]]:
    """Split checks into (to_run, {skipped: reason}), rehydrating from disk.

    Safe to call from a fresh interpreter such as the detached worker.
    """
    tracker = PipelineDirtyTracker.get_instance()
    tracker.ensure_loaded(project_root)
    return tracker.partition_skippable(check_names)
