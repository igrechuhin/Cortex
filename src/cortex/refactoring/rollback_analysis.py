"""
Rollback Analysis - Rollback Manager Support

Handle rollback impact analysis operations.
"""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Pydantic Models for Rollback Analysis
# ============================================================================


class FileRollbackAnalysis(BaseModel):
    """Analysis of a single file for rollback."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(..., description="File path")
    exists: bool = Field(..., description="Whether file exists on disk")
    has_conflict: bool = Field(..., description="Whether file has conflicts")
    can_restore: bool = Field(..., description="Whether file can be restored")
    reason: str | None = Field(default=None, description="Reason if cannot restore")


class RollbackImpactAnalysis(BaseModel):
    """Result of rollback impact analysis."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: Literal["success", "error"] = Field(..., description="Analysis status")
    execution_id: str = Field(..., description="Execution ID analyzed")
    snapshot_id: str | None = Field(default=None, description="Snapshot ID if found")
    total_files: int = Field(default=0, ge=0, description="Total files affected")
    conflicts: int = Field(default=0, ge=0, description="Number of conflicts")
    can_rollback_all: bool = Field(
        default=False, description="Whether all files can be rolled back"
    )
    files: list[FileRollbackAnalysis] = Field(
        default_factory=lambda: list[FileRollbackAnalysis](),
        description="Per-file analysis",
    )
    conflicts_detail: list[str] = Field(
        default_factory=list, description="Detailed conflict descriptions"
    )
    message: str | None = Field(default=None, description="Status message for errors")


async def analyze_rollback_impact(
    execution_id: str,
    memory_bank_dir: Path,
    find_snapshot_fn: Callable[[str], Awaitable[str | None]],
    get_affected_files_fn: Callable[[str, str], Awaitable[list[str]]],
    detect_conflicts_fn: Callable[[list[str], str], Awaitable[list[str]]],
) -> RollbackImpactAnalysis:
    """Analyze the impact of rolling back an execution.

    Args:
        execution_id: ID of the execution to analyze
        memory_bank_dir: Memory bank directory
        find_snapshot_fn: Function to find snapshot
        get_affected_files_fn: Function to get affected files
        detect_conflicts_fn: Function to detect conflicts

    Returns:
        RollbackImpactAnalysis with impact analysis
    """
    snapshot_id: str | None = await find_snapshot_fn(execution_id)
    if not snapshot_id:
        return RollbackImpactAnalysis(
            status="error",
            execution_id=execution_id,
            message=f"No snapshot found for execution {execution_id}",
        )

    affected_files: list[str] = await get_affected_files_fn(execution_id, snapshot_id)
    conflicts: list[str] = await detect_conflicts_fn(affected_files, snapshot_id)
    file_analysis = await _analyze_files_for_rollback(
        affected_files, conflicts, memory_bank_dir
    )

    return RollbackImpactAnalysis(
        status="success",
        execution_id=execution_id,
        snapshot_id=snapshot_id,
        total_files=len(affected_files),
        conflicts=len(conflicts),
        can_rollback_all=len(conflicts) == 0,
        files=file_analysis,
        conflicts_detail=conflicts,
    )


async def _analyze_files_for_rollback(
    affected_files: list[str], conflicts: list[str], memory_bank_dir: Path
) -> list[FileRollbackAnalysis]:
    """Analyze each file for rollback impact.

    Args:
        affected_files: List of affected files
        conflicts: List of conflicts
        memory_bank_dir: Memory bank directory

    Returns:
        List of FileRollbackAnalysis models
    """
    file_analysis: list[FileRollbackAnalysis] = []
    for file_path in affected_files:
        analysis = _analyze_single_file_rollback(file_path, conflicts, memory_bank_dir)
        file_analysis.append(analysis)
    return file_analysis


def _analyze_single_file_rollback(
    file_path: str, conflicts: list[str], memory_bank_dir: Path
) -> FileRollbackAnalysis:
    """Analyze a single file for rollback.

    Args:
        file_path: Path to file
        conflicts: List of conflicts
        memory_bank_dir: Memory bank directory

    Returns:
        FileRollbackAnalysis model
    """
    full_path = memory_bank_dir / file_path
    has_conflict = any(file_path in conflict for conflict in conflicts)

    if has_conflict:
        return FileRollbackAnalysis(
            file=file_path,
            exists=full_path.exists(),
            has_conflict=True,
            can_restore=False,
            reason="File has been manually edited",
        )

    return FileRollbackAnalysis(
        file=file_path,
        exists=full_path.exists(),
        has_conflict=False,
        can_restore=True,
    )
