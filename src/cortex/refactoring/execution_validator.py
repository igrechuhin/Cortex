"""
Execution Validator - Validation logic for refactoring operations.

This module provides validation logic for refactoring suggestions before execution.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex


@dataclass
class RefactoringOperation:
    """Single refactoring operation."""

    operation_id: str
    operation_type: (
        str  # "move", "rename", "create", "delete", "modify", "consolidate", "split"
    )
    target_file: str
    parameters: dict[str, object]
    status: str = "pending"
    error: str | None = None
    created_at: str | None = None
    completed_at: str | None = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


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
        issues: list[str] = []
        warnings: list[str] = []
        operations = self.extract_operations(suggestion)

        await self._run_validation_checks(operations, issues, warnings, dry_run)
        self._run_impact_checks(suggestion, warnings)

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "operations_count": len(operations),
            "dry_run": dry_run,
        }

    async def _validate_file_existence(
        self, operations: list[RefactoringOperation], issues: list[str]
    ) -> None:
        """Check file existence for all operations."""
        for op in operations:
            target_file = self.memory_bank_dir / op.target_file

            if op.operation_type in [
                "modify",
                "delete",
                "rename",
                "move",
                "consolidate",
            ]:
                if not target_file.exists():
                    issues.append(f"Target file does not exist: {op.target_file}")

            if op.operation_type in ["create"]:
                if target_file.exists():
                    issues.append(f"Target file already exists: {op.target_file}")

    async def _check_uncommitted_changes(
        self, operations: list[RefactoringOperation], warnings: list[str]
    ) -> None:
        """Check for conflicts with uncommitted changes."""
        for op in operations:
            target_file = self.memory_bank_dir / op.target_file
            if target_file.exists():
                # Check if file has been modified since last snapshot
                metadata: dict[str, object] | None = (
                    await self.metadata_index.get_file_metadata(op.target_file)
                )
                if metadata and metadata.get("modified_externally"):
                    warnings.append(
                        f"File has uncommitted changes: {op.target_file}. "
                        + "These may be overwritten."
                    )

    async def _check_dependency_integrity(
        self, operations: list[RefactoringOperation], warnings: list[str]
    ) -> None:
        """Check dependency integrity for delete/rename/move operations."""
        for op in operations:
            if op.operation_type not in ["delete", "rename", "move"]:
                continue

            # Check if other files depend on this file
            target_file = op.target_file
            all_files = await self.get_all_memory_bank_files()

            for file_path in all_files:
                if file_path == target_file:
                    continue

                await self._check_file_dependencies(file_path, target_file, warnings)

    async def _check_file_dependencies(
        self, file_path: str, target_file: str, warnings: list[str]
    ) -> None:
        """Check if a file has dependencies on target file.

        Args:
            file_path: File to check for dependencies
            target_file: Target file that may be referenced
            warnings: List to append warnings to
        """
        content, _ = await self.fs_manager.read_file(self.memory_bank_dir / file_path)

        has_dependency = (
            target_file in content or target_file.replace(".md", "") in content
        )

        if has_dependency:
            warnings.append(
                f"File {file_path} may have links to {target_file}. "
                + "Links may need to be updated."
            )

    def _check_token_budget_impact(
        self, suggestion: dict[str, object], warnings: list[str]
    ) -> None:
        """Check token budget impact."""
        estimated_impact: dict[str, object] = cast(
            dict[str, object], suggestion.get("estimated_impact", {})
        )
        estimated_token_change: int = cast(
            int, estimated_impact.get("token_savings", 0)
        )
        if estimated_token_change < -1000:
            warnings.append(
                f"Refactoring may increase token usage by {-estimated_token_change} tokens"
            )

    async def _run_validation_checks(
        self,
        operations: list[RefactoringOperation],
        issues: list[str],
        warnings: list[str],
        dry_run: bool,
    ) -> None:
        """Run all validation checks.

        Args:
            operations: List of refactoring operations
            issues: List to collect issues
            warnings: List to collect warnings
            dry_run: Whether this is a dry run
        """
        await self._validate_file_existence(operations, issues)
        await self._check_uncommitted_changes(operations, warnings)

        if not dry_run:
            await self._check_dependency_integrity(operations, warnings)

    def _run_impact_checks(
        self, suggestion: dict[str, object], warnings: list[str]
    ) -> None:
        """Run impact checks on suggestion.

        Args:
            suggestion: Refactoring suggestion
            warnings: List to collect warnings
        """
        self._check_token_budget_impact(suggestion, warnings)
        self._check_complexity_impact(suggestion, warnings)

    def _check_complexity_impact(
        self, suggestion: dict[str, object], warnings: list[str]
    ) -> None:
        """Check complexity impact."""
        estimated_impact: dict[str, object] = cast(
            dict[str, object], suggestion.get("estimated_impact", {})
        )
        estimated_complexity_change: float = cast(
            float, estimated_impact.get("complexity_reduction", 0.0)
        )
        if estimated_complexity_change < 0:
            warnings.append("Refactoring may increase complexity")

    def extract_operations(
        self, suggestion: dict[str, object]
    ) -> list[RefactoringOperation]:
        """Extract refactoring operations from a suggestion."""
        operations: list[RefactoringOperation] = []
        suggestion_type: str | None = cast(str | None, suggestion.get("type"))
        suggestion_id: str = cast(str, suggestion.get("suggestion_id", "unknown"))

        if suggestion_type == "consolidation":
            operations.extend(
                self._extract_consolidation_operations(suggestion, suggestion_id)
            )
        elif suggestion_type == "split":
            operations.extend(self._extract_split_operations(suggestion, suggestion_id))
        elif suggestion_type == "reorganization":
            operations.extend(
                self._extract_reorganization_operations(suggestion, suggestion_id)
            )

        return operations

    def _extract_consolidation_operations(
        self, suggestion: dict[str, object], suggestion_id: str
    ) -> list[RefactoringOperation]:
        """Extract consolidation operations from suggestion.

        Args:
            suggestion: Refactoring suggestion dictionary
            suggestion_id: Suggestion identifier

        Returns:
            List of consolidation operations
        """
        operations: list[RefactoringOperation] = []
        consolidate_target_file: str = cast(str, suggestion.get("target_file", ""))
        if not consolidate_target_file:
            return operations

        operations.append(
            RefactoringOperation(
                operation_id=f"{suggestion_id}-consolidate",
                operation_type="consolidate",
                target_file=consolidate_target_file,
                parameters={
                    "files": suggestion.get("files", []),
                    "sections": suggestion.get("sections", []),
                    "extraction_target": suggestion.get("extraction_target"),
                },
            )
        )
        return operations

    def _extract_split_operations(
        self, suggestion: dict[str, object], suggestion_id: str
    ) -> list[RefactoringOperation]:
        """Extract split operations from suggestion.

        Args:
            suggestion: Refactoring suggestion dictionary
            suggestion_id: Suggestion identifier

        Returns:
            List of split operations
        """
        operations: list[RefactoringOperation] = []
        original_file: str | None = cast(str | None, suggestion.get("file"))
        split_points: list[dict[str, object]] = cast(
            list[dict[str, object]], suggestion.get("split_points", [])
        )

        if original_file:
            for idx, split_point in enumerate(split_points):
                operations.append(
                    RefactoringOperation(
                        operation_id=f"{suggestion_id}-split-{idx}",
                        operation_type="split",
                        target_file=original_file,
                        parameters={
                            "new_file": split_point.get("new_file"),
                            "sections": split_point.get("sections", []),
                            "content": split_point.get("content", ""),
                        },
                    )
                )
        return operations

    def _extract_reorganization_operations(
        self, suggestion: dict[str, object], suggestion_id: str
    ) -> list[RefactoringOperation]:
        """Extract reorganization operations from suggestion.

        Uses dispatch table for action type routing.

        Args:
            suggestion: Refactoring suggestion dictionary
            suggestion_id: Suggestion identifier

        Returns:
            List of reorganization operations
        """
        operations: list[RefactoringOperation] = []
        actions: list[dict[str, object]] = cast(
            list[dict[str, object]], suggestion.get("actions", [])
        )

        # Action handlers dispatch table
        action_handlers = {
            "move": self._create_move_operation,
            "rename": self._create_rename_operation,
            "create_category": self._create_category_operation,
        }

        for action in actions:
            action_type = cast(str | None, action.get("action"))
            if not action_type:
                continue

            handler = action_handlers.get(action_type)
            if handler:
                operation = handler(action, suggestion_id)
                if operation:
                    operations.append(operation)

        return operations

    def _create_move_operation(
        self, action: dict[str, object], suggestion_id: str
    ) -> RefactoringOperation | None:
        """Create move operation from action.

        Args:
            action: Action dictionary
            suggestion_id: Suggestion identifier

        Returns:
            Move operation or None
        """
        target_file_val: str | None = cast(str | None, action.get("file"))
        if not target_file_val:
            return None

        return RefactoringOperation(
            operation_id=f"{suggestion_id}-move-{target_file_val}",
            operation_type="move",
            target_file=target_file_val,
            parameters={"destination": action.get("destination")},
        )

    def _create_rename_operation(
        self, action: dict[str, object], suggestion_id: str
    ) -> RefactoringOperation | None:
        """Create rename operation from action.

        Args:
            action: Action dictionary
            suggestion_id: Suggestion identifier

        Returns:
            Rename operation or None
        """
        target_file_val = cast(str | None, action.get("file"))
        if not isinstance(target_file_val, str):
            return None

        return RefactoringOperation(
            operation_id=f"{suggestion_id}-rename-{target_file_val}",
            operation_type="rename",
            target_file=target_file_val,
            parameters={"new_name": action.get("new_name")},
        )

    def _create_category_operation(
        self, action: dict[str, object], suggestion_id: str
    ) -> RefactoringOperation | None:
        """Create category operation from action.

        Args:
            action: Action dictionary
            suggestion_id: Suggestion identifier

        Returns:
            Create category operation or None
        """
        name_val: str | None = cast(str | None, action.get("name"))
        if not name_val:
            return None

        return RefactoringOperation(
            operation_id=f"{suggestion_id}-create-{name_val}",
            operation_type="create",
            target_file=name_val,
            parameters={"type": "directory"},
        )

    async def get_all_memory_bank_files(self) -> list[str]:
        """Get list of all memory bank files."""
        files: list[str] = []
        for file_path in self.memory_bank_dir.glob("**/*.md"):
            if file_path.is_file():
                rel_path = file_path.relative_to(self.memory_bank_dir)
                files.append(str(rel_path))
        return files
