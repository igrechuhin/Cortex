"""
Unit tests for file_system module.

Tests file system operations including locking, conflict detection, and markdown parsing.
"""

from pathlib import Path

import pytest

from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.file_system import FileSystemManager


class TestFileSystemManagerInitialization:
    """Tests for FileSystemManager initialization."""

    def test_initialization_with_valid_path(self, temp_project_root: Path):
        """Test FileSystemManager initializes with valid project root."""
        # Arrange & Act
        manager = FileSystemManager(temp_project_root)

        # Assert
        assert manager is not None
        assert manager.project_root == temp_project_root.resolve()
        assert (
            manager.memory_bank_dir.resolve()
            == (temp_project_root / ".cortex" / "memory-bank").resolve()
        )
        assert manager.lock_timeout == 5.0

    def test_initialization_resolves_path(self, temp_project_root: Path) -> None:
        """Test FileSystemManager resolves relative paths."""
        # Arrange
        relative_path = temp_project_root / "subdir" / ".."

        # Act
        manager = FileSystemManager(relative_path)

        # Assert
        assert manager.project_root == temp_project_root.resolve()


class TestPathValidation:
    """Tests for path validation and security."""

    def test_validate_path_within_project(self, temp_project_root: Path) -> None:
        """Test validation succeeds for path within project."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        valid_path = temp_project_root / ".cortex" / "memory-bank" / "test.md"

        # Act
        result = manager.validate_path(valid_path)

        # Assert
        assert result is True

    def test_validate_path_outside_project(self, temp_project_root: Path) -> None:
        """Test validation fails for path outside project."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        invalid_path = temp_project_root.parent / "outside.md"

        # Act
        result = manager.validate_path(invalid_path)

        # Assert
        assert result is False

    def test_validate_path_with_traversal_attempt(
        self, temp_project_root: Path
    ) -> None:
        """Test validation blocks directory traversal attempts."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        # Try to traverse outside project using ../
        traversal_path = (
            temp_project_root
            / ".cortex"
            / "memory-bank"
            / ".."
            / ".."
            / ".."
            / "outside.md"
        )

        # Act
        result = manager.validate_path(traversal_path)

        # Assert
        assert result is False


class TestComputeHash:
    """Tests for content hashing."""

    def test_compute_hash_simple_content(self, temp_project_root: Path) -> None:
        """Test computing hash for simple content."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        content = "Hello, world!"

        # Act
        hash_value = manager.compute_hash(content)

        # Assert
        assert hash_value.startswith("sha256:")
        assert len(hash_value) == 71  # "sha256:" (7) + 64 hex chars

    def test_compute_hash_deterministic(self, temp_project_root: Path) -> None:
        """Test hash computation is deterministic."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        content = "Test content"

        # Act
        hash1 = manager.compute_hash(content)
        hash2 = manager.compute_hash(content)

        # Assert
        assert hash1 == hash2

    def test_compute_hash_different_content(self, temp_project_root: Path) -> None:
        """Test different content produces different hashes."""
        # Arrange
        manager = FileSystemManager(temp_project_root)

        # Act
        hash1 = manager.compute_hash("Content A")
        hash2 = manager.compute_hash("Content B")

        # Assert
        assert hash1 != hash2

    def test_compute_hash_empty_string(self, temp_project_root: Path) -> None:
        """Test hashing empty string."""
        # Arrange
        manager = FileSystemManager(temp_project_root)

        # Act
        hash_value = manager.compute_hash("")

        # Assert
        assert hash_value.startswith("sha256:")
        assert len(hash_value) == 71


class TestReadFile:
    """Tests for file reading operations."""

    @pytest.mark.asyncio
    async def test_read_file_simple(self, temp_project_root: Path) -> None:
        """Test reading a simple file."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "test.md"
        expected_content = "# Test File\n\nThis is test content."
        _ = file_path.write_text(expected_content)

        # Act
        content, content_hash = await manager.read_file(file_path)

        # Assert
        assert content == expected_content
        assert content_hash.startswith("sha256:")
        assert content_hash == manager.compute_hash(expected_content)

    @pytest.mark.asyncio
    async def test_read_file_nonexistent(self, temp_project_root: Path) -> None:
        """Test reading nonexistent file raises error."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "nonexistent.md"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            _ = await manager.read_file(file_path)

    @pytest.mark.asyncio
    async def test_read_file_outside_project(self, temp_project_root: Path) -> None:
        """Test reading file outside project raises error."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root.parent / "outside.md"
        _ = file_path.write_text("Outside content")

        # Act & Assert
        with pytest.raises(PermissionError):
            _ = await manager.read_file(file_path)

    @pytest.mark.asyncio
    async def test_read_file_unicode_content(self, temp_project_root: Path) -> None:
        """Test reading file with unicode content."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "unicode.md"
        unicode_content = "Hello 世界! Привет мир! 🚀"
        _ = file_path.write_text(unicode_content, encoding="utf-8")

        # Act
        content, content_hash = await manager.read_file(file_path)

        # Assert
        assert content == unicode_content
        assert content_hash.startswith("sha256:")


class TestWriteFile:
    """Tests for file writing operations."""

    @pytest.mark.asyncio
    async def test_write_file_new_file(self, temp_project_root: Path) -> None:
        """Test writing a new file."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "new.md"
        content = "# New File\n\nNew content."

        # Act
        content_hash = await manager.write_file(file_path, content)

        # Assert
        assert file_path.exists()
        assert file_path.read_text() == content
        assert content_hash == manager.compute_hash(content)

    @pytest.mark.asyncio
    async def test_write_file_creates_parent_directories(
        self, temp_project_root: Path
    ) -> None:
        """Test writing file creates parent directories."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "subdir1" / "subdir2" / "file.md"
        content = "Test content"

        # Act
        _ = await manager.write_file(file_path, content)

        # Assert
        assert file_path.exists()
        assert file_path.parent.exists()

    @pytest.mark.asyncio
    async def test_write_file_overwrites_existing(
        self, temp_project_root: Path
    ) -> None:
        """Test writing file overwrites existing content."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "existing.md"
        _ = file_path.write_text("Old content")
        new_content = "New content"

        # Act
        content_hash = await manager.write_file(file_path, new_content)

        # Assert
        assert file_path.read_text() == new_content
        assert content_hash == manager.compute_hash(new_content)

    @pytest.mark.asyncio
    async def test_write_file_with_conflict_detection(
        self, temp_project_root: Path
    ) -> None:
        """Test write file detects external modifications."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "conflict.md"
        original_content = "Original content"
        _ = file_path.write_text(original_content)

        # Get expected hash
        _, expected_hash = await manager.read_file(file_path)

        # Modify file externally
        _ = file_path.write_text("Externally modified")

        # Act & Assert
        with pytest.raises(FileConflictError):
            _ = await manager.write_file(file_path, "New content", expected_hash)

    @pytest.mark.asyncio
    async def test_write_file_no_conflict_when_hash_matches(
        self, temp_project_root: Path
    ) -> None:
        """Test write succeeds when hash matches."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "test.md"
        original_content = "Original content"
        _ = file_path.write_text(original_content)

        # Get expected hash
        _, expected_hash = await manager.read_file(file_path)

        # Act
        new_content = "New content"
        content_hash = await manager.write_file(file_path, new_content, expected_hash)

        # Assert
        assert file_path.read_text() == new_content
        assert content_hash == manager.compute_hash(new_content)

    @pytest.mark.asyncio
    async def test_write_file_with_git_conflicts(self, temp_project_root: Path) -> None:
        """Test write file rejects content with git conflict markers."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "conflict.md"
        content_with_markers = """
<<<<<<< HEAD
Current content
=======
Incoming content
>>>>>>> branch
"""

        # Act & Assert
        with pytest.raises(GitConflictError):
            _ = await manager.write_file(file_path, content_with_markers)

    @pytest.mark.asyncio
    async def test_write_file_outside_project(self, temp_project_root: Path) -> None:
        """Test writing file outside project raises error."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root.parent / "outside.md"

        # Act & Assert
        with pytest.raises(PermissionError):
            _ = await manager.write_file(file_path, "Content")


class TestFileLocking:
    """Tests for file locking mechanism."""

    @pytest.mark.asyncio
    async def test_lock_acquired_and_released(self, temp_project_root: Path) -> None:
        """Test lock is acquired and released properly."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "test.md"
        lock_path = file_path.with_suffix(file_path.suffix + ".lock")

        # Act
        await manager.acquire_lock(lock_path)
        assert lock_path.exists()

        await manager.release_lock(lock_path)

        # Assert
        assert not lock_path.exists()

    @pytest.mark.asyncio
    async def test_lock_timeout(self, temp_project_root: Path) -> None:
        """Test lock acquisition times out."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        manager.lock_timeout = 1  # Short timeout for testing (int, not float)
        file_path = temp_project_root / "test.md"
        lock_path = file_path.with_suffix(file_path.suffix + ".lock")

        # Acquire lock
        await manager.acquire_lock(lock_path)

        # Act & Assert - Try to acquire again
        with pytest.raises(FileLockTimeoutError):
            await manager.acquire_lock(lock_path)

        # Cleanup
        await manager.release_lock(lock_path)

    @pytest.mark.asyncio
    async def test_write_file_uses_locking(self, temp_project_root: Path) -> None:
        """Test write_file properly uses locking."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "test.md"

        # Act - Write should acquire and release lock
        _ = await manager.write_file(file_path, "Content")

        # Assert - Lock should be released after write
        lock_path = file_path.with_suffix(file_path.suffix + ".lock")
        assert not lock_path.exists()


class TestParseSections:
    """Tests for markdown section parsing."""

    def test_parse_sections_simple(self, temp_project_root: Path) -> None:
        """Test parsing simple markdown sections."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        content = """# Title

## Section 1
Content 1

## Section 2
Content 2"""

        # Act
        sections = manager.parse_sections(content)

        # Assert
        assert len(sections) == 3
        assert sections[0]["heading"] == "# Title"
        assert sections[0]["level"] == 1
        assert sections[1]["heading"] == "## Section 1"
        assert sections[1]["level"] == 2

    def test_parse_sections_nested_levels(self, temp_project_root: Path) -> None:
        """Test parsing nested heading levels."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        content = """# Level 1
## Level 2
### Level 3
#### Level 4
##### Level 5
###### Level 6"""

        # Act
        sections = manager.parse_sections(content)

        # Assert
        assert len(sections) == 6
        assert sections[0]["level"] == 1
        assert sections[5]["level"] == 6

    def test_parse_sections_with_line_numbers(self, temp_project_root: Path) -> None:
        """Test sections include correct line numbers."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        content = """# First
Line 2
Line 3
## Second
Line 5"""

        # Act
        sections = manager.parse_sections(content)

        # Assert
        assert len(sections) == 2
        assert sections[0]["line_start"] == 1
        assert sections[0]["line_end"] == 3
        assert sections[1]["line_start"] == 4
        assert sections[1]["line_end"] == 5

    def test_parse_sections_with_content_hash(self, temp_project_root: Path) -> None:
        """Test sections include content hashes."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        content = """# Section
Content here"""

        # Act
        sections = manager.parse_sections(content)

        # Assert
        assert len(sections) == 1
        assert "content_hash" in sections[0]
        content_hash = sections[0]["content_hash"]
        assert isinstance(content_hash, str)
        assert content_hash.startswith("sha256:")

    def test_parse_sections_empty_content(self, temp_project_root: Path) -> None:
        """Test parsing empty content returns empty list."""
        # Arrange
        manager = FileSystemManager(temp_project_root)

        # Act
        sections = manager.parse_sections("")

        # Assert
        assert sections == []

    def test_parse_sections_no_headings(self, temp_project_root: Path) -> None:
        """Test parsing content without headings returns empty list."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        content = "Just plain text without any headings."

        # Act
        sections = manager.parse_sections(content)

        # Assert
        assert sections == []

    def test_parse_sections_ignores_inline_hashes(
        self, temp_project_root: Path
    ) -> None:
        """Test parser ignores hash symbols not at line start."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        content = """# Real Header
This is not a header: # Hash in middle
Code: `#define MACRO`
## Another Real Header"""

        # Act
        sections = manager.parse_sections(content)

        # Assert
        assert len(sections) == 2
        assert sections[0]["heading"] == "# Real Header"
        assert sections[1]["heading"] == "## Another Real Header"


class TestFileUtilities:
    """Tests for file utility methods."""

    @pytest.mark.asyncio
    async def test_ensure_directory(self, temp_project_root: Path) -> None:
        """Test ensure_directory creates directory."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        dir_path = temp_project_root / "new" / "nested" / "dir"

        # Act
        await manager.ensure_directory(dir_path)

        # Assert
        assert dir_path.exists()
        assert dir_path.is_dir()

    @pytest.mark.asyncio
    async def test_ensure_directory_existing(self, temp_project_root: Path) -> None:
        """Test ensure_directory with existing directory."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        dir_path = temp_project_root / "existing"
        dir_path.mkdir()

        # Act - Should not raise error
        await manager.ensure_directory(dir_path)

        # Assert
        assert dir_path.exists()

    @pytest.mark.asyncio
    async def test_file_exists_true(self, temp_project_root: Path) -> None:
        """Test file_exists returns True for existing file."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "exists.md"
        _ = file_path.write_text("Content")

        # Act
        result = await manager.file_exists(file_path)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_file_exists_false(self, temp_project_root: Path) -> None:
        """Test file_exists returns False for nonexistent file."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "nonexistent.md"

        # Act
        result = await manager.file_exists(file_path)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_file_exists_directory(self, temp_project_root: Path) -> None:
        """Test file_exists returns False for directory."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        dir_path = temp_project_root / "directory"
        dir_path.mkdir()

        # Act
        result = await manager.file_exists(dir_path)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_get_file_size(self, temp_project_root: Path) -> None:
        """Test get_file_size returns correct size."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "sized.md"
        content = "Test content with specific length"
        _ = file_path.write_text(content)
        expected_size = len(content.encode("utf-8"))

        # Act
        size = await manager.get_file_size(file_path)

        # Assert
        assert size == expected_size

    @pytest.mark.asyncio
    async def test_get_file_size_nonexistent(self, temp_project_root: Path) -> None:
        """Test get_file_size raises error for nonexistent file."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "nonexistent.md"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            _ = await manager.get_file_size(file_path)

    @pytest.mark.asyncio
    async def test_get_modification_time(self, temp_project_root: Path) -> None:
        """Test get_modification_time returns timestamp."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        file_path = temp_project_root / "timed.md"
        _ = file_path.write_text("Content")

        # Act
        mtime = await manager.get_modification_time(file_path)

        # Assert
        assert isinstance(mtime, float)
        assert mtime > 0

    @pytest.mark.asyncio
    async def test_cleanup_locks(self, temp_project_root: Path) -> None:
        """Test cleanup_locks removes stale lock files."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        memory_bank_dir = temp_project_root / ".cortex" / "memory-bank"
        memory_bank_dir.mkdir(exist_ok=True)

        # Create some lock files
        lock1 = memory_bank_dir / "file1.md.lock"
        lock2 = memory_bank_dir / "file2.md.lock"
        lock1.touch()
        lock2.touch()

        # Act
        await manager.cleanup_locks()

        # Assert
        assert not lock1.exists()
        assert not lock2.exists()

    @pytest.mark.asyncio
    async def test_cleanup_locks_no_directory(self, temp_project_root: Path) -> None:
        """Test cleanup_locks handles missing directory gracefully."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        # memory-bank directory doesn't exist

        # Act - Should not raise error
        await manager.cleanup_locks()

        # Assert - No error raised


class TestGitConflictDetection:
    """Tests for git conflict marker detection."""

    def test_has_git_conflicts_with_all_markers(self, temp_project_root: Path) -> None:
        """Test detection of content with all git conflict markers."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        content = """
<<<<<<< HEAD
Current content
=======
Incoming content
>>>>>>> branch
"""

        # Act
        result = manager.has_git_conflicts(content)

        # Assert
        assert result is True

    def test_has_git_conflicts_with_single_marker(
        self, temp_project_root: Path
    ) -> None:
        """Test detection with single conflict marker."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        content = "Some content\n<<<<<<< HEAD\nMore content"

        # Act
        result = manager.has_git_conflicts(content)

        # Assert
        assert result is True

    def test_has_git_conflicts_clean_content(self, temp_project_root: Path) -> None:
        """Test no detection with clean content."""
        # Arrange
        manager = FileSystemManager(temp_project_root)
        content = "# Clean File\n\nNo conflicts here."

        # Act
        result = manager.has_git_conflicts(content)

        # Assert
        assert result is False
