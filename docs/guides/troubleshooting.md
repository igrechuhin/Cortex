# Troubleshooting Guide

This guide helps you diagnose and fix common issues with Cortex.

## Common Issues

### Installation and Setup

#### Issue: `uv` command not found

**Symptoms**:

```bash
$ uvx cortex
-bash: uvx: command not found
```

**Solution**:
Install `uv` package manager:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using homebrew
brew install uv

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### Issue: Python version too old

**Symptoms**:

```text
ERROR: Python 3.13 or later is required
```

**Solution**:
Install Python 3.13+:

```bash
# Using uv
uv python install 3.13

# Or using pyenv
pyenv install 3.13.0
pyenv global 3.13.0
```

#### Issue: MCP server not found by client

**Symptoms**:

- Claude Desktop doesn't show Memory Bank tools
- Cursor IDE doesn't connect to server

**Solution**:

1. Check MCP configuration file location:
   - **Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
   - **Cursor**: `.cursor/mcp_config.json` in project root

2. Verify configuration:

   ```json
   {
     "mcpServers": {
       "memory-bank": {
         "command": "uvx",
         "args": ["--from", "git+https://github.com/igrechuhin/cortex.git", "cortex"]
       }
     }
   }
   ```

3. Restart the MCP client

### File Operations

#### Issue: File lock timeout

**Symptoms**:

```text
FileLockTimeoutError: Could not acquire lock for activeContext.md within 10 seconds
```

**Causes**:

- Another process is writing to the file
- Stale lock from crashed process

**Solution**:

1. Check for running processes:

   ```bash
   ps aux | grep cortex
   ```

2. Clean up stale locks:

   ```bash
   # Remove lock files
   rm .memory-bank/*.lock
   ```

3. Retry the operation

#### Issue: File conflict error

**Symptoms**:

```text
FileConflictError: File projectBrief.md was modified externally
```

**Causes**:

- File was edited outside Cortex
- Concurrent edits from multiple clients

**Solution**:

1. Read the current file content:

   ```json
   {
     "tool": "read_memory_bank_file",
     "args": {
       "project_root": "/path/to/project",
       "file_name": "projectBrief.md"
     }
   }
   ```

2. Merge your changes with the current content

3. Write with updated hash:

   ```json
   {
     "tool": "write_memory_bank_file",
     "args": {
       "project_root": "/path/to/project",
       "file_name": "projectBrief.md",
       "content": "merged content",
       "expected_hash": "current_hash_from_read"
     }
   }
   ```

#### Issue: Git conflict markers detected

**Symptoms**:

```text
GitConflictError: File systemPatterns.md contains Git conflict markers
```

**Solution**:

1. Open the file and resolve conflicts:

   ```markdown
   <<<<<<< HEAD
   Version A
   =======
   Version B
   >>>>>>> branch-name
   ```

2. Remove conflict markers and keep desired content

3. Retry the operation

### Validation Issues

#### Issue: Required sections missing

**Symptoms**:

```json
{
  "status": "error",
  "errors": [
    {
      "type": "missing_section",
      "file": "projectBrief.md",
      "section": "Project Overview"
    }
  ]
}
```

**Solution**:

Add the required section to the file:

```markdown
# Project Brief

## Project Overview

Your project overview here...
```

#### Issue: Duplication detected

**Symptoms**:

```json
{
  "duplications": [
    {
      "file1": "systemPatterns.md",
      "file2": "techContext.md",
      "similarity": 0.92
    }
  ]
}
```

**Solution**:

Use transclusion to eliminate duplication:

1. Extract shared content to a dedicated file:

   ```markdown
   <!-- shared.md -->
   ## Authentication
   Users authenticate via OAuth 2.0...
   ```

2. Use transclusion in both files:

   ```markdown
   <!-- systemPatterns.md -->
   {{include:shared.md#Authentication}}

   <!-- techContext.md -->
   {{include:shared.md#Authentication}}
   ```

#### Issue: Token budget exceeded

**Symptoms**:

```text
TokenLimitExceededError: 120000 tokens (limit: 100000)
```

**Solution**:

1. **Option A**: Increase budget in configuration:

   ```json
   {
     "token_budget": {
       "max_total_tokens": 150000
     }
   }
   ```

2. **Option B**: Archive old content:

   ```bash
   mkdir -p memory-bank/archive
   mv memory-bank/old-file.md memory-bank/archive/
   ```

3. **Option C**: Use summarization:

   ```json
   {
     "tool": "summarize_content",
     "args": {
       "project_root": "/path/to/project",
       "file_name": "large-file.md",
       "strategy": "extract_key_sections",
       "target_reduction": 0.5
     }
   }
   ```

### Link and Transclusion Issues

#### Issue: Broken link detected

**Symptoms**:

```json
{
  "broken_links": [
    {
      "file": "systemPatterns.md",
      "link": "missing-file.md",
      "type": "file_not_found"
    }
  ]
}
```

**Solution**:

1. Check if file exists:

   ```bash
   ls memory-bank/missing-file.md
   ```

2. Fix the link or create the missing file

#### Issue: Circular transclusion

**Symptoms**:

```text
Error: Circular transclusion detected: fileA.md -> fileB.md -> fileA.md
```

**Solution**:

1. Identify the cycle in your transclusions:

   ```markdown
   <!-- fileA.md -->
   {{include:fileB.md}}

   <!-- fileB.md -->
   {{include:fileA.md}}  <!-- Circular! -->
   ```

2. Restructure to eliminate the cycle:

   ```markdown
   <!-- Create fileC.md with shared content -->

   <!-- fileA.md -->
   {{include:fileC.md}}

   <!-- fileB.md -->
   {{include:fileC.md}}
   ```

#### Issue: Transclusion section not found

**Symptoms**:

```text
Error: Section 'NonExistent' not found in shared.md
```

**Solution**:

1. Check available sections:

   ```json
   {
     "tool": "parse_file_links",
     "args": {
       "project_root": "/path/to/project",
       "file_name": "shared.md"
     }
   }
   ```

2. Update the transclusion with correct section name:

   ```markdown
   <!-- Before -->
   {{include:shared.md#NonExistent}}

   <!-- After -->
   {{include:shared.md#Authentication}}
   ```

### Optimization Issues

#### Issue: Context optimization takes too long

**Symptoms**:

- Optimization takes > 10 seconds
- High CPU usage

**Causes**:

- Large number of files
- Complex dependency graphs
- Relevance scoring overhead

**Solution**:

1. Enable caching:

   ```json
   {
     "performance": {
       "cache_enabled": true,
       "cache_ttl_seconds": 600
     }
   }
   ```

2. Reduce file count:

   ```bash
   # Archive unused files
   mkdir -p memory-bank/archive
   mv memory-bank/unused-*.md memory-bank/archive/
   ```

3. Use simpler optimization strategy:

   ```json
   {
     "optimization": {
       "strategy": "priority"  // Instead of "hybrid"
     }
   }
   ```

#### Issue: Irrelevant files selected

**Symptoms**:

- Context optimization selects wrong files
- Low relevance scores for important files

**Solution**:

1. Adjust relevance scoring weights:

   ```json
   {
     "relevance_scoring": {
       "tfidf_weight": 0.6,        // Increase keyword weight
       "dependency_weight": 0.3,
       "recency_weight": 0.05,
       "quality_weight": 0.05
     }
   }
   ```

2. Use mandatory files:

   ```json
   {
     "optimization": {
       "mandatory_files": [
         "memorybankinstructions.md",
         "projectBrief.md",
         "important-context.md"
       ]
     }
   }
   ```

### Shared Rules Issues

#### Issue: Git submodule initialization fails

**Symptoms**:

```text
SharedRulesGitError: Git clone failed for shared rules
```

**Causes**:

- Invalid repository URL
- Authentication required
- Network issues

**Solution**:

1. Verify repository URL:

   ```bash
   git ls-remote https://github.com/your-org/shared-rules.git
   ```

2. Set up authentication:

   ```bash
   # SSH (recommended)
   git config --global url."git@github.com:".insteadOf "https://github.com/"

   # Or use personal access token
   git config --global credential.helper store
   ```

3. Retry initialization:

   ```json
   {
     "tool": "setup_shared_rules",
     "args": {
       "project_root": "/path/to/project",
       "repo_url": "git@github.com:your-org/shared-rules.git",
       "force_reinit": true
     }
   }
   ```

#### Issue: Context detection not working

**Symptoms**:

- Wrong rules loaded for task
- Generic rules only

**Solution**:

1. Add more language keywords:

   ```json
   {
     "shared_rules": {
       "context_detection": {
         "language_keywords": {
           "python": ["python", "py", "pytest", "django", "fastapi"],
           "swift": ["swift", "swiftui", "uikit", "combine"]
         }
       }
     }
   }
   ```

2. Manually specify context:

   ```json
   {
     "tool": "get_rules_with_context",
     "args": {
       "project_root": "/path/to/project",
       "task_description": "Implement Python REST API using FastAPI"
     }
   }
   ```

### Refactoring Issues

#### Issue: Refactoring execution fails

**Symptoms**:

```text
RefactoringExecutionError: Failed to execute refactoring consolidation_001
```

**Solution**:

1. Check refactoring status:

   ```json
   {
     "tool": "get_refactoring_history",
     "args": {
       "project_root": "/path/to/project",
       "suggestion_id": "consolidation_001"
     }
   }
   ```

2. Validate suggestion:

   ```json
   {
     "tool": "preview_refactoring",
     "args": {
       "project_root": "/path/to/project",
       "suggestion_id": "consolidation_001"
     }
   }
   ```

3. If validation fails, reject and request new suggestion

#### Issue: Rollback fails

**Symptoms**:

```text
RollbackError: Failed to rollback refactoring split_002
```

**Solution**:

1. Check rollback history:

   ```bash
   cat .memory-bank-rollbacks.json
   ```

2. Manual rollback:

   ```bash
   # Restore from version history
   cp .memory-bank-history/<timestamp>/file.md memory-bank/file.md
   ```

3. Update metadata:

   ```json
   {
     "tool": "get_memory_bank_stats",
     "args": {
       "project_root": "/path/to/project",
       "rebuild_index": true
     }
   }
   ```

### Performance Issues

#### Issue: Slow tiktoken initialization

**Symptoms**:

- First token count takes 10-30 seconds
- "Downloading encoding..." message

**Causes**:

- tiktoken downloads encoding files on first use

**Solution**:

This is expected behavior. The encoding is cached after first use:

```python
# First call (slow)
tokens = await token_counter.count_tokens(content)  # 10-30s

# Subsequent calls (fast)
tokens = await token_counter.count_tokens(content)  # <5ms
```

No action needed - performance is normal after initialization.

#### Issue: High memory usage

**Symptoms**:

- Python process using > 1GB RAM
- System slowdown

**Causes**:

- Large file caching
- Multiple project caches

**Solution**:

1. Reduce cache size:

   ```json
   {
     "performance": {
       "max_cache_size_mb": 50
     }
   }
   ```

2. Clear caches:

   ```bash
   # Remove cache files (safe - will regenerate)
   rm -rf ~/.cache/cortex/
   ```

3. Restart MCP server

## Diagnostic Tools

### Check Server Status

```bash
# Test server startup
uv run cortex

# Should see:
# MCP server started successfully
```

### Check Memory Bank Structure

```json
{
  "tool": "get_memory_bank_stats",
  "args": {
    "project_root": "/path/to/project"
  }
}
```

Returns:

- File count and sizes
- Token usage
- Version history size
- Metadata status

### Validate Everything

```json
{
  "tool": "validate_memory_bank",
  "args": {
    "project_root": "/path/to/project",
    "fix_issues": false
  }
}
```

Returns:

- Schema validation results
- Link validation results
- Duplication detection results
- Quality score

### Check Structure Health

```json
{
  "tool": "check_structure_health",
  "args": {
    "project_root": "/path/to/project"
  }
}
```

Returns:

- Health score (0-100)
- Required directories status
- Symlink status
- Recommendations

## Logging and Debugging

### Enable Debug Logging

Set environment variable:

```bash
# Verbose logging
export CORTEX_LOG_LEVEL=DEBUG

# Run server
uv run cortex
```

### Check Log Files

Logs are written to stderr (captured by MCP client):

```bash
# For standalone testing
uv run cortex 2> debug.log
```

### Inspect Metadata Files

```bash
# View metadata index
cat .memory-bank-index | jq .

# View access log
cat .memory-bank-access-log.json | jq .

# View learning data
cat .memory-bank-learning.json | jq .
```

## Getting Help

### Check Documentation

1. [Getting Started](../getting-started.md)
2. [Configuration Guide](./configuration.md)
3. [Architecture](../architecture.md)
4. [API Reference](../api/tools.md)

### Search Issues

[GitHub Issues](https://github.com/igrechuhin/cortex/issues)

### Create New Issue

Include:

1. **Symptoms**: What's happening?
2. **Expected**: What should happen?
3. **Steps**: How to reproduce?
4. **Environment**: OS, Python version, uv version
5. **Logs**: Relevant error messages

### Community Support

- GitHub Discussions
- MCP Community Discord
