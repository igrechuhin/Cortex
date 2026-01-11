"""Custom exceptions for MCP Memory Bank."""


class MemoryBankError(Exception):
    """Base exception for all Memory Bank errors."""

    pass


class FileConflictError(MemoryBankError):
    """Raised when file was modified externally during MCP write operation."""

    def __init__(self, file_name: str, expected_hash: str, actual_hash: str):
        self.file_name: str = file_name
        self.expected_hash: str = expected_hash
        self.actual_hash: str = actual_hash
        super().__init__(
            f"File {file_name} was modified externally. "
            + f"Expected hash {expected_hash[:8]}..., got {actual_hash[:8]}... "
            + "Please review changes before updating."
        )


class IndexCorruptedError(MemoryBankError):
    """Raised when .cortex/index.json is corrupted or invalid."""

    def __init__(self, reason: str):
        self.reason: str = reason
        super().__init__(
            f"Metadata index is corrupted: {reason}. "
            + "Index will be rebuilt from markdown files."
        )


class MigrationFailedError(MemoryBankError):
    """Raised when migration fails."""

    def __init__(self, reason: str, backup_location: str | None = None):
        self.reason: str = reason
        self.backup_location: str | None = backup_location
        message = f"Migration failed: {reason}"
        if backup_location:
            message += f". Backup available at {backup_location}"
        super().__init__(message)


class GitConflictError(MemoryBankError):
    """Raised when Git conflict markers are detected in file."""

    def __init__(self, file_name: str):
        self.file_name: str = file_name
        super().__init__(
            f"File {file_name} contains Git conflict markers "
            + "(<<<<<<, ======, >>>>>>). "
            + "Resolve conflicts before updating Memory Bank metadata."
        )


class TokenLimitExceededError(MemoryBankError):
    """Raised when token budget would be exceeded."""

    def __init__(self, current_tokens: int, limit: int):
        self.current_tokens: int = current_tokens
        self.limit: int = limit
        super().__init__(
            f"Token budget exceeded: {current_tokens} tokens "
            + f"(limit: {limit}). Consider archiving old content."
        )


class FileLockTimeoutError(MemoryBankError):
    """Raised when unable to acquire file lock within timeout."""

    def __init__(self, file_name: str, timeout_seconds: int):
        self.file_name: str = file_name
        self.timeout_seconds: int = timeout_seconds
        super().__init__(
            f"Could not acquire lock for {file_name} "
            + f"within {timeout_seconds} seconds. "
            + "File may be locked by another process."
        )


class ValidationError(MemoryBankError):
    """Raised when validation fails."""

    pass


class FileOperationError(MemoryBankError):
    """Raised when a file operation fails."""

    pass


# Phase 4 Enhancement & Phase 6: Rules-related exceptions


class RulesError(MemoryBankError):
    """Base exception for rules-related errors."""

    pass


class RulesIndexingError(RulesError):
    """Raised when rule indexing fails."""

    def __init__(self, folder: str, reason: str):
        self.folder: str = folder
        self.reason: str = reason
        super().__init__(f"Failed to index rules from {folder}: {reason}")


class SharedRulesError(RulesError):
    """Raised when shared rules operation fails."""

    pass


class SharedRulesGitError(SharedRulesError):
    """Raised when git operation on shared rules fails."""

    def __init__(self, operation: str, reason: str):
        self.operation: str = operation
        self.reason: str = reason
        super().__init__(f"Git {operation} failed for shared rules: {reason}")


# Phase 5: Refactoring and Learning exceptions


class RefactoringError(MemoryBankError):
    """Base exception for refactoring errors."""

    pass


class RefactoringValidationError(RefactoringError):
    """Raised when refactoring validation fails."""

    def __init__(self, suggestion_id: str, reason: str):
        self.suggestion_id: str = suggestion_id
        self.reason: str = reason
        super().__init__(
            f"Refactoring suggestion {suggestion_id} failed validation: {reason}"
        )


class RefactoringExecutionError(RefactoringError):
    """Raised when refactoring execution fails."""

    def __init__(self, suggestion_id: str, reason: str):
        self.suggestion_id: str = suggestion_id
        self.reason: str = reason
        super().__init__(f"Failed to execute refactoring {suggestion_id}: {reason}")


class RollbackError(MemoryBankError):
    """Raised when rollback operation fails."""

    def __init__(self, refactoring_id: str, reason: str):
        self.refactoring_id: str = refactoring_id
        self.reason: str = reason
        super().__init__(f"Failed to rollback refactoring {refactoring_id}: {reason}")


class LearningError(MemoryBankError):
    """Raised when learning engine encounters an error."""

    pass


class ApprovalError(MemoryBankError):
    """Raised when approval management fails."""

    def __init__(self, suggestion_id: str, reason: str):
        self.suggestion_id: str = suggestion_id
        self.reason: str = reason
        super().__init__(
            f"Approval operation failed for suggestion {suggestion_id}: {reason}"
        )


# Phase 8: Project Structure exceptions


class StructureError(MemoryBankError):
    """Base exception for project structure errors."""

    pass


class StructureMigrationError(StructureError):
    """Raised when structure migration fails."""

    def __init__(self, reason: str, backup_location: str | None = None):
        self.reason: str = reason
        self.backup_location: str | None = backup_location
        message = f"Structure migration failed: {reason}"
        if backup_location:
            message += f". Backup available at {backup_location}"
        super().__init__(message)


class SymlinkError(StructureError):
    """Raised when symlink operations fail."""

    def __init__(self, target: str, link: str, reason: str):
        self.target: str = target
        self.link: str = link
        self.reason: str = reason
        super().__init__(f"Failed to create symlink {link} → {target}: {reason}")
