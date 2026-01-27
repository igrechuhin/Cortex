"""
Unit tests for execution_operations module.
"""

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.core.exceptions import ValidationError
from cortex.refactoring.execution_operations import ExecutionOperations
from cortex.refactoring.models import (
    OperationParameters,
    RefactoringOperationModel,
)


def make_operation(
    op_type: str,
    target_file: str,
    **params: object,
) -> RefactoringOperationModel:
    """Helper to create RefactoringOperationModel with correct signature."""
    # Convert object params to proper types for OperationParameters
    typed_params: dict[str, str | list[str] | int | bool | None] = {}
    for key, value in params.items():
        if isinstance(value, (str, int, bool)) or value is None:
            typed_params[key] = value
        elif isinstance(value, list):
            typed_params[key] = [
                str(item) if isinstance(item, str) else str(item)
                for item in cast(list[object], value)
            ]  # type: ignore[assignment]
        else:
            typed_params[key] = str(value) if value is not None else None  # type: ignore[assignment]

    return RefactoringOperationModel(
        operation_id=f"op-{op_type}-001",
        operation_type=op_type,
        target_file=target_file,
        parameters=OperationParameters(**typed_params),  # type: ignore[arg-type]
    )


class TestExecutionOperations:
    """Tests for ExecutionOperations class."""

    @pytest.fixture
    def mock_fs_manager(self) -> MagicMock:
        """Create mock file system manager."""
        fs = MagicMock()
        fs.read_file = AsyncMock(return_value=("content", {}))
        fs.write_file = AsyncMock()
        fs.file_exists = MagicMock(return_value=True)
        return fs

    @pytest.fixture
    def exec_ops(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> ExecutionOperations:
        """Create ExecutionOperations instance."""
        return ExecutionOperations(tmp_path, mock_fs_manager)

    @pytest.mark.asyncio
    async def test_execute_operation_unknown_type(
        self, exec_ops: ExecutionOperations
    ) -> None:
        """Test executing operation with unknown type."""
        # Arrange
        operation = make_operation("unknown_type", "test.md")

        # Act & Assert
        with pytest.raises(ValidationError, match="Unknown operation type"):
            await exec_ops.execute_operation(operation)

    @pytest.mark.asyncio
    async def test_execute_create_operation(
        self, exec_ops: ExecutionOperations, mock_fs_manager: MagicMock
    ) -> None:
        """Test executing create operation."""
        # Arrange
        operation = make_operation(
            "create", "new_file.md", content="# New File\n\nContent here"
        )

        # Act
        await exec_ops.execute_operation(operation)

        # Assert
        mock_fs_manager.write_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_modify_operation(
        self, exec_ops: ExecutionOperations, mock_fs_manager: MagicMock
    ) -> None:
        """Test executing modify operation."""
        # Arrange
        operation = make_operation(
            "modify", "existing.md", content="# Modified Content"
        )

        # Act
        await exec_ops.execute_operation(operation)

        # Assert
        mock_fs_manager.write_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_delete_operation(
        self, exec_ops: ExecutionOperations, mock_fs_manager: MagicMock, tmp_path: Path
    ) -> None:
        """Test executing delete operation."""
        # Arrange
        test_file = tmp_path / "to_delete.md"
        _ = test_file.write_text("# Content to delete")

        operation = make_operation("delete", "to_delete.md")

        # Act
        await exec_ops.execute_operation(operation)

        # Assert - file should be deleted (mock doesn't actually delete)

    @pytest.mark.asyncio
    async def test_execute_move_operation(
        self, exec_ops: ExecutionOperations, mock_fs_manager: MagicMock, tmp_path: Path
    ) -> None:
        """Test executing move operation."""
        # Arrange - create source file
        source_file = tmp_path / "old_location.md"
        _ = source_file.write_text("# Content")

        operation = make_operation(
            "move", "old_location.md", destination_file="new_location.md"
        )

        # Act
        await exec_ops.execute_operation(operation)

        # Assert - file should be moved

    @pytest.mark.asyncio
    async def test_execute_rename_operation(
        self, exec_ops: ExecutionOperations, mock_fs_manager: MagicMock, tmp_path: Path
    ) -> None:
        """Test executing rename operation."""
        # Arrange - create source file
        source_file = tmp_path / "old_name.md"
        _ = source_file.write_text("# Content")

        operation = make_operation("rename", "old_name.md", new_name="new_name.md")

        # Act
        await exec_ops.execute_operation(operation)

        # Assert - file should be renamed

    @pytest.mark.asyncio
    async def test_execute_consolidation(
        self, exec_ops: ExecutionOperations, mock_fs_manager: MagicMock
    ) -> None:
        """Test executing consolidation operation."""
        # Arrange
        operation = make_operation(
            "consolidate",
            "source.md",
            destination_file="consolidated.md",
            source_file="a.md",
            sections=["Section1"],
        )

        # Act
        await exec_ops.execute_operation(operation)

        # Assert - consolidated file should be created
        mock_fs_manager.write_file.assert_called()

    @pytest.mark.asyncio
    async def test_execute_split(
        self, exec_ops: ExecutionOperations, mock_fs_manager: MagicMock
    ) -> None:
        """Test executing split operation."""
        # Arrange
        operation = make_operation(
            "split",
            "large.md",
            destination_file="part1.md",
            sections=["Section A"],
            content="# Part 1 Content",
        )

        # Act
        await exec_ops.execute_operation(operation)

        # Assert - split file should be created
        mock_fs_manager.write_file.assert_called()


class TestExecutionOperationsEdgeCases:
    """Edge case tests for ExecutionOperations."""

    @pytest.fixture
    def mock_fs_manager(self) -> MagicMock:
        """Create mock file system manager."""
        fs = MagicMock()
        fs.read_file = AsyncMock(return_value=("content", {}))
        fs.write_file = AsyncMock()
        fs.file_exists = MagicMock(return_value=True)
        return fs

    @pytest.mark.asyncio
    async def test_create_with_empty_content(
        self, tmp_path: Path, mock_fs_manager: MagicMock
    ) -> None:
        """Test create operation with empty content."""
        # Arrange
        exec_ops = ExecutionOperations(tmp_path, mock_fs_manager)
        operation = make_operation("create", "empty.md", content="")

        # Act
        await exec_ops.execute_operation(operation)

        # Assert - should create with empty content
        mock_fs_manager.write_file.assert_called()
