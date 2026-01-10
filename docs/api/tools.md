# MCP Tools API Reference

Complete reference for all 53 MCP tools provided by Cortex.

## Overview

Cortex provides 53 tools organized by functionality phases. All tools accept optional `project_root` parameter and return JSON responses with consistent error handling.

**Total Tools by Phase:**

| Phase | Tools | Category |
|-------|-------|----------|
| [Phase 1](#phase-1-foundation-tools) | 10 | Foundation (initialization, file ops, versioning) |
| [Phase 2](#phase-2-link-management-tools) | 4 | Link Management (parsing, validation, transclusion) |
| [Phase 3](#phase-3-validation-and-quality-tools) | 5 | Validation & Quality (schema, duplication, scoring) |
| [Phase 4](#phase-4-token-optimization-tools) | 7 | Token Optimization (context, loading, summarization, rules) |
| [Phase 5.1](#phase-51-pattern-analysis-and-insights) | 3 | Pattern Analysis & Insights |
| [Phase 5.2](#phase-52-refactoring-suggestions) | 4 | Refactoring Suggestions |
| [Phase 5.3-5.4](#phase-53-54-safe-execution-and-learning) | 6 | Safe Execution & Learning |
| [Phase 6](#phase-6-shared-rules-repository) | 4 | Shared Rules Repository |
| [Phase 8](#phase-8-project-structure-management) | 7 | Project Structure Management |
| [Legacy](#legacy-tools) | 3 | Legacy Support |

---

## Phase 1: Foundation Tools

Core tools for Memory Bank initialization, file operations, metadata management, versioning, and migration.

### initialize_memory_bank

Initialize Memory Bank in a project directory.

**Parameters:**

- `project_root` (str | None) - Optional path to project root (defaults to current directory)

**Description:**

Creates the memory-bank/ directory, generates all 7 core files from templates, initializes the metadata index, and auto-migrates if an old format is detected.

**Returns:**

JSON string with initialization status:

```json
{
  "status": "success",
  "message": "Memory Bank initialized successfully",
  "project_root": "/path/to/project",
  "files_created": ["projectBrief.md", "..."],
  "total_files": 7
}
```

**Status Values:**

- `success` - New Memory Bank created successfully
- `already_initialized` - Memory Bank already exists
- `migrated` - Existing Memory Bank migrated to Phase 1 format
- `error` - Initialization failed

---

### read_memory_bank_file

Read a Memory Bank file with optional metadata.

**Parameters:**

- `file_name` (str) - Name of the file to read (e.g., "projectBrief.md")
- `project_root` (str | None) - Optional path to project root
- `include_metadata` (bool) - If True, include metadata (tokens, versions, usage stats)

**Description:**

Reads file content with automatic locking and conflict detection. Optionally includes detailed metadata about the file.

**Returns:**

```json
{
  "status": "success",
  "file_name": "projectBrief.md",
  "content": "# Project Brief\n...",
  "metadata": {
    "token_count": 1234,
    "version": 5,
    "sections": ["# Project Brief", "## Goals"]
  }
}
```

---

### write_memory_bank_file

Write or update a Memory Bank file with automatic versioning.

**Parameters:**

- `file_name` (str) - Name of the file to write (e.g., "projectBrief.md")
- `content` (str) - New content for the file
- `project_root` (str | None) - Optional path to project root
- `change_description` (str | None) - Optional description of changes made

**Description:**

Writes file with automatic versioning, conflict detection, and metadata updates. Creates a snapshot before modification for rollback capability.

**Returns:**

```json
{
  "status": "success",
  "file_name": "projectBrief.md",
  "version": 6,
  "change_type": "modified",
  "token_count": 1250,
  "size_bytes": 5120,
  "content_hash": "abc123...",
  "sections_count": 4
}
```

**Change Types:**

- `created` - File was newly created
- `modified` - Existing file was updated

---

### get_file_metadata

Get detailed metadata for a Memory Bank file.

**Parameters:**

- `file_name` (str) - Name of the file (e.g., "projectBrief.md")
- `project_root` (str | None) - Optional path to project root

**Description:**

Returns comprehensive metadata including token counts, sections, version history, usage statistics, and file status.

**Returns:**

```json
{
  "status": "success",
  "file_name": "projectBrief.md",
  "metadata": {
    "token_count": 1234,
    "version": 5,
    "size_bytes": 5120,
    "content_hash": "abc123...",
    "sections": ["# Project Brief", "## Goals", "## Scope"],
    "last_modified": "2025-12-25T10:30:00Z",
    "access_count": 42,
    "last_accessed": "2025-12-25T15:00:00Z"
  }
}
```

---

### get_dependency_graph

Get the Memory Bank dependency graph.

**Parameters:**

- `project_root` (str | None) - Optional path to project root
- `format` (str) - Output format: `"json"` or `"mermaid"`

**Description:**

Shows relationships between files and their loading priority. Supports JSON (for programmatic use) and Mermaid (for visualization) formats.

**Returns:**

JSON format:

```json
{
  "status": "success",
  "format": "json",
  "graph": {
    "projectBrief.md": ["productContext.md", "techContext.md"],
    "activeContext.md": ["progress.md"]
  },
  "loading_order": ["projectBrief.md", "productContext.md", "..."]
}
```

Mermaid format:

```json
{
  "status": "success",
  "format": "mermaid",
  "diagram": "graph TD\n  A[projectBrief.md] --> B[productContext.md]\n  ..."
}
```

---

### get_version_history

Get version history for a Memory Bank file.

**Parameters:**

- `file_name` (str) - Name of the file (e.g., "projectBrief.md")
- `project_root` (str | None) - Optional path to project root
- `limit` (int) - Maximum number of versions to return (default: 10)

**Description:**

Returns list of versions with timestamps, change types, and descriptions.

**Returns:**

```json
{
  "status": "success",
  "file_name": "projectBrief.md",
  "total_versions": 15,
  "versions": [
    {
      "version": 15,
      "timestamp": "2025-12-25T10:30:00Z",
      "change_type": "modified",
      "description": "Updated project goals",
      "token_count": 1250,
      "size_bytes": 5120
    }
  ]
}
```

---

### rollback_file_version

Rollback a Memory Bank file to a previous version.

**Parameters:**

- `file_name` (str) - Name of the file (e.g., "projectBrief.md")
- `version` (int) - Version number to rollback to
- `project_root` (str | None) - Optional path to project root

**Description:**

Restores content from a snapshot and creates a new version entry. Does not delete history - the rollback itself becomes a new version.

**Returns:**

```json
{
  "status": "success",
  "file_name": "projectBrief.md",
  "rolled_back_from_version": 15,
  "new_version": 16,
  "token_count": 1200,
  "message": "Successfully rolled back to version 10"
}
```

---

### check_migration_status

Check if Memory Bank needs migration from old format.

**Parameters:**

- `project_root` (str | None) - Optional path to project root

**Description:**

Detects if the project uses the old (pre-Phase 1) format and provides information about what migration will do.

**Returns:**

```json
{
  "status": "migration_needed",
  "message": "Old format detected. Run migrate_memory_bank() to upgrade.",
  "old_format_details": {
    "has_old_files": true,
    "missing_metadata": true
  }
}
```

**Status Values:**

- `migration_needed` - Old format detected, migration required
- `up_to_date` - Already using Phase 1 format
- `not_initialized` - No Memory Bank exists yet
- `error` - Check failed

---

### migrate_memory_bank

Migrate Memory Bank from old format to Phase 1 format.

**Parameters:**

- `project_root` (str | None) - Optional path to project root
- `auto_backup` (bool) - If True, creates timestamped backup (default: True)

**Description:**

Creates backup, initializes metadata index, generates version history, and verifies the migration. Safe to run multiple times - idempotent operation.

**Returns:**

```json
{
  "status": "success",
  "message": "Migration completed successfully",
  "backup_created": true,
  "backup_path": "/path/to/memory-bank-backup-20251225",
  "files_migrated": 7,
  "metadata_created": true
}
```

---

### get_memory_bank_stats

Get overall Memory Bank statistics and analytics.

**Parameters:**

- `project_root` (str | None) - Optional path to project root

**Description:**

Returns comprehensive statistics about token usage, file sizes, version history, and usage patterns.

**Returns:**

```json
{
  "status": "success",
  "project_root": "/path/to/project",
  "summary": {
    "total_files": 7,
    "total_tokens": 8500,
    "total_size_bytes": 35000,
    "average_tokens_per_file": 1214,
    "total_versions": 42,
    "total_accesses": 156
  },
  "files": {
    "projectBrief.md": {
      "token_count": 1234,
      "versions": 5,
      "accesses": 20
    }
  },
  "last_updated": "2025-12-25T15:00:00Z"
}
```

---

## Phase 2: Link Management Tools

Tools for parsing, resolving, and validating markdown links and transclusions.

### parse_file_links

Parse and return all links in a Memory Bank file.

**Parameters:**

- `file_name` (str) - Name of the file to parse (e.g., "activeContext.md")
- `project_root` (str | None) - Optional path to project root

**Description:**

Extracts markdown links `[text](target)` and transclusion directives `{{include: file}}` from the specified file.

**Returns:**

```json
{
  "status": "success",
  "file": "activeContext.md",
  "markdown_links": [
    {
      "text": "Project Brief",
      "target": "projectBrief.md",
      "line": 10
    }
  ],
  "transclusions": [
    {
      "target": "progress.md",
      "section": "Current Sprint",
      "line": 25
    }
  ],
  "summary": {
    "markdown_links": 5,
    "transclusions": 2,
    "total": 7,
    "unique_files": 4
  }
}
```

---

### resolve_transclusions

Read file with all transclusions resolved.

**Parameters:**

- `file_name` (str) - Name of the file to read (e.g., "activeContext.md")
- `project_root` (str | None) - Optional path to project root
- `max_depth` (int) - Maximum transclusion depth (default: 5)

**Description:**

Resolves all `{{include: ...}}` directives by replacing them with actual content from referenced files and sections. Includes caching for performance.

**Returns:**

```json
{
  "status": "success",
  "file": "activeContext.md",
  "original_content": "# Active Context\n{{include: progress.md#Current Sprint}}",
  "resolved_content": "# Active Context\n## Current Sprint\n...",
  "has_transclusions": true,
  "transclusions_resolved": 2,
  "cache_stats": {
    "hits": 1,
    "misses": 1
  }
}
```

**Errors:**

- `CircularDependencyError` - File includes itself (directly or indirectly)
- `MaxDepthExceededError` - Transclusion nesting exceeds max_depth

---

### validate_links

Validate links in a file or all files.

**Parameters:**

- `file_name` (str | None) - Optional specific file to validate (if None, validates all files)
- `project_root` (str | None) - Optional path to project root

**Description:**

Checks that all markdown links and transclusion directives point to existing files and sections. Generates validation report with broken links and suggestions.

**Returns:**

```json
{
  "status": "success",
  "mode": "all_files",
  "files_checked": 7,
  "total_links": 42,
  "valid_links": 38,
  "broken_links": 4,
  "warnings": 2,
  "details": [
    {
      "file": "activeContext.md",
      "line": 15,
      "type": "broken_link",
      "target": "missing.md",
      "suggestion": "Did you mean 'systemPatterns.md'?"
    }
  ]
}
```

---

### get_link_graph

Get dynamic dependency graph based on actual links.

**Parameters:**

- `project_root` (str | None) - Optional path to project root
- `include_transclusions` (bool) - Include transclusion links (default: True)
- `format` (str) - Output format: `"json"` or `"mermaid"`

**Description:**

Builds dependency graph by parsing all markdown links and transclusion directives. Shows how files reference each other, including cycle detection.

**Returns:**

JSON format:

```json
{
  "status": "success",
  "format": "json",
  "nodes": [
    {"file": "projectBrief.md", "links_out": 3, "links_in": 0}
  ],
  "edges": [
    {"from": "activeContext.md", "to": "progress.md", "type": "transclusion"}
  ],
  "cycles": [
    ["fileA.md", "fileB.md", "fileA.md"]
  ],
  "summary": {
    "total_nodes": 7,
    "total_edges": 15,
    "cycles_detected": 0
  }
}
```

---

## Phase 3: Validation and Quality Tools

Tools for schema validation, duplication detection, quality metrics, and token budget management.

### validate_memory_bank

Run comprehensive validation on Memory Bank files.

**Parameters:**

- `file_name` (str | None) - Optional specific file to validate (if None, validates all files)
- `project_root` (str | None) - Optional project root path
- `strict` (bool) - Enable strict validation (warnings treated as errors)

**Description:**

Validates files against schemas checking: required sections presence, recommended sections, heading hierarchy, overall quality.

**Returns:**

```json
{
  "status": "success",
  "validation_passed": true,
  "strict_mode": false,
  "summary": {
    "files_validated": 7,
    "errors": 0,
    "warnings": 2,
    "passed": 7,
    "failed": 0
  },
  "results": [
    {
      "file": "projectBrief.md",
      "passed": true,
      "errors": [],
      "warnings": ["Missing recommended section: ## Constraints"],
      "suggestions": ["Consider adding a Constraints section"]
    }
  ]
}
```

---

### check_duplications

Find duplicate or highly similar content across files.

**Parameters:**

- `project_root` (str | None) - Optional project root path
- `threshold` (float) - Similarity threshold (0.0-1.0) to flag as duplicate (default: 0.85)
- `suggest_fixes` (bool) - Include refactoring suggestions in output (default: True)

**Description:**

Scans all files for duplicated content and suggests refactoring opportunities using transclusions.

**Returns:**

```json
{
  "status": "success",
  "threshold": 0.85,
  "summary": {
    "files_scanned": 7,
    "exact_duplicates": 2,
    "similar_sections": 5,
    "total_issues": 7,
    "potential_token_savings": 1200
  },
  "exact_duplicates": [
    {
      "content": "## Project Goals\n...",
      "files": ["projectBrief.md", "productContext.md"],
      "token_count": 150,
      "suggestion": "Extract to shared-goals.md and use {{include: shared-goals.md}}"
    }
  ],
  "similar_content": [
    {
      "files": ["file1.md", "file2.md"],
      "similarity": 0.92,
      "sections": ["## Architecture", "## System Design"]
    }
  ]
}
```

---

### get_quality_score

Calculate Memory Bank quality score and health metrics.

**Parameters:**

- `project_root` (str | None) - Optional project root path
- `detailed` (bool) - Include detailed breakdown and recommendations (default: True)

**Description:**

Analyzes Memory Bank providing: overall quality score (0-100), category breakdown, letter grade (A/B/C/D/F), health status and recommendations.

**Returns:**

```json
{
  "status": "success",
  "overall_score": 87,
  "grade": "B+",
  "status_health": "healthy",
  "breakdown": {
    "completeness": {"score": 90, "weight": 25, "weighted": 22.5},
    "consistency": {"score": 85, "weight": 25, "weighted": 21.25},
    "freshness": {"score": 80, "weight": 15, "weighted": 12.0},
    "structure": {"score": 90, "weight": 20, "weighted": 18.0},
    "token_efficiency": {"score": 85, "weight": 15, "weighted": 12.75}
  },
  "issues": [
    {
      "category": "consistency",
      "severity": "medium",
      "description": "3 duplicate sections found"
    }
  ],
  "recommendations": [
    "Consider consolidating duplicate content using transclusions",
    "Update stale files that haven't been modified in 90+ days"
  ]
}
```

**Grade Scale:**

- A: 90-100 (Excellent)
- B: 80-89 (Good)
- C: 70-79 (Fair)
- D: 60-69 (Needs Improvement)
- F: 0-59 (Poor)

---

### check_token_budget

Check token usage against budget and get projections.

**Parameters:**

- `project_root` (str | None) - Optional project root path
- `include_projections` (bool) - Include growth projections (default: True)

**Description:**

Analyzes current token usage across all files and compares to configured budgets.

**Returns:**

```json
{
  "status": "success",
  "budget_status": "healthy",
  "current_usage": {
    "total_tokens": 8500,
    "average_per_file": 1214
  },
  "budget_limits": {
    "max_total_tokens": 50000,
    "max_per_file": 5000,
    "warning_threshold": 80
  },
  "usage_percentage": 17.0,
  "remaining_tokens": 41500,
  "per_file_breakdown": [
    {
      "file": "projectBrief.md",
      "tokens": 1234,
      "percentage": 14.5,
      "status": "healthy"
    }
  ],
  "projections": {
    "at_current_rate": {
      "days_until_warning": 120,
      "days_until_limit": 180
    }
  }
}
```

**Budget Status:**

- `healthy` - Under warning threshold
- `warning` - Over warning threshold but under limit
- `over_budget` - Exceeds configured limit

---

### configure_validation

View or update validation configuration.

**Parameters:**

- `project_root` (str | None) - Optional project root path
- `config_key` (str | None) - Configuration key to set (dot notation: "token_budget.max_total_tokens")
- `config_value` (str | None) - Value to set (will be parsed as JSON)
- `show_current` (bool) - Show current configuration (default: False)

**Description:**

Allows viewing/updating validation settings stored in `.memory-bank-validation.json`.

**Returns:**

View configuration:

```json
{
  "status": "success",
  "action": "view",
  "configuration": {
    "token_budget": {
      "max_total_tokens": 50000,
      "max_per_file": 5000
    },
    "validation": {
      "strict_mode": false,
      "check_links": true
    }
  }
}
```

Update configuration:

```json
{
  "status": "success",
  "action": "updated",
  "key": "token_budget.max_total_tokens",
  "value": 60000,
  "message": "Configuration updated successfully"
}
```

---

## Phase 4: Token Optimization Tools

Tools for smart context loading, relevance scoring, summarization, and custom rules integration.

### optimize_context

Select optimal context for a task within token budget.

**Parameters:**

- `task_description` (str) - Description of the task or work to be done
- `token_budget` (int | None) - Maximum tokens allowed (defaults to config value)
- `strategy` (str) - Optimization strategy (default: "dependency_aware")
  - `"priority"` - Greedy selection by predefined priority
  - `"dependency_aware"` - Includes dependency trees
  - `"section_level"` - Partial file inclusion
  - `"hybrid"` - Combines multiple strategies
- `project_root` (str | None) - Optional project root path

**Description:**

Uses relevance scoring and optimization strategies to select the best subset of Memory Bank files that fit within a token budget.

**Returns:**

```json
{
  "status": "success",
  "task_description": "Implement authentication system",
  "token_budget": 10000,
  "strategy": "dependency_aware",
  "selected_files": [
    {
      "file": "systemPatterns.md",
      "tokens": 1500,
      "relevance_score": 0.95,
      "reason": "High relevance to authentication"
    }
  ],
  "selected_sections": [
    {
      "file": "techContext.md",
      "section": "## Security",
      "tokens": 300,
      "relevance_score": 0.88
    }
  ],
  "total_tokens": 8500,
  "utilization": 85.0,
  "excluded_files": ["progress.md"],
  "relevance_scores": {
    "systemPatterns.md": 0.95,
    "techContext.md": 0.88
  }
}
```

---

### load_progressive_context

Load context progressively based on strategy.

**Parameters:**

- `task_description` (str) - Description of the task
- `token_budget` (int | None) - Maximum tokens to load (defaults to config value)
- `loading_strategy` (str) - Strategy (default: "by_relevance")
  - `"by_priority"` - Load by predefined priority order
  - `"by_dependencies"` - Load by dependency chain traversal
  - `"by_relevance"` - Load by task-specific relevance
- `project_root` (str | None) - Optional project root path

**Description:**

Loads Memory Bank files incrementally, ordered by priority, relevance, or dependencies. Useful for streaming contexts or early stopping.

**Returns:**

```json
{
  "status": "success",
  "task_description": "Implement authentication",
  "loading_strategy": "by_relevance",
  "token_budget": 10000,
  "files_loaded": 5,
  "total_tokens": 8200,
  "loaded_files": [
    {
      "order": 1,
      "file": "systemPatterns.md",
      "tokens": 1500,
      "cumulative_tokens": 1500,
      "relevance_score": 0.95
    },
    {
      "order": 2,
      "file": "techContext.md",
      "tokens": 1200,
      "cumulative_tokens": 2700,
      "relevance_score": 0.88
    }
  ]
}
```

---

### summarize_content

Summarize Memory Bank content to reduce token usage.

**Parameters:**

- `file_name` (str | None) - File to summarize (None for all files)
- `target_reduction` (float) - Target token reduction (0.5 = reduce by 50%, default: 0.5)
- `strategy` (str) - Strategy (default: "extract_key_sections")
  - `"extract_key_sections"` - Keep most important sections
  - `"compress_verbose"` - Remove examples, compress code
  - `"headers_only"` - Outline view with headers
- `project_root` (str | None) - Optional project root path

**Description:**

Generates summaries of files to fit within token budgets while preserving key information.

**Returns:**

```json
{
  "status": "success",
  "strategy": "extract_key_sections",
  "target_reduction": 0.5,
  "files_summarized": 7,
  "total_original_tokens": 8500,
  "total_summarized_tokens": 4100,
  "total_reduction": 0.52,
  "results": [
    {
      "file": "projectBrief.md",
      "original_tokens": 1234,
      "summarized_tokens": 600,
      "reduction": 0.51,
      "summary": "# Project Brief\n## Goals\n..."
    }
  ]
}
```

---

### get_relevance_scores

Get relevance scores for all Memory Bank files.

**Parameters:**

- `task_description` (str) - Description of the task
- `project_root` (str | None) - Optional project root path
- `include_sections` (bool) - Whether to include section-level scores (default: False)

**Description:**

Scores files and optionally sections based on their relevance to a given task description using TF-IDF and dependency-based scoring.

**Returns:**

```json
{
  "status": "success",
  "task_description": "Implement authentication",
  "files_scored": 7,
  "file_scores": {
    "systemPatterns.md": 0.95,
    "techContext.md": 0.88,
    "projectBrief.md": 0.72,
    "progress.md": 0.15
  },
  "section_scores": {
    "techContext.md": {
      "## Security": 0.95,
      "## Architecture": 0.70
    }
  }
}
```

---

### configure_optimization

View or update optimization configuration.

**Parameters:**

- `config_key` (str | None) - Configuration key in dot notation (e.g., "token_budget.default_budget")
- `config_value` (str | None) - New value to set (as JSON string)
- `show_current` (bool) - Show current configuration (default: False)
- `project_root` (str | None) - Optional project root path

**Description:**

Allows viewing and modifying optimization settings like token budgets, loading strategies, and relevance weights stored in `.memory-bank-optimization.json`.

**Returns:**

View configuration:

```json
{
  "status": "success",
  "action": "view",
  "configuration": {
    "token_budget": {
      "default_budget": 10000,
      "max_budget": 50000
    },
    "loading": {
      "default_strategy": "by_relevance",
      "default_priority": ["projectBrief.md", "..."]
    },
    "summarization": {
      "default_strategy": "extract_key_sections",
      "target_reduction": 0.5
    }
  },
  "config_file": "/path/to/.memory-bank-optimization.json"
}
```

---

### index_rules

Index custom rules from configured rules folder.

**Parameters:**

- `force` (bool) - Force reindexing even if recently indexed (default: False)
- `project_root` (str | None) - Optional project root path

**Description:**

Scans the rules folder (e.g., `.cursorrules`) and indexes all rule files for use in context optimization.

**Returns:**

```json
{
  "status": "success",
  "message": "Indexed 12 rules from .cursorrules",
  "rules_indexed": 12,
  "total_tokens": 3500,
  "rules_by_category": {
    "python": 5,
    "testing": 3,
    "security": 4
  },
  "last_indexed": "2025-12-25T15:00:00Z"
}
```

---

### get_relevant_rules

Get custom rules relevant to a task description.

**Parameters:**

- `task_description` (str) - Description of the task
- `max_tokens` (int | None) - Maximum tokens for rules (defaults to config)
- `min_relevance_score` (float | None) - Minimum relevance score (defaults to config)
- `project_root` (str | None) - Optional project root path

**Description:**

Retrieves indexed rules that are relevant to the given task, useful for providing context-specific guidelines.

**Returns:**

```json
{
  "status": "success",
  "task_description": "Write unit tests for authentication",
  "max_tokens": 2000,
  "min_relevance_score": 0.3,
  "rules_count": 5,
  "total_tokens": 1800,
  "rules": [
    {
      "file": "testing-standards.md",
      "relevance_score": 0.92,
      "tokens": 450,
      "content": "# Testing Standards\n..."
    },
    {
      "file": "python-best-practices.md",
      "relevance_score": 0.75,
      "tokens": 380,
      "content": "# Python Best Practices\n..."
    }
  ]
}
```

---

## Phase 5.1: Pattern Analysis and Insights

Tools for analyzing usage patterns and structure to identify optimization opportunities.

### analyze_usage_patterns

Analyze Memory Bank usage patterns.

**Parameters:**

- `time_range_days` (int) - Number of days to analyze (default: 30)
- `min_access_count` (int) - Minimum access count to include (default: 1)
- `include_co_access` (bool) - Include frequently co-accessed file pairs (default: True)
- `include_unused` (bool) - Include analysis of unused/stale files (default: True)
- `include_task_patterns` (bool) - Include task-based access patterns (default: True)
- `include_temporal` (bool) - Include temporal patterns (default: True)
- `project_root` (str | None) - Optional project root path

**Description:**

Tracks file access frequency, identifies frequently co-accessed files, detects unused/stale content, and analyzes task-based and temporal access patterns.

**Returns:**

```json
{
  "status": "success",
  "time_range_days": 30,
  "analysis": {
    "access_frequency": {
      "projectBrief.md": 45,
      "activeContext.md": 38,
      "progress.md": 12
    },
    "co_access_patterns": [
      {
        "files": ["systemPatterns.md", "techContext.md"],
        "co_access_count": 25,
        "confidence": 0.85
      }
    ],
    "unused_files": [
      {
        "file": "old-notes.md",
        "days_since_access": 120,
        "recommendation": "Consider archiving"
      }
    ],
    "task_patterns": {
      "authentication": ["systemPatterns.md", "techContext.md"],
      "testing": ["progress.md", "activeContext.md"]
    },
    "temporal_patterns": {
      "hourly": {"peak_hour": 14, "access_count": 25},
      "daily": {"peak_day": "Monday", "access_count": 150},
      "weekly": {"trend": "increasing"}
    }
  }
}
```

---

### analyze_structure

Analyze Memory Bank structure and organization.

**Parameters:**

- `include_organization` (bool) - Include file organization analysis (default: True)
- `include_anti_patterns` (bool) - Check for organizational anti-patterns (default: True)
- `include_complexity` (bool) - Calculate complexity metrics (default: True)
- `include_dependency_chains` (bool) - Find long dependency chains (default: True)
- `max_chain_length` (int) - Maximum chain length to search for (default: 10)
- `project_root` (str | None) - Optional project root path

**Description:**

Analyzes file organization, detects anti-patterns, measures complexity metrics, and identifies problematic dependency chains.

**Returns:**

```json
{
  "status": "success",
  "analysis": {
    "organization": {
      "total_files": 7,
      "average_size_tokens": 1214,
      "file_size_distribution": {
        "small (<500 tokens)": 1,
        "medium (500-2000 tokens)": 5,
        "large (>2000 tokens)": 1
      }
    },
    "anti_patterns": [
      {
        "type": "oversized_file",
        "file": "systemPatterns.md",
        "size_tokens": 3500,
        "recommendation": "Consider splitting into smaller files"
      },
      {
        "type": "orphaned_file",
        "file": "notes.md",
        "recommendation": "No dependencies - consider removing or linking"
      }
    ],
    "complexity": {
      "max_dependency_depth": 3,
      "cyclomatic_complexity": 12,
      "fan_in_fan_out": {
        "projectBrief.md": {"fan_in": 0, "fan_out": 3}
      }
    },
    "dependency_chains": [
      {
        "chain": ["projectBrief.md", "productContext.md", "techContext.md"],
        "length": 3,
        "complexity_score": 0.6
      }
    ]
  }
}
```

---

### get_optimization_insights

Generate AI-driven insights and recommendations.

**Parameters:**

- `min_impact_score` (float) - Minimum impact score (0-1) to include (default: 0.5)
- `categories` (str | None) - Comma-separated list of categories or None for all
  - Categories: `usage`, `organization`, `redundancy`, `dependencies`, `quality`
- `include_reasoning` (bool) - Include detailed reasoning for insights (default: True)
- `export_format` (str) - Export format: `json`, `markdown`, or `text` (default: "json")
- `project_root` (str | None) - Optional project root path

**Description:**

Combines pattern and structure analysis to generate actionable insights with specific recommendations for improvement.

**Returns:**

JSON format:

```json
{
  "status": "success",
  "insights": [
    {
      "category": "usage",
      "severity": "high",
      "impact_score": 0.85,
      "title": "Frequently co-accessed files should be consolidated",
      "description": "systemPatterns.md and techContext.md are accessed together 85% of the time",
      "recommendation": "Consider using transclusions to reduce duplication",
      "estimated_token_savings": 500,
      "reasoning": "High co-access pattern indicates related content"
    }
  ],
  "summary": {
    "total_insights": 8,
    "high_impact": 3,
    "medium_impact": 4,
    "low_impact": 1,
    "estimated_total_savings": 1200
  }
}
```

Markdown format:

```markdown
# Memory Bank Optimization Insights

## High Impact (3)

### Frequently co-accessed files should be consolidated
**Category:** Usage | **Impact Score:** 0.85

systemPatterns.md and techContext.md are accessed together 85% of the time.

**Recommendation:** Consider using transclusions to reduce duplication

**Estimated Token Savings:** 500 tokens
...
```

---

## Phase 5.2: Refactoring Suggestions

Tools for generating intelligent refactoring suggestions based on pattern analysis.

### suggest_consolidation

Suggest content consolidation opportunities.

**Parameters:**

- `min_similarity` (float) - Minimum similarity score for consolidation (0-1, default: 0.80)
- `target_reduction` (float) - Target token reduction ratio (0-1, default: 0.30)
- `suggest_transclusion` (bool) - Include transclusion syntax suggestions (default: True)
- `files` (str | None) - Comma-separated list of files to analyze, or None for all
- `project_root` (str | None) - Optional project root path

**Description:**

Detects duplicate and similar content across files and suggests consolidation strategies using transclusion and shared sections.

**Returns:**

```json
{
  "status": "success",
  "total_opportunities": 5,
  "total_token_savings": 1200,
  "opportunities": [
    {
      "id": "consol-001",
      "type": "exact_duplicate",
      "files": ["projectBrief.md", "productContext.md"],
      "content_preview": "## Project Goals\nOur primary objectives are...",
      "similarity_score": 1.0,
      "tokens": 250,
      "suggestion": {
        "action": "extract",
        "target_file": "shared/project-goals.md",
        "transclusion": "{{include: shared/project-goals.md}}"
      },
      "estimated_savings": 250
    },
    {
      "id": "consol-002",
      "type": "similar_content",
      "files": ["systemPatterns.md", "techContext.md"],
      "sections": ["## Architecture", "## System Design"],
      "similarity_score": 0.87,
      "tokens": 450,
      "suggestion": {
        "action": "consolidate",
        "approach": "Merge into single section with transclusions"
      },
      "estimated_savings": 180
    }
  ],
  "summary": {
    "top_opportunity": {
      "id": "consol-001",
      "savings": 250
    },
    "average_savings": 240
  }
}
```

---

### suggest_file_splits

Suggest files that should be split.

**Parameters:**

- `max_file_size` (int) - Maximum recommended file size in tokens (default: 5000)
- `max_sections` (int) - Maximum recommended number of sections per file (default: 10)
- `files` (str | None) - Comma-separated list of files to analyze, or None for all
- `project_root` (str | None) - Optional project root path

**Description:**

Identifies large or complex files and recommends splitting strategies to improve context loading efficiency and maintainability.

**Returns:**

```json
{
  "status": "success",
  "total_recommendations": 2,
  "recommendations": [
    {
      "id": "split-001",
      "file": "systemPatterns.md",
      "current_tokens": 6500,
      "current_sections": 15,
      "reason": "File exceeds recommended size and section count",
      "strategy": "by_topics",
      "split_points": [
        {
          "line": 45,
          "section": "## Authentication Patterns",
          "new_file": "patterns/authentication.md",
          "tokens": 1500
        },
        {
          "line": 120,
          "section": "## Data Access Patterns",
          "new_file": "patterns/data-access.md",
          "tokens": 1800
        }
      ],
      "estimated_impact": {
        "original_load_time": "high",
        "new_load_time": "medium",
        "maintainability_improvement": "significant",
        "context_efficiency": "+35%"
      }
    }
  ],
  "summary": {
    "files_to_split": 2,
    "total_new_files": 5,
    "average_reduction": "55%"
  }
}
```

---

### suggest_reorganization

Suggest structural reorganization.

**Parameters:**

- `optimize_for` (str) - Optimization goal (default: "dependency_depth")
  - `"dependency_depth"` - Minimize dependency chain length
  - `"category_based"` - Organize by inferred categories
  - `"complexity"` - Reduce overall complexity
- `suggest_new_structure` (bool) - Include detailed new structure proposal (default: True)
- `preserve_history` (bool) - Preserve version history when reorganizing (default: True)
- `project_root` (str | None) - Optional project root path

**Description:**

Analyzes current structure and proposes improvements to reduce complexity, optimize dependencies, and improve file organization.

**Returns:**

```json
{
  "status": "success",
  "plan": {
    "id": "reorg-001",
    "optimization_goal": "dependency_depth",
    "current_state": {
      "max_depth": 5,
      "avg_depth": 2.8,
      "complexity_score": 0.72
    },
    "proposed_state": {
      "max_depth": 3,
      "avg_depth": 1.9,
      "complexity_score": 0.45
    },
    "actions": [
      {
        "type": "move",
        "file": "techContext.md",
        "from": "memory-bank/",
        "to": "memory-bank/technical/",
        "reason": "Groups with similar technical files"
      },
      {
        "type": "rename",
        "file": "progress.md",
        "new_name": "status/current-progress.md",
        "reason": "Better categorization"
      },
      {
        "type": "create_category",
        "name": "technical",
        "files": ["techContext.md", "systemPatterns.md"],
        "reason": "Group related technical documentation"
      }
    ],
    "estimated_impact": {
      "files_moved": 3,
      "categories_created": 2,
      "complexity_reduction": "38%",
      "dependency_improvement": "45%"
    },
    "risks": [
      "May break external references to moved files"
    ],
    "benefits": [
      "Clearer organization",
      "Reduced dependency depth",
      "Improved context loading efficiency"
    ]
  },
  "preview": {
    "before": "memory-bank/\n  projectBrief.md\n  techContext.md\n  ...",
    "after": "memory-bank/\n  core/\n    projectBrief.md\n  technical/\n    techContext.md\n  ..."
  }
}
```

---

### preview_refactoring

Preview the impact of a refactoring suggestion.

**Parameters:**

- `suggestion_id` (str) - ID of the refactoring suggestion to preview
- `show_diff` (bool) - Include diff preview of changes (default: True)
- `estimate_impact` (bool) - Include estimated impact analysis (default: True)
- `project_root` (str | None) - Optional project root path

**Description:**

Shows detailed information about what changes would be made, which files would be affected, and what the estimated impact would be.

**Returns:**

```json
{
  "status": "success",
  "suggestion_id": "consol-001",
  "preview": {
    "type": "consolidation",
    "files_affected": ["projectBrief.md", "productContext.md"],
    "files_created": ["shared/project-goals.md"],
    "changes": [
      {
        "file": "projectBrief.md",
        "action": "replace_section",
        "section": "## Project Goals",
        "with": "{{include: shared/project-goals.md}}",
        "diff": "- ## Project Goals\n- Our primary objectives...\n+ {{include: shared/project-goals.md}}"
      }
    ]
  },
  "estimated_impact": {
    "token_savings": 250,
    "files_modified": 2,
    "files_created": 1,
    "complexity_change": "-15%",
    "maintainability_improvement": "+20%"
  },
  "risks_and_benefits": {
    "risks": [
      "Adds transclusion dependency",
      "Slightly increases loading complexity"
    ],
    "benefits": [
      "Eliminates duplicate content",
      "Single source of truth for project goals",
      "Easier to maintain consistency"
    ]
  }
}
```

---

## Phase 5.3-5.4: Safe Execution and Learning

Tools for safe refactoring execution with rollback support and learning from user feedback.

### approve_refactoring

Approve a refactoring suggestion.

**Parameters:**

- `suggestion_id` (str) - ID of the suggestion to approve
- `auto_apply` (bool) - If True, automatically apply after approval (default: False)
- `user_comment` (str | None) - Optional comment explaining the approval
- `project_root` (str | None) - Optional project root path

**Description:**

Marks a suggestion as approved and optionally applies it immediately. Approved suggestions can be executed using `apply_refactoring`.

**Returns:**

```json
{
  "status": "success",
  "approval_id": "appr-001",
  "suggestion_id": "consol-001",
  "approved_at": "2025-12-25T15:30:00Z",
  "applied": false,
  "message": "Suggestion approved successfully",
  "next_steps": [
    "Use apply_refactoring(suggestion_id='consol-001') to execute"
  ]
}
```

With auto_apply=True:

```json
{
  "status": "success",
  "approval_id": "appr-001",
  "suggestion_id": "consol-001",
  "applied": true,
  "execution_id": "exec-001",
  "message": "Suggestion approved and applied successfully"
}
```

---

### apply_refactoring

Apply an approved refactoring suggestion.

**Parameters:**

- `suggestion_id` (str) - ID of the suggestion to apply
- `approval_id` (str | None) - Optional approval ID (auto-finds if not provided)
- `dry_run` (bool) - If True, simulate without making actual changes (default: False)
- `validate_first` (bool) - If True, validate before executing (default: True)
- `project_root` (str | None) - Optional project root path

**Description:**

Executes the refactoring operations defined in a suggestion. Creates a snapshot before making changes and validates the operations.

**Returns:**

```json
{
  "status": "success",
  "execution_id": "exec-001",
  "suggestion_id": "consol-001",
  "executed_at": "2025-12-25T15:35:00Z",
  "files_modified": 2,
  "files_created": 1,
  "snapshot_created": true,
  "snapshot_id": "snap-001",
  "changes_made": [
    {
      "file": "projectBrief.md",
      "action": "modified",
      "changes": "Replaced section with transclusion"
    },
    {
      "file": "shared/project-goals.md",
      "action": "created",
      "content_tokens": 250
    }
  ],
  "validation": {
    "passed": true,
    "warnings": [],
    "errors": []
  },
  "message": "Refactoring applied successfully"
}
```

Dry run:

```json
{
  "status": "success",
  "dry_run": true,
  "would_modify": 2,
  "would_create": 1,
  "preview": "..."
}
```

---

### rollback_refactoring

Rollback a previously applied refactoring.

**Parameters:**

- `execution_id` (str) - ID of the execution to rollback
- `restore_snapshot` (bool) - If True, restore from pre-refactoring snapshot (default: True)
- `preserve_manual_changes` (bool) - If True, try to preserve manual edits (default: True)
- `dry_run` (bool) - If True, simulate without making changes (default: False)
- `project_root` (str | None) - Optional project root path

**Description:**

Restores files to their state before the refactoring was applied. Can detect and preserve manual changes made after the refactoring.

**Returns:**

```json
{
  "status": "success",
  "execution_id": "exec-001",
  "rolled_back_at": "2025-12-25T16:00:00Z",
  "snapshot_id": "snap-001",
  "files_restored": 2,
  "files_removed": 1,
  "manual_changes_detected": true,
  "manual_changes_preserved": true,
  "conflicts": [],
  "changes": [
    {
      "file": "projectBrief.md",
      "action": "restored",
      "from_snapshot": true
    },
    {
      "file": "shared/project-goals.md",
      "action": "removed",
      "reason": "Created by refactoring"
    }
  ],
  "message": "Refactoring rolled back successfully"
}
```

---

### get_refactoring_history

Get history of applied refactorings.

**Parameters:**

- `time_range_days` (int) - Number of days to include in history (default: 90)
- `include_rollbacks` (bool) - Include rolled back executions (default: True)
- `project_root` (str | None) - Optional project root path

**Description:**

Shows all refactorings that have been executed, including their status, impact, and whether they were rolled back.

**Returns:**

```json
{
  "status": "success",
  "time_range_days": 90,
  "total_executions": 12,
  "active_executions": 10,
  "rolled_back_executions": 2,
  "executions": [
    {
      "execution_id": "exec-001",
      "suggestion_id": "consol-001",
      "type": "consolidation",
      "executed_at": "2025-12-25T15:35:00Z",
      "status": "active",
      "files_modified": 2,
      "token_savings": 250,
      "rolled_back": false
    },
    {
      "execution_id": "exec-002",
      "suggestion_id": "split-001",
      "type": "file_split",
      "executed_at": "2025-12-20T10:00:00Z",
      "status": "rolled_back",
      "rolled_back_at": "2025-12-22T14:00:00Z",
      "rollback_reason": "User preferred original structure"
    }
  ],
  "statistics": {
    "total_token_savings": 1200,
    "average_savings_per_execution": 120,
    "success_rate": 0.83
  }
}
```

---

### provide_feedback

Provide feedback on a refactoring suggestion.

**Parameters:**

- `suggestion_id` (str) - ID of the suggestion to provide feedback on
- `feedback_type` (str) - Type of feedback: `"helpful"`, `"not_helpful"`, or `"incorrect"`
- `comment` (str | None) - Optional comment explaining the feedback
- `adjust_preferences` (bool) - If True, update learning preferences (default: True)
- `project_root` (str | None) - Optional project root path

**Description:**

Allows giving feedback that helps the system learn and improve future suggestions. Feedback can be "helpful", "not_helpful", or "incorrect".

**Returns:**

```json
{
  "status": "success",
  "suggestion_id": "consol-001",
  "feedback_recorded": true,
  "feedback_type": "helpful",
  "recorded_at": "2025-12-25T16:30:00Z",
  "preferences_updated": true,
  "learning_summary": {
    "pattern_reinforced": "consolidation_for_duplicates",
    "confidence_adjustment": "+0.05",
    "total_feedback_count": 45,
    "positive_feedback_rate": 0.87
  },
  "message": "Thank you for your feedback! This helps improve future suggestions."
}
```

---

### configure_learning

Configure learning and adaptation behavior.

**Parameters:**

- `action` (str) - Action to perform (default: "view")
  - `"view"` - View current configuration
  - `"update"` - Update configuration
  - `"reset"` - Reset all learning data (use with caution)
  - `"export"` - Export learned patterns
  - `"insights"` - Get learning insights
- `config_key` (str | None) - Configuration key to update (e.g., "learning.enabled")
- `config_value` (str | None) - New value for the configuration key
- `reset_learning` (bool) - If True, reset all learning data (default: False)
- `export_patterns` (bool) - If True, export learned patterns (default: False)
- `project_root` (str | None) - Optional project root path

**Description:**

Allows viewing/updating learning settings, resetting learning data, or exporting learned patterns for analysis.

**Returns:**

View action:

```json
{
  "status": "success",
  "action": "view",
  "configuration": {
    "learning": {
      "enabled": true,
      "confidence_threshold": 0.7,
      "min_feedback_count": 5,
      "pattern_retention_days": 180
    },
    "adaptation": {
      "auto_adjust_thresholds": true,
      "learning_rate": 0.1
    }
  }
}
```

Insights action:

```json
{
  "status": "success",
  "action": "insights",
  "insights": {
    "total_suggestions": 125,
    "total_feedback": 87,
    "feedback_rate": 0.70,
    "patterns_learned": 15,
    "most_successful_pattern": {
      "type": "consolidation_for_duplicates",
      "success_rate": 0.92,
      "usage_count": 42
    },
    "least_successful_pattern": {
      "type": "aggressive_splitting",
      "success_rate": 0.45,
      "usage_count": 8
    },
    "confidence_trends": {
      "consolidation": "increasing",
      "splitting": "stable",
      "reorganization": "decreasing"
    }
  }
}
```

---

## Phase 6: Shared Rules Repository

Tools for managing shared rules across multiple projects using git submodules.

### setup_shared_rules

Initialize shared rules repository as git submodule.

**Parameters:**

- `repo_url` (str) - Git repository URL for shared rules (e.g., `git@github.com:org/shared-rules.git`)
- `local_path` (str) - Local path for shared rules folder (default: ".shared-rules")
- `force` (bool) - Force re-initialization even if submodule exists (default: False)

**Description:**

Sets up a shared rules repository that can be used across multiple projects. Rules are stored in a git submodule and automatically synced with other projects using the same repository.

**Returns:**

```json
{
  "status": "success",
  "message": "Shared rules repository initialized successfully",
  "repo_url": "git@github.com:org/shared-rules.git",
  "local_path": ".shared-rules",
  "submodule_added": true,
  "rules_manifest_found": true,
  "categories": ["generic", "python", "swift", "javascript"],
  "total_rules": 25
}
```

---

### sync_shared_rules

Sync shared rules repository with remote.

**Parameters:**

- `pull` (bool) - Pull latest changes from remote (default: True)
- `push` (bool) - Push local changes to remote (default: False)

**Description:**

Synchronizes the local shared rules with the remote repository. Use `pull=True` to get latest changes from other projects, and `push=True` to share your local rule changes with other projects.

**Returns:**

```json
{
  "status": "success",
  "message": "Shared rules synchronized successfully",
  "changes_pulled": {
    "files_updated": 3,
    "files_added": 1,
    "files_removed": 0,
    "commit": "abc123..."
  },
  "changes_pushed": {
    "files_updated": 0,
    "commit": null
  },
  "reindex_triggered": true,
  "current_commit": "abc123..."
}
```

---

### update_shared_rule

Update a shared rule and push to all projects.

**Parameters:**

- `category` (str) - Category name (e.g., "python", "generic", "swift")
- `file` (str) - Rule filename (e.g., "style-guide.md")
- `content` (str) - New content for the rule
- `commit_message` (str) - Git commit message describing the change

**Description:**

Updates a rule in the shared rules repository and commits/pushes the changes so they propagate to all other projects using the same shared rules repository.

**Returns:**

```json
{
  "status": "success",
  "message": "Shared rule updated and pushed successfully",
  "category": "python",
  "file": "style-guide.md",
  "file_updated": ".shared-rules/python/style-guide.md",
  "commit_hash": "def456...",
  "commit_message": "Update Python style guide with new naming conventions",
  "pushed_to_remote": true,
  "propagation_note": "Other projects will receive this update on their next sync"
}
```

---

### get_rules_with_context

Get intelligently selected rules based on task context.

**Parameters:**

- `task_description` (str) - Description of the current task
- `max_tokens` (int) - Maximum tokens to include (default: 10000)
- `min_relevance_score` (float) - Minimum relevance score to include (0.0-1.0, default: 0.3)
- `project_files` (str | None) - Optional comma-separated list of file paths for context detection
- `rule_priority` (str) - Priority strategy (default: "local_overrides_shared")
  - `"local_overrides_shared"` - Local rules take precedence
  - `"shared_overrides_local"` - Shared rules take precedence
- `context_aware` (bool) - Enable intelligent context detection (default: True)

**Description:**

Analyzes the task description and project context to intelligently select the most relevant rules from both shared and local sources. Automatically detects programming languages, frameworks, and task types to load appropriate rules.

**Returns:**

```json
{
  "status": "success",
  "task_description": "Implement JWT authentication for Flask API",
  "context": {
    "detected_languages": ["python"],
    "detected_frameworks": ["flask"],
    "detected_task_types": ["authentication", "api"],
    "confidence": 0.92
  },
  "rules_loaded": {
    "generic": [
      {
        "file": "security.md",
        "source": "shared",
        "relevance_score": 0.95,
        "tokens": 450
      },
      {
        "file": "coding-standards.md",
        "source": "shared",
        "relevance_score": 0.75,
        "tokens": 380
      }
    ],
    "python": [
      {
        "file": "best-practices.md",
        "source": "shared",
        "relevance_score": 0.88,
        "tokens": 520
      },
      {
        "file": "testing-standards.md",
        "source": "local",
        "relevance_score": 0.82,
        "tokens": 400
      }
    ],
    "local_overrides": [
      {
        "file": "auth-guidelines.md",
        "source": "local",
        "relevance_score": 0.98,
        "tokens": 350,
        "overrides": "shared/generic/auth-patterns.md"
      }
    ]
  },
  "total_rules": 8,
  "total_tokens": 2100,
  "token_budget": 10000,
  "utilization": 21.0,
  "merge_strategy": "local_overrides_shared"
}
```

---

## Phase 8: Project Structure Management

Tools for managing standardized `.memory-bank/` project structure with migration support.

### setup_project_structure

Initialize comprehensive project structure with optional interactive setup.

**Parameters:**

- `project_root` (str | None) - Project root directory (defaults to current directory)
- `project_name` (str | None) - Name of the project
- `project_type` (str | None) - Type of project (web, mobile, backend, library, etc.)
- `primary_language` (str | None) - Primary programming language
- `frameworks` (str | None) - Main frameworks/libraries used
- `use_shared_rules` (bool) - Whether to setup shared rules as git submodule (default: False)
- `shared_rules_repo` (str | None) - Git repository URL for shared rules
- `force` (bool) - Force recreation even if structure exists (default: False)

**Description:**

Creates the standardized `.memory-bank/` directory structure including:

- `knowledge/` directory for Memory Bank files
- `rules/` directory (local and optional shared via git submodule)
- `plans/` directory with templates
- `config/` directory for configuration
- Cursor IDE integration via symlinks

**Returns:**

```json
{
  "success": true,
  "message": "Project structure created successfully",
  "report": {
    "directories_created": [
      ".memory-bank/knowledge",
      ".memory-bank/rules/local",
      ".memory-bank/plans/templates",
      ".memory-bank/config"
    ],
    "files_created": [
      ".memory-bank/knowledge/projectBrief.md",
      ".memory-bank/rules/local/main.cursorrules",
      ".memory-bank/config/structure.json"
    ],
    "symlinks_created": [
      ".cursor/knowledge -> ../.memory-bank/knowledge",
      ".cursorrules -> .memory-bank/rules/local/main.cursorrules"
    ],
    "shared_rules_setup": false
  },
  "next_steps": [
    "Edit .memory-bank/knowledge/projectBrief.md to document your project",
    "Customize rules in .memory-bank/rules/local/",
    "Use setup_cursor_integration() if symlinks weren't created"
  ]
}
```

---

### migrate_project_structure

Migrate from legacy structure to standardized `.memory-bank/` structure.

**Parameters:**

- `project_root` (str | None) - Project root directory (defaults to current directory)
- `legacy_type` (str | None) - Type of legacy structure (auto-detected if not provided)
  - `"tradewing-style"` - Files in root + .cursor/plans
  - `"doc-mcp-style"` - docs/memory-bank structure
  - `"scattered-files"` - Memory bank files throughout project
  - `"cursor-default"` - Just .cursorrules file
- `backup` (bool) - Create backup of existing files before migration (default: True)
- `archive` (bool) - Archive legacy files after migration (default: True)
- `dry_run` (bool) - Preview migration without making changes (default: False)

**Description:**

Migrates from various legacy structures to the standardized format. Supports multiple legacy types with automatic detection.

**Returns:**

```json
{
  "success": true,
  "message": "Migration completed successfully",
  "report": {
    "legacy_type": "tradewing-style",
    "backup_created": true,
    "backup_path": "/path/to/project/.memory-bank-backup-20251225",
    "files_migrated": {
      "knowledge": 7,
      "rules": 3,
      "plans": 5
    },
    "files_archived": {
      "old_memory_bank": 7,
      "old_cursorrules": 1
    },
    "structure_created": true,
    "symlinks_created": true
  },
  "next_steps": [
    "Review migrated files in .memory-bank/",
    "Update any broken links using validate_links()",
    "Archive old structure if everything looks correct"
  ]
}
```

---

### setup_cursor_integration

Setup Cursor IDE integration via symlinks.

**Parameters:**

- `project_root` (str | None) - Project root directory (defaults to current directory)
- `force` (bool) - Force recreation of symlinks even if they exist (default: False)

**Description:**

Creates symlinks in `.cursor/` directory pointing to `.memory-bank/` structure. Works cross-platform (Unix/macOS with symlinks, Windows with junctions).

**Returns:**

```json
{
  "success": true,
  "message": "Cursor integration setup successfully",
  "report": {
    "platform": "darwin",
    "symlinks_created": [
      ".cursor/knowledge -> ../.memory-bank/knowledge",
      ".cursor/rules -> ../.memory-bank/rules",
      ".cursor/plans -> ../.memory-bank/plans",
      ".cursorrules -> .memory-bank/rules/local/main.cursorrules"
    ],
    "symlinks_recreated": 0,
    "errors": []
  }
}
```

---

### check_structure_health

Analyze project structure health and provide recommendations.

**Parameters:**

- `project_root` (str | None) - Project root directory (defaults to current directory)

**Description:**

Checks:

- All required directories exist
- Symlinks are valid and not broken
- Configuration file exists and is valid
- Files are organized properly
- No orphaned or misplaced files

**Returns:**

```json
{
  "success": true,
  "health": {
    "score": 85,
    "grade": "B",
    "status": "good",
    "checks": [
      {
        "name": "Required directories",
        "passed": true,
        "message": "All required directories exist"
      },
      {
        "name": "Symlinks",
        "passed": true,
        "message": "All symlinks are valid"
      },
      {
        "name": "Configuration",
        "passed": true,
        "message": "Configuration file is valid"
      },
      {
        "name": "File organization",
        "passed": true,
        "message": "Files are properly organized"
      },
      {
        "name": "Orphaned files",
        "passed": false,
        "message": "Found 2 misplaced files",
        "details": ["old-file.md in root", "temp.md in .memory-bank/"]
      }
    ],
    "issues": [
      {
        "severity": "warning",
        "category": "organization",
        "message": "Found 2 misplaced files",
        "files": ["old-file.md", ".memory-bank/temp.md"],
        "recommendation": "Move to appropriate directory or archive"
      }
    ],
    "recommendations": [
      "Move misplaced files to correct locations",
      "Run cleanup_project_structure() to automate cleanup"
    ]
  },
  "summary": "Structure is in good health with minor issues",
  "action_required": false
}
```

**Health Grades:**

- A (90-100): Excellent
- B (80-89): Good
- C (70-79): Fair
- D (60-69): Poor
- F (0-59): Critical

---

### cleanup_project_structure

Perform automated housekeeping on project structure.

**Parameters:**

- `project_root` (str | None) - Project root directory (defaults to current directory)
- `actions` (list[str] | None) - List of actions to perform (all if not specified)
  - `"archive_stale"` - Archive stale plans
  - `"organize_plans"` - Organize plans by status
  - `"fix_symlinks"` - Fix broken symlinks
  - `"update_index"` - Update metadata index
  - `"remove_empty"` - Remove empty directories
- `stale_days` (int) - Days of inactivity before considering plan stale (default: 90)
- `dry_run` (bool) - Preview actions without making changes (default: True)

**Description:**

Performs automated maintenance tasks to keep the structure clean and organized.

**Returns:**

```json
{
  "success": true,
  "message": "Cleanup completed successfully",
  "report": {
    "dry_run": false,
    "actions_performed": {
      "archive_stale": {
        "plans_archived": 3,
        "files": [
          "old-feature-plan.md",
          "abandoned-refactor.md",
          "obsolete-research.md"
        ]
      },
      "organize_plans": {
        "plans_moved": 5,
        "active_to_completed": 2,
        "completed_to_archived": 3
      },
      "fix_symlinks": {
        "symlinks_fixed": 1,
        "broken_symlinks_removed": 0
      },
      "update_index": {
        "entries_updated": 15,
        "stale_entries_removed": 2
      },
      "remove_empty": {
        "directories_removed": 2
      }
    },
    "total_changes": 11
  }
}
```

---

### get_structure_info

Get current structure configuration and status.

**Parameters:**

- `project_root` (str | None) - Project root directory (defaults to current directory)

**Description:**

Returns information about the current structure configuration and status.

**Returns:**

```json
{
  "success": true,
  "structure_info": {
    "version": "1.0.0",
    "root": "/path/to/project",
    "paths": {
      "memory_bank": ".memory-bank",
      "knowledge": ".memory-bank/knowledge",
      "rules_local": ".memory-bank/rules/local",
      "rules_shared": ".memory-bank/rules/shared",
      "plans": ".memory-bank/plans",
      "config": ".memory-bank/config"
    },
    "configuration": {
      "project_name": "My Project",
      "project_type": "web",
      "primary_language": "python",
      "use_shared_rules": true,
      "shared_rules_repo": "git@github.com:org/shared-rules.git"
    },
    "statistics": {
      "knowledge_files": 7,
      "local_rules": 5,
      "shared_rules": 25,
      "active_plans": 3,
      "completed_plans": 12,
      "archived_plans": 45
    },
    "cursor_integration": {
      "enabled": true,
      "symlinks": [
        ".cursor/knowledge -> ../.memory-bank/knowledge",
        ".cursor/rules -> ../.memory-bank/rules",
        ".cursor/plans -> ../.memory-bank/plans",
        ".cursorrules -> .memory-bank/rules/local/main.cursorrules"
      ]
    },
    "health": {
      "score": 85,
      "grade": "B",
      "status": "good"
    }
  },
  "message": "Structure information retrieved successfully"
}
```

---

## Legacy Tools

Legacy tools maintained for backward compatibility.

### get_memory_bank_structure

Get a detailed description of the Memory Bank file structure.

**Parameters:** None

**Description:**

Returns a description of the recommended Memory Bank structure and file organization.

**Returns:**

String with structure description:

```text
Memory Bank Structure:

memory-bank/
├── projectBrief.md - Foundation document
├── productContext.md - Product context
├── activeContext.md - Current work
├── systemPatterns.md - Architecture
├── techContext.md - Technical details
├── progress.md - Development progress
└── roadmap.md - Future plans

Each file serves a specific purpose in maintaining context for AI assistants...
```

---

### generate_memory_bank_template

[LEGACY] Generate a template for a specific Memory Bank file.

**Parameters:**

- `file_name` (str) - The name of the file to generate a template for (e.g., "projectBrief.md")

**Description:**

**NOTE:** This tool is legacy. For new projects, use `initialize_memory_bank()` instead, which creates all files at once with proper metadata tracking.

Returns a template for the specified file.

**Returns:**

String with template content:

```markdown
# Project Brief

## Overview
[Brief description of the project]

## Goals
[Key objectives and goals]

## Scope
[What's in scope and out of scope]
...
```

---

### analyze_project_summary

Analyze a project summary and provide suggestions for Memory Bank content.

**Parameters:**

- `project_summary` (str) - A summary of the project

**Description:**

Analyzes a project description and suggests what should go into each Memory Bank file.

**Returns:**

```json
{
  "status": "success",
  "suggestions": {
    "projectBrief.md": [
      "Include project goals and objectives",
      "Define scope and boundaries",
      "List key stakeholders"
    ],
    "productContext.md": [
      "Describe target users",
      "Explain problem being solved",
      "Outline solution approach"
    ],
    "techContext.md": [
      "List technologies used",
      "Document architecture decisions",
      "Note development setup requirements"
    ]
  }
}
```

---

## Error Handling

All tools follow consistent error handling:

### Success Response

```json
{
  "status": "success",
  ...
}
```

### Error Response

```json
{
  "status": "error",
  "error": "Error message describing what went wrong",
  "error_type": "FileNotFoundError",
  "details": {
    "file": "missing-file.md",
    "attempted_path": "/path/to/memory-bank/missing-file.md"
  }
}
```

### Common Error Types

- `FileNotFoundError` - Requested file doesn't exist
- `FileConflictError` - File was modified externally during operation
- `FileLockTimeoutError` - Couldn't acquire file lock (file in use)
- `CircularDependencyError` - Circular transclusion detected
- `MaxDepthExceededError` - Transclusion nesting too deep
- `ValidationError` - Invalid input parameters
- `MigrationFailedError` - Migration process failed
- `GitConflictError` - Git operation conflict

---

## See Also

- [Architecture Documentation](../architecture.md) - System architecture details
- [API Modules Reference](modules.md) - Module-level API documentation
- [Configuration Guide](../guides/configuration.md) - Configuration options
- [Troubleshooting Guide](../guides/troubleshooting.md) - Common issues and solutions
