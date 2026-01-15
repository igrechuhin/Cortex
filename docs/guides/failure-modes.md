# Failure Modes and Recovery

This document describes all known failure modes in Cortex, their causes, impacts, and recovery procedures.

## Overview

Cortex implements multiple layers of error handling:

- **Automatic Retry:** Transient failures are retried with exponential backoff
- **Graceful Degradation:** Optional features fall back to simpler alternatives
- **Error Recovery:** Corrupted data can be automatically rebuilt
- **Defensive Programming:** Validation and sanity checks throughout

## Critical Failures

These failures can prevent the system from operating and require immediate action.

### 1. Memory Bank Index Corruption

**Severity:** High
**Impact:** All metadata operations may fail

**Symptoms:**

- `IndexCorruptedError` on startup or operations
- Error: "Invalid JSON at line X"
- Error: "Invalid schema structure"
- Missing or incorrect file metadata
- Inconsistent dependency graph

**Causes:**

- Disk failure during write operation
- Concurrent modification by multiple processes
- Invalid JSON syntax in `.memory-bank-index` file
- Power loss during save
- File system corruption

**Impact:**

- File metadata may be stale or missing
- Token counts may be incorrect
- Dependency information may be wrong
- Version history may be lost
- Operations fail until resolved

**Recovery Procedure:**

1. **Automatic Recovery (Preferred):**

   ```bash
   # Delete corrupted index
   rm .memory-bank-index

   # Run any operation to trigger rebuild
   get_memory_bank_stats()
   ```

   The system automatically:
   - Creates backup of corrupted index (`.memory-bank-index.corrupted`)
   - Builds new index from scratch
   - Scans all memory bank files
   - Regenerates metadata

2. **Manual Verification:**

   ```bash
   # After rebuild, validate
   validate_memory_bank()

   # Check stats look correct
   get_memory_bank_stats()
   ```

3. **If Problems Persist:**
   - Check disk space: `df -h`
   - Check file system health
   - Verify file permissions
   - Check for concurrent processes

**Prevention:**

- Enable atomic writes (default: enabled)
- Use file locking (default: enabled)
- Maintain regular backups
- Monitor disk space
- Run single MCP server instance per directory
- Use UPS for power protection

**Recovery Time:** 1-30 seconds (depends on number of files)

---

### 2. File Lock Deadlock

**Severity:** High
**Impact:** File operations blocked, server may become unresponsive

**Symptoms:**

- Operations hang indefinitely
- `FileLockTimeoutError` after 5 seconds
- Error: "Failed to acquire lock after 5s"
- Stale `.lock` files in memory-bank directory
- Multiple processes waiting

**Causes:**

- Process crash during locked operation
- Server terminated without cleanup
- Network file system latency issues
- Multiple concurrent write attempts
- Lock file not released properly

**Impact:**

- All write operations to locked file blocked
- Read operations may be delayed
- Server appears frozen for that file
- Other files remain accessible

**Recovery Procedure:**

1. **Identify Stale Locks:**

   ```bash
   # List lock files with timestamps
   ls -lh memory-bank/*.lock

   # Find locks older than 1 minute
   find memory-bank/ -name "*.lock" -mmin +1
   ```

2. **Verify No Active Processes:**

   ```bash
   # Check for running MCP servers
   ps aux | grep cortex

   # Check what process holds the lock (Linux)
   lsof memory-bank/*.lock
   ```

3. **Remove Stale Locks:**

   ```bash
   # Remove specific lock
   rm memory-bank/filename.md.lock

   # Or remove all locks older than 1 minute
   find memory-bank/ -name "*.lock" -mmin +1 -delete
   ```

4. **Restart Server (if needed):**

   ```bash
   # Stop MCP server
   pkill -f cortex

   # Server auto-cleans locks on startup
   ```

**Prevention:**

- Use single MCP server instance
- Implement proper shutdown handlers
- Configure appropriate timeout (default: 5s)
- Enable automatic stale lock cleanup
- Avoid SIGKILL, use SIGTERM
- Use local file system (avoid NFS if possible)

**Recovery Time:** Immediate (remove lock file)

---

### 3. Project Root Path Traversal

**Severity:** Critical (Security)
**Impact:** Potential unauthorized file access

**Symptoms:**

- `PermissionError`: "Path outside project root"
- File operations rejected
- Validation failures

**Causes:**

- Malicious input with path traversal (../)
- Incorrect project root configuration
- Symbolic link manipulation
- Absolute paths outside project

**Impact:**

- Operations correctly rejected (defense working)
- No data corruption
- No unauthorized access

**Recovery Procedure:**

1. **Verify Project Root:**

   ```python
   # Check configured project root
   print(file_system.project_root)
   ```

2. **Use Correct Paths:**
   - Use relative paths within project
   - Avoid `../` in file names
   - No absolute paths outside project

3. **Check File Paths:**

   ```bash
   # Verify all files are within project
   find . -name "*.md" -not -path "./.git/*"
   ```

**Prevention:**

- All paths validated on input (enabled by default)
- Paths resolved to absolute before validation
- No operations allowed outside project root
- File name validation rejects dangerous characters

**Recovery Time:** N/A (operation correctly rejected)

---

## Non-Critical Failures

These failures degrade functionality but allow system to continue operating.

### 4. Shared Rules Sync Failure

**Severity:** Medium
**Impact:** Shared rules may be outdated, local rules still work

**Symptoms:**

- `GitOperationError` during sync
- Error: "Git pull failed with exit code 1"
- Network timeout errors
- Shared rules not updated

**Causes:**

- Network unavailable
- Git repository unreachable
- Authentication failure
- Local changes conflict with remote
- Git not installed

**Impact:**

- Shared rules may be stale
- Local rules continue working
- System marks status as `degraded: true`
- Context-aware rule loading reduced

**Degradation Behavior:**

```json
{
  "status": "degraded",
  "local_rules": ["..."],
  "shared_rules": [],
  "degradation_reason": "Git unavailable",
  "warning": "Using local rules only"
}
```

**Recovery Procedure:**

1. **Check Network:**

   ```bash
   ping github.com
   curl -I https://github.com
   ```

2. **Verify Git Access:**

   ```bash
   git --version
   git ls-remote <repo-url>
   ```

3. **Check Credentials:**

   ```bash
   git config --list | grep credential
   ssh -T git@github.com  # For SSH
   ```

4. **Retry Sync:**

   ```python
   # Auto-retries with backoff
   result = await sync_shared_rules()
   ```

5. **Handle Conflicts:**

   ```bash
   # If local changes conflict
   cd .shared-rules
   git status
   git stash  # Or commit/resolve conflicts
   cd ..
   await sync_shared_rules()
   ```

**Prevention:**

- Check network connectivity before sync
- Use credential caching
- Sync during low-traffic periods
- Commit local changes before sync
- Handle merge conflicts promptly

**Recovery Time:** Depends on network (auto-retry: 2 attempts)

---

### 5. Token Count Estimation Fallback

**Severity:** Low
**Impact:** Token counts less accurate but usable

**Symptoms:**

- Warning: "tiktoken not available, using word-based estimation"
- Token counts approximate
- Budget estimates less precise

**Causes:**

- `tiktoken` not installed
- tiktoken import failed
- Encoding download failed
- Python version incompatibility

**Impact:**

- Token counts ~80% accurate
- Token budgets slightly off
- Optimization less precise
- System continues functioning

**Degradation Behavior:**

- Uses word-based estimation: ~1 token per 4 characters
- Less accurate than tiktoken (±20%)
- Sufficient for most use cases
- Warning logged once

**Recovery Procedure:**

1. **Install tiktoken:**

   ```bash
   pip install tiktoken
   ```

2. **Verify Installation:**

   ```bash
   python -c "import tiktoken; print('OK')"
   ```

3. **Clear Cache:**

   ```python
   token_counter.clear_cache()
   ```

4. **Re-run Operations:**

   ```python
   # Token counts will now be accurate
   result = await get_memory_bank_stats()
   ```

**Prevention:**

- Include tiktoken in requirements
- Test installation in CI/CD
- Document as recommended dependency

**Recovery Time:** Immediate after installing tiktoken

---

### 6. Configuration File Corruption

**Severity:** Low
**Impact:** Falls back to default configuration

**Symptoms:**

- Warning: "Failed to load config"
- Error: "Invalid JSON format"
- Config validation errors

**Causes:**

- Invalid JSON syntax in `.memory-bank-validation.json`
- Invalid config values (out of range)
- File corruption
- Manual editing errors

**Impact:**

- System uses default configuration
- Custom settings ignored
- Validation rules at defaults
- No data loss

**Degradation Behavior:**

- Loads default config automatically
- Warns about fallback
- System operates normally
- Can recreate config later

**Recovery Procedure:**

1. **Validate JSON:**

   ```bash
   python -m json.tool .memory-bank-validation.json
   ```

2. **Check Syntax Errors:**
   - Review JSON formatting
   - Check for missing commas, braces
   - Verify quotes around strings

3. **Fix Config Values:**

   ```python
   # Validate config
   errors = validation_config.validate_config()
   print(errors)  # Shows what's wrong
   ```

4. **Reset to Defaults (if needed):**

   ```bash
   # Backup current
   mv .memory-bank-validation.json .memory-bank-validation.json.bak

   # System uses defaults
   ```

5. **Recreate Config:**

   ```python
   validation_config.reset_to_defaults()
   # Customize as needed
   validation_config.set("token_budget.max_total_tokens", 150000)
   await validation_config.save()
   ```

**Prevention:**

- Validate config after manual edits
- Use API to modify config when possible
- Backup config before changes
- Run validation regularly

**Recovery Time:** Immediate (falls back to defaults)

---

### 7. Transclusion Resolution Failure

**Severity:** Low
**Impact:** Content not included, error comment inserted

**Symptoms:**

- `<!-- TRANSCLUSION ERROR: ... -->` in output
- Missing included content
- Circular dependency detected
- Section not found

**Causes:**

- Circular transclusion (A includes B includes A)
- Maximum depth exceeded (>5 levels)
- Target file not found
- Section heading doesn't exist

**Impact:**

- Specific transclusion fails
- Other transclusions work
- Error marked in output
- No data corruption

**Degradation Behavior:**

```markdown
<!-- TRANSCLUSION ERROR: Circular dependency detected:
fileA.md -> fileB.md -> fileA.md -->
```

**Recovery Procedure:**

1. **Circular Dependencies:**
   - Review error message for cycle path
   - Remove one include to break cycle
   - Reorganize content structure

2. **Max Depth Exceeded:**
   - Flatten include hierarchy
   - Increase max_depth parameter
   - Use direct includes

3. **Target Not Found:**
   - Verify file exists
   - Check spelling (case-sensitive)
   - Use correct path

4. **Section Not Found:**
   - List available sections
   - Check heading case
   - Verify exact heading text

**Prevention:**

- Plan transclusion hierarchy
- Avoid bidirectional includes
- Keep depth under 5 levels
- Use section includes judiciously
- Test transclusions regularly

**Recovery Time:** Immediate after fixing includes

---

## Failure Detection and Monitoring

### Logging

All failures are logged with appropriate severity:

```python
# Error level: Critical failures
logger.error("Index corrupted", extra={"path": index_path})

# Warning level: Degraded operation
logger.warning("Using word-based token estimation")

# Info level: Recovery actions
logger.info("Rebuilding index from files")
```

### Health Checks

Run periodic health checks:

```python
# Validation check
result = await validate_memory_bank()
if result['status'] != 'valid':
    handle_issues(result['issues'])

# Stats check
stats = await get_memory_bank_stats()
if stats['totals']['total_files'] == 0:
    alert("No files found")
```

### Metrics

Monitor these metrics:

- File operation retry rate
- Lock timeout frequency
- Index corruption events
- Degraded operation mode
- Token estimation fallback usage

---

## Recovery Time Objectives (RTO)

| Failure Mode | Severity | RTO | Data Loss |
|--------------|----------|-----|-----------|
| Index Corruption | High | 1-30s | None (rebuilds) |
| File Lock Deadlock | High | <5s | None |
| Path Traversal | Critical | N/A | None (prevented) |
| Shared Rules Sync | Medium | Auto-retry | None |
| Token Estimation | Low | Immediate | None (estimation) |
| Config Corruption | Low | Immediate | None (defaults) |
| Transclusion Error | Low | Manual | None (marked) |

---

## Emergency Procedures

### Complete Reset

If system is severely corrupted:

```bash
# 1. Backup current state
tar -czf memory-bank-backup-$(date +%Y%m%d).tar.gz memory-bank/ .memory-bank-*

# 2. Remove all metadata
rm .memory-bank-index
rm .memory-bank-validation.json
rm .memory-bank-history/*

# 3. Reinitialize
initialize_memory_bank()

# 4. Validate
validate_memory_bank()
```

### Force Recovery

If standard recovery fails:

```bash
# 1. Stop all MCP servers
pkill -f cortex

# 2. Clean locks
find . -name "*.lock" -delete

# 3. Reset index
rm .memory-bank-index

# 4. Restart fresh
initialize_memory_bank()
```

---

## Testing Failure Modes

Test these scenarios in development:

1. **Simulate Index Corruption:**

   ```bash
   # Create invalid JSON
   echo "{invalid}" > .memory-bank-index
   # Verify auto-recovery
   ```

2. **Simulate Lock Timeout:**

   ```bash
   # Create stale lock
   touch memory-bank/test.md.lock
   # Verify timeout handling
   ```

3. **Simulate Network Failure:**

   ```python
   # Mock git commands to fail
   # Verify graceful degradation
   ```

4. **Simulate tiktoken Unavailable:**

   ```python
   # Uninstall tiktoken temporarily
   # Verify estimation fallback
   ```

---

## Related Documentation

- [Error Recovery Guide](error-recovery.md) - Step-by-step error solutions
- [Troubleshooting Guide](troubleshooting.md) - Common issues and fixes
- [Configuration Guide](configuration.md) - Configuration options
- [Architecture](../architecture.md) - System design and components
