"""Unit tests for RefactoringExecutor - Phase 5.3"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock

import pytest

from cortex.core.exceptions import ValidationError
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.linking.link_parser import LinkParser
from cortex.refactoring.models import (
    OperationParameters,
    RefactoringExecutionModel,
    RefactoringOperationModel,
    RefactoringStatus,
)
from cortex.refactoring.refactoring_executor import RefactoringExecutor


class TestRefactoringStatus:
    """Test RefactoringStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        # Assert
        assert RefactoringStatus.PENDING.value == "pending"
        assert RefactoringStatus.VALIDATING.value == "validating"
        assert RefactoringStatus.EXECUTING.value == "executing"
        assert RefactoringStatus.COMPLETED.value == "completed"
        assert RefactoringStatus.FAILED.value == "failed"
        assert RefactoringStatus.ROLLED_BACK.value == "rolled_back"


class TestRefactoringExecution:
    """Test RefactoringExecutionModel Pydantic model."""

    def test_to_dict_conversion(self):
        """Test converting execution to dictionary."""
        # Arrange
        operation = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="move",
            target_file="test.md",
            parameters=OperationParameters(destination_file="new/"),
        )

        execution = RefactoringExecutionModel(
            execution_id="exec-1",
            suggestion_id="sug-1",
            approval_id="apr-1",
            operations=[operation],
            status=RefactoringStatus.COMPLETED,
            created_at="2025-01-01T12:00:00",
        )

        # Act
        result = execution.model_dump()
        operations = cast(list[dict[str, object]], result["operations"])

        # Assert
        assert result["execution_id"] == "exec-1"
        assert result["suggestion_id"] == "sug-1"
        assert result["approval_id"] == "apr-1"
        assert len(operations) == 1
        assert isinstance(operations[0], dict)


class TestRefactoringExecutorInitialization:
    """Test RefactoringExecutor initialization."""

    @pytest.mark.asyncio
    async def test_initialization_creates_validator(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test executor initialization creates validator."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        # Act
        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Assert
        assert executor.validator is not None
        assert executor.memory_bank_dir == Path(memory_bank_dir)
        assert executor.executions == {}

    @pytest.mark.asyncio
    async def test_initialization_loads_existing_history(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test executor loads existing execution history."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        # Create history file
        history_file = memory_bank_dir.parent / "refactoring-history.json"
        history_data: dict[str, object] = {
            "executions": {
                "exec-1": {
                    "execution_id": "exec-1",
                    "suggestion_id": "sug-1",
                    "approval_id": "apr-1",
                    "operations": [],
                    "status": "completed",
                    "created_at": "2025-01-01T12:00:00",
                }
            }
        }
        # Create parent directory
        history_file.parent.mkdir(parents=True, exist_ok=True)
        _ = history_file.write_text(json.dumps(history_data))

        # Act
        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Assert
        assert len(executor.executions) == 1
        assert "exec-1" in executor.executions


class TestExecuteRefactoring:
    """Test refactoring execution."""

    @pytest.mark.asyncio
    async def test_execute_with_validation_failure(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test execution stops on validation failure."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        suggestion: dict[str, object] = {
            "suggestion_id": "sug-1",
            "type": "consolidation",
            "target_file": "nonexistent.md",
            "files": [],
            "sections": [],
        }

        # Act
        result = await executor.execute_refactoring(
            suggestion_id="sug-1",
            approval_id="apr-1",
            suggestion=suggestion,
            dry_run=False,
            validate_first=True,
        )

        # Assert
        assert result["status"] == "failed"
        error = cast(str | None, result.get("error"))
        assert error is not None and "Validation failed" in error

    @pytest.mark.asyncio
    async def test_execute_with_dry_run(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test dry run execution doesn't make changes."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        suggestion: dict[str, object] = {
            "suggestion_id": "sug-1",
            "type": "split",
            "file": "test.md",
            "split_points": [
                {"new_file": "part1.md", "sections": [], "content": "Content1"}
            ],
        }

        # Act
        result = await executor.execute_refactoring(
            suggestion_id="sug-1",
            approval_id="apr-1",
            suggestion=suggestion,
            dry_run=True,
            validate_first=False,
        )

        # Assert
        assert result["status"] == "success"
        assert result["dry_run"] is True
        assert result["snapshot_id"] is None

    @pytest.mark.asyncio
    async def test_execute_creates_snapshot(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test execution creates snapshot before changes."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Create target file
        target_file = memory_bank_dir / "target.md"
        _ = target_file.write_text("Original content")

        suggestion: dict[str, object] = {
            "suggestion_id": "sug-1",
            "type": "reorganization",
            "actions": [
                {"action": "rename", "file": "target.md", "new_name": "renamed.md"}
            ],
        }

        # Mock version manager
        version_manager.create_snapshot = AsyncMock(return_value="snapshot-1")

        # Act
        result = await executor.execute_refactoring(
            suggestion_id="sug-1",
            approval_id="apr-1",
            suggestion=suggestion,
            dry_run=False,
            validate_first=False,
        )

        # Assert
        assert result["snapshot_id"] is not None
        version_manager.create_snapshot.assert_called()


class TestOperationExecution:
    """Test individual operation execution."""

    @pytest.mark.asyncio
    async def test_execute_move_operation(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test moving a file."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Create source file
        source_file = memory_bank_dir / "source.md"
        _ = source_file.write_text("Content")

        # Create destination directory
        dest_dir = memory_bank_dir / "newdir"
        dest_dir.mkdir()

        operation = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="move",
            target_file="source.md",
            parameters=OperationParameters(destination_file="newdir/source.md"),
        )

        # Act
        await executor.execute_operation(operation)

        # Assert
        assert not source_file.exists()
        assert (dest_dir / "source.md").exists()

    @pytest.mark.asyncio
    async def test_execute_rename_operation(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test renaming a file."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Create source file
        old_file = memory_bank_dir / "old.md"
        _ = old_file.write_text("Content")

        operation = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="rename",
            target_file="old.md",
            parameters=OperationParameters(new_name="new.md"),
        )

        # Act
        await executor.execute_operation(operation)

        # Assert
        assert not old_file.exists()
        assert (memory_bank_dir / "new.md").exists()

    @pytest.mark.asyncio
    async def test_execute_create_directory_operation(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test creating a directory."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        operation = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="create",
            target_file="newdir",
            parameters=OperationParameters(is_directory=True),
        )

        # Act
        await executor.execute_operation(operation)

        # Assert
        assert (memory_bank_dir / "newdir").exists()
        assert (memory_bank_dir / "newdir").is_dir()

    @pytest.mark.asyncio
    async def test_execute_delete_operation(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test deleting a file."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Create file to delete
        file_to_delete = memory_bank_dir / "delete.md"
        _ = file_to_delete.write_text("Content")

        operation = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="delete",
            target_file="delete.md",
            parameters=OperationParameters(),
        )

        # Act
        await executor.execute_operation(operation)

        # Assert
        assert not file_to_delete.exists()

    @pytest.mark.asyncio
    async def test_execute_modify_operation(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test modifying a file."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        file_path = memory_bank_dir / "modify.md"
        _ = file_path.write_text("Original")

        mock_file_system.write_file = AsyncMock()

        operation = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="modify",
            target_file="modify.md",
            parameters=OperationParameters(content="Modified content"),
        )

        # Act
        await executor.execute_operation(operation)

        # Assert
        mock_file_system.write_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_unknown_operation_raises_error(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test unknown operation type raises ValidationError."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        operation = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="unknown",
            target_file="test.md",
            parameters=OperationParameters(),
        )

        # Act & Assert
        with pytest.raises(ValidationError, match="Unknown operation type"):
            await executor.execute_operation(operation)


class TestExecutionHistory:
    """Test execution history management."""

    @pytest.mark.asyncio
    async def test_get_execution_history_filters_by_time(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test history filtering by time range."""
        # Arrange
        from datetime import datetime, timedelta

        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Add old and new executions
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        new_date = datetime.now().isoformat()

        executor.executions["old"] = RefactoringExecutionModel(
            execution_id="old",
            suggestion_id="sug-1",
            approval_id="apr-1",
            operations=[],
            status=RefactoringStatus.COMPLETED,
            created_at=old_date,
        )

        executor.executions["new"] = RefactoringExecutionModel(
            execution_id="new",
            suggestion_id="sug-2",
            approval_id="apr-2",
            operations=[],
            status=RefactoringStatus.COMPLETED,
            created_at=new_date,
        )

        # Act
        result: dict[str, object] = await executor.get_execution_history(
            time_range_days=90
        )

        # Assert
        assert result["total_executions"] == 1
        executions = cast(list[dict[str, object]], result["executions"])
        assert executions[0]["execution_id"] == "new"

    @pytest.mark.asyncio
    async def test_get_execution_by_id(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test retrieving execution by ID."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        execution = RefactoringExecutionModel(
            execution_id="exec-1",
            suggestion_id="sug-1",
            approval_id="apr-1",
            operations=[],
            status=RefactoringStatus.COMPLETED,
            created_at="2025-01-01T12:00:00",
        )
        executor.executions["exec-1"] = execution

        # Act
        result = await executor.get_execution("exec-1")

        # Assert
        assert result is not None
        assert result["execution_id"] == "exec-1"

    @pytest.mark.asyncio
    async def test_get_nonexistent_execution_returns_none(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test getting nonexistent execution returns None."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Act
        result = await executor.get_execution("nonexistent")

        # Assert
        assert result is None


class TestValidateRefactoring:
    """Test refactoring validation."""

    @pytest.mark.asyncio
    async def test_validate_consolidation_suggestion(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test validating consolidation suggestion."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Create target files
        file1 = memory_bank_dir / "file1.md"
        _ = file1.write_text("# Section\nContent")

        suggestion: dict[str, object] = {
            "suggestion_id": "sug-1",
            "type": "consolidation",
            "files": ["file1.md"],
            "sections": ["Section"],
            "target_file": "consolidated.md",
        }

        # Act
        result = await executor.validate_refactoring(suggestion)

        # Assert
        assert "valid" in result
        assert "issues" in result
        assert "warnings" in result
        assert "operations_count" in result

    @pytest.mark.asyncio
    async def test_validate_split_suggestion(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test validating split suggestion."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Create source file
        source = memory_bank_dir / "source.md"
        _ = source.write_text("# Part1\nContent1\n# Part2\nContent2")

        suggestion: dict[str, object] = {
            "suggestion_id": "sug-1",
            "type": "split",
            "file": "source.md",
            "split_points": [
                {
                    "new_file": "part1.md",
                    "sections": ["Part1"],
                    "content": "# Part1\nContent1",
                }
            ],
        }

        # Act
        result = await executor.validate_refactoring(suggestion)

        # Assert
        assert "valid" in result
        assert "issues" in result
        assert "warnings" in result
        assert "operations_count" in result


class TestConsolidationExecution:
    """Test consolidation operation execution."""

    @pytest.mark.asyncio
    async def test_execute_consolidation_merges_sections(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test consolidation merges sections from multiple files."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Create source files
        file1 = memory_bank_dir / "file1.md"
        _ = file1.write_text("# Section1\nContent1")
        file2 = memory_bank_dir / "file2.md"
        _ = file2.write_text("# Section2\nContent2")

        operation = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="consolidate",
            target_file="consolidated.md",
            parameters=OperationParameters(
                source_files=["file1.md", "file2.md"],
                sections=["Section1", "Section2"],
                destination_file="consolidated.md",
            ),
        )

        # Act
        await executor.execute_consolidation(operation)

        # Assert
        target = memory_bank_dir / "consolidated.md"
        assert target.exists()
        content = target.read_text()
        assert "Section1" in content
        assert "Section2" in content


class TestSplitExecution:
    """Test split operation execution."""

    @pytest.mark.asyncio
    async def test_execute_split_creates_new_files(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test split operation creates new files."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Create source file
        source = memory_bank_dir / "source.md"
        _ = source.write_text("# Part1\nContent1\n# Part2\nContent2")

        operation1 = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="split",
            target_file="source.md",
            parameters=OperationParameters(
                destination_file="part1.md",
                sections=[],
                content="# Part1\nContent1",
            ),
        )

        operation2 = RefactoringOperationModel(
            operation_id="op-2",
            operation_type="split",
            target_file="source.md",
            parameters=OperationParameters(
                destination_file="part2.md",
                sections=[],
                content="# Part2\nContent2",
            ),
        )

        # Act
        await executor.execute_split(operation1)
        await executor.execute_split(operation2)

        # Assert
        assert (memory_bank_dir / "part1.md").exists()
        assert (memory_bank_dir / "part2.md").exists()


class TestCreateOperation:
    """Test create operation."""

    @pytest.mark.asyncio
    async def test_execute_create_file_operation(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test creating a new file."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        operation = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="create",
            target_file="newfile.md",
            parameters=OperationParameters(
                content="New content",
                is_directory=False,
            ),
        )

        # Act
        await executor.execute_create(operation)

        # Assert
        new_file = memory_bank_dir / "newfile.md"
        assert new_file.exists()
        assert new_file.read_text() == "New content"


class TestImpactMeasurement:
    """Test impact measurement."""

    @pytest.mark.asyncio
    async def test_measure_impact_calculates_token_changes(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test impact measurement calculates token changes."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        # Create files
        file1 = memory_bank_dir / "file1.md"
        _ = file1.write_text("Original content")

        operations = [
            RefactoringOperationModel(
                operation_id="op-1",
                operation_type="modify",
                target_file="file1.md",
                parameters=OperationParameters(content="Modified longer content here"),
            )
        ]

        # Act
        result = await executor.measure_impact(operations, {"estimated_impact": {}})

        # Assert
        assert "files_affected" in result
        assert "operations_completed" in result
        assert result["operations_completed"] == 1


class TestExtractOperations:
    """Test operation extraction from suggestions."""

    def test_extract_operations_from_consolidation(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test extracting operations from consolidation suggestion."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        suggestion: dict[str, object] = {
            "type": "consolidation",
            "files": ["file1.md", "file2.md"],
            "sections": ["Section1"],
            "target_file": "consolidated.md",
        }

        # Act
        operations = executor.extract_operations(suggestion)

        # Assert
        assert len(operations) == 1
        assert operations[0].operation_type == "consolidate"

    def test_extract_operations_from_split(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test extracting operations from split suggestion."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        suggestion: dict[str, object] = {
            "type": "split",
            "file": "large.md",
            "split_points": [
                {"new_file": "part1.md", "sections": [], "content": "Content1"}
            ],
        }

        # Act
        operations = executor.extract_operations(suggestion)

        # Assert
        assert len(operations) == 1
        assert operations[0].operation_type == "split"

    def test_extract_operations_from_reorganization(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
        mock_link_parser: LinkParser,
    ):
        """Test extracting operations from reorganization suggestion."""
        # Arrange
        from cortex.core.version_manager import VersionManager
        from cortex.linking.link_validator import LinkValidator

        version_manager = VersionManager(
            mock_file_system.project_root,
        )
        link_validator = LinkValidator(
            mock_file_system,
            mock_link_parser,
        )

        executor = RefactoringExecutor(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            link_validator=link_validator,
            metadata_index=mock_metadata_index,
        )

        suggestion: dict[str, object] = {
            "type": "reorganization",
            "actions": [
                {
                    "action": "move",
                    "file": "file1.md",
                    "destination": "newdir/file1.md",
                },
                {"action": "rename", "file": "file2.md", "new_name": "renamed.md"},
            ],
        }

        # Act
        operations = executor.extract_operations(suggestion)

        # Assert
        assert len(operations) == 2
        assert operations[0].operation_type == "move"
        assert operations[1].operation_type == "rename"
