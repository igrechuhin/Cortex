"""Impact and snapshot helpers for RefactoringExecutor.

Collect affected files, extract consolidation files, build impact/results.
Keeps refactoring_executor.py under 400 lines.
"""

import hashlib
from datetime import datetime
from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager

from .models import (
    ExecutionResult,
    ExecutionStatus,
    RefactoringExecutionModel,
    RefactoringImpactMetrics,
    RefactoringOperationModel,
    RefactoringStatus,
    RefactoringSuggestionModel,
)


def create_execution_record(
    suggestion_id: str,
    approval_id: str,
    operations: list[RefactoringOperationModel],
) -> RefactoringExecutionModel:
    """Create initial execution record."""
    execution_id = f"exec-{suggestion_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return RefactoringExecutionModel(
        execution_id=execution_id,
        suggestion_id=suggestion_id,
        approval_id=approval_id,
        operations=operations,
        status=RefactoringStatus.PENDING,
        created_at=datetime.now().isoformat(),
    )


def collect_affected_files(
    operations: list[RefactoringOperationModel],
) -> set[str]:
    """Collect all files that will be affected by operations."""
    affected_files: set[str] = set()
    for operation in operations:
        affected_files.add(operation.target_file)
        if operation.operation_type in ["consolidate"]:
            consolidation_files = extract_consolidation_files(operation)
            affected_files.update(consolidation_files)
    return affected_files


def extract_consolidation_files(
    operation: RefactoringOperationModel,
) -> list[str]:
    """Extract file list from consolidation operation parameters."""
    files: list[str] = []
    if operation.parameters.source_file:
        files = [operation.parameters.source_file]
    return files


def extract_estimated_impact(
    suggestion: RefactoringSuggestionModel | ModelDict,
) -> RefactoringImpactMetrics:
    """Extract estimated impact data from suggestion (legacy-safe)."""
    if isinstance(suggestion, RefactoringSuggestionModel):
        return suggestion.estimated_impact
    return RefactoringImpactMetrics()


def build_impact_result(
    operations: list[RefactoringOperationModel],
    affected_files: set[str],
    total_tokens_after: int,
    estimated_impact: RefactoringImpactMetrics,
) -> RefactoringImpactMetrics:
    """Build impact measurement result model."""
    return RefactoringImpactMetrics(
        token_savings=estimated_impact.token_savings,
        files_affected=len(affected_files),
        operations_completed=len(operations),
        complexity_reduction=estimated_impact.complexity_reduction,
        risk_level=estimated_impact.risk_level,
    )


def build_success_result(
    execution: RefactoringExecutionModel,
    operations: list[RefactoringOperationModel],
    dry_run: bool,
) -> ExecutionResult:
    """Build success response model."""
    actual_impact = (
        RefactoringImpactMetrics.model_validate(execution.actual_impact)
        if execution.actual_impact
        else RefactoringImpactMetrics()
    )
    return ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        execution_id=execution.execution_id,
        suggestion_id=execution.suggestion_id,
        approval_id=execution.approval_id,
        operations_completed=len([op for op in operations if op.status == "completed"]),
        snapshot_id=execution.snapshot_id,
        actual_impact=actual_impact,
        dry_run=dry_run,
        rollback_available=execution.snapshot_id is not None,
    )


def build_validation_error_result(
    execution: RefactoringExecutionModel,
    validation_issues: list[str],
) -> ExecutionResult:
    """Build validation failure response model."""
    return ExecutionResult(
        status=ExecutionStatus.FAILED,
        execution_id=execution.execution_id,
        suggestion_id=execution.suggestion_id,
        approval_id=execution.approval_id,
        error=execution.error or "",
        validation_errors=validation_issues,
    )


def build_failure_result(
    execution: RefactoringExecutionModel,
    operations: list[RefactoringOperationModel],
    error_msg: str,
) -> ExecutionResult:
    """Build failure response model."""
    return ExecutionResult(
        status=ExecutionStatus.FAILED,
        execution_id=execution.execution_id,
        suggestion_id=execution.suggestion_id,
        approval_id=execution.approval_id,
        error=error_msg,
        operations_completed=len([op for op in operations if op.status == "completed"]),
        rollback_available=execution.snapshot_id is not None,
    )


async def create_snapshots_for_files(
    affected_files: set[str],
    snapshot_id: str,
    memory_bank_dir: Path,
    fs_manager: FileSystemManager,
    version_manager: VersionManager,
    token_counter: TokenCounter,
) -> None:
    """Create snapshots for all affected files."""
    for file_path in affected_files:
        full_path = memory_bank_dir / file_path
        if full_path.exists():
            await _create_file_snapshot(
                full_path, snapshot_id, fs_manager, version_manager, token_counter
            )


async def _create_file_snapshot(
    full_path: Path,
    snapshot_id: str,
    fs_manager: FileSystemManager,
    version_manager: VersionManager,
    token_counter: TokenCounter,
) -> None:
    """Create a single file snapshot."""
    content, _ = await fs_manager.read_file(full_path)
    content_bytes = content.encode("utf-8")
    size_bytes = len(content_bytes)
    token_count = token_counter.count_tokens(content)
    content_hash = hashlib.sha256(content_bytes).hexdigest()
    version = 1
    _ = await version_manager.create_snapshot(
        full_path,
        version=version,
        content=content,
        size_bytes=size_bytes,
        token_count=token_count,
        content_hash=content_hash,
        change_type="modified",
        change_description=f"Pre-refactoring snapshot: {snapshot_id}",
    )


async def calculate_token_totals(
    affected_files: set[str],
    memory_bank_dir: Path,
    metadata_index: MetadataIndex,
) -> int:
    """Calculate total tokens for affected files."""
    total = 0
    for file_path in affected_files:
        full_path = memory_bank_dir / file_path
        if full_path.exists():
            metadata_raw = await metadata_index.get_file_metadata(file_path)
            if metadata_raw is not None:
                total += metadata_raw.token_count
    return total
