# Manager Classes Reference

Complete reference for all manager classes in Cortex.

## Overview

Manager classes are the core implementations providing Memory Bank functionality. They implement the Protocol interfaces and coordinate file operations, validation, optimization, and refactoring.

**Manager Categories:**

| Category | Managers | Purpose |
|----------|----------|---------|
| [Foundation](#foundation-managers) | 6 | File I/O, metadata, tokens, dependencies, versions, migration |
| [Linking](#linking-managers) | 3 | Link parsing, transclusion, validation |
| [Validation](#validation-managers) | 3 | Schema validation, duplication detection, quality metrics |
| [Optimization](#optimization-managers) | 4 | Context optimization, relevance scoring, loading, summarization |
| [Analysis](#analysis-managers) | 3 | Pattern analysis, structure analysis, insights |
| [Refactoring](#refactoring-managers) | 7 | Suggestions, consolidation, splitting, reorganization, execution |
| [Rules](#rules-managers) | 1 | Shared rules management |
| [Structure](#structure-managers) | 1 | Project structure management |

---

## Foundation Managers

### FileSystemManager

Manages file I/O operations with safety features including locking, conflict detection, and markdown parsing.

**Module:** `cortex.core.file_system`

**Implements:** `FileSystemProtocol`

**Constructor:**

```python
def __init__(self, project_root: Path)
```

**Parameters:**
- `project_root` (Path) - Root directory of project for path validation

**Attributes:**
- `project_root` (Path) - Resolved project root path
- `memory_bank_dir` (Path) - Path to memory-bank/ directory
- `lock_timeout` (int) - Seconds to wait for file locks (default: 5)
- `rate_limiter` (RateLimiter) - Rate limiter for file operations

**Key Methods:**

#### validate_path

```python
def validate_path(self, file_path: Path) -> bool
```

Validate path is within project root (prevents directory traversal).

#### validate_file_name

```python
def validate_file_name(self, file_name: str) -> str
```

Validate file name for security (no path traversal characters, invalid chars).

**Raises:** `ValueError` if file name is invalid

#### construct_safe_path

```python
def construct_safe_path(self, base_dir: Path, file_name: str) -> Path
```

Construct safe file path by validating file name and base directory.

**Raises:**
- `ValueError` - Invalid file name or path
- `PermissionError` - Path outside project root

#### read_file

```python
async def read_file(self, file_path: Path) -> tuple[str, str]
```

Read file with automatic locking and return (content, hash).

**Rate Limited:** Yes (default: 10 ops/second)

**Raises:**
- `FileNotFoundError` - File doesn't exist
- `FileLockTimeoutError` - Lock timeout exceeded
- `MemoryBankError` - Other I/O errors

#### write_file

```python
async def write_file(
    self,
    file_path: Path,
    content: str,
    expected_hash: str | None = None,
    create_version: bool = True,
) -> str
```

Write file with optional conflict detection and automatic versioning.

**Conflict Detection:** If `expected_hash` provided, verifies current content hash matches before writing.

**Versioning:** If `create_version=True` (default), creates snapshot before writing.

**Returns:** New content hash

**Raises:**
- `FileConflictError` - Hash mismatch (concurrent modification detected)
- `GitConflictError` - Git conflict markers detected in content

#### compute_hash

```python
def compute_hash(self, content: str) -> str
```

Compute SHA-256 hash of content.

#### parse_sections

```python
def parse_sections(self, content: str) -> list[dict[str, str | int]]
```

Parse markdown headers into sections.

**Returns:** List of dicts with `title`, `level`, `start_line`, `end_line`

#### file_exists

```python
async def file_exists(self, file_path: Path) -> bool
```

Check if file exists.

#### cleanup_locks

```python
async def cleanup_locks(self)
```

Clean up stale lock files (call during shutdown).

**Design Decisions:**

- **File Locking:** Simple file-based locking for cross-platform compatibility
- **Conflict Detection:** Hash-based to detect concurrent modifications
- **Rate Limiting:** Prevents resource exhaustion from rapid file operations

**Usage Example:**

```python
from pathlib import Path
from cortex.core.file_system import FileSystemManager

fs = FileSystemManager(Path("/project"))

# Read with locking
content, hash = await fs.read_file(Path("memory-bank/projectBrief.md"))

# Write with conflict detection
new_content = content + "\n## New Section"
new_hash = await fs.write_file(
    Path("memory-bank/projectBrief.md"),
    new_content,
    expected_hash=hash,
    create_version=True
)
```

---

### MetadataIndex

Manages metadata index (.memory-bank-index) with JSON storage and corruption recovery.

**Module:** `cortex.core.metadata_index`

**Implements:** `MetadataIndexProtocol`

**Constructor:**

```python
def __init__(self, project_root: Path)
```

**Parameters:**
- `project_root` (Path) - Root directory of project

**Attributes:**
- `project_root` (Path) - Project root path
- `index_path` (Path) - Path to .memory-bank-index file
- `memory_bank_dir` (Path) - Path to memory-bank/ directory
- `SCHEMA_VERSION` (str) - Index schema version ("1.0.0")

**Key Methods:**

#### load

```python
async def load(self) -> dict[str, object]
```

Load index from disk with automatic corruption recovery.

**Recovery:** If corrupted, attempts to rebuild from markdown files.

**Returns:** Index data dictionary

#### save

```python
async def save(self)
```

Save index to disk using atomic write (write to .tmp, then rename).

#### update_file_metadata

```python
async def update_file_metadata(
    self,
    file_name: str,
    path: Path,
    exists: bool,
    size_bytes: int,
    token_count: int,
    content_hash: str,
    sections: list[dict[str, str | int]] | None = None,
    links: list[dict[str, str]] | None = None,
    transclusions: list[str] | None = None,
)
```

Update metadata for a file.

**Auto-Updates:** Updates `last_modified` timestamp automatically.

#### get_file_metadata

```python
async def get_file_metadata(self, file_name: str) -> dict[str, object] | None
```

Get metadata for specific file.

#### get_all_files_metadata

```python
async def get_all_files_metadata(self) -> dict[str, dict[str, object]]
```

Get metadata for all files.

#### list_all_files

```python
async def list_all_files(self) -> list[str]
```

Get list of all file names in index.

#### increment_read_count

```python
async def increment_read_count(self, file_name: str)
```

Increment read counter and update last_access timestamp.

**Additional Methods:**

- `create_empty_index()` - Create empty index structure
- `validate_schema(data)` - Validate index schema
- `_recover_from_corruption(error_msg)` - Attempt index recovery

**Index Structure:**

```python
{
    "version": "1.0.0",
    "last_updated": "2024-01-10T12:00:00",
    "files": {
        "projectBrief.md": {
            "path": "/full/path/to/file.md",
            "exists": True,
            "size_bytes": 1234,
            "token_count": 500,
            "content_hash": "abc123...",
            "sections": [{"title": "...", "level": 1, ...}],
            "links": [{"text": "...", "target": "...", ...}],
            "transclusions": ["path/to/file.md"],
            "read_count": 5,
            "last_access": "2024-01-10T11:00:00",
            "last_modified": "2024-01-09T10:00:00"
        }
    }
}
```

**Design Decisions:**

- **JSON Storage:** Human-readable, easy debugging
- **Atomic Writes:** Prevents corruption during write
- **Auto-Recovery:** Rebuilds from files if corrupted

---

### TokenCounter

Accurate token counting using tiktoken library with graceful degradation.

**Module:** `cortex.core.token_counter`

**Implements:** `TokenCounterProtocol`

**Constructor:**

```python
def __init__(self, model: str = "cl100k_base")
```

**Parameters:**
- `model` (str) - Tiktoken model name:
  - `"cl100k_base"` - GPT-4, GPT-3.5-turbo, text-embedding-ada-002
  - `"p50k_base"` - Codex models
  - `"o200k_base"` - GPT-4o models

**Attributes:**
- `model` (str) - Tiktoken model name
- `encoding_impl` (object | None) - Lazy-loaded encoding
- `_cache` (dict[str, int]) - Token count cache
- `_tiktoken_available` (bool) - Whether tiktoken library is available

**Key Methods:**

#### count_tokens

```python
def count_tokens(self, text: str | None) -> int
```

Count tokens in text.

**Fallback:** If tiktoken unavailable, uses word-based estimation (~1 token per 4 characters).

**Raises:** `TypeError` if text is None

#### count_tokens_with_cache

```python
def count_tokens_with_cache(self, text: str, content_hash: str) -> int
```

Count tokens with caching by content hash.

**Cache Key:** Uses content hash to avoid redundant tokenization.

#### count_tokens_in_file

```python
async def count_tokens_in_file(self, file_path: Path) -> int
```

Count tokens in a file.

**Additional Methods:**

- `_check_tiktoken_available()` - Check if tiktoken is installed
- `_estimate_tokens_by_words(text)` - Fallback estimation

**Design Decisions:**

- **Lazy Loading:** Encoding loaded on first use to avoid startup delay
- **Graceful Degradation:** Falls back to estimation if tiktoken unavailable
- **Caching:** Prevents redundant tokenization for unchanged content

**Usage Example:**

```python
from cortex.core.token_counter import TokenCounter

counter = TokenCounter(model="cl100k_base")

# Simple counting
tokens = counter.count_tokens("This is example text.")

# With caching
content, hash = await fs.read_file(path)
tokens = counter.count_tokens_with_cache(content, hash)

# File counting
tokens = await counter.count_tokens_in_file(Path("memory-bank/projectBrief.md"))
```

---

### DependencyGraph

Manages file dependency relationships and computes optimal loading order.

**Module:** `cortex.core.dependency_graph`

**Implements:** `DependencyGraphProtocol`

**Constructor:**

```python
def __init__(self)
```

**Attributes:**
- `static_deps` (dict) - Static dependency relationships from templates
- `dynamic_deps` (dict) - Dynamic dependencies from markdown links
- `link_types` (dict) - Link type tracking ("reference" vs "transclusion")

**Static Dependencies:**

```python
STATIC_DEPENDENCIES = {
    "memorybankinstructions.md": {"depends_on": [], "priority": 0, "category": "meta"},
    "projectBrief.md": {"depends_on": [], "priority": 1, "category": "foundation"},
    "productContext.md": {"depends_on": ["projectBrief.md"], "priority": 2, ...},
    "systemPatterns.md": {"depends_on": ["projectBrief.md"], "priority": 2, ...},
    "techContext.md": {"depends_on": ["projectBrief.md"], "priority": 2, ...},
    "activeContext.md": {"depends_on": ["productContext.md", ...], "priority": 3, ...},
    "progress.md": {"depends_on": ["activeContext.md"], "priority": 4, ...},
}
```

**Key Methods:**

#### compute_loading_order

```python
def compute_loading_order(self, files: list[str] | None = None) -> list[str]
```

Compute optimal loading order using topological sort.

**Algorithm:**
1. Attempts topological sort if dynamic dependencies exist
2. Falls back to priority-based sort if topological sort fails
3. Breaks ties alphabetically for stability

**Returns:** Files ordered with dependencies first

#### get_dependencies

```python
def get_dependencies(self, file_name: str) -> list[str]
```

Get immediate dependencies (combines static and dynamic).

#### get_dependents

```python
def get_dependents(self, file_name: str) -> list[str]
```

Get files that depend on this file (reverse dependencies).

#### add_dynamic_dependency

```python
def add_dynamic_dependency(self, from_file: str, to_file: str)
```

Add runtime-discovered dependency.

#### has_circular_dependency

```python
def has_circular_dependency(self) -> bool
```

Check if graph has cycles.

#### detect_cycles

```python
def detect_cycles(self) -> list[list[str]]
```

Detect all circular dependency chains using DFS.

#### to_dict

```python
def to_dict(self) -> dict[str, object]
```

Export graph to dictionary format.

#### build_from_links

```python
async def build_from_links(
    self,
    file_system: FileSystemProtocol,
    link_parser: object,
    memory_bank_path: Path,
)
```

Build dynamic dependencies by scanning file links.

**Additional Methods:**

- `get_transitive_dependencies(file_name, max_depth)` - Get all dependencies recursively
- `get_category(file_name)` - Get file category from static deps
- `get_priority(file_name)` - Get file priority

**Design Decisions:**

- **Static + Dynamic:** Combines template structure with discovered links
- **Topological Sort:** Ensures dependencies loaded before dependents
- **Fallback Sort:** Priority-based sort if topological sort fails (handles cycles)

---

### VersionManager

Manages version history with snapshot storage and rollback capabilities.

**Module:** `cortex.core.version_manager`

**Implements:** `VersionManagerProtocol`

**Constructor:**

```python
def __init__(self, project_root: Path, keep_versions: int = 10)
```

**Parameters:**
- `project_root` (Path) - Root directory of project
- `keep_versions` (int) - Number of versions to keep per file (default: 10)

**Attributes:**
- `project_root` (Path) - Project root path
- `history_dir` (Path) - Path to .memory-bank-history/ directory
- `keep_versions` (int) - Version retention limit

**Key Methods:**

#### create_snapshot

```python
async def create_snapshot(
    self,
    file_path: Path,
    version: int,
    content: str,
    size_bytes: int,
    token_count: int,
    content_hash: str,
    change_type: str = "modified",
    changed_sections: list[str] | None = None,
    change_description: str | None = None,
) -> dict[str, object]
```

Create version snapshot.

**Parameters:**
- `change_type` (str) - "created", "modified", or "rollback"
- `changed_sections` (list | None) - Section headings that changed
- `change_description` (str | None) - Optional change description

**Returns:** Version metadata dictionary

**Side Effect:** Calls `prune_versions()` to maintain retention limit

#### get_snapshot_content

```python
async def get_snapshot_content(self, snapshot_path: Path) -> str
```

Read content from version snapshot.

#### rollback_to_version

```python
async def rollback_to_version(
    self,
    file_name: str,
    version_history: list[dict[str, object]],
    target_version: int,
) -> dict[str, object] | None
```

Rollback file to specific version.

**Returns:** Version metadata of target version, or None if not found

#### prune_versions

```python
async def prune_versions(self, file_name: str)
```

Remove old versions beyond retention limit.

**Retention:** Keeps most recent `keep_versions` snapshots

**Additional Methods:**

- `_write_snapshot_file(file_path, version, content)` - Write snapshot to disk
- `_build_version_metadata(...)` - Build version metadata dict

**Snapshot File Naming:**

```
.memory-bank-history/
  projectBrief_v1.md
  projectBrief_v2.md
  activeContext_v1.md
  activeContext_v2.md
```

**Version Metadata Structure:**

```python
{
    "version": 2,
    "timestamp": "2024-01-10T12:00:00",
    "content_hash": "abc123...",
    "size_bytes": 1234,
    "token_count": 500,
    "change_type": "modified",
    "snapshot_path": ".memory-bank-history/projectBrief_v2.md",
    "changed_sections": ["## Overview", "## Goals"],
    "change_description": "Updated project goals"
}
```

**Design Decisions:**

- **Full Snapshots:** Stores complete content (not diffs) for simplicity
- **Automatic Pruning:** Maintains retention limit to prevent disk bloat
- **Rich Metadata:** Tracks change type, sections, descriptions for auditability

---

### MigrationManager

Handles automatic migration between Memory Bank schema versions.

**Module:** `cortex.core.migration`

**Constructor:**

```python
def __init__(
    self,
    project_root: Path,
    file_system: FileSystemProtocol,
    metadata_index: MetadataIndexProtocol,
)
```

**Parameters:**
- `project_root` (Path) - Project root directory
- `file_system` (FileSystemProtocol) - File system manager
- `metadata_index` (MetadataIndexProtocol) - Metadata index

**Attributes:**
- `project_root` (Path) - Project root path
- `memory_bank_dir` (Path) - Memory bank directory path
- `file_system` (FileSystemProtocol) - File system manager
- `metadata_index` (MetadataIndexProtocol) - Metadata index
- `CURRENT_VERSION` (str) - Current schema version ("1.0.0")

**Key Methods:**

#### check_migration_needed

```python
async def check_migration_needed(self) -> dict[str, object]
```

Check if migration is needed.

**Returns:** Migration status dictionary:
```python
{
    "needs_migration": bool,
    "current_version": str,
    "target_version": str,
    "detected_format": str,
    "files_to_migrate": list[str]
}
```

#### auto_migrate

```python
async def auto_migrate(self) -> dict[str, object]
```

Automatically migrate to current version.

**Returns:** Migration result dictionary:
```python
{
    "migrated": bool,
    "from_version": str,
    "to_version": str,
    "files_migrated": list[str],
    "backup_created": bool
}
```

**Additional Methods:**

- `_detect_format()` - Detect current format version
- `_migrate_legacy_format()` - Migrate from legacy format
- `_create_backup()` - Create backup before migration

**Design Decisions:**

- **Automatic Detection:** Detects format from file structure
- **Backup Creation:** Creates backup before migration
- **Idempotent:** Safe to run multiple times

---

### FileWatcher

Watches Memory Bank directory for external file changes.

**Module:** `cortex.core.file_watcher`

**Constructor:**

```python
def __init__(
    self,
    memory_bank_dir: Path,
    metadata_index: MetadataIndexProtocol,
    poll_interval: float = 2.0,
)
```

**Parameters:**
- `memory_bank_dir` (Path) - Memory bank directory to watch
- `metadata_index` (MetadataIndexProtocol) - Metadata index
- `poll_interval` (float) - Seconds between checks (default: 2.0)

**Attributes:**
- `memory_bank_dir` (Path) - Directory being watched
- `metadata_index` (MetadataIndexProtocol) - Metadata index
- `poll_interval` (float) - Polling interval
- `running` (bool) - Whether watcher is running
- `_watch_task` (Task | None) - Background watch task

**Key Methods:**

#### start

```python
async def start(self)
```

Start watching for changes (spawns background task).

#### stop

```python
async def stop(self)
```

Stop watching (cancels background task).

#### detect_external_changes

```python
async def detect_external_changes(self) -> list[dict[str, object]]
```

Detect files modified externally (hash mismatch with index).

**Returns:** List of changed files:
```python
[
    {
        "file_name": "projectBrief.md",
        "current_hash": "abc123...",
        "stored_hash": "def456...",
        "action": "refresh_recommended"
    }
]
```

**Additional Methods:**

- `_watch_loop()` - Background polling loop

**Design Decisions:**

- **Polling-Based:** Simple cross-platform approach
- **Hash Comparison:** Detects changes by comparing file hashes
- **Non-Intrusive:** Only detects changes, doesn't auto-reload

---

## Linking Managers

### LinkParser

Parses markdown links and transclusion syntax from content.

**Module:** `cortex.linking.link_parser`

**Implements:** `LinkParserProtocol`

**Constructor:**

```python
def __init__(self)
```

**Key Methods:**

#### parse_markdown_links

```python
def parse_markdown_links(self, content: str) -> list[dict[str, str]]
```

Parse markdown `[text](target)` links.

**Returns:** List of link dictionaries with `text`, `target`, `line_number`

**Patterns Matched:**
- Standard: `[text](target)`
- Reference: `[text][ref]`
- Inline: `[text](target "title")`

#### parse_transclusions

```python
def parse_transclusions(self, content: str) -> list[dict[str, str]]
```

Parse `{{include:path}}` transclusion syntax.

**Returns:** List of transclusion dictionaries with `target`, `line_number`

**Additional Methods:**

- `_extract_line_number(content, match)` - Calculate line number for match

**Design Decisions:**

- **Regex-Based:** Fast and sufficient for markdown parsing
- **Line Numbers:** Enables precise error reporting

---

### TransclusionEngine

Resolves transclusion syntax by recursively including content.

**Module:** `cortex.linking.transclusion_engine`

**Implements:** `TransclusionEngineProtocol`

**Constructor:**

```python
def __init__(
    self,
    file_system: FileSystemProtocol,
    link_parser: LinkParserProtocol,
    memory_bank_dir: Path,
    max_depth: int = 10,
)
```

**Parameters:**
- `file_system` (FileSystemProtocol) - File system manager
- `link_parser` (LinkParserProtocol) - Link parser
- `memory_bank_dir` (Path) - Memory bank directory
- `max_depth` (int) - Maximum recursion depth (default: 10)

**Attributes:**
- `file_system` (FileSystemProtocol) - File system
- `link_parser` (LinkParserProtocol) - Link parser
- `memory_bank_dir` (Path) - Memory bank directory
- `max_depth` (int) - Max recursion depth
- `_cache` (dict) - Resolution cache
- `_resolution_stack` (list) - Circular dependency detection

**Key Methods:**

#### resolve_file

```python
async def resolve_file(self, file_path: Path, max_depth: int | None = None) -> str
```

Resolve all transclusions in file recursively.

**Cycle Detection:** Tracks resolution stack to detect circular dependencies.

**Caching:** Caches resolved content for performance.

**Raises:**
- `CircularDependencyError` - Circular transclusion detected
- `FileNotFoundError` - Target file not found
- `ValueError` - Max depth exceeded

#### clear_cache

```python
def clear_cache(self)
```

Clear resolution cache.

**Additional Methods:**

- `_resolve_transclusions(content, base_path, depth)` - Recursive resolution
- `_resolve_single_transclusion(target, base_path, depth)` - Resolve one transclusion

**Design Decisions:**

- **Recursive Resolution:** Supports nested transclusions
- **Cycle Detection:** Prevents infinite recursion
- **Max Depth Limit:** Safety against deep nesting
- **Caching:** Improves performance for repeated resolutions

---

### LinkValidator

Validates markdown links and transclusions.

**Module:** `cortex.linking.link_validator`

**Implements:** `LinkValidatorProtocol`

**Constructor:**

```python
def __init__(
    self,
    file_system: FileSystemProtocol,
    link_parser: LinkParserProtocol,
)
```

**Parameters:**
- `file_system` (FileSystemProtocol) - File system manager
- `link_parser` (LinkParserProtocol) - Link parser

**Key Methods:**

#### validate_file_links

```python
async def validate_file_links(
    self, file_path: Path, memory_bank_path: Path
) -> dict[str, object]
```

Validate all links in file.

**Validates:**
- Internal file links (relative paths)
- Transclusion targets
- (Optional: External URLs if enabled)

**Returns:** Validation result dictionary

**Additional Methods:**

- `_validate_internal_link(target, base_path)` - Check if file exists
- `_validate_transclusion(target, base_path)` - Check if target exists

**Design Decisions:**

- **Separate Internal/External:** Different validation for file vs URL links
- **Detailed Results:** Reports line numbers for broken links

---

## Validation Managers

### SchemaValidator

Validates Memory Bank file schemas and structure.

**Module:** `cortex.validation.schema_validator`

**Constructor:**

```python
def __init__(self, schemas: dict[str, dict[str, object]])
```

**Parameters:**
- `schemas` (dict) - Schema definitions per file type

**Key Methods:**

#### validate_file

```python
async def validate_file(
    self, file_name: str, content: str
) -> dict[str, object]
```

Validate file against schema.

**Returns:** Validation result with errors and warnings

**Additional Methods:**

- `_check_required_sections(content, schema)` - Verify required sections exist
- `_check_section_order(content, schema)` - Verify section order
- `_check_metadata(content, schema)` - Verify frontmatter metadata

---

### DuplicationDetector

Detects duplicated content across files.

**Module:** `cortex.validation.duplication_detector`

**Constructor:**

```python
def __init__(
    self,
    similarity_threshold: float = 0.8,
    min_block_size: int = 50,
)
```

**Parameters:**
- `similarity_threshold` (float) - Similarity threshold (0-1) for duplication
- `min_block_size` (int) - Minimum block size to consider

**Key Methods:**

#### detect_duplications

```python
async def detect_duplications(
    self, files_content: dict[str, str]
) -> list[dict[str, object]]
```

Detect duplicated content across files.

**Returns:** List of duplication reports with similarity scores

**Algorithm:** Uses Levenshtein distance for similarity calculation

---

### QualityMetrics

Calculates quality metrics for Memory Bank files.

**Module:** `cortex.validation.quality_metrics`

**Constructor:**

```python
def __init__(
    self,
    metadata_index: MetadataIndexProtocol,
    token_counter: TokenCounterProtocol,
)
```

**Key Methods:**

#### calculate_metrics

```python
async def calculate_metrics(
    self, file_name: str, content: str
) -> dict[str, object]
```

Calculate quality metrics for file.

**Metrics:**
- Completeness score
- Consistency score
- Clarity score
- Link integrity score
- Overall quality score

**Returns:** Quality metrics dictionary

---

## Optimization Managers

### RelevanceScorer

Scores files and sections by relevance to task descriptions.

**Module:** `cortex.optimization.relevance_scorer`

**Implements:** `RelevanceScorerProtocol`

**Constructor:**

```python
def __init__(
    self,
    token_counter: TokenCounterProtocol,
    use_tfidf: bool = True,
)
```

**Parameters:**
- `token_counter` (TokenCounterProtocol) - Token counter
- `use_tfidf` (bool) - Use TF-IDF scoring (default: True)

**Key Methods:**

#### score_files

```python
async def score_files(
    self,
    task_description: str,
    files_content: dict[str, str],
    files_metadata: dict[str, dict[str, object]],
    quality_scores: dict[str, float] | None = None,
) -> dict[str, dict[str, float | str]]
```

Score files by relevance using TF-IDF or keyword matching.

**Algorithm:**
1. TF-IDF vectorization of task and files
2. Cosine similarity calculation
3. Quality score multiplier (if provided)
4. Final relevance score

#### score_sections

```python
async def score_sections(
    self, task_description: str, file_name: str, content: str
) -> list[dict[str, object]]
```

Score sections within file by relevance.

---

### ContextOptimizer

Optimizes context selection within token budgets.

**Module:** `cortex.optimization.context_optimizer`

**Implements:** `ContextOptimizerProtocol`

**Constructor:**

```python
def __init__(
    self,
    relevance_scorer: RelevanceScorerProtocol,
    dependency_graph: DependencyGraphProtocol,
    token_counter: TokenCounterProtocol,
)
```

**Key Methods:**

#### optimize

```python
async def optimize(
    self,
    task_description: str,
    files_content: dict[str, str],
    files_metadata: dict[str, dict[str, object]],
    strategy: str = "hybrid",
    token_budget: int | None = None,
    mandatory_files: list[str] | None = None,
) -> dict[str, object]
```

Optimize context within token budget.

**Strategies:**
- `"relevance"` - By relevance score only
- `"dependency"` - By dependency order
- `"hybrid"` - Relevance + dependency (default)

**Algorithm:**
1. Score files by relevance
2. Include mandatory files first
3. Add files by strategy until budget exhausted

---

### ProgressiveLoader

Loads Memory Bank context progressively.

**Module:** `cortex.optimization.progressive_loader`

**Implements:** `ProgressiveLoaderProtocol`

**Constructor:**

```python
def __init__(
    self,
    file_system: FileSystemProtocol,
    dependency_graph: DependencyGraphProtocol,
    token_counter: TokenCounterProtocol,
    relevance_scorer: RelevanceScorerProtocol,
)
```

**Key Methods:**

#### load_by_priority

```python
async def load_by_priority(
    self,
    memory_bank_path: Path,
    priority_order: list[str] | None = None,
    token_budget: int | None = None,
) -> dict[str, object]
```

Load files by priority order.

**Default Priority:** ["projectBrief.md", "activeContext.md", ...]

#### load_by_dependencies

```python
async def load_by_dependencies(
    self,
    memory_bank_path: Path,
    start_files: list[str] | None = None,
    token_budget: int | None = None,
) -> dict[str, object]
```

Load files following dependency order.

#### load_by_relevance

```python
async def load_by_relevance(
    self,
    memory_bank_path: Path,
    task_description: str,
    token_budget: int | None = None,
) -> dict[str, object]
```

Load files by relevance to task.

---

### SummarizationEngine

Summarizes file content when full content exceeds budgets.

**Module:** `cortex.optimization.summarization_engine`

**Implements:** `SummarizationEngineProtocol`

**Constructor:**

```python
def __init__(
    self,
    file_system: FileSystemProtocol,
    token_counter: TokenCounterProtocol,
)
```

**Key Methods:**

#### summarize_file

```python
async def summarize_file(
    self,
    file_path: Path,
    strategy: str = "key_sections",
    target_reduction: float = 0.5,
) -> dict[str, object]
```

Summarize file content.

**Strategies:**
- `"key_sections"` - Extract most important sections
- `"truncate"` - Simple truncation
- `"abstract"` - Generate abstract (if AI available)

#### extract_key_sections

```python
async def extract_key_sections(self, content: str, target_tokens: int) -> str
```

Extract key sections to meet token target.

---

## Analysis Managers

### PatternAnalyzer

Analyzes file access patterns and correlations.

**Module:** `cortex.analysis.pattern_analyzer`

**Implements:** `PatternAnalyzerProtocol`

**Constructor:**

```python
def __init__(self, metadata_index: MetadataIndexProtocol)
```

**Key Methods:**

#### get_access_frequency

```python
async def get_access_frequency(
    self, time_window_days: int = 30
) -> dict[str, dict[str, int | float]]
```

Get file access frequency statistics.

#### get_co_access_patterns

```python
async def get_co_access_patterns(
    self, min_correlation: float = 0.5
) -> list[dict[str, object]]
```

Get files frequently accessed together.

#### get_unused_files

```python
async def get_unused_files(
    self, days_threshold: int = 90
) -> list[dict[str, object]]
```

Get files not accessed recently.

---

### StructureAnalyzer

Analyzes Memory Bank file organization and structure.

**Module:** `cortex.analysis.structure_analyzer`

**Implements:** `StructureAnalyzerProtocol`

**Constructor:**

```python
def __init__(self, dependency_graph: DependencyGraphProtocol)
```

**Key Methods:**

#### analyze_organization

```python
async def analyze_organization(self, memory_bank_path: Path) -> dict[str, object]
```

Analyze file organization structure.

#### detect_anti_patterns

```python
async def detect_anti_patterns(
    self, memory_bank_path: Path
) -> list[dict[str, object]]
```

Detect structural anti-patterns like deep nesting, circular dependencies.

---

### InsightEngine

Generates actionable insights from analysis data.

**Module:** `cortex.analysis.insight_engine`

**Constructor:**

```python
def __init__(
    self,
    pattern_analyzer: PatternAnalyzerProtocol,
    structure_analyzer: StructureAnalyzerProtocol,
    duplication_detector: object,
)
```

**Key Methods:**

#### generate_insights

```python
async def generate_insights(
    self,
    memory_bank_path: Path,
    categories: list[str] | None = None,
) -> dict[str, object]
```

Generate insights across multiple categories.

**Categories:**
- Usage patterns
- Organization issues
- Quality issues
- Optimization opportunities
- Dependency issues

**Returns:** Insights result with prioritized recommendations

---

## Refactoring Managers

### RefactoringEngine

Generates refactoring suggestions.

**Module:** `cortex.refactoring.refactoring_engine`

**Implements:** `RefactoringEngineProtocol`

**Constructor:**

```python
def __init__(
    self,
    memory_bank_path: Path,
    min_confidence: float = 0.7,
    max_suggestions_per_run: int = 10,
)
```

**Key Methods:**

#### generate_suggestions

```python
async def generate_suggestions(
    self,
    pattern_data: dict[str, object] | None = None,
    structure_data: dict[str, object] | None = None,
    insights: list[dict[str, object]] | None = None,
    categories: list[str] | None = None,
) -> list[RefactoringSuggestion]
```

Generate refactoring suggestions from analysis data.

**Suggestion Types:**
- Consolidation
- Split
- Reorganization
- Transclusion
- Rename
- Merge

#### export_suggestions

```python
async def export_suggestions(
    self, suggestions: list[dict[str, object]], format: str = "json"
) -> str
```

Export suggestions in JSON, Markdown, or text format.

---

### ConsolidationDetector

Detects content consolidation opportunities.

**Module:** `cortex.refactoring.consolidation_detector`

**Implements:** `ConsolidationDetectorProtocol`

---

### SplitRecommender

Recommends file splitting opportunities.

**Module:** `cortex.refactoring.split_recommender`

**Implements:** `SplitRecommenderProtocol`

---

### ReorganizationPlanner

Creates reorganization plans.

**Module:** `cortex.refactoring.reorganization_planner`

**Implements:** `ReorganizationPlannerProtocol`

---

### RefactoringExecutor

Executes approved refactorings safely.

**Module:** `cortex.refactoring.refactoring_executor`

**Constructor:**

```python
def __init__(
    self,
    file_system: FileSystemProtocol,
    version_manager: VersionManagerProtocol,
    approval_manager: ApprovalManagerProtocol,
)
```

**Key Methods:**

#### execute_refactoring

```python
async def execute_refactoring(
    self, suggestion_id: str, dry_run: bool = False
) -> dict[str, object]
```

Execute approved refactoring.

**Dry Run:** If True, validates but doesn't apply changes.

#### get_execution_status

```python
async def get_execution_status(self, execution_id: str) -> dict[str, object]
```

Get status of refactoring execution.

---

### ApprovalManager

Manages refactoring approvals.

**Module:** `cortex.refactoring.approval_manager`

**Implements:** `ApprovalManagerProtocol`

**See Protocol documentation for full API.**

---

### RollbackManager

Manages refactoring rollbacks.

**Module:** `cortex.refactoring.rollback_manager`

**Implements:** `RollbackManagerProtocol`

**See Protocol documentation for full API.**

---

### LearningEngine

Learns from user feedback.

**Module:** `cortex.refactoring.learning_engine`

**Implements:** `LearningEngineProtocol`

**See Protocol documentation for full API.**

---

## Rules Managers

### SharedRulesManager

Manages shared rules repositories.

**Module:** `cortex.rules.shared_rules_manager`

**Implements:** `RulesManagerProtocol`

**Constructor:**

```python
def __init__(
    self,
    rules_dir: Path,
    token_counter: TokenCounterProtocol,
    config: dict[str, object] | None = None,
)
```

**Key Methods:**

#### index_rules

```python
async def index_rules(self, force: bool = False) -> dict[str, object]
```

Index rules from directory.

#### get_relevant_rules

```python
async def get_relevant_rules(
    self,
    task_description: str,
    max_tokens: int | None = None,
    min_relevance: float | None = None,
) -> dict[str, object]
```

Get rules relevant to task.

**See Protocol documentation for full API.**

---

## Structure Managers

### StructureManager

Manages project structure and templates.

**Module:** `cortex.structure.structure_manager`

**Constructor:**

```python
def __init__(
    self,
    project_root: Path,
    file_system: FileSystemProtocol,
)
```

**Key Methods:**

#### setup_project_structure

```python
async def setup_project_structure(
    self, template_name: str = "default"
) -> dict[str, object]
```

Setup project structure from template.

#### validate_project_structure

```python
async def validate_project_structure(self) -> dict[str, object]
```

Validate project structure against template.

#### get_structure_templates

```python
async def get_structure_templates(self) -> list[dict[str, object]]
```

Get available structure templates.

---

## Manager Initialization

### Container Pattern

Managers are initialized via dependency injection container:

```python
from cortex.managers import get_managers

# Initialize all managers
managers = await get_managers(project_root=Path("/project"))

# Access managers
fs = managers.file_system
metadata = managers.metadata_index
token_counter = managers.token_counter
# ... etc
```

### Lazy Loading

Some managers support lazy loading to improve startup performance:

```python
from cortex.managers import LazyManager

lazy_mgr = LazyManager(factory=lambda: expensive_initialization())
result = await lazy_mgr.get()  # Initialized on first access
```

---

## See Also

- [Protocol Reference](./protocols.md) - Protocol interface definitions
- [Types Reference](./types.md) - TypedDict and dataclass definitions
- [MCP Tools Reference](./tools.md) - MCP tool interfaces
- [Exceptions Reference](./exceptions.md) - Exception hierarchy
