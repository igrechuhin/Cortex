"""
Validation rules for execution validator.

File existence, uncommitted changes, dependency integrity, and impact checks
(token budget, complexity) for refactoring operations.
"""

from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex

from .models import (
    RefactoringOperationModel,
    RefactoringSuggestionModel,
)


def get_all_memory_bank_files(memory_bank_dir: Path) -> list[str]:
    """Return list of all memory bank markdown file paths (relative)."""
    files: list[str] = []
    for file_path in memory_bank_dir.glob("**/*.md"):
        if file_path.is_file():
            rel_path = file_path.relative_to(memory_bank_dir)
            files.append(str(rel_path))
    return files


async def validate_file_existence(
    memory_bank_dir: Path,
    operations: list[RefactoringOperationModel],
    issues: list[str],
) -> None:
    """Check file existence for all operations."""
    for op in operations:
        target_file = memory_bank_dir / op.target_file

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


async def check_uncommitted_changes(
    memory_bank_dir: Path,
    metadata_index: MetadataIndex,
    operations: list[RefactoringOperationModel],
    warnings: list[str],
) -> None:
    """Check for conflicts with uncommitted changes."""
    for op in operations:
        target_file = memory_bank_dir / op.target_file
        if target_file.exists():
            metadata = await metadata_index.get_file_metadata(op.target_file)
            if metadata:
                warnings.append(
                    f"File has uncommitted changes: {op.target_file}. "
                    + "These may be overwritten."
                )


async def check_dependency_integrity(
    memory_bank_dir: Path,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    operations: list[RefactoringOperationModel],
    warnings: list[str],
) -> None:
    """Check dependency integrity for delete/rename/move operations."""
    for op in operations:
        if op.operation_type not in ["delete", "rename", "move"]:
            continue

        target_file = op.target_file
        all_files = get_all_memory_bank_files(memory_bank_dir)

        for file_path in all_files:
            if file_path == target_file:
                continue

            await check_file_dependencies(
                fs_manager, memory_bank_dir, file_path, target_file, warnings
            )


async def check_file_dependencies(
    fs_manager: FileSystemManager,
    memory_bank_dir: Path,
    file_path: str,
    target_file: str,
    warnings: list[str],
) -> None:
    """Check if a file has dependencies on target file."""
    content, _ = await fs_manager.read_file(memory_bank_dir / file_path)

    has_dependency = target_file in content or target_file.replace(".md", "") in content

    if has_dependency:
        warnings.append(
            f"File {file_path} may have links to {target_file}. "
            + "Links may need to be updated."
        )


def check_token_budget_impact(
    suggestion: RefactoringSuggestionModel,
    warnings: list[str],
) -> None:
    """Check token budget impact."""
    estimated_token_change = suggestion.estimated_impact.token_savings
    if estimated_token_change < -1000:
        msg = (
            "Refactoring may increase token usage by "
            + f"{-estimated_token_change} tokens"
        )
        warnings.append(msg)


def check_complexity_impact(
    suggestion: RefactoringSuggestionModel,
    warnings: list[str],
) -> None:
    """Check complexity impact."""
    estimated_complexity_change = suggestion.estimated_impact.complexity_reduction
    if estimated_complexity_change < 0:
        warnings.append("Refactoring may increase complexity")
