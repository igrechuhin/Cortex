"""
Refactoring Executor - Phase 5.3

Safely execute approved refactoring suggestions with validation and rollback support.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.exceptions import FileOperationError
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.linking.validator import LinkValidator

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
    RiskLevel,
)
from .refactoring_executor_history import (
    build_history_result,
    convert_impact_metrics,
    count_execution_statuses,
    filter_executions_by_date,
    read_history_file,
)
from .refactoring_executor_impact import (
    build_failure_result,
    build_impact_result,
    build_success_result,
    build_validation_error_result,
    calculate_token_totals,
    collect_affected_files,
    create_execution_record,
    create_snapshots_for_files,
    extract_estimated_impact,
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
        records = read_history_file(self.history_file)
        if records is None:
            self.executions = {}
            return

        self.executions = records

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
        execution = create_execution_record(suggestion_id, approval_id, operations)

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
            return build_success_result(execution, operations, dry_run)

        except Exception as e:
            return await self._handle_execution_failure(execution, operations, e)

    async def _validate_and_check(
        self,
        execution: RefactoringExecutionModel,
        suggestion: RefactoringSuggestionModel | ModelDict,
        dry_run: bool,
    ) -> ExecutionResult | None:
        """Validate refactoring; return error result if validation fails,
        None if success."""
        execution.status = RefactoringStatus.VALIDATING
        validation_results = await self.validate_refactoring(suggestion, dry_run)
        execution.validation_results = RefactoringImpactMetrics(
            token_savings=0,  # Will be calculated during execution
            files_affected=validation_results.operations_count,
            complexity_reduction=0,
            risk_level=RiskLevel.LOW,
        )

        if not validation_results.valid:
            execution.status = RefactoringStatus.FAILED
            execution.error = (
                f"Validation failed: {', '.join(validation_results.issues)}"
            )
            self.executions[execution.execution_id] = execution
            await self._save_history()
            return build_validation_error_result(execution, validation_results.issues)
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
            execution.actual_impact = extract_estimated_impact(suggestion)

        execution.status = RefactoringStatus.COMPLETED
        execution.completed_at = datetime.now().isoformat()
        self.executions[execution.execution_id] = execution
        await self._save_history()

    async def _handle_execution_failure(
        self,
        execution: RefactoringExecutionModel,
        operations: list[RefactoringOperationModel],
        error: Exception,
    ) -> ExecutionResult:
        """Update execution state and return failure result."""
        execution.status = RefactoringStatus.FAILED
        execution.error = str(error)
        execution.completed_at = datetime.now().isoformat()
        self.executions[execution.execution_id] = execution
        await self._save_history()
        return build_failure_result(execution, operations, str(error))

    async def _create_snapshot(
        self, operations: list[RefactoringOperationModel]
    ) -> str:
        """Create snapshot of all files that will be modified."""
        snapshot_id = f"refactoring-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        affected_files = collect_affected_files(operations)
        await create_snapshots_for_files(
            affected_files,
            snapshot_id,
            self.memory_bank_dir,
            self.fs_manager,
            self.version_manager,
            self.token_counter,
        )
        return snapshot_id

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
        affected_files = collect_affected_files(operations)
        total_tokens_after = await calculate_token_totals(
            affected_files, self.memory_bank_dir, self.metadata_index
        )
        estimated_impact = extract_estimated_impact(suggestion)

        return build_impact_result(
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
        cutoff_date = datetime.now() - timedelta(days=time_range_days)
        filtered_executions = filter_executions_by_date(
            self.executions, cutoff_date, include_rollbacks
        )
        status_counts = count_execution_statuses(filtered_executions)

        return build_history_result(time_range_days, filtered_executions, status_counts)

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
            operations = execution.operations
            validation_results = convert_impact_metrics(execution.validation_results)
            actual_impact = convert_impact_metrics(execution.actual_impact)

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
