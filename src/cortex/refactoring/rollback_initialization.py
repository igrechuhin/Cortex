"""
Rollback Initialization - Rollback Manager Support

Handle rollback initialization and record creation.
"""

from datetime import datetime

from cortex.refactoring.models import RollbackRecordModel


def initialize_rollback(
    execution_id: str, preserve_manual_changes: bool
) -> tuple[str, RollbackRecordModel]:
    """Initialize rollback by creating ID and record.

    Args:
        execution_id: Execution ID
        preserve_manual_changes: Whether to preserve manual changes

    Returns:
        Tuple of (rollback_id, rollback_record)
    """
    rollback_id = generate_rollback_id(execution_id)
    rollback_record = create_rollback_record(
        rollback_id, execution_id, preserve_manual_changes
    )
    return rollback_id, rollback_record


def generate_rollback_id(execution_id: str) -> str:
    """Generate unique rollback ID.

    Args:
        execution_id: Execution ID

    Returns:
        Rollback ID
    """
    return f"rollback-{execution_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def create_rollback_record(
    rollback_id: str, execution_id: str, preserve_manual_changes: bool
) -> RollbackRecordModel:
    """Create rollback record.

    Args:
        rollback_id: Rollback ID
        execution_id: Execution ID
        preserve_manual_changes: Whether to preserve manual changes

    Returns:
        Rollback record
    """
    return RollbackRecordModel(
        rollback_id=rollback_id,
        execution_id=execution_id,
        created_at=datetime.now().isoformat(),
        preserve_manual_edits=preserve_manual_changes,
    )
