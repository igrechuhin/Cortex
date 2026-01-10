"""
Unit tests for exceptions module.

Tests the custom exception hierarchy and error types defined for MCP Memory Bank.
"""

import pytest

from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    FileOperationError,
    GitConflictError,
    IndexCorruptedError,
    MemoryBankError,
    MigrationFailedError,
    TokenLimitExceededError,
    ValidationError,
)


class TestMemoryBankError:
    """Tests for base MemoryBankError exception."""

    def test_memory_bank_error_is_exception(self):
        """Test that MemoryBankError is an Exception."""
        # Arrange & Act
        error = MemoryBankError("test error")

        # Assert
        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_memory_bank_error_with_cause(self):
        """Test MemoryBankError with underlying cause."""
        # Arrange
        cause = ValueError("original error")

        # Act
        error = MemoryBankError("wrapped error")
        error.__cause__ = cause

        # Assert
        assert error.__cause__ == cause
        assert str(error) == "wrapped error"


class TestFileConflictError:
    """Tests for FileConflictError exception."""

    def test_file_conflict_error_inherits_memory_bank_error(self):
        """Test that FileConflictError inherits from MemoryBankError."""
        # Arrange & Act
        error = FileConflictError("test.md", "hash1", "hash2")

        # Assert
        assert isinstance(error, MemoryBankError)
        assert isinstance(error, Exception)

    def test_file_conflict_error_stores_attributes(self):
        """Test FileConflictError stores file and hash information."""
        # Arrange
        file_name = "projectBrief.md"
        expected_hash = "abc123def456"
        actual_hash = "xyz789uvw012"

        # Act
        error = FileConflictError(file_name, expected_hash, actual_hash)

        # Assert
        assert error.file_name == file_name
        assert error.expected_hash == expected_hash
        assert error.actual_hash == actual_hash
        assert file_name in str(error)
        assert expected_hash[:8] in str(error)
        assert actual_hash[:8] in str(error)

    def test_file_conflict_error_message_format(self):
        """Test FileConflictError has helpful message format."""
        # Arrange & Act
        error = FileConflictError("test.md", "abcdef1234", "123456abcd")

        # Assert
        message = str(error)
        assert "File test.md was modified externally" in message
        assert "Expected hash" in message
        assert "got" in message


class TestIndexCorruptedError:
    """Tests for IndexCorruptedError exception."""

    def test_index_corrupted_error_inherits_memory_bank_error(self):
        """Test that IndexCorruptedError inherits from MemoryBankError."""
        # Arrange & Act
        error = IndexCorruptedError("Invalid JSON")

        # Assert
        assert isinstance(error, MemoryBankError)

    def test_index_corrupted_error_stores_reason(self):
        """Test IndexCorruptedError stores reason."""
        # Arrange
        reason = "JSON parsing failed"

        # Act
        error = IndexCorruptedError(reason)

        # Assert
        assert error.reason == reason
        assert reason in str(error)

    def test_index_corrupted_error_message_mentions_rebuild(self):
        """Test IndexCorruptedError message mentions rebuilding."""
        # Arrange & Act
        error = IndexCorruptedError("test reason")

        # Assert
        message = str(error)
        assert "corrupted" in message.lower()
        assert "rebuilt" in message.lower()


class TestMigrationFailedError:
    """Tests for MigrationFailedError exception."""

    def test_migration_failed_error_inherits_memory_bank_error(self):
        """Test that MigrationFailedError inherits from MemoryBankError."""
        # Arrange & Act
        error = MigrationFailedError("migration failed")

        # Assert
        assert isinstance(error, MemoryBankError)

    def test_migration_failed_error_with_reason_only(self):
        """Test MigrationFailedError with reason only."""
        # Arrange
        reason = "Incompatible format"

        # Act
        error = MigrationFailedError(reason)

        # Assert
        assert error.reason == reason
        assert reason in str(error)
        assert error.backup_location is None

    def test_migration_failed_error_with_backup_location(self):
        """Test MigrationFailedError with backup location."""
        # Arrange
        reason = "Migration failed"
        backup = "/tmp/backup_20250101"

        # Act
        error = MigrationFailedError(reason, backup)

        # Assert
        assert error.reason == reason
        assert error.backup_location == backup
        assert reason in str(error)
        assert backup in str(error)
        assert "Backup available" in str(error)


class TestGitConflictError:
    """Tests for GitConflictError exception."""

    def test_git_conflict_error_inherits_memory_bank_error(self):
        """Test that GitConflictError inherits from MemoryBankError."""
        # Arrange & Act
        error = GitConflictError("test.md")

        # Assert
        assert isinstance(error, MemoryBankError)

    def test_git_conflict_error_stores_file_name(self):
        """Test GitConflictError stores file name."""
        # Arrange
        file_name = "activeContext.md"

        # Act
        error = GitConflictError(file_name)

        # Assert
        assert error.file_name == file_name
        assert file_name in str(error)

    def test_git_conflict_error_mentions_conflict_markers(self):
        """Test GitConflictError message mentions conflict markers."""
        # Arrange & Act
        error = GitConflictError("test.md")

        # Assert
        message = str(error)
        assert "conflict markers" in message.lower()
        assert "<<<<<<" in message or "======" in message or ">>>>>>" in message


class TestTokenLimitExceededError:
    """Tests for TokenLimitExceededError exception."""

    def test_token_limit_exceeded_error_inherits_memory_bank_error(self):
        """Test that TokenLimitExceededError inherits from MemoryBankError."""
        # Arrange & Act
        error = TokenLimitExceededError(100000, 80000)

        # Assert
        assert isinstance(error, MemoryBankError)

    def test_token_limit_exceeded_error_stores_values(self):
        """Test TokenLimitExceededError stores current and limit values."""
        # Arrange
        current_tokens = 95000
        limit = 80000

        # Act
        error = TokenLimitExceededError(current_tokens, limit)

        # Assert
        assert error.current_tokens == current_tokens
        assert error.limit == limit
        assert str(current_tokens) in str(error)
        assert str(limit) in str(error)

    def test_token_limit_exceeded_error_message_format(self):
        """Test TokenLimitExceededError has helpful message."""
        # Arrange & Act
        error = TokenLimitExceededError(100000, 80000)

        # Assert
        message = str(error)
        assert "Token budget exceeded" in message
        assert "archiving" in message.lower()


class TestFileLockTimeoutError:
    """Tests for FileLockTimeoutError exception."""

    def test_file_lock_timeout_error_inherits_memory_bank_error(self):
        """Test that FileLockTimeoutError inherits from MemoryBankError."""
        # Arrange & Act
        error = FileLockTimeoutError("test.md", 30)

        # Assert
        assert isinstance(error, MemoryBankError)

    def test_file_lock_timeout_error_stores_values(self):
        """Test FileLockTimeoutError stores file and timeout values."""
        # Arrange
        file_name = "projectBrief.md"
        timeout = 60

        # Act
        error = FileLockTimeoutError(file_name, timeout)

        # Assert
        assert error.file_name == file_name
        assert error.timeout_seconds == timeout
        assert file_name in str(error)
        assert str(timeout) in str(error)

    def test_file_lock_timeout_error_message_format(self):
        """Test FileLockTimeoutError has helpful message."""
        # Arrange & Act
        error = FileLockTimeoutError("test.md", 30)

        # Assert
        message = str(error)
        assert "Could not acquire lock" in message
        assert "another process" in message.lower()


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_validation_error_inherits_memory_bank_error(self):
        """Test that ValidationError inherits from MemoryBankError."""
        # Arrange & Act
        error = ValidationError("validation failed")

        # Assert
        assert isinstance(error, MemoryBankError)
        assert str(error) == "validation failed"


class TestFileOperationError:
    """Tests for FileOperationError exception."""

    def test_file_operation_error_inherits_memory_bank_error(self):
        """Test that FileOperationError inherits from MemoryBankError."""
        # Arrange & Act
        error = FileOperationError("operation failed")

        # Assert
        assert isinstance(error, MemoryBankError)
        assert str(error) == "operation failed"


class TestExceptionHierarchy:
    """Tests for exception hierarchy and inheritance."""

    def test_all_exceptions_inherit_from_memory_bank_error(self):
        """Test that all custom exceptions inherit from MemoryBankError."""
        # Arrange
        exceptions = [
            FileConflictError("f", "h1", "h2"),
            IndexCorruptedError("reason"),
            MigrationFailedError("reason"),
            GitConflictError("file"),
            TokenLimitExceededError(100, 80),
            FileLockTimeoutError("file", 30),
            ValidationError("test"),
            FileOperationError("test"),
        ]

        # Act & Assert
        for exc in exceptions:
            assert isinstance(exc, MemoryBankError)
            assert isinstance(exc, Exception)

    def test_exception_hierarchy_structure(self):
        """Test the exception hierarchy structure."""
        # Arrange & Act & Assert
        # All custom exceptions inherit from MemoryBankError
        assert issubclass(FileConflictError, MemoryBankError)
        assert issubclass(IndexCorruptedError, MemoryBankError)
        assert issubclass(MigrationFailedError, MemoryBankError)
        assert issubclass(GitConflictError, MemoryBankError)
        assert issubclass(TokenLimitExceededError, MemoryBankError)
        assert issubclass(FileLockTimeoutError, MemoryBankError)
        assert issubclass(ValidationError, MemoryBankError)
        assert issubclass(FileOperationError, MemoryBankError)

        # MemoryBankError inherits from Exception
        assert issubclass(MemoryBankError, Exception)

    def test_catching_specific_exception_with_base(self):
        """Test catching specific exceptions with base exception."""

        # Arrange
        def raise_file_conflict_error():
            raise FileConflictError("test.md", "hash1", "hash2")

        # Act & Assert
        with pytest.raises(MemoryBankError) as exc_info:
            raise_file_conflict_error()

        assert isinstance(exc_info.value, FileConflictError)
        assert "test.md" in str(exc_info.value)

    def test_catching_specific_exception_type(self):
        """Test catching specific exception type."""

        # Arrange
        def raise_token_limit_error():
            raise TokenLimitExceededError(100000, 80000)

        # Act & Assert
        with pytest.raises(TokenLimitExceededError) as exc_info:
            raise_token_limit_error()

        assert exc_info.value.current_tokens == 100000
        assert exc_info.value.limit == 80000
