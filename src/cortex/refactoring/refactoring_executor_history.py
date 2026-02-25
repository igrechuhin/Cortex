"""History helpers for RefactoringExecutor.

Read, filter, count, and build history results.
Keeps refactoring_executor.py under 400 lines.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.models import JsonValue, ModelDict

from .models import (
    ExecutionHistoryResult,
    RefactoringExecutionModel,
    RefactoringImpactMetrics,
    RefactoringStatus,
)


def read_history_file(
    history_file: Path,
) -> dict[str, RefactoringExecutionModel] | None:
    """
    Read and parse the JSON history file, return None if corrupted.

    Note:
        Uses synchronous I/O during initialization for simplicity.
    """
    if not history_file.exists():
        return None

    try:
        with open(history_file) as f:
            raw_obj = json.load(f)

        if not isinstance(raw_obj, dict):
            return None
        raw = cast(ModelDict, raw_obj)

        executions_raw = raw.get("executions", {})
        if not isinstance(executions_raw, dict):
            return None

        records: dict[str, RefactoringExecutionModel] = {}
        executions_dict = cast(dict[str, JsonValue], executions_raw)
        for exec_id, exec_data in executions_dict.items():
            try:
                model = RefactoringExecutionModel.model_validate(exec_data)
            except Exception:
                continue
            records[str(exec_id)] = model

        return records
    except Exception as e:
        from cortex.core.logging_config import logger

        logger.warning(f"Refactoring history corrupted, starting fresh: {e}")
        return None


def filter_executions_by_date(
    executions: dict[str, RefactoringExecutionModel],
    cutoff_date: datetime,
    include_rollbacks: bool,
) -> list[RefactoringExecutionModel]:
    """Filter executions by date and rollback status."""
    result: list[RefactoringExecutionModel] = []
    for execution in executions.values():
        exec_date = datetime.fromisoformat(execution.created_at)
        if exec_date >= cutoff_date:
            if include_rollbacks or execution.status != RefactoringStatus.ROLLED_BACK:
                result.append(execution)
    return result


def count_execution_statuses(
    filtered_executions: list[RefactoringExecutionModel],
) -> dict[str, int]:
    """Count execution statuses from filtered executions."""
    successful = len(
        [e for e in filtered_executions if e.status == RefactoringStatus.COMPLETED]
    )
    failed = len(
        [e for e in filtered_executions if e.status == RefactoringStatus.FAILED]
    )
    rolled_back = len(
        [e for e in filtered_executions if e.status == RefactoringStatus.ROLLED_BACK]
    )
    return {
        "total": len(filtered_executions),
        "successful": successful,
        "failed": failed,
        "rolled_back": rolled_back,
    }


def convert_impact_metrics(
    impact: RefactoringImpactMetrics | None,
) -> RefactoringImpactMetrics | None:
    """Convert impact metrics to Pydantic model."""
    if impact:
        return RefactoringImpactMetrics.model_validate(impact)
    return None


def build_history_result(
    time_range_days: int,
    filtered_executions: list[RefactoringExecutionModel],
    status_counts: dict[str, int],
) -> ExecutionHistoryResult:
    """Build execution history result model."""
    sorted_executions = sorted(
        filtered_executions,
        key=lambda e: e.created_at,
        reverse=True,
    )

    return ExecutionHistoryResult(
        time_range_days=time_range_days,
        total_executions=status_counts["total"],
        successful=status_counts["successful"],
        failed=status_counts["failed"],
        rolled_back=status_counts["rolled_back"],
        executions=sorted_executions,
    )
