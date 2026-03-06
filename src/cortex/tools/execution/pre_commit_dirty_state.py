"""Dirty-state tracking for pre-commit pipeline optimization.

Tracks file fingerprints between Phase A and Step 12 to skip redundant
checks when no source files changed between phases.

Phase 89: Commit Pipeline Efficiency — Reduce Redundant Check Runs.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

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


def _compute_git_file_hash(project_root: Path) -> PipelineFingerprint:
    """Compute fingerprint from git status of staged and modified files."""
    source_entries: list[str] = []
    all_entries: list[str] = []
    _collect_entries_from_diff(project_root, source_entries, all_entries)
    _collect_untracked(project_root, source_entries, all_entries)
    source_entries.sort()
    all_entries.sort()
    source_hash = hashlib.sha256("\n".join(source_entries).encode()).hexdigest()[:16]
    all_hash = hashlib.sha256("\n".join(all_entries).encode()).hexdigest()[:16]
    return PipelineFingerprint(
        source_hash=source_hash,
        all_files_hash=all_hash,
        source_file_count=len(source_entries),
        total_file_count=len(all_entries),
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
    _active: bool = field(default=False, init=False)

    @classmethod
    def get_instance(cls) -> PipelineDirtyTracker:
        """Get or create the singleton tracker instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the tracker (for testing or new pipeline runs)."""
        cls._instance = None

    def record_phase_a(self, project_root: Path, passed: bool) -> None:
        """Record Phase A completion and compute fingerprint."""
        self.project_root = project_root
        self.phase_a_passed = passed
        if passed:
            self.phase_a_fingerprint = _compute_git_file_hash(project_root)
            self._active = True
            logger.info(
                "Phase A fingerprint recorded: source=%s, files=%d",
                self.phase_a_fingerprint.source_hash,
                self.phase_a_fingerprint.source_file_count,
            )
        else:
            self.phase_a_fingerprint = None
            self._active = False

    def can_skip_check(self, check_name: str) -> SkipDecision:
        """Determine if a Step 12 check can be skipped."""
        if not self._active or self.phase_a_fingerprint is None:
            return SkipDecision(
                can_skip=False,
                reason="No Phase A fingerprint recorded",
            )
        if self.project_root is None:
            return SkipDecision(can_skip=False, reason="No project root")
        current = _compute_git_file_hash(self.project_root)
        if check_name in _SOURCE_DEPENDENT_CHECKS:
            if current.source_hash == self.phase_a_fingerprint.source_hash:
                return SkipDecision(
                    can_skip=True,
                    reason=(
                        f"No source files changed since Phase A "
                        f"(hash={current.source_hash[:8]})"
                    ),
                )
            return SkipDecision(
                can_skip=False,
                reason=(
                    f"Source files changed: "
                    f"Phase A={self.phase_a_fingerprint.source_hash[:8]}, "
                    f"current={current.source_hash[:8]}"
                ),
            )
        return SkipDecision(
            can_skip=False,
            reason=f"Check '{check_name}' always re-runs",
        )

    @property
    def is_active(self) -> bool:
        """Whether dirty tracking is active (Phase A was recorded)."""
        return self._active
