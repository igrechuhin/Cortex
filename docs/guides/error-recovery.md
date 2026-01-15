# Error Recovery Guide

This guide provides solutions for common errors in Cortex.

## File Operations Errors

### FileNotFoundError

**Symptoms:**

- Error message: `Failed to read/get file size/get modification time for 'filename'`
- File operations fail

**Causes:**

- The requested file doesn't exist
- File path is incorrect
- Memory bank not initialized

**Solutions:**

1. **Initialize Memory Bank:**

   ```bash
   # Run initialization to create default files
   initialize_memory_bank()
   ```

2. **Check File Path:**
   - Verify the file path is correct (case-sensitive)
   - Ensure you're using the correct directory
   - Check for typos in the filename

3. **Verify Memory Bank Directory:**

   ```bash
   ls -la .cursor/memory-bank/
   # OR
   ls -la memory-bank/
   ```

### PermissionError

**Symptoms:**

- Error message: `Failed to read/write/create directory 'filename': Permission denied`
- Cannot access files or directories

**Causes:**

- Insufficient file system permissions
- File or directory owned by different user
- Read-only file system

**Solutions:**

1. **Check File Permissions:**

   ```bash
   ls -la <file>
   ```

2. **Change Ownership (if appropriate):**

   ```bash
   chown <user> <file>
   # OR for entire directory:
   chown -R <user> memory-bank/
   ```

3. **Change Permissions:**

   ```bash
   chmod 644 <file>  # For files
   chmod 755 <directory>  # For directories
   ```

4. **Run with Appropriate Privileges:**
   - Ensure you're running as the correct user
   - Avoid running with sudo unless necessary

### FileConflictError

**Symptoms:**

- Error message: `Failed to write 'filename': File was modified externally`
- Write operations fail with hash mismatch

**Causes:**

- File modified by external process or user
- Concurrent modifications
- Stale content hash

**Solutions:**

1. **Reload File:**
   - Read the file again to get latest content
   - Review changes made externally
   - Merge changes if needed

2. **Resolve Conflicts Manually:**
   - Compare your changes with external changes
   - Decide which changes to keep
   - Write merged content

3. **Force Write (Use with Caution):**
   - Only if you're certain external changes can be overwritten
   - Write without expected hash check
   - Note: This will discard external changes

### FileLockTimeoutError

**Symptoms:**

- Error message: `Failed to acquire lock on 'filename' after 5s`
- Operations hang or timeout
- Stale `.lock` files exist

**Causes:**

- Another process is writing to the file
- Process crash left stale lock
- Network file system issues

**Solutions:**

1. **Wait and Retry:**
   - Another process may be legitimately writing
   - Wait for operation to complete
   - Retry your operation

2. **Check for Stale Locks:**

   ```bash
   # List lock files
   ls -la memory-bank/*.lock

   # Check age of lock files
   find memory-bank/ -name "*.lock" -mmin +5
   ```

3. **Remove Stale Locks:**

   ```bash
   # Remove locks older than 5 minutes
   find memory-bank/ -name "*.lock" -mmin +5 -delete
   ```

4. **Verify No Other Processes:**

   ```bash
   # Check for MCP server processes
   ps aux | grep cortex
   ```

### GitConflictError

**Symptoms:**

- Error message: `Git conflict markers detected in content`
- Cannot save file with conflict markers

**Causes:**

- Unresolved git merge conflict
- File contains `<<<<<<<`, `=======`, `>>>>>>>` markers

**Solutions:**

1. **Resolve Git Conflicts:**

   ```bash
   # View git status
   git status

   # Open file and manually resolve conflicts
   # Remove conflict markers
   # Keep desired changes
   ```

2. **Remove Conflict Markers:**
   - Edit the file
   - Choose which version to keep
   - Remove all `<<<<<<<`, `=======`, `>>>>>>>` lines
   - Save the resolved file

## Index Errors

### IndexCorruptedError

**Symptoms:**

- Error message: `Failed to load memory bank index: Invalid schema structure`
- Error message: `Invalid JSON at line X`
- Metadata operations fail

**Causes:**

- Corrupted `.memory-bank-index` file
- Invalid JSON in index
- Disk failure during write
- Concurrent modifications

**Solutions:**

1. **Delete and Rebuild Index:**

   ```bash
   # Delete corrupted index
   rm .memory-bank-index

   # Trigger rebuild by running any operation
   get_memory_bank_stats()
   ```

2. **Verify with Validation:**

   ```bash
   # After rebuild, validate
   validate_memory_bank()
   ```

3. **Check Disk Space:**

   ```bash
   df -h
   ```

4. **Check File System Health (if recurring):**

   ```bash
   # macOS
   diskutil verifyVolume /

   # Linux
   fsck -n /dev/sdX
   ```

## Transclusion Errors

### CircularDependencyError

**Symptoms:**

- Error message: `Circular dependency detected: fileA.md -> fileB.md -> fileA.md`
- Transclusion resolution fails

**Causes:**

- File A includes file B
- File B includes file A (or chain back to A)
- Creates infinite loop

**Solutions:**

1. **Identify the Cycle:**
   - Review the error message for the cycle path
   - Check which files include each other

2. **Break the Cycle:**
   - Remove one of the `{{include:}}` directives
   - Reorganize content to avoid circular references
   - Use section-level includes instead of full file includes

3. **Reorganize Content:**
   - Extract shared content to a common file
   - Have both files include the common file
   - Avoid bidirectional includes

### MaxDepthExceededError

**Symptoms:**

- Error message: `Maximum transclusion depth (5) exceeded`
- Deep nested includes fail

**Causes:**

- Too many nested `{{include:}}` directives
- Default depth limit of 5 reached

**Solutions:**

1. **Reduce Nesting Depth:**
   - Flatten the include hierarchy
   - Include files directly rather than through chains

2. **Increase Depth Limit:**

   ```python
   # When initializing TransclusionEngine
   engine = TransclusionEngine(
       file_system=fs,
       link_parser=parser,
       max_depth=10  # Increase from default 5
   )
   ```

3. **Reorganize Content:**
   - Extract deeply nested content to top-level files
   - Use more direct include paths

### Section Not Found

**Symptoms:**

- Error message: `Failed to transclude section 'Section Name': Section heading not found`

**Causes:**

- Section heading doesn't exist in target file
- Case sensitivity mismatch
- Special characters in heading

**Solutions:**

1. **Check Exact Heading:**
   - Review the target file
   - Verify exact heading text including case
   - Check for special characters

2. **List Available Sections:**

   ```python
   # Parse file to see available sections
   result = await parse_file_links(file_name)
   print(result['sections'])
   ```

3. **Fix Include Directive:**

   ```markdown
   # Before (incorrect case)
   {{include:techContext.md#api reference}}

   # After (correct case)
   {{include:techContext.md#API Reference}}
   ```

## Configuration Errors

### Invalid Configuration

**Symptoms:**

- Error messages about invalid config values
- Config validation fails

**Causes:**

- Invalid JSON syntax in `.memory-bank-validation.json`
- Invalid config values (out of range, wrong type)
- Corrupted config file

**Solutions:**

1. **Fix JSON Syntax:**

   ```bash
   # Validate JSON
   python -m json.tool .memory-bank-validation.json
   ```

2. **Check Config Values:**
   - Review validation error messages
   - Ensure values are within valid ranges
   - Check types (string, number, boolean)

3. **Delete Config to Use Defaults:**

   ```bash
   # Backup current config
   mv .memory-bank-validation.json .memory-bank-validation.json.bak

   # System will use default values
   ```

4. **Reset to Defaults:**

   ```python
   # In code
   validation_config.reset_to_defaults()
   await validation_config.save()
   ```

## Git Operation Errors

### Git Operation Failed

**Symptoms:**

- Shared rules sync fails
- Git commands return errors

**Causes:**

- Network unavailable
- Git repository unreachable
- Authentication failure
- Merge conflicts

**Solutions:**

1. **Check Network Connectivity:**

   ```bash
   ping github.com
   ```

2. **Verify Git Credentials:**

   ```bash
   git config --list | grep user
   ```

3. **Check Repository Access:**

   ```bash
   git ls-remote <repository-url>
   ```

4. **Retry Sync:**

   ```python
   # Sync will retry automatically with backoff
   await sync_shared_rules()
   ```

5. **Force Sync (if needed):**
   - Use `force_sync=True` to overwrite local changes
   - Only if local changes can be discarded

## Retry Behavior

Cortex automatically retries transient failures:

### File Operations

- **Retries:** 3 attempts
- **Base Delay:** 0.5 seconds
- **Max Delay:** 10 seconds
- **Retry On:** OSError, IOError, PermissionError, BlockingIOError

### Git Operations

- **Retries:** 2 attempts
- **Base Delay:** 1.0 second
- **Max Delay:** 10 seconds
- **Retry On:** OSError, ConnectionError, TimeoutError

### Metadata Index

- **Retries:** 3 attempts
- **Base Delay:** 0.5 seconds
- **Max Delay:** 10 seconds
- **Retry On:** OSError, IOError, PermissionError

Retries use exponential backoff with jitter to avoid thundering herd problems.

## Graceful Degradation

### Token Counting

- **Primary:** tiktoken (accurate)
- **Fallback:** Word-based estimation (~1 token per 4 characters)
- **Trigger:** tiktoken unavailable or import fails
- **Install:** `pip install tiktoken`

### Shared Rules

- **Primary:** Git-based shared rules
- **Fallback:** Local rules only
- **Trigger:** Git unavailable or network issues
- **Note:** `degraded: true` flag in responses

### Configuration

- **Primary:** User config from `.memory-bank-validation.json`
- **Fallback:** Default configuration values
- **Trigger:** Config file missing, corrupted, or invalid

## Prevention Best Practices

1. **Regular Backups:**
   - Backup `.memory-bank-index` periodically
   - Version control memory bank files with git

2. **Single Server Instance:**
   - Avoid running multiple MCP servers on same directory
   - Use file locking (enabled by default)

3. **Proper Shutdown:**
   - Stop server gracefully to release locks
   - Avoid SIGKILL if possible

4. **Disk Space Monitoring:**
   - Monitor disk space regularly
   - Ensure sufficient space for operations

5. **Regular Validation:**

   ```python
   # Run periodic validation
   result = await validate_memory_bank()
   if result['status'] != 'valid':
       print(result['issues'])
   ```

## Getting Additional Help

If you continue to experience issues:

1. **Check Logs:**
   - Review MCP server logs
   - Look for warning/error messages

2. **Validate Installation:**

   ```bash
   pip show cortex
   python -c "import cortex; print(cortex.__version__)"
   ```

3. **Report Issues:**
   - Include error messages
   - Provide reproduction steps
   - Share relevant log excerpts
   - Note your environment (OS, Python version, etc.)
