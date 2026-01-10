# Configuration Guide

This guide covers all configuration options for Cortex.

## Overview

Cortex uses JSON configuration files for various features. Configuration files are stored in the project root and are **not** tracked by Git (add them to `.gitignore`).

## Configuration Files

### `.memory-bank-validation.json`

Controls validation behavior for schema validation, duplication detection, and quality metrics.

**Location**: Project root

**Default Values**:

```json
{
  "schema_validation": {
    "enabled": true,
    "custom_schemas": {},
    "required_sections": {
      "projectBrief.md": ["Project Overview", "Goals"],
      "productContext.md": ["Product Description"],
      "systemPatterns.md": ["Architecture"],
      "techContext.md": ["Technologies"]
    },
    "heading_hierarchy": true
  },
  "duplication_detection": {
    "enabled": true,
    "similarity_threshold": 0.85,
    "min_section_length": 50
  },
  "quality_metrics": {
    "enabled": true,
    "weights": {
      "completeness": 0.25,
      "consistency": 0.25,
      "freshness": 0.15,
      "structure": 0.20,
      "token_efficiency": 0.15
    }
  },
  "token_budget": {
    "max_total_tokens": 100000,
    "warning_threshold": 0.9,
    "max_file_tokens": 10000
  }
}
```

**Configuration Options**:

#### Schema Validation

- `enabled` (bool): Enable/disable schema validation
- `custom_schemas` (dict): Custom schemas for specific files
- `required_sections` (dict): Required sections per file
- `heading_hierarchy` (bool): Enforce heading hierarchy (H1 → H2 → H3)

#### Duplication Detection

- `enabled` (bool): Enable/disable duplication detection
- `similarity_threshold` (float): Similarity threshold (0.0-1.0, default: 0.85)
- `min_section_length` (int): Minimum section length to check (default: 50 characters)

#### Quality Metrics

- `enabled` (bool): Enable/disable quality scoring
- `weights` (dict): Category weights (must sum to 1.0)
  - `completeness`: Required sections present
  - `consistency`: Low duplication, good links
  - `freshness`: Recently updated
  - `structure`: Good organization
  - `token_efficiency`: Within budget

#### Validation Token Budget

- `max_total_tokens` (int): Maximum total tokens across all files
- `warning_threshold` (float): Threshold for warnings (0.0-1.0)
- `max_file_tokens` (int): Maximum tokens per file

**Example Custom Configuration**:

```json
{
  "schema_validation": {
    "enabled": true,
    "required_sections": {
      "projectBrief.md": ["Overview", "Goals", "Scope", "Timeline"],
      "techContext.md": ["Tech Stack", "Infrastructure", "Dependencies"]
    }
  },
  "duplication_detection": {
    "similarity_threshold": 0.90
  },
  "token_budget": {
    "max_total_tokens": 150000
  }
}
```

### `.memory-bank-optimization.json`

Controls context optimization, progressive loading, and summarization.

**Location**: Project root

**Default Values**:

```json
{
  "token_budget": {
    "default_budget": 100000,
    "max_budget": 200000,
    "reserve_budget": 10000
  },
  "optimization": {
    "strategy": "hybrid",
    "mandatory_files": ["memorybankinstructions.md"],
    "include_dependencies": true,
    "section_level": false
  },
  "progressive_loading": {
    "enabled": true,
    "default_strategy": "by_relevance",
    "default_priority": [
      "memorybankinstructions.md",
      "projectBrief.md",
      "activeContext.md",
      "systemPatterns.md",
      "techContext.md",
      "productContext.md",
      "progress.md"
    ]
  },
  "summarization": {
    "enabled": true,
    "default_strategy": "extract_key_sections",
    "target_reduction": 0.5,
    "cache_summaries": true
  },
  "relevance_scoring": {
    "tfidf_weight": 0.4,
    "dependency_weight": 0.3,
    "recency_weight": 0.2,
    "quality_weight": 0.1
  },
  "rules": {
    "enabled": true,
    "rules_folder": ".cursorrules",
    "auto_include": true,
    "max_rules_tokens": 20000,
    "min_relevance_score": 0.3,
    "reindex_interval_hours": 24
  },
  "shared_rules": {
    "enabled": false,
    "repo_url": "",
    "branch": "main",
    "folder": ".shared-rules",
    "auto_sync": true,
    "sync_interval_hours": 24,
    "priority": "local_overrides_shared",
    "context_detection": {
      "enabled": true,
      "language_keywords": {
        "python": ["python", "py", "django", "flask"],
        "swift": ["swift", "swiftui", "ios", "macos"],
        "javascript": ["javascript", "js", "react", "vue", "node"]
      }
    },
    "always_include_generic": true
  },
  "performance": {
    "cache_enabled": true,
    "cache_ttl_seconds": 300,
    "max_cache_size_mb": 100
  }
}
```

**Configuration Options**:

#### Optimization Token Budget

- `default_budget` (int): Default token budget for operations
- `max_budget` (int): Maximum allowed budget
- `reserve_budget` (int): Reserved tokens for metadata

#### Optimization

- `strategy` (str): Strategy to use ("priority", "dependency", "section", "hybrid")
- `mandatory_files` (list): Files always included
- `include_dependencies` (bool): Include dependencies of selected files
- `section_level` (bool): Enable section-level optimization

#### Progressive Loading

- `enabled` (bool): Enable progressive loading
- `default_strategy` (str): Strategy ("by_priority", "by_dependencies", "by_relevance")
- `default_priority` (list): File priority order

#### Summarization

- `enabled` (bool): Enable summarization
- `default_strategy` (str): Strategy ("extract_key_sections", "compress_verbose", "headers_only")
- `target_reduction` (float): Target reduction percentage (0.0-1.0)
- `cache_summaries` (bool): Cache summaries for reuse

#### Relevance Scoring

- `tfidf_weight` (float): Weight for keyword matching (0.0-1.0)
- `dependency_weight` (float): Weight for dependency-based relevance
- `recency_weight` (float): Weight for recently modified files
- `quality_weight` (float): Weight for quality score

#### Rules

- `enabled` (bool): Enable custom rules integration
- `rules_folder` (str): Folder containing rule files
- `auto_include` (bool): Auto-include rules in context
- `max_rules_tokens` (int): Maximum tokens for rules
- `min_relevance_score` (float): Minimum relevance threshold
- `reindex_interval_hours` (int): Hours between re-indexing

#### Shared Rules

- `enabled` (bool): Enable shared rules via git submodule
- `repo_url` (str): Git repository URL
- `branch` (str): Branch to use
- `folder` (str): Local folder for submodule
- `auto_sync` (bool): Automatically sync with remote
- `sync_interval_hours` (int): Hours between syncs
- `priority` (str): Merge strategy ("local_overrides_shared", "shared_overrides_local")
- `context_detection` (dict): Context detection settings
- `always_include_generic` (bool): Always include generic rules

#### Performance

- `cache_enabled` (bool): Enable caching
- `cache_ttl_seconds` (int): Cache TTL in seconds
- `max_cache_size_mb` (int): Maximum cache size in MB

**Example Custom Configuration**:

```json
{
  "token_budget": {
    "default_budget": 150000
  },
  "optimization": {
    "strategy": "dependency",
    "mandatory_files": ["memorybankinstructions.md", "projectBrief.md"]
  },
  "rules": {
    "enabled": true,
    "rules_folder": ".cursor/rules"
  },
  "shared_rules": {
    "enabled": true,
    "repo_url": "https://github.com/your-org/shared-rules.git"
  }
}
```

### `.memory-bank-learning.json`

Controls learning engine behavior for refactoring adaptation.

**Location**: Project root (auto-created)

**Structure**:

```json
{
  "pattern_confidence": {
    "duplication_consolidation": 0.8,
    "file_splitting": 0.7,
    "reorganization": 0.6
  },
  "feedback_history": [
    {
      "timestamp": "2024-12-25T10:30:00Z",
      "suggestion_id": "consolidation_001",
      "action": "approved",
      "feedback_type": "positive",
      "comment": "Consolidation worked well"
    }
  ],
  "learned_patterns": {
    "prefer_transclusion_for_duplicates": true,
    "max_file_size": 500
  }
}
```

**Note**: This file is managed automatically by the learning engine. Manual edits are not recommended.

### `.memory-bank-approvals.json`

Stores refactoring approval records.

**Location**: Project root (auto-created)

**Structure**:

```json
{
  "approvals": {
    "consolidation_001": {
      "status": "approved",
      "timestamp": "2024-12-25T10:30:00Z",
      "approved_by": "user",
      "notes": "Looks good"
    },
    "split_002": {
      "status": "pending",
      "timestamp": "2024-12-25T11:00:00Z"
    }
  }
}
```

**Note**: Managed automatically. Do not edit manually.

## MCP Tools for Configuration

### Update Validation Configuration

Use `configure_validation` tool:

```json
{
  "project_root": "/path/to/project",
  "config": {
    "token_budget.max_total_tokens": 150000,
    "duplication_detection.similarity_threshold": 0.90
  }
}
```

### Update Optimization Configuration

Use `configure_optimization` tool:

```json
{
  "project_root": "/path/to/project",
  "config": {
    "token_budget.default_budget": 120000,
    "rules.enabled": true,
    "shared_rules.enabled": true
  }
}
```

### Update Learning Configuration

Use `configure_learning` tool:

```json
{
  "project_root": "/path/to/project",
  "config": {
    "pattern_confidence.duplication_consolidation": 0.9
  }
}
```

## Configuration Best Practices

### 1. Start with Defaults

Begin with default configuration and adjust based on your needs:

```bash
# No configuration needed initially
# Defaults work for most projects
```

### 2. Adjust Token Budgets

Set budgets based on your context window:

```json
{
  "token_budget": {
    "default_budget": 100000,  // For Claude Sonnet
    "max_budget": 200000       // Maximum safety limit
  }
}
```

### 3. Configure Rules Folders

Point to your rules directory:

```json
{
  "rules": {
    "enabled": true,
    "rules_folder": ".cursor/rules"
  }
}
```

### 4. Enable Shared Rules

For multi-project consistency:

```json
{
  "shared_rules": {
    "enabled": true,
    "repo_url": "https://github.com/your-org/shared-rules.git",
    "priority": "local_overrides_shared"
  }
}
```

### 5. Tune Relevance Scoring

Adjust weights based on your workflow:

```json
{
  "relevance_scoring": {
    "tfidf_weight": 0.5,        // Keyword matching
    "dependency_weight": 0.3,   // File relationships
    "recency_weight": 0.1,      // Recent edits
    "quality_weight": 0.1       // Quality score
  }
}
```

### 6. Add to .gitignore

```gitignore
# Memory Bank Configuration (not tracked)
.memory-bank-validation.json
.memory-bank-optimization.json
.memory-bank-learning.json
.memory-bank-approvals.json
.memory-bank-index
.memory-bank-history/
.memory-bank-access-log.json
.memory-bank-refactoring-history.json
.memory-bank-rollbacks.json
```

## Environment Variables

Currently, Cortex does not use environment variables for configuration. All configuration is file-based.

## See Also

- [Getting Started](../getting-started.md) - Initial setup
- [MCP Tools](../api/tools.md) - Configuration tools
- [Architecture](../architecture.md) - System design
