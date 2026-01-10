# Type Definitions Reference

Complete reference for TypedDict definitions, dataclasses, and enums in Cortex.

## Overview

Cortex uses strongly-typed data structures for all operations. This document covers:

- **TypedDict Classes:** Type-safe dictionary structures
- **Dataclasses:** Immutable and mutable data structures
- **Enums:** Enumeration types for constants

**Type Categories:**

| Category | Types | Purpose |
|----------|-------|---------|
| [Core Types](#core-types) | 5 | File dependencies, cache stats, access patterns |
| [Insight Types](#insight-types) | 3 | Insight data structures |
| [Pattern Types](#pattern-types) | 7 | Access patterns, usage statistics |
| [Optimization Types](#optimization-types) | 2 | Progressive loading, optimization results |
| [Refactoring Types](#refactoring-types) | 10+ | Suggestions, actions, approvals, executions |
| [Enums](#enums) | 5 | Status values, priorities, types |

---

## Core Types

### FileDependencyInfo

Typed dictionary for file dependency information.

**Module:** `cortex.core.dependency_graph`

**Definition:**

```python
class FileDependencyInfo(TypedDict):
    depends_on: list[str]
    priority: int
    category: str
```

**Fields:**

- `depends_on` (list[str]) - List of file names this file depends on
- `priority` (int) - Loading priority (0 = highest)
- `category` (str) - File category: "meta", "foundation", "context", "active", "status"

**Usage Example:**

```python
dep_info: FileDependencyInfo = {
    "depends_on": ["projectBrief.md"],
    "priority": 2,
    "category": "context"
}
```

---

### CacheStats

Statistics about cache performance.

**Module:** `cortex.core.advanced_cache`

**Definition:**

```python
class CacheStats(TypedDict):
    hits: int
    misses: int
    size: int
    evictions: int
    hit_rate: float
```

**Fields:**

- `hits` (int) - Number of cache hits
- `misses` (int) - Number of cache misses
- `size` (int) - Current cache size
- `evictions` (int) - Number of items evicted
- `hit_rate` (float) - Cache hit rate (0-1)

---

### AccessPattern

Pattern of file access behavior.

**Module:** `cortex.core.advanced_cache`

**Definition:**

```python
class AccessPattern(TypedDict):
    frequency: float
    recency: float
    priority: int
```

**Fields:**

- `frequency` (float) - Access frequency (accesses per day)
- `recency` (float) - Time since last access (days)
- `priority` (int) - Computed priority score

---

### WarmingStrategy

Cache warming strategy configuration.

**Module:** `cortex.core.cache_warming`

**Definition:**

```python
class WarmingStrategy(TypedDict):
    name: str
    files: list[str]
    preload_transclusions: bool
```

**Fields:**

- `name` (str) - Strategy name
- `files` (list[str]) - Files to warm
- `preload_transclusions` (bool) - Whether to preload transclusions

---

### CacheWarmingResult

Result of cache warming operation.

**Module:** `cortex.core.cache_warming`

**Definition:**

```python
class CacheWarmingResult(TypedDict):
    files_warmed: int
    total_tokens: int
    time_ms: float
    strategy: str
```

**Fields:**

- `files_warmed` (int) - Number of files warmed
- `total_tokens` (int) - Total tokens loaded
- `time_ms` (float) - Time taken in milliseconds
- `strategy` (str) - Strategy used

---

## Insight Types

### InsightDict

Individual insight data structure.

**Module:** `cortex.analysis.insight_types`

**Definition:**

```python
class InsightDict(TypedDict, total=False):
    id: str
    category: str
    title: str
    description: str
    impact_score: float
    severity: str
    evidence: dict[str, object]
    recommendations: list[str]
    estimated_token_savings: int
    affected_files: list[str]
```

**Fields:**

- `id` (str) - Unique insight identifier
- `category` (str) - Insight category: "usage", "organization", "quality", "optimization", "dependency"
- `title` (str) - Short insight title
- `description` (str) - Detailed description
- `impact_score` (float) - Impact score (0-1)
- `severity` (str) - Severity level: "high", "medium", "low"
- `evidence` (dict[str, object]) - Supporting evidence data
- `recommendations` (list[str]) - Recommended actions
- `estimated_token_savings` (int) - Estimated token savings if applied
- `affected_files` (list[str]) - Files affected by this insight

**Note:** `total=False` means all fields are optional.

**Usage Example:**

```python
insight: InsightDict = {
    "id": "insight-001",
    "category": "duplication",
    "title": "Duplicated content detected",
    "description": "Files A and B contain 80% similar content",
    "impact_score": 0.8,
    "severity": "high",
    "evidence": {"similarity": 0.82, "files": ["A.md", "B.md"]},
    "recommendations": ["Use transclusion to avoid duplication"],
    "estimated_token_savings": 500,
    "affected_files": ["A.md", "B.md"]
}
```

---

### SummaryDict

Summary of insights analysis.

**Module:** `cortex.analysis.insight_types`

**Definition:**

```python
class SummaryDict(TypedDict, total=False):
    status: str
    message: str
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    top_recommendations: list[dict[str, object]]
```

**Fields:**

- `status` (str) - Overall status: "healthy", "needs_attention", "critical"
- `message` (str) - Summary message
- `high_severity_count` (int) - Count of high severity insights
- `medium_severity_count` (int) - Count of medium severity insights
- `low_severity_count` (int) - Count of low severity insights
- `top_recommendations` (list[dict]) - Top prioritized recommendations

---

### InsightsResultDict

Complete insights generation result.

**Module:** `cortex.analysis.insight_types`

**Definition:**

```python
class InsightsResultDict(TypedDict):
    generated_at: str
    total_insights: int
    high_impact_count: int
    medium_impact_count: int
    low_impact_count: int
    estimated_total_token_savings: int
    insights: list[InsightDict]
    summary: SummaryDict
```

**Fields:**

- `generated_at` (str) - ISO timestamp of generation
- `total_insights` (int) - Total number of insights
- `high_impact_count` (int) - Count of high impact insights
- `medium_impact_count` (int) - Count of medium impact insights
- `low_impact_count` (int) - Count of low impact insights
- `estimated_total_token_savings` (int) - Total estimated token savings
- `insights` (list[InsightDict]) - List of insights
- `summary` (SummaryDict) - Summary information

---

## Pattern Types

### AccessRecord

Record of a file access event.

**Module:** `cortex.analysis.pattern_analyzer`

**Definition:**

```python
class AccessRecord(TypedDict):
    file_name: str
    timestamp: str
    task_context: str | None
```

**Fields:**

- `file_name` (str) - Name of file accessed
- `timestamp` (str) - ISO timestamp of access
- `task_context` (str | None) - Optional task context

---

### FileStatsEntry

File access statistics entry.

**Module:** `cortex.analysis.pattern_analyzer`

**Definition:**

```python
class FileStatsEntry(TypedDict, total=False):
    file_name: str
    read_count: int
    last_access: str
    frequency: float
    days_since_access: int
```

**Fields:**

- `file_name` (str) - Name of file
- `read_count` (int) - Total read count
- `last_access` (str) - ISO timestamp of last access
- `frequency` (float) - Access frequency (per day)
- `days_since_access` (int) - Days since last access

---

### TaskPatternEntry

Task-based access pattern entry.

**Module:** `cortex.analysis.pattern_analyzer`

**Definition:**

```python
class TaskPatternEntry(TypedDict, total=False):
    task_type: str
    files: list[str]
    frequency: int
    avg_file_count: float
```

**Fields:**

- `task_type` (str) - Type of task
- `files` (list[str]) - Files accessed for this task
- `frequency` (int) - How often this pattern occurs
- `avg_file_count` (float) - Average number of files accessed

---

### UnusedFileEntry

Information about an unused file.

**Module:** `cortex.analysis.pattern_analyzer`

**Definition:**

```python
class UnusedFileEntry(TypedDict):
    file_name: str
    last_access: str
    days_since_access: int
    size_bytes: int
    token_count: int
```

**Fields:**

- `file_name` (str) - Name of file
- `last_access` (str) - ISO timestamp of last access
- `days_since_access` (int) - Days since last access
- `size_bytes` (int) - File size in bytes
- `token_count` (int) - Token count

---

### TaskPatternResult

Result of task pattern analysis.

**Module:** `cortex.analysis.pattern_analyzer`

**Definition:**

```python
class TaskPatternResult(TypedDict):
    patterns: list[TaskPatternEntry]
    total_tasks: int
```

**Fields:**

- `patterns` (list[TaskPatternEntry]) - Detected patterns
- `total_tasks` (int) - Total number of tasks analyzed

---

### TemporalPatternsResult

Result of temporal pattern analysis.

**Module:** `cortex.analysis.pattern_analyzer`

**Definition:**

```python
class TemporalPatternsResult(TypedDict):
    hourly: dict[str, int]
    daily: dict[str, int]
    weekly: dict[str, int]
```

**Fields:**

- `hourly` (dict[str, int]) - Access counts by hour
- `daily` (dict[str, int]) - Access counts by day
- `weekly` (dict[str, int]) - Access counts by week

---

### AccessLog

Complete access log entry.

**Module:** `cortex.analysis.pattern_analyzer`

**Definition:**

```python
class AccessLog(TypedDict):
    file_name: str
    timestamp: str
    task_context: str | None
    session_id: str
```

**Fields:**

- `file_name` (str) - File accessed
- `timestamp` (str) - ISO timestamp
- `task_context` (str | None) - Optional task context
- `session_id` (str) - Session identifier

---

## Optimization Types

### LoadedFileContent

Content of a progressively loaded file.

**Module:** `cortex.optimization.progressive_loader`

**Definition:**

```python
class LoadedFileContent(TypedDict):
    file_name: str
    content: str
    tokens: int
    summarized: bool
```

**Fields:**

- `file_name` (str) - Name of file
- `content` (str) - File content (full or summarized)
- `tokens` (int) - Token count of content
- `summarized` (bool) - Whether content was summarized

---

### LoadingOrder

Progressive loading order dataclass.

**Module:** `cortex.optimization.progressive_loader`

**Definition:**

```python
@dataclass
class LoadingOrder:
    """Represents an ordered list of files to load."""

    files: list[str]
    strategy: str  # "priority", "dependency", "relevance"
    metadata: dict[str, object]
```

**Fields:**

- `files` (list[str]) - Ordered list of file names
- `strategy` (str) - Loading strategy used
- `metadata` (dict[str, object]) - Additional metadata

---

## Refactoring Types

### RefactoringType

Enumeration of refactoring types.

**Module:** `cortex.refactoring.refactoring_engine`

**Definition:**

```python
class RefactoringType(Enum):
    CONSOLIDATION = "consolidation"
    SPLIT = "split"
    REORGANIZATION = "reorganization"
    TRANSCLUSION = "transclusion"
    RENAME = "rename"
    MERGE = "merge"
```

**Values:**

- `CONSOLIDATION` - Consolidate duplicated content
- `SPLIT` - Split large file into smaller files
- `REORGANIZATION` - Reorganize file structure
- `TRANSCLUSION` - Convert duplication to transclusion
- `RENAME` - Rename file for consistency
- `MERGE` - Merge related files

---

### RefactoringPriority

Enumeration of refactoring priorities.

**Module:** `cortex.refactoring.refactoring_engine`

**Definition:**

```python
class RefactoringPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"
```

**Values:**

- `CRITICAL` - Significant issues, high impact (must address)
- `HIGH` - Important improvements (should address)
- `MEDIUM` - Moderate improvements (nice to have)
- `LOW` - Minor improvements (consider)
- `OPTIONAL` - Minor optimizations (optional)

---

### RefactoringAction

Individual action within a refactoring.

**Module:** `cortex.refactoring.refactoring_engine`

**Definition:**

```python
@dataclass
class RefactoringAction:
    action_type: str  # "move", "create", "delete", "modify", "rename"
    target_file: str
    description: str
    details: dict[str, object] = field(default_factory=dict)
```

**Fields:**

- `action_type` (str) - Type of action: "move", "create", "delete", "modify", "rename"
- `target_file` (str) - File being acted upon
- `description` (str) - Human-readable description
- `details` (dict[str, object]) - Additional action details

**Usage Example:**

```python
action = RefactoringAction(
    action_type="create",
    target_file="shared/glossary.md",
    description="Extract glossary terms into shared file",
    details={
        "source_files": ["projectBrief.md", "techContext.md"],
        "content": "# Glossary\n..."
    }
)
```

---

### RefactoringSuggestion

Complete refactoring suggestion.

**Module:** `cortex.refactoring.refactoring_engine`

**Definition:**

```python
@dataclass
class RefactoringSuggestion:
    suggestion_id: str
    refactoring_type: RefactoringType
    priority: RefactoringPriority
    title: str
    description: str
    reasoning: str
    affected_files: list[str]
    actions: list[RefactoringAction]
    estimated_impact: dict[str, object]
    confidence_score: float  # 0-1
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary."""
        ...
```

**Fields:**

- `suggestion_id` (str) - Unique suggestion identifier (e.g., "REF-CON-20240110-001")
- `refactoring_type` (RefactoringType) - Type of refactoring
- `priority` (RefactoringPriority) - Priority level
- `title` (str) - Short title
- `description` (str) - Detailed description
- `reasoning` (str) - Explanation of why this refactoring is suggested
- `affected_files` (list[str]) - Files that will be affected
- `actions` (list[RefactoringAction]) - Specific actions to execute
- `estimated_impact` (dict[str, object]) - Estimated impact (tokens saved, etc.)
- `confidence_score` (float) - Confidence score (0-1)
- `metadata` (dict[str, object]) - Additional metadata
- `created_at` (str) - ISO timestamp

**Usage Example:**

```python
suggestion = RefactoringSuggestion(
    suggestion_id="REF-CON-20240110120000-001",
    refactoring_type=RefactoringType.CONSOLIDATION,
    priority=RefactoringPriority.HIGH,
    title="Consolidate duplicated glossary terms",
    description="Multiple files contain duplicate glossary definitions",
    reasoning="Reduces duplication, improves maintainability",
    affected_files=["projectBrief.md", "techContext.md"],
    actions=[...],
    estimated_impact={
        "token_savings": 500,
        "files_affected": 2,
        "maintenance_improvement": "high"
    },
    confidence_score=0.85
)
```

---

### ApprovalStatus

Enumeration of approval statuses.

**Module:** `cortex.refactoring.approval_manager`

**Definition:**

```python
class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    APPLIED = "applied"
```

**Values:**

- `PENDING` - Awaiting approval
- `APPROVED` - Approved for execution
- `REJECTED` - Rejected by user
- `EXPIRED` - Approval expired
- `APPLIED` - Successfully applied

---

### Approval

Approval record dataclass.

**Module:** `cortex.refactoring.approval_manager`

**Definition:**

```python
@dataclass
class Approval:
    approval_id: str
    suggestion_id: str
    suggestion_type: str
    status: str
    created_at: str
    approved_at: str | None = None
    applied_at: str | None = None
    user_comment: str | None = None
    auto_apply: bool = False
    execution_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary."""
        ...
```

**Fields:**

- `approval_id` (str) - Unique approval identifier
- `suggestion_id` (str) - Associated suggestion ID
- `suggestion_type` (str) - Type of suggestion
- `status` (str) - Current status (from ApprovalStatus)
- `created_at` (str) - ISO timestamp of creation
- `approved_at` (str | None) - ISO timestamp of approval
- `applied_at` (str | None) - ISO timestamp of application
- `user_comment` (str | None) - Optional user comment
- `auto_apply` (bool) - Whether to auto-apply on approval
- `execution_id` (str | None) - Associated execution ID

---

### ApprovalPreference

User preference for auto-approvals.

**Module:** `cortex.refactoring.approval_manager`

**Definition:**

```python
@dataclass
class ApprovalPreference:
    pattern_type: str
    conditions: dict[str, object]
    auto_approve: bool
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary."""
        ...
```

**Fields:**

- `pattern_type` (str) - Pattern type: "consolidation", "split", etc.
- `conditions` (dict[str, object]) - Conditions for auto-approval
- `auto_approve` (bool) - Whether to auto-approve
- `created_at` (str) - ISO timestamp

**Usage Example:**

```python
pref = ApprovalPreference(
    pattern_type="consolidation",
    conditions={
        "min_confidence": 0.8,
        "max_files_affected": 3
    },
    auto_approve=True,
    created_at=datetime.now().isoformat()
)
```

---

### RefactoringStatus

Enumeration of refactoring execution statuses.

**Module:** `cortex.refactoring.refactoring_executor`

**Definition:**

```python
class RefactoringStatus(Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
```

**Values:**

- `PENDING` - Awaiting execution
- `VALIDATING` - Pre-execution validation in progress
- `EXECUTING` - Execution in progress
- `COMPLETED` - Successfully completed
- `FAILED` - Execution failed
- `ROLLED_BACK` - Changes rolled back

---

### RefactoringExecution

Execution record dataclass.

**Module:** `cortex.refactoring.refactoring_executor`

**Definition:**

```python
@dataclass
class RefactoringExecution:
    execution_id: str
    suggestion_id: str
    approval_id: str
    operations: list[RefactoringOperation]
    status: str
    created_at: str
    completed_at: str | None = None
    snapshot_id: str | None = None
    validation_results: dict[str, object] | None = None
    actual_impact: dict[str, object] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary."""
        ...
```

**Fields:**

- `execution_id` (str) - Unique execution identifier
- `suggestion_id` (str) - Associated suggestion ID
- `approval_id` (str) - Associated approval ID
- `operations` (list[RefactoringOperation]) - Operations executed
- `status` (str) - Current status (from RefactoringStatus)
- `created_at` (str) - ISO timestamp of creation
- `completed_at` (str | None) - ISO timestamp of completion
- `snapshot_id` (str | None) - Version snapshot ID (for rollback)
- `validation_results` (dict[str, object] | None) - Validation results
- `actual_impact` (dict[str, object] | None) - Measured impact after execution
- `error` (str | None) - Error message if failed

---

### RefactoringOperation

Individual operation within refactoring execution.

**Module:** `cortex.refactoring.execution_validator`

**Definition:**

```python
@dataclass
class RefactoringOperation:
    operation_type: str  # "create", "modify", "delete", "move", "rename"
    target_file: str
    source_file: str | None = None
    content: str | None = None
    backup_path: str | None = None
```

**Fields:**

- `operation_type` (str) - Type of operation
- `target_file` (str) - Target file path
- `source_file` (str | None) - Source file (for move/rename)
- `content` (str | None) - New content (for create/modify)
- `backup_path` (str | None) - Backup file path (for rollback)

---

### SplitPoint

Suggested file split point.

**Module:** `cortex.refactoring.split_recommender`

**Definition:**

```python
@dataclass
class SplitPoint:
    line_number: int
    section_title: str
    reason: str
    confidence: float
```

**Fields:**

- `line_number` (int) - Line number to split at
- `section_title` (str) - Section title at split point
- `reason` (str) - Reason for split
- `confidence` (float) - Confidence score (0-1)

---

### SplitSuggestion

File split suggestion.

**Module:** `cortex.refactoring.split_recommender`

**Definition:**

```python
@dataclass
class SplitSuggestion:
    file_path: str
    reason: str
    split_points: list[SplitPoint]
    estimated_impact: dict[str, object]
    confidence: float
```

**Fields:**

- `file_path` (str) - File to split
- `reason` (str) - Reason for splitting
- `split_points` (list[SplitPoint]) - Suggested split points
- `estimated_impact` (dict[str, object]) - Estimated impact
- `confidence` (float) - Overall confidence (0-1)

---

### ReorganizationMove

File move operation in reorganization.

**Module:** `cortex.refactoring.reorganization_planner`

**Definition:**

```python
@dataclass
class ReorganizationMove:
    from_path: str
    to_path: str
    reason: str
    affects_links: list[str]
```

**Fields:**

- `from_path` (str) - Current file path
- `to_path` (str) - New file path
- `reason` (str) - Reason for move
- `affects_links` (list[str]) - Files with links that need updating

---

## Enums

### All Enums Summary

| Enum | Module | Values |
|------|--------|--------|
| `RefactoringType` | refactoring_engine | CONSOLIDATION, SPLIT, REORGANIZATION, TRANSCLUSION, RENAME, MERGE |
| `RefactoringPriority` | refactoring_engine | CRITICAL, HIGH, MEDIUM, LOW, OPTIONAL |
| `ApprovalStatus` | approval_manager | PENDING, APPROVED, REJECTED, EXPIRED, APPLIED |
| `RefactoringStatus` | refactoring_executor | PENDING, VALIDATING, EXECUTING, COMPLETED, FAILED, ROLLED_BACK |

---

## Type Safety Guidelines

### Using TypedDict

```python
from typing import TypedDict

class MyType(TypedDict):
    field1: str
    field2: int

# Usage
data: MyType = {"field1": "value", "field2": 42}

# Type checking will catch errors
data["field3"] = "error"  # mypy error: unexpected key
```

### Using Dataclasses

```python
from dataclasses import dataclass

@dataclass
class MyClass:
    field1: str
    field2: int = 0  # Default value

# Usage
obj = MyClass(field1="value")
print(obj.field2)  # 0 (default)

# Immutable variant
@dataclass(frozen=True)
class ImmutableClass:
    field: str
```

### Using Enums

```python
from enum import Enum

class Status(Enum):
    PENDING = "pending"
    COMPLETED = "completed"

# Usage
status = Status.PENDING
if status == Status.PENDING:
    print(status.value)  # "pending"
```

---

## Common Patterns

### Optional Fields with total=False

```python
class OptionalType(TypedDict, total=False):
    optional_field: str
    another_optional: int

# Valid - no fields required
data: OptionalType = {}

# Also valid
data: OptionalType = {"optional_field": "value"}
```

### Nested Types

```python
class InnerType(TypedDict):
    value: str

class OuterType(TypedDict):
    inner: InnerType
    items: list[InnerType]

# Usage
data: OuterType = {
    "inner": {"value": "test"},
    "items": [{"value": "item1"}, {"value": "item2"}]
}
```

### Dataclass with Factory Defaults

```python
from dataclasses import dataclass, field

@dataclass
class MyClass:
    items: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

# Each instance gets fresh collections
obj1 = MyClass()
obj2 = MyClass()
obj1.items.append("test")
print(obj2.items)  # [] (not shared)
```

---

## See Also

- [Protocol Reference](./protocols.md) - Protocol interface definitions
- [Manager Reference](./managers.md) - Manager class implementations
- [MCP Tools Reference](./tools.md) - MCP tool interfaces
- [Exceptions Reference](./exceptions.md) - Exception hierarchy
