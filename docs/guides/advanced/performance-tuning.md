# Performance Tuning Guide

This guide covers optimization strategies for Cortex performance, focusing on token management, caching, and large codebase handling.

## Table of Contents

1. [Performance Overview](#performance-overview)
2. [Token Budget Optimization](#token-budget-optimization)
3. [Cache Configuration and Tuning](#cache-configuration-and-tuning)
4. [Large Codebase Handling](#large-codebase-handling)
5. [Lazy Loading Configuration](#lazy-loading-configuration)
6. [Benchmark Interpretation](#benchmark-interpretation)
7. [Monitoring and Profiling](#monitoring-and-profiling)
8. [Database and Index Optimization](#database-and-index-optimization)
9. [Network and I/O Optimization](#network-and-io-optimization)
10. [Memory Management](#memory-management)

---

## Performance Overview

### Key Performance Metrics

Cortex tracks several performance metrics:

| Metric | Target | Critical Threshold |
|--------|--------|--------------------|
| File Read Time | <50ms | >200ms |
| File Write Time | <100ms | >500ms |
| Validation Time | <200ms | >1s |
| Token Counting | <10ms | >50ms |
| Link Resolution | <100ms | >500ms |
| Context Loading | <500ms | >2s |
| Cache Hit Rate | >90% | <70% |
| Memory Usage | <500MB | >2GB |

### Performance Budget

```json
{
  "performance_budget": {
    "file_operations": {
      "read_ms": 50,
      "write_ms": 100,
      "delete_ms": 50
    },
    "validation": {
      "schema_ms": 100,
      "links_ms": 200,
      "duplicates_ms": 500,
      "quality_ms": 300
    },
    "optimization": {
      "token_count_ms": 10,
      "context_load_ms": 500,
      "summarization_ms": 1000
    },
    "cache": {
      "hit_rate_min": 0.9,
      "lookup_ms": 5,
      "write_ms": 10
    }
  }
}
```

### Bottleneck Identification

**Run Performance Analysis:**

```bash
# Run comprehensive performance analysis
cortex analyze_performance --output=perf-report.json

# Run lightweight benchmarks
cortex run_benchmarks --suite=lightweight

# Profile specific operation
cortex profile_operation --operation=validate_memory_bank
```

**Performance Report Structure:**

```json
{
  "timestamp": "2024-01-10T12:00:00Z",
  "total_duration_ms": 1234,
  "operations": {
    "file_operations": {
      "count": 150,
      "total_ms": 450,
      "avg_ms": 3.0,
      "slowest": {
        "file": "systemPatterns.md",
        "duration_ms": 45
      }
    },
    "validation": {
      "count": 7,
      "total_ms": 890,
      "avg_ms": 127.1,
      "slowest": {
        "validator": "duplication_detector",
        "duration_ms": 456
      }
    },
    "cache": {
      "hits": 1234,
      "misses": 56,
      "hit_rate": 0.957,
      "avg_lookup_ms": 2.3
    }
  },
  "bottlenecks": [
    {
      "component": "duplication_detector",
      "severity": "high",
      "duration_ms": 456,
      "recommendation": "Enable caching for duplication results"
    }
  ]
}
```

---

## Token Budget Optimization

### Understanding Token Usage

**Token Distribution Analysis:**

```bash
# Analyze token usage across files
cortex analyze_token_distribution --output=tokens.json
```

**Sample Output:**

```json
{
  "total_tokens": 45678,
  "budget": 100000,
  "utilization": 0.457,
  "files": [
    {
      "file": "systemPatterns.md",
      "tokens": 12345,
      "percentage": 27.0,
      "sections": [
        {"name": "Architecture", "tokens": 5678, "percentage": 46.0},
        {"name": "Design Patterns", "tokens": 3456, "percentage": 28.0},
        {"name": "Implementation", "tokens": 3211, "percentage": 26.0}
      ]
    },
    {
      "file": "techContext.md",
      "tokens": 8901,
      "percentage": 19.5
    }
  ],
  "recommendations": [
    {
      "file": "systemPatterns.md",
      "action": "Consider splitting 'Architecture' section",
      "potential_savings": 2000
    }
  ]
}
```

### Token Budget Configuration

**Optimal Configuration:**

```json
{
  "token_budget": {
    "max_total_tokens": 100000,
    "max_file_tokens": 10000,
    "warning_threshold": 0.85,
    "critical_threshold": 0.95,

    "file_budgets": {
      "projectBrief.md": 5000,
      "systemPatterns.md": 15000,
      "techContext.md": 12000,
      "activeContext.md": 8000,
      "productContext.md": 10000,
      "progress.md": 7000,
      "roadmap.md": 8000
    },

    "section_budgets": {
      "systemPatterns.md": {
        "Architecture": 6000,
        "Design Patterns": 5000,
        "Implementation": 4000
      }
    },

    "optimization": {
      "auto_summarize": true,
      "summarize_threshold": 0.9,
      "compression_ratio": 0.5,
      "preserve_sections": [
        "Overview",
        "Quick Start",
        "Current Sprint"
      ]
    }
  }
}
```

### Progressive Token Loading

**Priority-Based Loading:**

```json
{
  "progressive_loading": {
    "enabled": true,
    "strategy": "priority",

    "priorities": {
      "critical": {
        "files": ["projectBrief.md", "activeContext.md"],
        "load_immediately": true,
        "token_reserve": 15000
      },
      "high": {
        "files": ["systemPatterns.md", "techContext.md"],
        "load_on_request": true,
        "token_reserve": 25000
      },
      "medium": {
        "files": ["productContext.md", "progress.md"],
        "load_on_demand": true,
        "token_reserve": 15000
      },
      "low": {
        "files": ["roadmap.md"],
        "defer_loading": true,
        "token_reserve": 10000
      }
    },

    "loading_strategy": {
      "batch_size": 3,
      "delay_between_batches_ms": 100,
      "parallel_loading": true,
      "max_concurrent": 5
    }
  }
}
```

### Token Optimization Strategies

**1. Content Summarization:**

```json
{
  "summarization": {
    "enabled": true,
    "trigger_threshold": 0.85,
    "target_ratio": 0.6,

    "strategies": {
      "extractive": {
        "enabled": true,
        "sentence_count": 10,
        "preserve_headings": true
      },
      "abstractive": {
        "enabled": false,
        "max_length": 500
      }
    },

    "file_preferences": {
      "systemPatterns.md": {
        "strategy": "extractive",
        "preserve_sections": ["Architecture", "Key Patterns"],
        "summarize_sections": ["Implementation Details", "Examples"]
      }
    }
  }
}
```

**2. Selective Transclusion:**

```markdown
<!-- Instead of full inclusion -->
{{include:systemPatterns.md}}

<!-- Use selective inclusion -->
{{include:systemPatterns.md#Architecture}}
{{include:systemPatterns.md#Design Patterns | summarize:0.5}}

<!-- Use conditional inclusion -->
{{include:techContext.md#Tech Stack | tokens:max=2000}}
```

**3. Token-Aware Caching:**

```json
{
  "cache": {
    "token_aware": true,
    "cache_summaries": true,
    "cache_sections": true,

    "strategies": {
      "full_content": {
        "max_tokens": 5000,
        "ttl_seconds": 3600
      },
      "summarized_content": {
        "max_tokens": 10000,
        "ttl_seconds": 7200
      },
      "sections_only": {
        "max_tokens": 20000,
        "ttl_seconds": 1800
      }
    }
  }
}
```

---

## Cache Configuration and Tuning

### Multi-Level Caching

**Cache Architecture:**

```
┌─────────────────────────────────────────────────────────┐
│                     L1 Cache (Memory)                   │
│                   Fast, Small (50MB)                    │
│                     TTL: 5 minutes                      │
└────────────────────┬────────────────────────────────────┘
                     │ Miss
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   L2 Cache (Disk LRU)                   │
│                  Medium, Larger (500MB)                 │
│                    TTL: 1 hour                          │
└────────────────────┬────────────────────────────────────┘
                     │ Miss
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  File System (Source)                   │
│                    Slow, Unlimited                      │
└─────────────────────────────────────────────────────────┘
```

**Configuration:**

```json
{
  "cache": {
    "multi_level": {
      "enabled": true,

      "l1": {
        "type": "memory",
        "max_size_mb": 50,
        "max_entries": 1000,
        "ttl_seconds": 300,
        "eviction": "lru"
      },

      "l2": {
        "type": "disk",
        "path": ".memory-bank-cache",
        "max_size_mb": 500,
        "max_entries": 10000,
        "ttl_seconds": 3600,
        "eviction": "lfu",
        "compression": true
      },

      "promotion": {
        "l2_to_l1_threshold": 3,
        "access_window_seconds": 300
      }
    }
  }
}
```

### Cache Warming

**Pre-populate Cache on Startup:**

```json
{
  "cache": {
    "warming": {
      "enabled": true,
      "on_startup": true,
      "files": [
        "projectBrief.md",
        "activeContext.md",
        "systemPatterns.md"
      ],
      "include_transclusions": true,
      "parallel": true,
      "max_concurrent": 5
    }
  }
}
```

**Scheduled Cache Warming:**

```bash
# Warm cache every hour
*/60 * * * * cortex warm_cache --files="critical"
```

### Cache Invalidation Strategies

**Smart Invalidation:**

```json
{
  "cache": {
    "invalidation": {
      "strategy": "smart",

      "triggers": {
        "file_modified": {
          "enabled": true,
          "invalidate_transclusions": true,
          "cascade_invalidation": true
        },
        "dependency_changed": {
          "enabled": true,
          "check_interval_seconds": 60
        },
        "manual_trigger": {
          "enabled": true,
          "api_endpoint": true
        }
      },

      "granularity": {
        "file_level": true,
        "section_level": true,
        "transclusion_level": true
      }
    }
  }
}
```

### Cache Performance Tuning

**Monitor Cache Performance:**

```bash
# Get cache statistics
cortex get_cache_stats

# Output:
{
  "l1": {
    "hits": 1234,
    "misses": 56,
    "hit_rate": 0.957,
    "size_mb": 45.2,
    "entries": 876,
    "avg_lookup_ms": 2.1,
    "evictions": 23
  },
  "l2": {
    "hits": 456,
    "misses": 89,
    "hit_rate": 0.837,
    "size_mb": 234.5,
    "entries": 4567,
    "avg_lookup_ms": 15.3,
    "evictions": 123
  },
  "recommendations": [
    "Increase L1 cache size to 100MB (high hit rate)",
    "Enable compression for L2 cache (large size)"
  ]
}
```

**Optimize Cache Settings:**

```python
# scripts/optimize-cache.py
import json

def optimize_cache_config(stats: dict) -> dict:
    """Generate optimized cache configuration based on stats."""
    config = {"cache": {}}

    # L1 optimization
    if stats["l1"]["hit_rate"] > 0.95 and stats["l1"]["evictions"] > 100:
        # High hit rate with evictions = need more space
        config["cache"]["l1"] = {
            "max_size_mb": stats["l1"]["size_mb"] * 1.5
        }

    # L2 optimization
    if stats["l2"]["size_mb"] > 400:
        # Large cache = enable compression
        config["cache"]["l2"] = {
            "compression": True,
            "compression_algorithm": "lz4"
        }

    # Eviction strategy
    if stats["l1"]["evictions"] / stats["l1"]["hits"] > 0.05:
        # High eviction rate = switch to LFU
        config["cache"]["l1"]["eviction"] = "lfu"

    return config
```

---

## Large Codebase Handling

### Scalability Configuration

**For Codebases > 100K LOC:**

```json
{
  "large_codebase": {
    "enabled": true,
    "threshold_loc": 100000,

    "optimizations": {
      "lazy_initialization": true,
      "parallel_processing": true,
      "max_workers": 8,
      "chunk_size": 1000,

      "file_watching": {
        "enabled": true,
        "debounce_ms": 1000,
        "batch_updates": true,
        "exclude_patterns": [
          "node_modules/**",
          ".git/**",
          "dist/**",
          "build/**",
          "__pycache__/**",
          "*.pyc"
        ]
      },

      "indexing": {
        "incremental": true,
        "background": true,
        "priority": "low",
        "index_interval_seconds": 300
      }
    }
  }
}
```

### Selective Processing

**File Filtering:**

```json
{
  "processing": {
    "include_patterns": [
      "src/**/*.py",
      "src/**/*.ts",
      "docs/**/*.md"
    ],
    "exclude_patterns": [
      "**/*.test.py",
      "**/*.spec.ts",
      "**/vendor/**",
      "**/third_party/**"
    ],
    "max_file_size_kb": 500,
    "skip_binary_files": true
  }
}
```

### Distributed Processing

**Multi-Process Configuration:**

```json
{
  "distributed": {
    "enabled": true,
    "mode": "multiprocess",

    "workers": {
      "count": "auto",
      "max_count": 16,
      "per_cpu_ratio": 2
    },

    "task_distribution": {
      "strategy": "work_stealing",
      "queue_size": 1000,
      "chunk_size": 100
    },

    "coordination": {
      "lock_manager": "file_based",
      "lock_timeout_seconds": 30,
      "retry_count": 3
    }
  }
}
```

### Incremental Updates

**Smart Update Strategy:**

```json
{
  "incremental_updates": {
    "enabled": true,

    "change_detection": {
      "method": "hash",
      "granularity": "file",
      "check_interval_seconds": 60
    },

    "update_strategy": {
      "batch_updates": true,
      "batch_size": 10,
      "batch_delay_ms": 500,
      "priority_files": [
        "activeContext.md",
        "progress.md"
      ]
    },

    "validation": {
      "validate_on_change": true,
      "incremental_validation": true,
      "parallel_validation": true
    }
  }
}
```

---

## Lazy Loading Configuration

### On-Demand Loading

**Lazy Load Strategy:**

```json
{
  "lazy_loading": {
    "enabled": true,
    "mode": "on_demand",

    "strategies": {
      "immediate": {
        "files": ["projectBrief.md"],
        "sections": ["Overview", "Quick Start"]
      },

      "on_first_access": {
        "files": ["systemPatterns.md", "techContext.md"],
        "cache_after_load": true
      },

      "defer_until_needed": {
        "files": ["roadmap.md", "progress.md"],
        "load_trigger": "explicit_request"
      }
    },

    "preloading": {
      "enabled": true,
      "predict_next_access": true,
      "prefetch_related": true,
      "prefetch_transclusions": true
    }
  }
}
```

### Dependency-Based Loading

**Load Based on Dependencies:**

```json
{
  "dependency_loading": {
    "enabled": true,

    "rules": {
      "transclusions": {
        "load_on_parent_access": true,
        "depth_limit": 3,
        "parallel_loading": true
      },

      "references": {
        "load_on_reference": false,
        "cache_referenced": true
      },

      "circular_dependencies": {
        "detect": true,
        "break_strategy": "oldest_first",
        "max_depth": 5
      }
    }
  }
}
```

### Streaming Loading

**Stream Large Files:**

```json
{
  "streaming": {
    "enabled": true,
    "threshold_kb": 100,

    "strategies": {
      "chunked_loading": {
        "chunk_size_kb": 50,
        "overlap_lines": 10,
        "parallel_chunks": true
      },

      "section_streaming": {
        "load_by_section": true,
        "keep_headers": true,
        "cache_sections": true
      }
    }
  }
}
```

---

## Benchmark Interpretation

### Running Benchmarks

**Standard Benchmark Suite:**

```bash
# Run full benchmark suite
cortex run_benchmarks --suite=full --output=benchmark-results.json

# Run lightweight benchmarks (faster)
cortex run_benchmarks --suite=lightweight --iterations=100

# Run specific benchmark
cortex run_benchmarks --benchmark=file_operations

# Compare against baseline
cortex run_benchmarks --compare-baseline=v1.0.0
```

### Benchmark Results

**Sample Output:**

```json
{
  "benchmark_suite": "full",
  "timestamp": "2024-01-10T12:00:00Z",
  "duration_seconds": 123.45,
  "system_info": {
    "cpu": "Apple M1 Pro",
    "cores": 10,
    "memory_gb": 16,
    "os": "macOS 14.0"
  },
  "results": {
    "file_operations": {
      "read": {
        "avg_ms": 12.3,
        "min_ms": 8.1,
        "max_ms": 45.6,
        "p50_ms": 11.2,
        "p95_ms": 23.4,
        "p99_ms": 38.9,
        "operations_per_second": 81.3,
        "status": "pass"
      },
      "write": {
        "avg_ms": 23.4,
        "operations_per_second": 42.7,
        "status": "pass"
      }
    },
    "validation": {
      "schema": {
        "avg_ms": 45.6,
        "status": "pass"
      },
      "links": {
        "avg_ms": 123.4,
        "status": "warning",
        "notes": "Slower than target (100ms)"
      },
      "duplicates": {
        "avg_ms": 567.8,
        "status": "fail",
        "notes": "Exceeds critical threshold (500ms)"
      }
    }
  },
  "comparison": {
    "baseline": "v1.0.0",
    "improvements": [
      {
        "metric": "file_operations.read.avg_ms",
        "baseline": 18.7,
        "current": 12.3,
        "improvement_percent": 34.2
      }
    ],
    "regressions": [
      {
        "metric": "validation.duplicates.avg_ms",
        "baseline": 456.7,
        "current": 567.8,
        "regression_percent": 24.3
      }
    ]
  },
  "recommendations": [
    {
      "severity": "high",
      "component": "duplication_detector",
      "issue": "Exceeds performance budget",
      "recommendation": "Enable caching or optimize algorithm",
      "estimated_improvement": "50% faster"
    }
  ]
}
```

### Performance Regression Detection

**Automated Regression Tracking:**

```json
{
  "regression_detection": {
    "enabled": true,
    "baseline": "main",

    "thresholds": {
      "warning_percent": 10,
      "critical_percent": 25
    },

    "metrics": [
      "file_operations.read.avg_ms",
      "file_operations.write.avg_ms",
      "validation.*.avg_ms",
      "cache.hit_rate",
      "memory.peak_mb"
    ],

    "actions": {
      "on_warning": "log",
      "on_critical": "fail",
      "notify": true
    }
  }
}
```

### Benchmark CI Integration

```yaml
# .github/workflows/benchmark.yml
name: Performance Benchmarks

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install Dependencies
        run: pip install git+https://github.com/igrechuhin/cortex.git

      - name: Run Benchmarks
        run: |
          cortex run_benchmarks \
            --suite=lightweight \
            --compare-baseline=main \
            --output=benchmark-results.json

      - name: Check for Regressions
        run: |
          python scripts/check-regression.py benchmark-results.json

      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: benchmark-results.json

      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const results = JSON.parse(fs.readFileSync('benchmark-results.json'));
            const comment = generateBenchmarkComment(results);
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
```

---

## Monitoring and Profiling

### Real-Time Monitoring

**Enable Monitoring:**

```json
{
  "monitoring": {
    "enabled": true,
    "interval_seconds": 60,

    "metrics": {
      "file_operations": {
        "track_duration": true,
        "track_count": true,
        "track_errors": true
      },
      "cache": {
        "track_hit_rate": true,
        "track_size": true,
        "track_evictions": true
      },
      "memory": {
        "track_usage": true,
        "track_peak": true,
        "track_leaks": true
      },
      "cpu": {
        "track_usage": true,
        "track_per_operation": true
      }
    },

    "export": {
      "format": "prometheus",
      "endpoint": "http://localhost:9090",
      "labels": {
        "service": "cortex",
        "environment": "production"
      }
    }
  }
}
```

### Profiling Tools

**Profile Operations:**

```bash
# Profile specific operation
cortex profile \
  --operation=validate_memory_bank \
  --output=profile.json \
  --format=flamegraph

# Profile all operations for duration
cortex profile \
  --duration=300 \
  --sample-rate=100 \
  --output=profile-full.json

# Generate profiling report
cortex analyze_profile \
  --input=profile.json \
  --format=html \
  --output=profile-report.html
```

**Profiling Configuration:**

```json
{
  "profiling": {
    "enabled": false,
    "mode": "sampling",

    "sampling": {
      "rate_hz": 100,
      "include_threads": true,
      "include_native": false
    },

    "tracing": {
      "enabled": false,
      "trace_all_functions": false,
      "include_patterns": [
        "cortex.core.*",
        "cortex.validation.*"
      ]
    },

    "memory_profiling": {
      "enabled": false,
      "track_allocations": true,
      "snapshot_interval_seconds": 60
    }
  }
}
```

### Performance Dashboards

**Grafana Dashboard Configuration:**

```json
{
  "dashboard": {
    "title": "Cortex Performance",
    "panels": [
      {
        "title": "File Operations Latency",
        "type": "graph",
        "metrics": [
          "file_read_duration_ms",
          "file_write_duration_ms"
        ],
        "target": 50,
        "critical": 200
      },
      {
        "title": "Cache Hit Rate",
        "type": "gauge",
        "metrics": ["cache_hit_rate"],
        "min": 0,
        "max": 1,
        "target": 0.9
      },
      {
        "title": "Memory Usage",
        "type": "graph",
        "metrics": [
          "memory_usage_mb",
          "memory_peak_mb"
        ],
        "target": 500,
        "critical": 2000
      },
      {
        "title": "Operations Per Second",
        "type": "graph",
        "metrics": [
          "file_operations_per_second",
          "validation_operations_per_second"
        ]
      }
    ]
  }
}
```

---

## Database and Index Optimization

### Metadata Index Optimization

```json
{
  "metadata_index": {
    "backend": "sqlite",
    "path": ".memory-bank-index.db",

    "optimization": {
      "wal_mode": true,
      "cache_size_mb": 50,
      "page_size": 4096,
      "auto_vacuum": "incremental",

      "indexes": [
        {"fields": ["file_path"], "unique": true},
        {"fields": ["last_modified"], "unique": false},
        {"fields": ["content_hash"], "unique": false},
        {"fields": ["file_path", "version"], "unique": true}
      ]
    },

    "maintenance": {
      "vacuum_interval_days": 7,
      "analyze_interval_days": 1,
      "checkpoint_interval_seconds": 300
    }
  }
}
```

### Query Optimization

```sql
-- Optimize common queries
CREATE INDEX idx_file_modified ON metadata(file_path, last_modified);
CREATE INDEX idx_content_hash ON metadata(content_hash);
CREATE INDEX idx_tokens ON metadata(token_count);

-- Analyze query performance
EXPLAIN QUERY PLAN
SELECT * FROM metadata
WHERE file_path LIKE '.cursor/memory-bank/%'
  AND last_modified > datetime('now', '-7 days');

-- Optimize with covering index
CREATE INDEX idx_recent_files ON metadata(last_modified, file_path, token_count);
```

---

## Network and I/O Optimization

### Async I/O Configuration

```json
{
  "async_io": {
    "enabled": true,
    "backend": "asyncio",

    "connection_pool": {
      "size": 10,
      "max_overflow": 20,
      "timeout_seconds": 30
    },

    "buffering": {
      "read_buffer_kb": 64,
      "write_buffer_kb": 64,
      "flush_interval_ms": 100
    },

    "concurrency": {
      "max_concurrent_reads": 50,
      "max_concurrent_writes": 10,
      "semaphore_timeout_seconds": 30
    }
  }
}
```

### Batch Operations

```python
# Batch file operations for better performance
async def batch_read_files(files: list[str]) -> dict[str, str]:
    """Read multiple files concurrently."""
    async with asyncio.TaskGroup() as tg:
        tasks = {
            file: tg.create_task(read_file(file))
            for file in files
        }

    return {
        file: task.result()
        for file, task in tasks.items()
    }

# Usage
files = [
    ".cursor/memory-bank/projectBrief.md",
    ".cursor/memory-bank/systemPatterns.md",
    ".cursor/memory-bank/techContext.md"
]
contents = await batch_read_files(files)
```

---

## Memory Management

### Memory Budget Configuration

```json
{
  "memory": {
    "max_usage_mb": 1000,
    "warning_threshold_mb": 800,

    "gc": {
      "mode": "auto",
      "threshold_mb": 700,
      "aggressive_on_pressure": true
    },

    "limits": {
      "max_file_size_mb": 10,
      "max_cache_size_mb": 500,
      "max_buffer_size_mb": 100
    },

    "leak_detection": {
      "enabled": true,
      "check_interval_seconds": 300,
      "report_threshold_mb": 50
    }
  }
}
```

### Memory Profiling

```bash
# Profile memory usage
cortex profile_memory \
  --duration=300 \
  --output=memory-profile.json

# Detect memory leaks
cortex detect_leaks \
  --threshold-mb=50 \
  --output=leak-report.json
```

---

## Best Practices

### Performance Optimization Checklist

- ✅ Enable multi-level caching
- ✅ Configure token budget appropriately
- ✅ Use progressive/lazy loading for large codebases
- ✅ Enable parallel processing
- ✅ Optimize file watching (exclude unnecessary paths)
- ✅ Use incremental validation
- ✅ Configure appropriate cache TTLs
- ✅ Monitor performance metrics
- ✅ Run regular benchmarks
- ✅ Profile slow operations
- ✅ Optimize database indexes
- ✅ Use batch operations where possible

### Common Performance Issues

**Issue: High memory usage**

Solutions:
- Reduce cache size
- Enable memory limits
- Use streaming for large files
- Optimize token budget

**Issue: Slow validation**

Solutions:
- Enable caching for validation results
- Use incremental validation
- Parallelize validation tasks
- Optimize duplication detection

**Issue: Cache thrashing**

Solutions:
- Increase cache size
- Adjust TTL values
- Switch eviction strategy (LRU → LFU)
- Enable cache warming

---

## Next Steps

- Review [Advanced Patterns Guide](./advanced-patterns.md) for complex setups
- Check [Extension Development Guide](./extension-development.md) for customization
- See [Configuration Guide](../configuration.md) for detailed settings
- Read [Troubleshooting Guide](../troubleshooting.md) for common issues
