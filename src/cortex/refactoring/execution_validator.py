"""
Execution Validator - Validation logic for refactoring operations.

This module provides validation logic for refactoring suggestions before execution.
"""

from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonValue, ModelDict

from .models import (
    OperationParameters,
    RefactoringActionModel,
    RefactoringOperationModel,
    RefactoringStatus,
    RefactoringSuggestionModel,
    RefactoringValidationResult,
)


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
        files: list[str] = []
        for file_path in self.memory_bank_dir.glob("**/*.md"):
            if file_path.is_file():
                rel_path = file_path.relative_to(self.memory_bank_dir)
                files.append(str(rel_path))
        return files

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
            _run_legacy_impact_checks(suggestion, warnings)

        return RefactoringValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            operations_count=len(operations),
            dry_run=dry_run,
        )

    async def _validate_file_existence(
        self, operations: list[RefactoringOperationModel], issues: list[str]
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
        self, operations: list[RefactoringOperationModel], warnings: list[str]
    ) -> None:
        """Check for conflicts with uncommitted changes."""
        for op in operations:
            target_file = self.memory_bank_dir / op.target_file
            if target_file.exists():
                # Check if file has been modified since last snapshot
                metadata = await self.metadata_index.get_file_metadata(op.target_file)
                # Note: modified_externally is not currently tracked in
                # DetailedFileMetadata. This check is a placeholder for
                # future external change detection
                if metadata:
                    warnings.append(
                        f"File has uncommitted changes: {op.target_file}. "
                        + "These may be overwritten."
                    )

    async def _check_dependency_integrity(
        self, operations: list[RefactoringOperationModel], warnings: list[str]
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
        self,
        suggestion: RefactoringSuggestionModel,
        warnings: list[str],
    ) -> None:
        """Check token budget impact."""
        estimated_token_change = suggestion.estimated_impact.token_savings
        if estimated_token_change < -1000:
            warnings.append(
                (
                    f"Refactoring may increase token usage by "
                    f"{-estimated_token_change} tokens"
                )
            )

    async def _run_validation_checks(
        self,
        operations: list[RefactoringOperationModel],
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
        self,
        suggestion: RefactoringSuggestionModel,
        warnings: list[str],
    ) -> None:
        """Run impact checks on suggestion.

        Args:
            suggestion: Refactoring suggestion
            warnings: List to collect warnings
        """
        self._check_token_budget_impact(suggestion, warnings)
        self._check_complexity_impact(suggestion, warnings)

    def _check_complexity_impact(
        self,
        suggestion: RefactoringSuggestionModel,
        warnings: list[str],
    ) -> None:
        """Check complexity impact."""
        estimated_complexity_change = suggestion.estimated_impact.complexity_reduction
        if estimated_complexity_change < 0:
            warnings.append("Refactoring may increase complexity")

    def extract_operations(
        self, suggestion: RefactoringSuggestionModel | ModelDict
    ) -> list[RefactoringOperationModel]:
        """Extract refactoring operations from a suggestion."""
        operations: list[RefactoringOperationModel] = []
        if isinstance(suggestion, dict):
            return self._extract_operations_from_legacy_dict(suggestion)

        suggestion_type = suggestion.refactoring_type.value
        suggestion_id = suggestion.suggestion_id

        if suggestion_type == "consolidation":
            operations.extend(
                _extract_consolidation_operations(suggestion, suggestion_id)
            )
        elif suggestion_type == "split":
            operations.extend(_extract_split_operations(suggestion, suggestion_id))
        elif suggestion_type == "reorganization":
            operations.extend(
                _extract_reorganization_operations(suggestion, suggestion_id)
            )

        return operations

    def _extract_operations_from_legacy_dict(
        self, suggestion: ModelDict
    ) -> list[RefactoringOperationModel]:
        """Extract operations from legacy dict-shaped suggestions (used by tests)."""
        suggestion_type = str(suggestion.get("type", ""))
        suggestion_id = str(suggestion.get("suggestion_id", "legacy"))
        if suggestion_type == "consolidation":
            return _extract_legacy_consolidation_operations(suggestion_id, suggestion)
        if suggestion_type == "split":
            return _extract_legacy_split_operations(suggestion_id, suggestion)
        if suggestion_type == "reorganization":
            return _extract_legacy_reorganization_operations(suggestion_id, suggestion)
        return []


def _run_legacy_impact_checks(suggestion: ModelDict, warnings: list[str]) -> None:
    impact_raw = suggestion.get("estimated_impact")
    if not isinstance(impact_raw, dict):
        return
    impact = cast(dict[str, JsonValue], impact_raw)

    token_savings_raw = impact.get("token_savings")
    if isinstance(token_savings_raw, (int, float)):
        token_savings = int(token_savings_raw)
        if token_savings < -1000:
            warnings.append(
                f"Refactoring may increase token usage by {-token_savings} tokens"
            )

    complexity_raw = impact.get("complexity_reduction")
    if isinstance(complexity_raw, (int, float)):
        complexity_reduction = float(complexity_raw)
        if complexity_reduction < 0:
            warnings.append("Refactoring may increase complexity")


def _extract_legacy_str_list(value: JsonValue) -> list[str]:
    if not isinstance(value, list):
        return []
    items = cast(list[JsonValue], value)
    return [str(item) for item in items if isinstance(item, (str, int, float))]


def _extract_legacy_consolidation_operations(
    suggestion_id: str, suggestion: ModelDict
) -> list[RefactoringOperationModel]:
    target_file = suggestion.get("target_file")
    if not isinstance(target_file, str) or not target_file:
        return []
    files = _extract_legacy_str_list(suggestion.get("files", []))
    sections = _extract_legacy_str_list(suggestion.get("sections", []))
    return [
        RefactoringOperationModel(
            operation_id=f"{suggestion_id}-consolidate",
            operation_type="consolidate",
            target_file=target_file,
            parameters=OperationParameters(
                source_file=files[0] if files else None,
                source_files=files,
                destination_file=target_file,
                sections=sections,
            ),
            status=RefactoringStatus.PENDING,
            created_at=datetime.now().isoformat(),
        )
    ]


def _extract_legacy_split_operations(
    suggestion_id: str, suggestion: ModelDict
) -> list[RefactoringOperationModel]:
    source_file = suggestion.get("file")
    if not isinstance(source_file, str) or not source_file:
        return []
    split_points_raw = suggestion.get("split_points", [])
    if not isinstance(split_points_raw, list):
        return []
    split_points = cast(list[JsonValue], split_points_raw)
    operations: list[RefactoringOperationModel] = []
    for idx, split_point_raw in enumerate(split_points):
        if not isinstance(split_point_raw, dict):
            continue
        split_point = cast(dict[str, JsonValue], split_point_raw)
        op = _build_split_operation(suggestion_id, idx, source_file, split_point)
        if op:
            operations.append(op)
    return operations


def _build_split_operation(
    suggestion_id: str,
    idx: int,
    source_file: str,
    split_point: dict[str, JsonValue],
) -> RefactoringOperationModel | None:
    """Build a split operation from split point."""
    new_file = split_point.get("new_file")
    if not isinstance(new_file, str) or not new_file:
        return None
    content_raw = split_point.get("content", "")
    content = str(content_raw) if content_raw is not None else ""
    sections = _extract_legacy_str_list(split_point.get("sections", []))
    return RefactoringOperationModel(
        operation_id=f"{suggestion_id}-split-{idx}",
        operation_type="split",
        target_file=source_file,
        parameters=OperationParameters(
            source_file=source_file,
            destination_file=new_file,
            content=content,
            sections=sections,
        ),
        status=RefactoringStatus.PENDING,
        created_at=datetime.now().isoformat(),
    )


def _create_category_operation(
    suggestion_id: str, idx: int, name: str
) -> RefactoringOperationModel:
    """Create a category operation."""
    return RefactoringOperationModel(
        operation_id=f"{suggestion_id}-create-{idx}",
        operation_type="create",
        target_file=name,
        parameters=OperationParameters(is_directory=True),
        status=RefactoringStatus.PENDING,
        created_at=datetime.now().isoformat(),
    )


def _create_move_operation(
    suggestion_id: str, idx: int, target_file: str, destination: str
) -> RefactoringOperationModel:
    """Create a move operation."""
    return RefactoringOperationModel(
        operation_id=f"{suggestion_id}-move-{idx}",
        operation_type="move",
        target_file=target_file,
        parameters=OperationParameters(
            source_file=target_file, destination_file=destination
        ),
        status=RefactoringStatus.PENDING,
        created_at=datetime.now().isoformat(),
    )


def _create_rename_operation(
    suggestion_id: str, idx: int, target_file: str, new_name: str
) -> RefactoringOperationModel:
    """Create a rename operation."""
    return RefactoringOperationModel(
        operation_id=f"{suggestion_id}-rename-{idx}",
        operation_type="rename",
        target_file=target_file,
        parameters=OperationParameters(source_file=target_file, new_name=new_name),
        status=RefactoringStatus.PENDING,
        created_at=datetime.now().isoformat(),
    )


def _extract_legacy_reorganization_operations(
    suggestion_id: str, suggestion: ModelDict
) -> list[RefactoringOperationModel]:
    actions_raw = suggestion.get("actions", [])
    if not isinstance(actions_raw, list):
        return []
    operations: list[RefactoringOperationModel] = []
    actions = cast(list[JsonValue], actions_raw)
    for idx, action_raw in enumerate(actions):
        if not isinstance(action_raw, dict):
            continue
        action = cast(dict[str, JsonValue], action_raw)
        op = _extract_single_reorganization_operation(suggestion_id, idx, action)
        if op:
            operations.append(op)
    return operations


def _extract_single_reorganization_operation(
    suggestion_id: str, idx: int, action: dict[str, JsonValue]
) -> RefactoringOperationModel | None:
    """Extract a single reorganization operation from action dict."""
    action_type = str(action.get("action", ""))
    if action_type == "create_category":
        name = action.get("name")
        if isinstance(name, str) and name:
            return _create_category_operation(suggestion_id, idx, name)
        return None

    target_file = action.get("file")
    if not isinstance(target_file, str) or not target_file:
        return None
    if action_type == "move":
        destination = action.get("destination")
        if isinstance(destination, str) and destination:
            return _create_move_operation(suggestion_id, idx, target_file, destination)
    elif action_type == "rename":
        new_name = action.get("new_name")
        if isinstance(new_name, str) and new_name:
            return _create_rename_operation(suggestion_id, idx, target_file, new_name)
    return None


def _create_category_operation_from_action(
    action: RefactoringActionModel, suggestion_id: str
) -> RefactoringOperationModel | None:
    """Create a category operation from RefactoringActionModel."""
    if not action.target_file:
        return None

    return RefactoringOperationModel(
        operation_id=f"{suggestion_id}-create-{action.target_file}",
        operation_type="create",
        target_file=action.target_file,
        parameters=OperationParameters(
            destination_file=action.target_file,
            is_directory=True,
        ),
        status=RefactoringStatus.PENDING,
        created_at=datetime.now().isoformat(),
    )


def _create_move_operation_from_action(
    action: RefactoringActionModel, suggestion_id: str
) -> RefactoringOperationModel | None:
    """Create a move operation from RefactoringActionModel."""
    if not action.target_file or not action.details.destination_file:
        return None

    return RefactoringOperationModel(
        operation_id=f"{suggestion_id}-move-{action.target_file}",
        operation_type="move",
        target_file=action.target_file,
        parameters=OperationParameters(
            source_file=action.target_file,
            destination_file=action.details.destination_file,
        ),
        status=RefactoringStatus.PENDING,
        created_at=datetime.now().isoformat(),
    )


def _create_rename_operation_from_action(
    action: RefactoringActionModel, suggestion_id: str
) -> RefactoringOperationModel | None:
    """Create a rename operation from RefactoringActionModel."""
    if not action.target_file or not action.details.destination_file:
        return None

    return RefactoringOperationModel(
        operation_id=f"{suggestion_id}-rename-{action.target_file}",
        operation_type="rename",
        target_file=action.target_file,
        parameters=OperationParameters(
            source_file=action.target_file,
            new_name=action.details.destination_file,
        ),
        status=RefactoringStatus.PENDING,
        created_at=datetime.now().isoformat(),
    )


def _extract_consolidation_operations(
    suggestion: RefactoringSuggestionModel, suggestion_id: str
) -> list[RefactoringOperationModel]:
    """Extract consolidation operations from suggestion."""
    operations: list[RefactoringOperationModel] = []
    target_file: str | None = None
    for action in suggestion.actions:
        if action.details.destination_file:
            target_file = action.details.destination_file
            break

    if not target_file:
        return operations

    files = suggestion.affected_files
    sections: list[str] = []
    for action in suggestion.actions:
        if action.details.sections:
            sections.extend(action.details.sections or [])

    operations.append(
        RefactoringOperationModel(
            operation_id=f"{suggestion_id}-consolidate",
            operation_type="consolidate",
            target_file=target_file,
            parameters=OperationParameters(
                source_file=files[0] if files else None,
                destination_file=target_file,
                sections=sections,
            ),
            status=RefactoringStatus.PENDING,
            created_at=datetime.now().isoformat(),
        )
    )
    return operations


def _extract_split_operations(
    suggestion: RefactoringSuggestionModel, suggestion_id: str
) -> list[RefactoringOperationModel]:
    """Extract split operations from suggestion."""
    operations: list[RefactoringOperationModel] = []
    if not suggestion.affected_files:
        return operations

    original_file = suggestion.affected_files[0]
    for idx, action in enumerate(suggestion.actions):
        if action.action_type not in {"split", "create"}:
            continue
        new_file = action.details.destination_file or action.target_file
        sections = action.details.sections or []
        content = action.details.content or ""

        operations.append(
            RefactoringOperationModel(
                operation_id=f"{suggestion_id}-split-{idx}",
                operation_type="split",
                target_file=original_file,
                parameters=OperationParameters(
                    source_file=original_file,
                    destination_file=new_file,
                    sections=sections,
                    content=content,
                ),
                status=RefactoringStatus.PENDING,
                created_at=datetime.now().isoformat(),
            )
        )
    return operations


def _extract_reorganization_operations(
    suggestion: RefactoringSuggestionModel, suggestion_id: str
) -> list[RefactoringOperationModel]:
    """Extract reorganization operations from suggestion."""
    operations: list[RefactoringOperationModel] = []
    action_handlers = {
        "move": _create_move_operation_from_action,
        "rename": _create_rename_operation_from_action,
        "create_category": _create_category_operation_from_action,
    }

    for action in suggestion.actions:
        handler = action_handlers.get(action.action_type)
        if handler is None:
            continue
        operation = handler(action, suggestion_id)
        if operation is not None:
            operations.append(operation)

    return operations
