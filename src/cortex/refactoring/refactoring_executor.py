"""
Refactoring Executor - Phase 5.3

Safely execute approved refactoring suggestions with validation and rollback support.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.exceptions import FileOperationError
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.linking.link_validator import LinkValidator

from .execution_operations import ExecutionOperations
from .execution_validator import ExecutionValidator, RefactoringOperation


class RefactoringStatus(Enum):
    """Status of a refactoring operation."""

    PENDING = "pending"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class RefactoringExecution:
    """Record of a refactoring execution."""

    execution_id: str
    suggestion_id: str
    approval_id: str
    operations: list[RefactoringOperation]
    status: str
    created_at: str
    completed_at: str | None = None
    snapshot_id: str | None = None
    validation_results: dict[str, object] | None = None
    actual_impact: dict[str, object] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary."""
        data = asdict(self)
        data["operations"] = [asdict(op) for op in self.operations]
        return data


class RefactoringExecutor:
    """
    Execute approved refactoring operations safely.

    Features:
    - Pre-execution validation
    - Atomic operations (all-or-nothing)
    - Automatic snapshots before changes
    - Change validation after execution
    - Impact measurement
    - Detailed execution logs
    """

    def __init__(
        self,
        memory_bank_dir: Path,
        fs_manager: FileSystemManager,
        version_manager: VersionManager,
        link_validator: LinkValidator,
        metadata_index: MetadataIndex,
        config: dict[str, object] | None = None,
    ):
        self.memory_bank_dir: Path = Path(memory_bank_dir)
        self.fs_manager: FileSystemManager = fs_manager
        self.version_manager: VersionManager = version_manager
        self.link_validator: LinkValidator = link_validator
        self.metadata_index: MetadataIndex = metadata_index
        self.config: dict[str, object] = config or {}
        self.token_counter: TokenCounter = TokenCounter()

        self.validator: ExecutionValidator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=fs_manager,
            metadata_index=metadata_index,
        )

        self.operations: ExecutionOperations = ExecutionOperations(
            memory_bank_dir=memory_bank_dir,
            fs_manager=fs_manager,
        )

        self.history_file: Path = (
            self.memory_bank_dir.parent / ".memory-bank-refactoring-history.json"
        )
        self.executions: dict[str, RefactoringExecution] = {}
        self._load_history()

    def _load_history(self) -> None:
        """Load execution history from disk."""
        data = self._read_history_file()
        if data is None:
            self.executions = {}
            return

        executions_dict = cast(dict[str, object], data.get("executions", {}))
        for exec_id, exec_data in executions_dict.items():
            self.executions[str(exec_id)] = self._reconstruct_execution(
                str(exec_id), cast(dict[str, object], exec_data)
            )

    def _read_history_file(self) -> dict[str, object] | None:
        """
        Read and parse the JSON history file, return None if corrupted.

        Note:
            This method uses synchronous I/O during initialization for simplicity.
            For performance-critical paths, consider using async alternatives.
        """
        if not self.history_file.exists():
            return None

        try:
            with open(self.history_file) as f:
                return cast(dict[str, object], json.load(f))
        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Refactoring history corrupted, starting fresh: {e}")
            return None

    def _reconstruct_operation(
        self, op_data: dict[str, object]
    ) -> RefactoringOperation:
        """Convert a dict to RefactoringOperation with all type casts."""
        return RefactoringOperation(
            operation_id=cast(str, op_data.get("operation_id", "")),
            operation_type=cast(str, op_data.get("operation_type", "")),
            target_file=cast(str, op_data.get("target_file", "")),
            parameters=cast(dict[str, object], op_data.get("parameters", {})),
            status=cast(str, op_data.get("status", "pending")),
            error=cast(str | None, op_data.get("error")),
            created_at=cast(str | None, op_data.get("created_at")),
            completed_at=cast(str | None, op_data.get("completed_at")),
        )

    def _reconstruct_execution(
        self, exec_id: str, exec_data: dict[str, object]
    ) -> RefactoringExecution:
        """Convert a dict to RefactoringExecution with reconstructed operations."""
        operations_list = cast(list[object], exec_data.get("operations", []))
        operations = [
            self._reconstruct_operation(cast(dict[str, object], op_data))
            for op_data in operations_list
            if isinstance(op_data, dict)
        ]

        return RefactoringExecution(
            execution_id=cast(str, exec_data.get("execution_id", "")),
            suggestion_id=cast(str, exec_data.get("suggestion_id", "")),
            approval_id=cast(str, exec_data.get("approval_id", "")),
            operations=operations,
            status=cast(str, exec_data.get("status", "pending")),
            created_at=cast(str, exec_data.get("created_at", "")),
            completed_at=cast(str | None, exec_data.get("completed_at")),
            snapshot_id=cast(str | None, exec_data.get("snapshot_id")),
            validation_results=cast(
                dict[str, object] | None, exec_data.get("validation_results")
            ),
            actual_impact=cast(
                dict[str, object] | None, exec_data.get("actual_impact")
            ),
            error=cast(str | None, exec_data.get("error")),
        )

    async def _save_history(self):
        """Save execution history to disk."""
        try:
            data = {
                "last_updated": datetime.now().isoformat(),
                "executions": {
                    exec_id: execution.to_dict()
                    for exec_id, execution in self.executions.items()
                },
            }
            async with open_async_text_file(self.history_file, "w", "utf-8") as f:
                _ = await f.write(json.dumps(data, indent=2))
        except Exception as e:
            raise FileOperationError(f"Failed to save execution history: {e}") from e

    async def validate_refactoring(
        self,
        suggestion: dict[str, object],
        dry_run: bool = True,
    ) -> dict[str, object]:
        """
        Validate a refactoring suggestion before execution.

        Args:
            suggestion: Refactoring suggestion to validate
            dry_run: If True, only simulate without making changes

        Returns:
            Validation results with issues and warnings
        """
        return await self.validator.validate_refactoring(suggestion, dry_run)

    def extract_operations(
        self, suggestion: dict[str, object]
    ) -> list[RefactoringOperation]:
        """Extract refactoring operations from a suggestion."""
        return self.validator.extract_operations(suggestion)

    async def execute_refactoring(
        self,
        suggestion_id: str,
        approval_id: str,
        suggestion: dict[str, object],
        dry_run: bool = False,
        validate_first: bool = True,
    ) -> dict[str, object]:
        """
        Execute an approved refactoring suggestion.

        Args:
            suggestion_id: ID of the suggestion to execute
            approval_id: ID of the approval
            suggestion: The refactoring suggestion
            dry_run: If True, simulate without making changes
            validate_first: If True, validate before executing

        Returns:
            Execution results with status and impact
        """
        operations = self.extract_operations(suggestion)
        execution = self._create_execution_record(
            suggestion_id, approval_id, operations
        )

        try:
            if validate_first:
                error_result = await self._validate_and_check(
                    execution, suggestion, dry_run
                )
                if error_result:
                    return error_result

            if not dry_run:
                execution.snapshot_id = await self._create_snapshot(operations)

            execution.status = RefactoringStatus.EXECUTING.value
            if not dry_run:
                await self._execute_operations_batch(execution, operations)

            await self._finalize_execution(execution, operations, suggestion, dry_run)
            return self._build_success_result(execution, operations, dry_run)

        except Exception as e:
            return await self._build_failure_result(execution, operations, e)

    def _create_execution_record(
        self,
        suggestion_id: str,
        approval_id: str,
        operations: list[RefactoringOperation],
    ) -> RefactoringExecution:
        """Create initial execution record."""
        execution_id = f"exec-{suggestion_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return RefactoringExecution(
            execution_id=execution_id,
            suggestion_id=suggestion_id,
            approval_id=approval_id,
            operations=operations,
            status=RefactoringStatus.PENDING.value,
            created_at=datetime.now().isoformat(),
        )

    async def _validate_and_check(
        self,
        execution: RefactoringExecution,
        suggestion: dict[str, object],
        dry_run: bool,
    ) -> dict[str, object] | None:
        """Validate refactoring; return error dict if validation fails, None if success."""
        execution.status = RefactoringStatus.VALIDATING.value
        validation_results = await self.validate_refactoring(suggestion, dry_run)
        execution.validation_results = validation_results

        if not validation_results["valid"]:
            execution.status = RefactoringStatus.FAILED.value
            issues = cast(list[str], validation_results.get("issues", []))
            execution.error = f"Validation failed: {', '.join(issues)}"
            self.executions[execution.execution_id] = execution
            await self._save_history()
            return {
                "status": "failed",
                "execution_id": execution.execution_id,
                "error": execution.error,
                "validation_results": validation_results,
            }
        return None

    async def _execute_operations_batch(
        self, execution: RefactoringExecution, operations: list[RefactoringOperation]
    ) -> None:
        """Execute all operations in the list."""
        for operation in operations:
            operation.status = "executing"
            try:
                await self.execute_operation(operation)
                operation.status = "completed"
                operation.completed_at = datetime.now().isoformat()
            except Exception as e:
                operation.status = "failed"
                operation.error = str(e)
                raise

    async def _finalize_execution(
        self,
        execution: RefactoringExecution,
        operations: list[RefactoringOperation],
        suggestion: dict[str, object],
        dry_run: bool,
    ) -> None:
        """Measure impact and mark execution as completed."""
        if not dry_run:
            actual_impact = await self.measure_impact(operations, suggestion)
            execution.actual_impact = actual_impact
        else:
            estimated_impact = suggestion.get("estimated_impact", {})
            execution.actual_impact = cast(
                dict[str, object] | None,
                estimated_impact if estimated_impact else None,
            )

        execution.status = RefactoringStatus.COMPLETED.value
        execution.completed_at = datetime.now().isoformat()
        self.executions[execution.execution_id] = execution
        await self._save_history()

    def _build_success_result(
        self,
        execution: RefactoringExecution,
        operations: list[RefactoringOperation],
        dry_run: bool,
    ) -> dict[str, object]:
        """Build success response dict."""
        return {
            "status": "success",
            "execution_id": execution.execution_id,
            "operations_completed": len(
                [op for op in operations if op.status == "completed"]
            ),
            "snapshot_id": execution.snapshot_id,
            "actual_impact": execution.actual_impact,
            "dry_run": dry_run,
        }

    async def _build_failure_result(
        self,
        execution: RefactoringExecution,
        operations: list[RefactoringOperation],
        error: Exception,
    ) -> dict[str, object]:
        """Build failure response dict."""
        execution.status = RefactoringStatus.FAILED.value
        execution.error = str(error)
        execution.completed_at = datetime.now().isoformat()
        self.executions[execution.execution_id] = execution
        await self._save_history()

        return {
            "status": "failed",
            "execution_id": execution.execution_id,
            "error": str(error),
            "operations_completed": len(
                [op for op in operations if op.status == "completed"]
            ),
            "rollback_available": execution.snapshot_id is not None,
        }

    async def _create_snapshot(self, operations: list[RefactoringOperation]) -> str:
        """Create snapshot of all files that will be modified."""
        snapshot_id = f"refactoring-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        affected_files = self._collect_affected_files(operations)
        await self._create_snapshots_for_files(affected_files, snapshot_id)
        return snapshot_id

    def _collect_affected_files(
        self, operations: list[RefactoringOperation]
    ) -> set[str]:
        """Collect all files that will be affected by operations.

        Reduced nesting: Extracted file collection for consolidation operations.
        Nesting: 2 levels (down from 5 levels)
        """
        affected_files: set[str] = set()
        for operation in operations:
            affected_files.add(operation.target_file)
            if operation.operation_type in ["consolidate"]:
                consolidation_files = self._extract_consolidation_files(operation)
                affected_files.update(consolidation_files)
        return affected_files

    def _extract_consolidation_files(
        self, operation: RefactoringOperation
    ) -> list[str]:
        """Extract file list from consolidation operation parameters.

        Args:
            operation: Consolidation operation

        Returns:
            List of file paths from operation parameters
        """
        files_param_raw = operation.parameters.get("files", [])
        if not isinstance(files_param_raw, list):
            return []

        files_param = cast(list[object], files_param_raw)
        return [
            str(file_item) for file_item in files_param if isinstance(file_item, str)
        ]

    async def _create_snapshots_for_files(
        self, affected_files: set[str], snapshot_id: str
    ) -> None:
        """Create snapshots for all affected files."""
        for file_path in affected_files:
            full_path = self.memory_bank_dir / file_path
            if full_path.exists():
                await self._create_file_snapshot(full_path, snapshot_id)

    async def _create_file_snapshot(self, full_path: Path, snapshot_id: str) -> None:
        """Create a single file snapshot."""
        content, _ = await self.fs_manager.read_file(full_path)
        content_bytes = content.encode("utf-8")
        size_bytes = len(content_bytes)
        token_count = self.token_counter.count_tokens(content)
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        version = 1

        _ = await self.version_manager.create_snapshot(
            full_path,
            version=version,
            content=content,
            size_bytes=size_bytes,
            token_count=token_count,
            content_hash=content_hash,
            change_type="modified",
            change_description=f"Pre-refactoring snapshot: {snapshot_id}",
        )

    async def execute_operation(self, operation: RefactoringOperation):
        """Execute a single refactoring operation."""
        await self.operations.execute_operation(operation)

    async def execute_consolidation(self, operation: RefactoringOperation) -> None:
        """Execute consolidation operation."""
        await self.operations.execute_consolidation(operation)

    async def execute_split(self, operation: RefactoringOperation) -> None:
        """Execute split operation."""
        await self.operations.execute_split(operation)

    async def execute_create(self, operation: RefactoringOperation) -> None:
        """Execute create operation."""
        await self.operations.execute_create(operation)

    async def measure_impact(
        self,
        operations: list[RefactoringOperation],
        suggestion: dict[str, object],
    ) -> dict[str, object]:
        """Measure actual impact of refactoring."""
        affected_files = self._collect_affected_files(operations)
        total_tokens_after = await self._calculate_token_totals(affected_files)
        estimated_impact = self._extract_estimated_impact(suggestion)

        return self._build_impact_result(
            operations, affected_files, total_tokens_after, estimated_impact
        )

    async def get_execution_history(
        self,
        time_range_days: int = 90,
        include_rollbacks: bool = True,
    ) -> dict[str, object]:
        """
        Get refactoring execution history.

        Args:
            time_range_days: Number of days to include
            include_rollbacks: Include rolled back executions

        Returns:
            Execution history with statistics
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=time_range_days)
        filtered_executions = self._filter_executions_by_date(
            cutoff_date, include_rollbacks
        )
        status_counts = self._count_execution_statuses(filtered_executions)

        return self._build_history_result(
            time_range_days, filtered_executions, status_counts
        )

    async def get_execution(self, execution_id: str) -> dict[str, object] | None:
        """Get a specific execution by ID."""
        execution = self.executions.get(execution_id)
        if execution:
            return execution.to_dict()
        return None

    async def _calculate_token_totals(self, affected_files: set[str]) -> int:
        """Calculate total tokens for affected files."""
        total_tokens_after = 0
        for file_path in affected_files:
            full_path = self.memory_bank_dir / file_path
            if full_path.exists():
                metadata_raw = await self.metadata_index.get_file_metadata(file_path)
                if isinstance(metadata_raw, dict):
                    token_count_raw = metadata_raw.get("token_count", 0)
                    token_count = (
                        int(token_count_raw)
                        if isinstance(token_count_raw, (int, float))
                        else 0
                    )
                    total_tokens_after += token_count
        return total_tokens_after

    def _extract_estimated_impact(
        self, suggestion: dict[str, object]
    ) -> dict[str, object]:
        """Extract estimated impact data from suggestion."""
        estimated_impact_raw = suggestion.get("estimated_impact", {})
        return cast(
            dict[str, object],
            estimated_impact_raw if isinstance(estimated_impact_raw, dict) else {},
        )

    def _build_impact_result(
        self,
        operations: list[RefactoringOperation],
        affected_files: set[str],
        total_tokens_after: int,
        estimated_impact: dict[str, object],
    ) -> dict[str, object]:
        """Build impact measurement result dictionary."""
        estimated_token_savings_raw = estimated_impact.get("token_savings", 0)
        estimated_token_savings = (
            int(estimated_token_savings_raw)
            if isinstance(estimated_token_savings_raw, (int, float))
            else 0
        )

        complexity_reduction_raw = estimated_impact.get("complexity_reduction", 0.0)
        complexity_reduction = (
            float(complexity_reduction_raw)
            if isinstance(complexity_reduction_raw, (int, float))
            else 0.0
        )

        return {
            "operations_completed": len(operations),
            "files_affected": len(affected_files),
            "token_change": total_tokens_after - 0,  # total_tokens_before was always 0
            "estimated_token_savings": estimated_token_savings,
            "complexity_reduction": complexity_reduction,
        }

    def _filter_executions_by_date(
        self, cutoff_date: datetime, include_rollbacks: bool
    ) -> list[dict[str, object]]:
        """Filter executions by date and rollback status."""
        filtered_executions: list[dict[str, object]] = []
        for execution in self.executions.values():
            exec_date = datetime.fromisoformat(execution.created_at)
            if exec_date >= cutoff_date:
                if (
                    include_rollbacks
                    or execution.status != RefactoringStatus.ROLLED_BACK.value
                ):
                    filtered_executions.append(execution.to_dict())
        return filtered_executions

    def _count_execution_statuses(
        self, filtered_executions: list[dict[str, object]]
    ) -> dict[str, int]:
        """Count execution statuses from filtered executions."""
        successful = len(
            [e for e in filtered_executions if str(e.get("status", "")) == "completed"]
        )
        failed = len(
            [e for e in filtered_executions if str(e.get("status", "")) == "failed"]
        )
        rolled_back = len(
            [
                e
                for e in filtered_executions
                if str(e.get("status", "")) == "rolled_back"
            ]
        )
        return {
            "total": len(filtered_executions),
            "successful": successful,
            "failed": failed,
            "rolled_back": rolled_back,
        }

    def _build_history_result(
        self,
        time_range_days: int,
        filtered_executions: list[dict[str, object]],
        status_counts: dict[str, int],
    ) -> dict[str, object]:
        """Build execution history result dictionary."""
        total_executions = status_counts["total"]
        successful = status_counts["successful"]

        return {
            "time_range_days": time_range_days,
            "total_executions": total_executions,
            "successful": successful,
            "failed": status_counts["failed"],
            "rolled_back": status_counts["rolled_back"],
            "success_rate": (
                successful / total_executions if total_executions > 0 else 0
            ),
            "executions": sorted(
                filtered_executions,
                key=lambda e: str(e.get("created_at", "")),
                reverse=True,
            ),
        }
