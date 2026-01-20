"""
Rollback History - Rollback Manager Support

Handle rollback history management and statistics.
"""

from collections.abc import Iterable
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from cortex.refactoring.models import RollbackRecordModel

# ============================================================================
# Pydantic Models for Rollback History
# ============================================================================


class RollbackStatistics(BaseModel):
    """Statistics for rollback history."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total: int = Field(default=0, ge=0, description="Total rollbacks")
    successful: int = Field(default=0, ge=0, description="Successful rollbacks")
    failed: int = Field(default=0, ge=0, description="Failed rollbacks")
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Success rate")


class RollbackHistoryResult(BaseModel):
    """Result of rollback history query."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    time_range_days: int = Field(..., ge=0, description="Time range in days")
    total_rollbacks: int = Field(default=0, ge=0, description="Total rollbacks")
    successful: int = Field(default=0, ge=0, description="Successful rollbacks")
    failed: int = Field(default=0, ge=0, description="Failed rollbacks")
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Success rate")
    rollbacks: list[RollbackRecordModel] = Field(
        default_factory=lambda: list[RollbackRecordModel](),
        description="List of rollbacks sorted by date",
    )


def filter_rollbacks_by_date(
    rollbacks: Iterable[RollbackRecordModel], cutoff_date: datetime
) -> list[RollbackRecordModel]:
    """Filter rollbacks by date cutoff.

    Args:
        rollbacks: Iterable of rollback records
        cutoff_date: Date cutoff

    Returns:
        List of RollbackRecordModel filtered by date
    """
    filtered: list[RollbackRecordModel] = []
    for rollback in rollbacks:
        rollback_date = datetime.fromisoformat(rollback.created_at)
        if rollback_date >= cutoff_date:
            filtered.append(rollback)
    return filtered


def calculate_rollback_statistics(
    filtered_rollbacks: list[RollbackRecordModel],
) -> RollbackStatistics:
    """Calculate rollback statistics.

    Args:
        filtered_rollbacks: List of filtered rollback records

    Returns:
        RollbackStatistics model
    """
    total = len(filtered_rollbacks)
    successful = len([r for r in filtered_rollbacks if r.status == "completed"])
    failed = len([r for r in filtered_rollbacks if r.status == "failed"])
    return RollbackStatistics(
        total=total,
        successful=successful,
        failed=failed,
        success_rate=successful / total if total > 0 else 0.0,
    )


def build_rollback_history_result(
    time_range_days: int,
    filtered_rollbacks: list[RollbackRecordModel],
    stats: RollbackStatistics,
) -> RollbackHistoryResult:
    """Build rollback history result.

    Args:
        time_range_days: Time range in days
        filtered_rollbacks: List of filtered rollback records
        stats: Rollback statistics

    Returns:
        RollbackHistoryResult model
    """
    # Sort rollbacks by created_at descending
    sorted_rollbacks = sorted(
        filtered_rollbacks,
        key=lambda r: r.created_at,
        reverse=True,
    )

    return RollbackHistoryResult(
        time_range_days=time_range_days,
        total_rollbacks=stats.total,
        successful=stats.successful,
        failed=stats.failed,
        success_rate=stats.success_rate,
        rollbacks=sorted_rollbacks,
    )
