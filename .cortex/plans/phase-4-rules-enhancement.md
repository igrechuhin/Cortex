# Phase 4 Enhancement: Custom Rules Integration

## Overview

Enhanced Phase 4 with custom rules folder support, allowing users to integrate project-specific rules (like Cursor's `.cursorrules` or similar) into the Cortex context optimization system.

## New Features

### 1. Rules Manager (`rules_manager.py`)

A new module that indexes and manages custom rule files from a configurable folder.

**Key Features:**

- **Automatic indexing** of rule files from configured folder
- **Periodic re-indexing** to keep rules current
- **Relevance scoring** for task-specific rule retrieval
- **Token-aware selection** to fit rules within budget
- **Multi-format support** (`.md`, `.txt`, `.rules`, `.cursorrules`, etc.)
- **Section parsing** for fine-grained rule organization

**API:**

```python
rules_manager = RulesManager(
    project_root=project_root,
    file_system=fs_manager,
    metadata_index=metadata_index,
    token_counter=token_counter,
    rules_folder=".cursorrules",  # Configurable
    reindex_interval_minutes=30     # Auto-reindex every 30 min
)

# Initialize and index rules
await rules_manager.initialize()

# Get relevant rules for a task
relevant_rules = await rules_manager.get_relevant_rules(
    task_description="Implement authentication",
    max_tokens=5000,
    min_relevance_score=0.3
)
```

### 2. Enhanced Optimization Configuration

Extended `.memory-bank-optimization.json` with rules settings:

```json
{
  "rules": {
    "enabled": false,                    // Enable/disable rules indexing
    "rules_folder": ".cursorrules",      // Folder to scan (relative to project root)
    "reindex_interval_minutes": 30,      // How often to re-index
    "auto_include_in_context": true,     // Auto-include rules in context
    "max_rules_tokens": 5000,            // Max tokens for rules
    "min_relevance_score": 0.3           // Min score to include rule
  }
}
```

**New Config Methods:**

- `is_rules_enabled()` - Check if rules are enabled
- `get_rules_folder()` - Get rules folder path
- `get_rules_reindex_interval()` - Get reindex interval
- `get_rules_max_tokens()` - Get max tokens for rules
- `get_rules_min_relevance()` - Get min relevance score

### 3. New MCP Tools

#### `index_rules(force, project_root)`

Index custom rules from the configured rules folder.

**Parameters:**

- `force` (bool): Force reindexing even if recently indexed
- `project_root` (str): Optional project root path

**Returns:**

```json
{
  "status": "success",
  "indexed_at": "2025-12-19T10:30:00Z",
  "rules_folder": ".cursorrules",
  "total_files": 5,
  "indexed": 2,
  "updated": 3,
  "unchanged": 0,
  "errors": 0
}
```

#### `get_relevant_rules(task_description, max_tokens, min_relevance_score, project_root)`

Get rules relevant to a task description.

**Parameters:**

- `task_description` (str): Description of the task
- `max_tokens` (int): Maximum tokens (defaults to config)
- `min_relevance_score` (float): Minimum relevance (defaults to config)
- `project_root` (str): Optional project root path

**Returns:**

```json
{
  "status": "success",
  "task_description": "Implement authentication",
  "rules_count": 3,
  "total_tokens": 2450,
  "rules": [
    {
      "file": ".cursorrules/auth-rules.md",
      "content": "...",
      "tokens": 850,
      "relevance_score": 0.92,
      "sections": [...]
    }
  ]
}
```

## Usage Workflow

### Setup

1. **Create rules folder** in your project:

   ```bash
   mkdir .cursorrules
   # or use any folder name you prefer
   ```

2. **Add rule files**:

   ```bash
   # .cursorrules/general-rules.md
   # Your coding standards, patterns, etc.

   # .cursorrules/auth-rules.md
   # Authentication-specific rules
   ```

3. **Enable in configuration**:

   ```json
   {
     "rules": {
       "enabled": true,
       "rules_folder": ".cursorrules"
     }
   }
   ```

### Using Rules

**Manual indexing:**

```javascript
// Call via MCP
await mcp.call_tool("index_rules", { force: true })
```

**Get relevant rules for a task:**

```javascript
// Get rules relevant to authentication work
await mcp.call_tool("get_relevant_rules", {
  task_description: "Implement JWT authentication with refresh tokens",
  max_tokens: 5000
})
```

**Automatic integration:**
When `auto_include_in_context` is enabled, relevant rules are automatically included in context optimization.

## Technical Details

### Re-indexing Strategy

- **Automatic re-indexing** runs every N minutes (configurable)
- **Content-based change detection** using SHA-256 hashes
- **Incremental updates** - only re-index changed files
- **Background task** doesn't block other operations

### Relevance Scoring

Rules are scored based on:

- **Keyword matching** with task description
- **TF-IDF scoring** for better relevance
- **Section-level analysis** for fine-grained matching

### Performance

- **Efficient indexing** - only scans on changes
- **Token counting** integrated with existing counter
- **Lazy initialization** - only loads when enabled
- **Async operations** throughout

## Example Configuration

### For Cursor Users

```json
{
  "rules": {
    "enabled": true,
    "rules_folder": ".cursorrules",
    "reindex_interval_minutes": 15,
    "max_rules_tokens": 8000,
    "min_relevance_score": 0.4
  }
}
```

### For General AI Rules

```json
{
  "rules": {
    "enabled": true,
    "rules_folder": ".ai-rules",
    "reindex_interval_minutes": 30,
    "auto_include_in_context": true,
    "max_rules_tokens": 5000,
    "min_relevance_score": 0.3
  }
}
```

## Benefits

1. **Context-Aware Rules** - Rules are automatically selected based on task relevance
2. **Token Efficient** - Only includes rules that fit within budget and are relevant
3. **Always Current** - Automatic re-indexing keeps rules up-to-date
4. **Flexible** - Works with any folder structure and file format
5. **Integrated** - Seamlessly works with existing optimization features

## Future Enhancements

Potential improvements for future versions:

- Machine learning-based relevance scoring
- Rule conflict detection
- Rule versioning and change tracking
- Rule templates and inheritance
- Integration with git hooks for auto-reindexing

---

**Module:** `rules_manager.py` (370 lines)
**New MCP Tools:** 2 (`index_rules`, `get_relevant_rules`)
**Configuration Keys:** 6 (in `rules` section)
**Total Enhancement:** ~400 lines of new code
