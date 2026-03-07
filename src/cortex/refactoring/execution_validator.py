"""
Execution Validator - Validation logic for refactoring operations.

This module provides validation logic for refactoring suggestions before execution.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict

from .execution_validator_checks import (
    check_complexity_impact,
    check_dependency_integrity,
    check_token_budget_impact,
    check_uncommitted_changes,
    validate_file_existence,
)
from .execution_validator_checks import (
    get_all_memory_bank_files as get_checks_memory_bank_files,
)
from .execution_validator_extraction import (
    extract_consolidation_operations,
    extract_legacy_consolidation_operations,
    extract_legacy_reorganization_operations,
    extract_legacy_split_operations,
    extract_reorganization_operations,
    extract_split_operations,
    run_legacy_impact_checks,
)
from .models import (
    RefactoringSuggestionModel,
    RefactoringType,
    RefactoringValidationResult,
)

if TYPE_CHECKING:
    from .models import RefactoringOperationModel


class ExecutionValidator:
    """
    Validate refactoring operations before execution.

    Features:
    - File existence checks
    - Conflict detection
    - Dependency integrity validation
    - Token budget impact validation
    - Complexity impact validation
    - Operation extraction from suggestions
    """

    def __init__(
        self,
        memory_bank_dir: Path,
        fs_manager: FileSystemManager,
        metadata_index: MetadataIndex,
    ) -> None:
        self.memory_bank_dir: Path = Path(memory_bank_dir)
        self.fs_manager: FileSystemManager = fs_manager
        self.metadata_index: MetadataIndex = metadata_index

    async def get_all_memory_bank_files(self) -> list[str]:
        """Get list of all memory bank markdown files (relative paths)."""
        return get_checks_memory_bank_files(self.memory_bank_dir)

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
            RefactoringValidationResult with validation status
        """

        issues: list[str] = []
        warnings: list[str] = []
        operations = self.extract_operations(suggestion)

        await self._run_validation_checks(operations, issues, warnings, dry_run)
        if isinstance(suggestion, RefactoringSuggestionModel):
            self._run_impact_checks(suggestion, warnings)
        else:
            run_legacy_impact_checks(suggestion, warnings)

        return RefactoringValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            operations_count=len(operations),
            dry_run=dry_run,
        )

    async def _run_validation_checks(
        self,
        operations: list["RefactoringOperationModel"],
        issues: list[str],
        warnings: list[str],
        dry_run: bool,
    ) -> None:
        """Run all validation checks."""
        await validate_file_existence(self.memory_bank_dir, operations, issues)
        await check_uncommitted_changes(
            self.memory_bank_dir, self.metadata_index, operations, warnings
        )

        if not dry_run:
            await check_dependency_integrity(
                self.memory_bank_dir,
                self.fs_manager,
                self.metadata_index,
                operations,
                warnings,
            )

    def _run_impact_checks(
        self,
        suggestion: RefactoringSuggestionModel,
        warnings: list[str],
    ) -> None:
        """Run impact checks on suggestion."""
        check_token_budget_impact(suggestion, warnings)
        check_complexity_impact(suggestion, warnings)

    def extract_operations(
        self, suggestion: RefactoringSuggestionModel | ModelDict
    ) -> list["RefactoringOperationModel"]:
        """Extract refactoring operations from a suggestion."""

        if isinstance(suggestion, dict):
            return self._extract_operations_from_legacy_dict(suggestion)

        suggestion_type = suggestion.refactoring_type
        suggestion_id = suggestion.suggestion_id

        if suggestion_type == RefactoringType.CONSOLIDATION:
            return extract_consolidation_operations(suggestion, suggestion_id)
        if suggestion_type == RefactoringType.SPLIT:
            return extract_split_operations(suggestion, suggestion_id)
        if suggestion_type == RefactoringType.REORGANIZATION:
            return extract_reorganization_operations(suggestion, suggestion_id)

        return []

    def _extract_operations_from_legacy_dict(
        self, suggestion: ModelDict
    ) -> list["RefactoringOperationModel"]:
        """Extract operations from legacy dict-shaped suggestions (used by tests)."""

        suggestion_type = str(suggestion.get("type", ""))
        suggestion_id = str(suggestion.get("suggestion_id", "legacy"))
        if suggestion_type == RefactoringType.CONSOLIDATION.value:
            return extract_legacy_consolidation_operations(suggestion_id, suggestion)
        if suggestion_type == RefactoringType.SPLIT.value:
            return extract_legacy_split_operations(suggestion_id, suggestion)
        if suggestion_type == RefactoringType.REORGANIZATION.value:
            return extract_legacy_reorganization_operations(suggestion_id, suggestion)
        return []
