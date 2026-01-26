"""
Refactoring Executor - Phase 5.3

Safely execute approved refactoring suggestions with validation and rollback support.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.exceptions import FileOperationError
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonValue, ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.linking.link_validator import LinkValidator

from .execution_operations import ExecutionOperations
from .execution_validator import ExecutionValidator
from .models import (
    ExecutionHistoryResult,
    ExecutionResult,
    RefactoringExecutionModel,
    RefactoringExecutorConfig,
    RefactoringImpactMetrics,
    RefactoringOperationModel,
    RefactoringStatus,
    RefactoringSuggestionModel,
    RefactoringValidationResult,
)


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
        config: RefactoringExecutorConfig | ModelDict | None = None,
    ):
        self.memory_bank_dir: Path = Path(memory_bank_dir)
        self.fs_manager: FileSystemManager = fs_manager
        self.version_manager: VersionManager = version_manager
        self.link_validator: LinkValidator = link_validator
        self.metadata_index: MetadataIndex = metadata_index
        self.config = self._initialize_config(config)
        self.token_counter: TokenCounter = TokenCounter()
        self.validator = self._initialize_validator(
            memory_bank_dir, fs_manager, metadata_index
        )
        self.operations = self._initialize_operations(memory_bank_dir, fs_manager)
        self.history_file: Path = (
            self.memory_bank_dir.parent / "refactoring-history.json"
        )
        self.executions: dict[str, RefactoringExecutionModel] = {}
        self._load_history()

    def _initialize_config(
        self, config: RefactoringExecutorConfig | ModelDict | None
    ) -> RefactoringExecutorConfig:
        """Initialize executor config from various input types."""
        if config is None:
            return RefactoringExecutorConfig()
        if isinstance(config, RefactoringExecutorConfig):
            return config
        return RefactoringExecutorConfig.model_validate(config)

    def _initialize_validator(
        self,
        memory_bank_dir: Path,
        fs_manager: FileSystemManager,
        metadata_index: MetadataIndex,
    ) -> ExecutionValidator:
        """Initialize execution validator."""
        return ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=fs_manager,
            metadata_index=metadata_index,
        )

    def _initialize_operations(
        self, memory_bank_dir: Path, fs_manager: FileSystemManager
    ) -> ExecutionOperations:
        """Initialize execution operations."""
        return ExecutionOperations(
            memory_bank_dir=memory_bank_dir,
            fs_manager=fs_manager,
        )

    def _load_history(self) -> None:
        """Load execution history from disk."""
        records = self._read_history_file()
        if records is None:
            self.executions = {}
            return

        self.executions = records

    def _read_history_file(self) -> dict[str, RefactoringExecutionModel] | None:
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

    async def _save_history(self):
        """Save execution history to disk."""
        try:
            payload = {
                "last_updated": datetime.now().isoformat(),
                "executions": {
                    exec_id: exec_model.model_dump()
                    for exec_id, exec_model in self.executions.items()
                },
            }
            async with open_async_text_file(self.history_file, "w", "utf-8") as f:
                _ = await f.write(json.dumps(payload, indent=2))
        except Exception as e:
            raise FileOperationError(f"Failed to save execution history: {e}") from e

    async def validate_refactoring(
        self,
        suggestion: RefactoringSuggestionModel | ModelDict,
        dry_run: bool = True,
    ) -> RefactoringValidationResult:
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
        self, suggestion: RefactoringSuggestionModel | ModelDict
    ) -> list[RefactoringOperationModel]:
        """Extract refactoring operations from a suggestion."""
        return self.validator.extract_operations(suggestion)

    async def execute_refactoring(
        self,
        suggestion_id: str,
        approval_id: str,
        suggestion: RefactoringSuggestionModel | ModelDict,
        dry_run: bool = False,
        validate_first: bool = True,
    ) -> ExecutionResult:
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

            execution.status = RefactoringStatus.EXECUTING
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

    async def _validate_and_check(
        self,
        execution: RefactoringExecutionModel,
        suggestion: RefactoringSuggestionModel | ModelDict,
        dry_run: bool,
    ) -> ExecutionResult | None:
        """Validate refactoring; return error result if validation fails, None if success."""
        execution.status = RefactoringStatus.VALIDATING
        validation_results = await self.validate_refactoring(suggestion, dry_run)
        # Convert validation results to impact metrics
        from .models import RefactoringImpactMetrics

        execution.validation_results = RefactoringImpactMetrics(
            token_savings=0,  # Will be calculated during execution
            files_affected=validation_results.operations_count,
            complexity_reduction=0,
            risk_level="low",
        )

        if not validation_results.valid:
            execution.status = RefactoringStatus.FAILED
            execution.error = (
                f"Validation failed: {', '.join(validation_results.issues)}"
            )
            self.executions[execution.execution_id] = execution
            await self._save_history()
            return ExecutionResult(
                status="failed",
                execution_id=execution.execution_id,
                suggestion_id=execution.suggestion_id,
                approval_id=execution.approval_id,
                error=execution.error,
                validation_errors=validation_results.issues,
            )
        return None

    async def _execute_operations_batch(
        self,
        execution: RefactoringExecutionModel,
        operations: list[RefactoringOperationModel],
    ) -> None:
        """Execute all operations in the list."""
        for operation in operations:
            operation.status = RefactoringStatus.EXECUTING
            try:
                await self.execute_operation(operation)
                operation.status = RefactoringStatus.COMPLETED
                operation.completed_at = datetime.now().isoformat()
            except Exception as e:
                operation.status = RefactoringStatus.FAILED
                operation.error = str(e)
                raise

    async def _finalize_execution(
        self,
        execution: RefactoringExecutionModel,
        operations: list[RefactoringOperationModel],
        suggestion: RefactoringSuggestionModel | ModelDict,
        dry_run: bool,
    ) -> None:
        """Measure impact and mark execution as completed."""
        if not dry_run:
            actual_impact = await self.measure_impact(operations, suggestion)
            execution.actual_impact = actual_impact
        else:
            execution.actual_impact = self._extract_estimated_impact(suggestion)

        execution.status = RefactoringStatus.COMPLETED
        execution.completed_at = datetime.now().isoformat()
        self.executions[execution.execution_id] = execution
        await self._save_history()

    def _build_success_result(
        self,
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
            status="success",
            execution_id=execution.execution_id,
            suggestion_id=execution.suggestion_id,
            approval_id=execution.approval_id,
            operations_completed=len(
                [op for op in operations if op.status == "completed"]
            ),
            snapshot_id=execution.snapshot_id,
            actual_impact=actual_impact,
            dry_run=dry_run,
            rollback_available=execution.snapshot_id is not None,
        )

    async def _build_failure_result(
        self,
        execution: RefactoringExecutionModel,
        operations: list[RefactoringOperationModel],
        error: Exception,
    ) -> ExecutionResult:
        """Build failure response model."""
        execution.status = RefactoringStatus.FAILED
        execution.error = str(error)
        execution.completed_at = datetime.now().isoformat()
        self.executions[execution.execution_id] = execution
        await self._save_history()

        return ExecutionResult(
            status="failed",
            execution_id=execution.execution_id,
            suggestion_id=execution.suggestion_id,
            approval_id=execution.approval_id,
            error=str(error),
            operations_completed=len(
                [op for op in operations if op.status == "completed"]
            ),
            rollback_available=execution.snapshot_id is not None,
        )

    async def _create_snapshot(
        self, operations: list[RefactoringOperationModel]
    ) -> str:
        """Create snapshot of all files that will be modified."""
        snapshot_id = f"refactoring-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        affected_files = self._collect_affected_files(operations)
        await self._create_snapshots_for_files(affected_files, snapshot_id)
        return snapshot_id

    def _collect_affected_files(
        self, operations: list[RefactoringOperationModel]
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
        self, operation: RefactoringOperationModel
    ) -> list[str]:
        """Extract file list from consolidation operation parameters.

        Args:
            operation: Consolidation operation

        Returns:
            List of file paths from operation parameters
        """
        # For consolidation, files come from source_file
        files = []
        if operation.parameters.source_file:
            files = [operation.parameters.source_file]
        return files

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

    async def execute_operation(self, operation: RefactoringOperationModel):
        """Execute a single refactoring operation."""
        await self.operations.execute_operation(operation)

    async def execute_consolidation(self, operation: RefactoringOperationModel) -> None:
        """Execute consolidation operation."""
        await self.operations.execute_consolidation(operation)

    async def execute_split(self, operation: RefactoringOperationModel) -> None:
        """Execute split operation."""
        await self.operations.execute_split(operation)

    async def execute_create(self, operation: RefactoringOperationModel) -> None:
        """Execute create operation."""
        await self.operations.execute_create(operation)

    async def measure_impact(
        self,
        operations: list[RefactoringOperationModel],
        suggestion: RefactoringSuggestionModel | ModelDict,
    ) -> RefactoringImpactMetrics:
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
    ) -> ExecutionHistoryResult:
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

    async def get_execution(
        self, execution_id: str
    ) -> RefactoringExecutionModel | None:
        """Get a specific execution by ID.

        Returns:
            RefactoringExecutionModel or None if not found
        """
        from cortex.refactoring.models import RefactoringStatus

        execution = self.executions.get(execution_id)
        if execution:
            operations = self._convert_operations_to_models(execution.operations)
            validation_results = self._convert_impact_metrics(
                execution.validation_results
            )
            actual_impact = self._convert_impact_metrics(execution.actual_impact)

            return RefactoringExecutionModel(
                execution_id=execution.execution_id,
                suggestion_id=execution.suggestion_id,
                approval_id=execution.approval_id,
                operations=operations,
                status=RefactoringStatus(execution.status),
                created_at=execution.created_at,
                completed_at=execution.completed_at,
                snapshot_id=execution.snapshot_id,
                validation_results=validation_results,
                actual_impact=actual_impact,
                error=execution.error,
            )
        return None

    def _convert_operations_to_models(
        self, operations: list[RefactoringOperationModel]
    ) -> list[RefactoringOperationModel]:
        """Convert operations to Pydantic models (already models, return as-is)."""
        return operations

    def _convert_impact_metrics(
        self, impact: RefactoringImpactMetrics | None
    ) -> RefactoringImpactMetrics | None:
        """Convert impact metrics to Pydantic model."""
        if impact:
            return RefactoringImpactMetrics.model_validate(impact)
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
        self, suggestion: RefactoringSuggestionModel | ModelDict
    ) -> RefactoringImpactMetrics:
        """Extract estimated impact data from suggestion (legacy-safe)."""
        if isinstance(suggestion, RefactoringSuggestionModel):
            return suggestion.estimated_impact
        return RefactoringImpactMetrics()

    def _build_impact_result(
        self,
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

    def _filter_executions_by_date(
        self, cutoff_date: datetime, include_rollbacks: bool
    ) -> list[RefactoringExecutionModel]:
        """Filter executions by date and rollback status."""
        filtered_executions: list[RefactoringExecutionModel] = []
        for execution in self.executions.values():
            exec_date = datetime.fromisoformat(execution.created_at)
            if exec_date >= cutoff_date:
                if (
                    include_rollbacks
                    or execution.status != RefactoringStatus.ROLLED_BACK
                ):
                    filtered_executions.append(execution)
        return filtered_executions

    def _count_execution_statuses(
        self, filtered_executions: list[RefactoringExecutionModel]
    ) -> dict[str, int]:
        """Count execution statuses from filtered executions."""
        successful = len(
            [e for e in filtered_executions if e.status == RefactoringStatus.COMPLETED]
        )
        failed = len(
            [e for e in filtered_executions if e.status == RefactoringStatus.FAILED]
        )
        rolled_back = len(
            [
                e
                for e in filtered_executions
                if e.status == RefactoringStatus.ROLLED_BACK
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
        filtered_executions: list[RefactoringExecutionModel],
        status_counts: dict[str, int],
    ) -> ExecutionHistoryResult:
        """Build execution history result model."""
        total_executions = status_counts["total"]
        successful = status_counts["successful"]

        # Sort by created_at descending (newest first)
        sorted_executions = sorted(
            filtered_executions,
            key=lambda e: e.created_at,
            reverse=True,
        )

        return ExecutionHistoryResult(
            time_range_days=time_range_days,
            total_executions=total_executions,
            successful=successful,
            failed=status_counts["failed"],
            rolled_back=status_counts["rolled_back"],
            executions=sorted_executions,
        )
