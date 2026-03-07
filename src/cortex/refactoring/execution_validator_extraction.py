"""
Operation extraction for execution validator.

Extracts RefactoringOperationModel lists from RefactoringSuggestionModel or
legacy dict-shaped suggestions (consolidation, split, reorganization).
"""

from datetime import datetime
from typing import cast

from cortex.core.models import JsonValue, ModelDict

from .models import (
    OperationParameters,
    RefactoringActionModel,
    RefactoringOperationModel,
    RefactoringStatus,
    RefactoringSuggestionModel,
)


def run_legacy_impact_checks(suggestion: ModelDict, warnings: list[str]) -> None:
    """Run impact checks on legacy dict-shaped suggestion."""
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


def extract_legacy_consolidation_operations(
    suggestion_id: str, suggestion: ModelDict
) -> list[RefactoringOperationModel]:
    """Extract consolidation operations from legacy dict suggestion."""
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


def extract_legacy_split_operations(
    suggestion_id: str, suggestion: ModelDict
) -> list[RefactoringOperationModel]:
    """Extract split operations from legacy dict suggestion."""
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


def extract_legacy_reorganization_operations(
    suggestion_id: str, suggestion: ModelDict
) -> list[RefactoringOperationModel]:
    """Extract reorganization operations from legacy dict suggestion."""
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


def extract_consolidation_operations(
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


def extract_split_operations(
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


def extract_reorganization_operations(
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
