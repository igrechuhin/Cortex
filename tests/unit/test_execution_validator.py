"""Unit tests for ExecutionValidator - Phase 5.3"""

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock

import pytest

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.refactoring.execution_validator import ExecutionValidator
from cortex.refactoring.models import (
    ActionDetails,
    OperationParameters,
    RefactoringActionModel,
    RefactoringImpactMetrics,
    RefactoringOperationModel,
    RefactoringPriority,
    RefactoringStatus,
    RefactoringSuggestionModel,
    RefactoringType,
)


@pytest.fixture
def memory_bank_dir(temp_project_root: Path) -> Path:
    """Memory bank directory for ExecutionValidator tests (uses path_resolver)."""
    return get_cortex_path(temp_project_root, CortexResourceType.MEMORY_BANK)


class TestRefactoringOperation:
    """Test RefactoringOperationModel Pydantic model."""

    def test_initialization_with_required_fields(self):
        """Test operation initialization with required fields."""
        # Arrange & Act
        op = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="consolidate",
            target_file="test.md",
            parameters=OperationParameters(),
        )

        # Assert
        assert op.operation_id == "op-1"
        assert op.operation_type == "consolidate"
        assert op.target_file == "test.md"
        assert isinstance(op.parameters, OperationParameters)
        assert op.status == RefactoringStatus.PENDING
        assert op.error is None
        assert op.created_at is not None

    def test_default_created_at(self):
        """Test default created_at timestamp."""
        # Arrange & Act
        op = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="modify",
            target_file="test.md",
            parameters=OperationParameters(),
        )

        # Assert
        assert op.created_at is not None
        assert isinstance(op.created_at, str)

    def test_custom_created_at(self):
        """Test that custom created_at is preserved."""
        # Arrange
        custom_time = "2025-01-01T12:00:00"

        # Act
        op = RefactoringOperationModel(
            operation_id="op-1",
            operation_type="delete",
            target_file="test.md",
            parameters=OperationParameters(),
            created_at=custom_time,
        )

        # Assert
        assert op.created_at == custom_time


class TestExecutionValidatorInitialization:
    """Test ExecutionValidator initialization."""

    @pytest.mark.asyncio
    async def test_initialization_with_valid_dependencies(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test validator initialization with valid dependencies."""
        # Arrange & Act
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )

        # Assert
        assert validator.memory_bank_dir == Path(memory_bank_dir)
        assert validator.fs_manager == mock_file_system
        assert validator.metadata_index == mock_metadata_index


class TestExtractOperations:
    """Test operation extraction from suggestions."""

    @pytest.mark.asyncio
    async def test_extract_consolidation_operation(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test extracting consolidation operation from suggestion."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )
        suggestion = RefactoringSuggestionModel(
            suggestion_id="sug-1",
            refactoring_type=RefactoringType.CONSOLIDATION,
            priority=RefactoringPriority.MEDIUM,
            title="Consolidate",
            description="Consolidate duplicate content",
            reasoning="Reduce duplication",
            affected_files=["file1.md", "file2.md"],
            actions=[
                RefactoringActionModel(
                    action_type="consolidate",
                    target_file="consolidated.md",
                    description="Consolidate",
                    details=ActionDetails(
                        destination_file="consolidated.md",
                        sections=["Section1"],
                    ),
                ),
            ],
            confidence_score=0.8,
        )

        # Act
        operations = validator.extract_operations(suggestion)

        # Assert
        assert len(operations) == 1
        assert operations[0].operation_type == "consolidate"
        assert operations[0].target_file == "consolidated.md"
        assert operations[0].parameters.source_file == "file1.md"
        assert operations[0].parameters.destination_file == "consolidated.md"
        assert operations[0].parameters.sections == ["Section1"]

    @pytest.mark.asyncio
    async def test_extract_split_operations(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test extracting split operations from suggestion."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )
        suggestion = RefactoringSuggestionModel(
            suggestion_id="sug-2",
            refactoring_type=RefactoringType.SPLIT,
            priority=RefactoringPriority.MEDIUM,
            title="Split",
            description="Split file",
            reasoning="Test",
            affected_files=["large.md"],
            actions=[
                RefactoringActionModel(
                    action_type="split",
                    target_file="large.md",
                    description="Split",
                    details=ActionDetails(
                        destination_file="part1.md",
                        sections=["Section1"],
                        content="Content1",
                    ),
                ),
                RefactoringActionModel(
                    action_type="split",
                    target_file="large.md",
                    description="Split",
                    details=ActionDetails(
                        destination_file="part2.md",
                        sections=["Section2"],
                        content="Content2",
                    ),
                ),
            ],
            confidence_score=0.8,
        )

        # Act
        operations = validator.extract_operations(suggestion)

        # Assert
        assert len(operations) == 2
        assert all(op.operation_type == "split" for op in operations)
        assert operations[0].target_file == "large.md"
        assert operations[0].parameters.destination_file == "part1.md"
        assert operations[1].parameters.destination_file == "part2.md"

    @pytest.mark.asyncio
    async def test_extract_reorganization_operations(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test extracting reorganization operations from suggestion."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )
        suggestion = RefactoringSuggestionModel(
            suggestion_id="sug-3",
            refactoring_type=RefactoringType.REORGANIZATION,
            priority=RefactoringPriority.MEDIUM,
            title="Reorganize",
            description="Reorganize",
            reasoning="Test",
            affected_files=[],
            actions=[
                RefactoringActionModel(
                    action_type="move",
                    target_file="file1.md",
                    description="Move",
                    details=ActionDetails(destination_file="subdir/"),
                ),
                RefactoringActionModel(
                    action_type="rename",
                    target_file="file2.md",
                    description="Rename",
                    details=ActionDetails(destination_file="renamed.md"),
                ),
                RefactoringActionModel(
                    action_type="create_category",
                    target_file="newdir",
                    description="Create category",
                    details=ActionDetails(),
                ),
            ],
            confidence_score=0.8,
        )

        # Act
        operations = validator.extract_operations(suggestion)

        # Assert
        assert len(operations) == 3
        assert operations[0].operation_type == "move"
        assert operations[1].operation_type == "rename"
        assert operations[2].operation_type == "create"

    @pytest.mark.asyncio
    async def test_extract_operations_with_no_type(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test extracting operations from suggestion with no type."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )

        suggestion = {"suggestion_id": "sug-4"}

        # Act
        operations = validator.extract_operations(cast(ModelDict, suggestion))

        # Assert
        assert len(operations) == 0


class TestValidateRefactoring:
    """Test refactoring validation."""

    @pytest.mark.asyncio
    async def test_validate_with_nonexistent_target_file(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test validation fails when target file doesn't exist."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )

        suggestion = RefactoringSuggestionModel(
            suggestion_id="sug-1",
            refactoring_type=RefactoringType.CONSOLIDATION,
            priority=RefactoringPriority.MEDIUM,
            title="Consolidate",
            description="Consolidate",
            reasoning="Test",
            affected_files=[],
            actions=[
                RefactoringActionModel(
                    action_type="consolidate",
                    target_file="nonexistent.md",
                    description="Consolidate",
                    details=ActionDetails(destination_file="nonexistent.md"),
                ),
            ],
            confidence_score=0.8,
        )

        # Act
        result = await validator.validate_refactoring(suggestion, dry_run=True)

        # Assert
        assert result.valid is False
        assert len(result.issues) > 0
        assert any("does not exist" in issue for issue in result.issues)

    @pytest.mark.asyncio
    async def test_validate_with_existing_file_creation(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test validation fails when creating file that exists."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )

        # Create existing file
        existing_file = memory_bank_dir / "existing.md"
        _ = existing_file.write_text("Content")

        suggestion = RefactoringSuggestionModel(
            suggestion_id="sug-2",
            refactoring_type=RefactoringType.REORGANIZATION,
            priority=RefactoringPriority.MEDIUM,
            title="Reorganize",
            description="Reorganize",
            reasoning="Test",
            affected_files=[],
            actions=[
                RefactoringActionModel(
                    action_type="create_category",
                    target_file="existing.md",
                    description="Create category",
                    details=ActionDetails(),
                ),
            ],
            confidence_score=0.8,
        )

        # Act
        result = await validator.validate_refactoring(suggestion, dry_run=True)

        # Assert
        assert result.valid is False
        assert any("already exists" in issue for issue in result.issues)

    @pytest.mark.asyncio
    async def test_validate_with_uncommitted_changes_warning(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test validation warns about uncommitted changes."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )

        # Create target file
        target_file = memory_bank_dir / "modified.md"
        _ = target_file.write_text("Content")

        # Mock metadata to indicate external modification
        mock_metadata_index.get_file_metadata = AsyncMock(
            return_value={"modified_externally": True}
        )

        suggestion = RefactoringSuggestionModel(
            suggestion_id="sug-3",
            refactoring_type=RefactoringType.REORGANIZATION,
            priority=RefactoringPriority.MEDIUM,
            title="Reorganize",
            description="Reorganize",
            reasoning="Test",
            affected_files=[],
            actions=[
                RefactoringActionModel(
                    action_type="rename",
                    target_file="modified.md",
                    description="Rename",
                    details=ActionDetails(destination_file="new.md"),
                ),
            ],
            confidence_score=0.8,
        )

        # Act
        result = await validator.validate_refactoring(suggestion, dry_run=True)

        # Assert
        assert len(result.warnings) > 0
        assert any("uncommitted changes" in warn for warn in result.warnings)

    @pytest.mark.asyncio
    async def test_validate_with_token_budget_impact_warning(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test validation warns about negative token impact."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )

        suggestion = RefactoringSuggestionModel(
            suggestion_id="sug-4",
            refactoring_type=RefactoringType.SPLIT,
            priority=RefactoringPriority.MEDIUM,
            title="Split",
            description="Split",
            reasoning="Test",
            affected_files=["large.md"],
            actions=[],
            confidence_score=0.8,
            estimated_impact=RefactoringImpactMetrics(token_savings=-1500),
        )

        # Act
        result = await validator.validate_refactoring(suggestion, dry_run=True)

        # Assert
        assert len(result.warnings) > 0
        assert any("increase token usage" in warn for warn in result.warnings)

    @pytest.mark.asyncio
    async def test_validate_with_complexity_increase_warning(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test validation warns about complexity increase."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )

        suggestion = RefactoringSuggestionModel(
            suggestion_id="sug-5",
            refactoring_type=RefactoringType.CONSOLIDATION,
            priority=RefactoringPriority.MEDIUM,
            title="Consolidate",
            description="Consolidate",
            reasoning="Test",
            affected_files=[],
            actions=[
                RefactoringActionModel(
                    action_type="consolidate",
                    target_file="test.md",
                    description="Consolidate",
                    details=ActionDetails(destination_file="test.md"),
                ),
            ],
            confidence_score=0.8,
            estimated_impact=RefactoringImpactMetrics(complexity_reduction=-0.2),
        )

        # Act
        result = await validator.validate_refactoring(suggestion, dry_run=True)

        # Assert
        assert len(result.warnings) > 0
        assert any("increase complexity" in warn for warn in result.warnings)

    @pytest.mark.asyncio
    async def test_validate_dependency_integrity_check(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test validation checks for dependency integrity."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )

        # Create files with dependency
        target_file = memory_bank_dir / "target.md"
        _ = target_file.write_text("Target content")

        dependent_file = memory_bank_dir / "dependent.md"
        _ = dependent_file.write_text("Link to [target](target.md)")

        mock_file_system.read_file = AsyncMock(
            return_value=("Link to [target](target.md)", None)
        )

        suggestion = RefactoringSuggestionModel(
            suggestion_id="sug-6",
            refactoring_type=RefactoringType.REORGANIZATION,
            priority=RefactoringPriority.MEDIUM,
            title="Reorganize",
            description="Reorganize",
            reasoning="Test",
            affected_files=[],
            actions=[
                RefactoringActionModel(
                    action_type="move",
                    target_file="target.md",
                    description="Move",
                    details=ActionDetails(destination_file="new/"),
                ),
            ],
            confidence_score=0.8,
        )

        # Act
        result = await validator.validate_refactoring(suggestion, dry_run=False)

        # Assert
        assert len(result.warnings) > 0
        assert any("may have links to target.md" in warn for warn in result.warnings)

    @pytest.mark.asyncio
    async def test_validate_returns_operations_count(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test validation returns operations count."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )

        suggestion = RefactoringSuggestionModel(
            suggestion_id="sug-7",
            refactoring_type=RefactoringType.SPLIT,
            priority=RefactoringPriority.MEDIUM,
            title="Split",
            description="Split",
            reasoning="Test",
            affected_files=["test.md"],
            actions=[
                RefactoringActionModel(
                    action_type="split",
                    target_file="test.md",
                    description="Split",
                    details=ActionDetails(
                        destination_file="part1.md",
                        sections=[],
                        content="",
                    ),
                ),
                RefactoringActionModel(
                    action_type="split",
                    target_file="test.md",
                    description="Split",
                    details=ActionDetails(
                        destination_file="part2.md",
                        sections=[],
                        content="",
                    ),
                ),
            ],
            confidence_score=0.8,
        )

        # Act
        result = await validator.validate_refactoring(suggestion, dry_run=True)

        # Assert
        assert result.operations_count == 2
        assert result.dry_run is True


class TestGetAllMemoryBankFiles:
    """Test getting all memory bank files."""

    @pytest.mark.asyncio
    async def test_get_all_files_with_multiple_files(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test retrieving all memory bank files."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )

        # Create test files
        _ = (memory_bank_dir / "file1.md").write_text("Content1")
        _ = (memory_bank_dir / "file2.md").write_text("Content2")
        subdir = memory_bank_dir / "subdir"
        subdir.mkdir()
        _ = (subdir / "file3.md").write_text("Content3")

        # Act
        files = await validator.get_all_memory_bank_files()

        # Assert
        assert len(files) == 3
        assert "file1.md" in files
        assert "file2.md" in files
        assert "subdir/file3.md" in files

    @pytest.mark.asyncio
    async def test_get_all_files_excludes_non_markdown(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test that non-markdown files are excluded."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )

        # Create test files
        _ = (memory_bank_dir / "file1.md").write_text("Content1")
        _ = (memory_bank_dir / "file2.txt").write_text("Content2")
        _ = (memory_bank_dir / "file3.json").write_text("{}")

        # Act
        files = await validator.get_all_memory_bank_files()

        # Assert
        assert len(files) == 1
        assert "file1.md" in files

    @pytest.mark.asyncio
    async def test_get_all_files_empty_directory(
        self,
        memory_bank_dir: Path,
        mock_file_system: FileSystemManager,
        mock_metadata_index: MetadataIndex,
    ):
        """Test getting files from empty directory."""
        # Arrange
        validator = ExecutionValidator(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            metadata_index=mock_metadata_index,
        )

        # Act
        files = await validator.get_all_memory_bank_files()

        # Assert
        assert len(files) == 0
