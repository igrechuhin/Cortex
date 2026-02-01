"""
Rollback History Operations - Rollback Manager Support

Filter, statistics, and result building for rollback history using RefactoringStatus.
"""

from collections.abc import Iterable
from datetime import datetime

from cortex.refactoring.models import (
    RefactoringStatus,
    RollbackHistoryResult,
    RollbackRecordModel,
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
) -> dict[str, int | float]:
    """Calculate rollback statistics using RefactoringStatus.

    Args:
        filtered_rollbacks: List of filtered rollback records

    Returns:
        Dict with total, successful, failed, success_rate
    """
    total = len(filtered_rollbacks)
    successful = len(
        [r for r in filtered_rollbacks if r.status == RefactoringStatus.COMPLETED]
    )
    failed = len(
        [r for r in filtered_rollbacks if r.status == RefactoringStatus.FAILED]
    )
    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "success_rate": successful / total if total > 0 else 0,
    }


def build_rollback_history_result(
    time_range_days: int,
    filtered_rollbacks: list[RollbackRecordModel],
    stats: dict[str, int | float],
) -> RollbackHistoryResult:
    """Build RollbackHistoryResult from filtered rollbacks and stats.

    Args:
        time_range_days: Time range in days
        filtered_rollbacks: List of filtered rollback records
        stats: Dict from calculate_rollback_statistics

    Returns:
        RollbackHistoryResult model from cortex.refactoring.models
    """
    sorted_rollbacks = sorted(
        filtered_rollbacks,
        key=lambda r: r.created_at,
        reverse=True,
    )
    return RollbackHistoryResult(
        time_range_days=time_range_days,
        total_rollbacks=int(stats["total"]),
        successful=int(stats["successful"]),
        failed=int(stats["failed"]),
        rollbacks=sorted_rollbacks,
    )
