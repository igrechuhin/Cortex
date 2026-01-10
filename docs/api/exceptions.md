# Exception Reference

This document provides a comprehensive reference for all custom exceptions in Cortex.

## Exception Hierarchy

```text
Exception
└── MemoryBankError (base)
    ├── FileConflictError
    ├── IndexCorruptedError
    ├── MigrationFailedError
    ├── GitConflictError
    ├── TokenLimitExceededError
    ├── FileLockTimeoutError
    ├── ValidationError
    ├── FileOperationError
    ├── RulesError
    │   ├── RulesIndexingError
    │   ├── SharedRulesError
    │   └── SharedRulesGitError
    ├── RefactoringError
    │   ├── RefactoringValidationError
    │   └── RefactoringExecutionError
    ├── RollbackError
    ├── LearningError
    ├── ApprovalError
    └── StructureError
        ├── StructureMigrationError
        └── SymlinkError
```

## Base Exceptions

### MemoryBankError

**Module**: `cortex.exceptions`

Base exception for all Memory Bank errors.

```python
class MemoryBankError(Exception):
    """Base exception for all Memory Bank errors."""
```

**Usage**: Catch all Memory Bank-specific exceptions:

```python
try:
    # Memory Bank operations
    ...
except MemoryBankError as e:
    # Handle Memory Bank error
    logger.error(f"Memory Bank error: {e}")
```

## File System Exceptions

### FileConflictError

Raised when file was modified externally during MCP write operation.

**Attributes**:

- `file_name` (str): Name of the conflicting file
- `expected_hash` (str): Expected SHA-256 hash
- `actual_hash` (str): Actual SHA-256 hash found

**Example**:

```python
try:
    await fs_manager.write_file("projectBrief.md", content, expected_hash=hash)
except FileConflictError as e:
    print(f"File {e.file_name} was modified externally")
    print(f"Expected: {e.expected_hash}, Got: {e.actual_hash}")
    # Handle conflict (e.g., refresh and retry)
```

### FileLockTimeoutError

Raised when unable to acquire file lock within timeout.

**Attributes**:

- `file_name` (str): Name of the locked file
- `timeout_seconds` (int): Timeout duration in seconds

**Example**:

```python
try:
    async with fs_manager.acquire_lock("activeContext.md"):
        # Critical section
        ...
except FileLockTimeoutError as e:
    print(f"Could not lock {e.file_name} within {e.timeout_seconds}s")
    # Handle timeout (e.g., retry later)
```

### FileOperationError

Raised when a file operation fails.

**Example**:

```python
try:
    await fs_manager.delete_file("old_file.md")
except FileOperationError as e:
    logger.error(f"Failed to delete file: {e}")
```

### GitConflictError

Raised when Git conflict markers are detected in file.

**Attributes**:

- `file_name` (str): Name of file with conflicts

**Example**:

```python
try:
    await fs_manager.validate_no_conflicts("systemPatterns.md")
except GitConflictError as e:
    print(f"File {e.file_name} contains unresolved Git conflicts")
    # Prompt user to resolve conflicts
```

## Index and Metadata Exceptions

### IndexCorruptedError

Raised when `.memory-bank-index` is corrupted or invalid.

**Attributes**:

- `reason` (str): Reason for corruption

**Example**:

```python
try:
    index = await metadata_index.load()
except IndexCorruptedError as e:
    logger.warning(f"Index corrupted: {e.reason}")
    # Rebuild index from markdown files
    await metadata_index.rebuild()
```

### MigrationFailedError

Raised when migration fails.

**Attributes**:

- `reason` (str): Reason for failure
- `backup_location` (str | None): Path to backup if created

**Example**:

```python
try:
    await migration_manager.migrate()
except MigrationFailedError as e:
    print(f"Migration failed: {e.reason}")
    if e.backup_location:
        print(f"Backup available at: {e.backup_location}")
    # Restore from backup
```

## Validation Exceptions

### ValidationError

Raised when validation fails.

**Example**:

```python
try:
    await schema_validator.validate_file("projectBrief.md")
except ValidationError as e:
    print(f"Validation error: {e}")
    # Show validation errors to user
```

### TokenLimitExceededError

Raised when token budget would be exceeded.

**Attributes**:

- `current_tokens` (int): Current token count
- `limit` (int): Token limit

**Example**:

```python
try:
    await context_optimizer.add_file("large_file.md")
except TokenLimitExceededError as e:
    print(f"Token limit exceeded: {e.current_tokens}/{e.limit}")
    # Suggest archiving or summarization
```

## Rules Exceptions

### RulesError

Base exception for rules-related errors.

### RulesIndexingError

Raised when rule indexing fails.

**Attributes**:

- `folder` (str): Folder being indexed
- `reason` (str): Reason for failure

**Example**:

```python
try:
    await rules_manager.index_rules(".cursorrules")
except RulesIndexingError as e:
    print(f"Failed to index {e.folder}: {e.reason}")
```

### SharedRulesError

Base exception for shared rules operations.

### SharedRulesGitError

Raised when git operation on shared rules fails.

**Attributes**:

- `operation` (str): Git operation (e.g., "pull", "push", "clone")
- `reason` (str): Reason for failure

**Example**:

```python
try:
    await shared_rules_manager.sync()
except SharedRulesGitError as e:
    print(f"Git {e.operation} failed: {e.reason}")
    # Handle git error (e.g., check network, credentials)
```

## Refactoring Exceptions

### RefactoringError

Base exception for refactoring errors.

### RefactoringValidationError

Raised when refactoring validation fails.

**Attributes**:

- `suggestion_id` (str): ID of the suggestion
- `reason` (str): Validation failure reason

**Example**:

```python
try:
    await refactoring_executor.validate_suggestion(suggestion)
except RefactoringValidationError as e:
    print(f"Suggestion {e.suggestion_id} invalid: {e.reason}")
```

### RefactoringExecutionError

Raised when refactoring execution fails.

**Attributes**:

- `suggestion_id` (str): ID of the suggestion
- `reason` (str): Execution failure reason

**Example**:

```python
try:
    await refactoring_executor.execute(suggestion_id)
except RefactoringExecutionError as e:
    print(f"Failed to execute {e.suggestion_id}: {e.reason}")
    # Attempt rollback
```

### RollbackError

Raised when rollback operation fails.

**Attributes**:

- `refactoring_id` (str): ID of the refactoring
- `reason` (str): Rollback failure reason

**Example**:

```python
try:
    await rollback_manager.rollback(refactoring_id)
except RollbackError as e:
    print(f"Rollback failed for {e.refactoring_id}: {e.reason}")
    # Manual intervention required
```

## Learning Exceptions

### LearningError

Raised when learning engine encounters an error.

**Example**:

```python
try:
    await learning_engine.submit_feedback(feedback)
except LearningError as e:
    logger.error(f"Learning engine error: {e}")
```

### ApprovalError

Raised when approval management fails.

**Attributes**:

- `suggestion_id` (str): ID of the suggestion
- `reason` (str): Approval operation failure reason

**Example**:

```python
try:
    await approval_manager.approve(suggestion_id)
except ApprovalError as e:
    print(f"Approval failed for {e.suggestion_id}: {e.reason}")
```

## Project Structure Exceptions

### StructureError

Base exception for project structure errors.

### StructureMigrationError

Raised when structure migration fails.

**Attributes**:

- `reason` (str): Migration failure reason
- `backup_location` (str | None): Path to backup if created

**Example**:

```python
try:
    await structure_manager.migrate_structure()
except StructureMigrationError as e:
    print(f"Structure migration failed: {e.reason}")
    if e.backup_location:
        print(f"Backup at: {e.backup_location}")
```

### SymlinkError

Raised when symlink operations fail.

**Attributes**:

- `target` (str): Symlink target path
- `link` (str): Symlink path
- `reason` (str): Failure reason

**Example**:

```python
try:
    await structure_manager.create_cursor_symlinks()
except SymlinkError as e:
    print(f"Failed to create symlink {e.link} → {e.target}")
    print(f"Reason: {e.reason}")
```

## Error Handling Best Practices

### 1. Catch Specific Exceptions

```python
# Good
try:
    await fs_manager.write_file(...)
except FileConflictError:
    # Handle conflict specifically
    ...
except FileLockTimeoutError:
    # Handle timeout specifically
    ...

# Avoid
try:
    await fs_manager.write_file(...)
except Exception:  # Too broad
    ...
```

### 2. Log with Context

```python
try:
    await fs_manager.write_file(file_path, content)
except MemoryBankError as e:
    logger.error(
        "File write failed",
        extra={
            "file_path": str(file_path),
            "error_type": type(e).__name__,
            "error": str(e)
        }
    )
```

### 3. Provide User-Friendly Messages

```python
try:
    await validation_manager.validate()
except ValidationError as e:
    return {
        "status": "error",
        "message": "Validation failed. Please check your files.",
        "details": str(e)
    }
```

### 4. Clean Up Resources

```python
lock = None
try:
    lock = await fs_manager.acquire_lock(file_path)
    # Critical section
    ...
except FileLockTimeoutError:
    # Handle timeout
    ...
finally:
    if lock:
        await lock.release()
```

### 5. Re-raise When Appropriate

```python
try:
    await some_operation()
except MemoryBankError:
    logger.error("Operation failed")
    raise  # Re-raise to propagate error
```

## Common Error Scenarios

### File Modified Externally

```python
try:
    await fs_manager.write_file(path, content, expected_hash=hash)
except FileConflictError as e:
    # Refresh content and merge changes
    current_content = await fs_manager.read_file(path)
    merged = merge_changes(content, current_content)
    new_hash = compute_hash(current_content)
    await fs_manager.write_file(path, merged, expected_hash=new_hash)
```

### Lock Acquisition Timeout

```python
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        async with fs_manager.acquire_lock(path):
            # Critical section
            break
    except FileLockTimeoutError:
        if attempt == MAX_RETRIES - 1:
            raise
        await asyncio.sleep(1)
```

### Index Corruption

```python
try:
    metadata = await metadata_index.load()
except IndexCorruptedError:
    logger.warning("Rebuilding corrupted index")
    metadata = await metadata_index.rebuild()
```

### Migration Failure

```python
try:
    await migration_manager.migrate()
except MigrationFailedError as e:
    if e.backup_location:
        logger.info(f"Restoring from backup: {e.backup_location}")
        await restore_backup(e.backup_location)
    raise
```

## See Also

- [Architecture](../architecture.md) - Error handling architecture
- [MCP Tools](./tools.md) - Tool error responses
- [Module Documentation](./modules.md) - Module-specific exceptions
