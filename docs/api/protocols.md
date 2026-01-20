# Protocol Reference

Complete reference for all 20 Protocol classes in Cortex.

## Overview

Cortex uses Protocol classes (PEP 544) for structural subtyping, enabling loose coupling and testability without explicit inheritance. Any class implementing the required methods automatically satisfies the protocol.

**Protocol Categories:**

| Category | Protocols | Purpose |
|----------|-----------|---------|
| [File System](#file-system-protocols) | 2 | File I/O and metadata management |
| [Token & Dependencies](#token-and-dependency-protocols) | 2 | Token counting and dependency tracking |
| [Linking](#linking-protocols) | 3 | Link parsing, transclusion, validation |
| [Versioning](#versioning-protocols) | 1 | Version management and snapshots |
| [Optimization](#optimization-protocols) | 2 | Context optimization and relevance scoring |
| [Loading](#loading-protocols) | 2 | Progressive loading and summarization |
| [Analysis](#analysis-protocols) | 2 | Pattern and structure analysis |
| [Refactoring](#refactoring-protocols) | 4 | Refactoring suggestions and planning |
| [Execution](#execution-protocols) | 3 | Approval, rollback, and learning |
| [Rules](#rules-protocols) | 1 | Rules management |

---

## File System Protocols

### FileSystemProtocol

Protocol for safe file I/O operations with conflict detection, content hashing, and markdown parsing.

**Module:** `cortex.core.protocols.file_system`

**Used By:**

- FileSystemManager - Concrete implementation
- DependencyGraph - Reading files for dependency analysis
- TransclusionEngine - Reading and resolving transclusions
- ValidationTools - Reading and validating content

**Methods:**

#### validate_path

```python
def validate_path(self, file_path: Path) -> bool
```

Validate that a path is safe and within project bounds.

**Parameters:**

- `file_path` (Path) - Path to validate

**Returns:**

- `bool` - True if path is valid and safe

**Purpose:** Prevents directory traversal attacks by ensuring paths stay within project root.

---

#### read_file

```python
async def read_file(self, file_path: Path) -> tuple[str, str]
```

Read file and return content with SHA-256 hash.

**Parameters:**

- `file_path` (Path) - Path to file to read

**Returns:**

- `tuple[str, str]` - (content, content_hash)

**Raises:**

- `FileNotFoundError` - If file doesn't exist
- `MemoryBankError` - For other I/O errors

**Usage Example:**

```python
content, hash = await fs.read_file(Path("memory-bank/projectBrief.md"))
print(f"Content hash: {hash}")
```

---

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

Write content to file with optional conflict detection.

**Parameters:**

- `file_path` (Path) - Path to file
- `content` (str) - Content to write
- `expected_hash` (str | None) - Expected current hash for conflict detection (optional)
- `create_version` (bool) - Whether to create version snapshot (default: True)

**Returns:**

- `str` - New content hash

**Raises:**

- `ConflictError` - If expected_hash provided and doesn't match current content
- `MemoryBankError` - For other write errors

**Usage Example:**

```python
# With conflict detection
content, current_hash = await fs.read_file(path)
new_content = content + "\n## New Section"
new_hash = await fs.write_file(path, new_content, expected_hash=current_hash)

# Without conflict detection
new_hash = await fs.write_file(path, content, create_version=False)
```

---

#### compute_hash

```python
def compute_hash(self, content: str) -> str
```

Compute SHA-256 hash of content.

**Parameters:**

- `content` (str) - Content to hash

**Returns:**

- `str` - Hex digest of SHA-256 hash

**Usage Example:**

```python
hash1 = fs.compute_hash("content 1")
hash2 = fs.compute_hash("content 1")
assert hash1 == hash2  # Same content = same hash
```

---

#### parse_sections

```python
def parse_sections(self, content: str) -> list[dict[str, str | int]]
```

Parse markdown content into sections by headers.

**Parameters:**

- `content` (str) - Markdown content

**Returns:**

- `list[dict[str, str | int]]` - List of section dictionaries with:
  - `title` (str) - Section header text
  - `level` (int) - Header level (1-6)
  - `start_line` (int) - Starting line number
  - `end_line` (int) - Ending line number

**Usage Example:**

```python
content = """# Main Title
Content here.
## Subsection
More content.
"""
sections = fs.parse_sections(content)
# [
#   {"title": "Main Title", "level": 1, "start_line": 1, "end_line": 2},
#   {"title": "Subsection", "level": 2, "start_line": 3, "end_line": 4}
# ]
```

---

#### file_exists

```python
async def file_exists(self, file_path: Path) -> bool
```

Check if file exists.

**Parameters:**

- `file_path` (Path) - Path to check

**Returns:**

- `bool` - True if file exists

---

#### cleanup_locks

```python
async def cleanup_locks(self)
```

Clean up stale file locks.

**Purpose:** Called during shutdown to remove lock files that may have been left behind.

---

### MetadataIndexProtocol

Protocol for managing file metadata including token counts, hashes, sections, links, and access statistics.

**Module:** `cortex.core.protocols.file_system`

**Used By:**

- MetadataIndex - JSON-based implementation
- DependencyGraph - Accessing file metadata
- PatternAnalyzer - Analyzing access patterns
- QualityMetrics - Calculating quality scores

**Methods:**

#### load

```python
async def load(self) -> dict[str, object]
```

Load metadata index from disk with corruption recovery.

**Returns:**

- `dict[str, object]` - Index data dictionary with structure:

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
              "sections": [...],
              "links": [...],
              "transclusions": [...],
              "read_count": 5,
              "last_access": "2024-01-10T11:00:00"
          }
      }
  }
  ```

**Raises:**

- `MemoryBankError` - If load fails and recovery is not possible

---

#### save

```python
async def save(self)
```

Save metadata index to disk atomically.

**Purpose:** Uses atomic write (write to temp file, then rename) to prevent corruption.

**Raises:**

- `MemoryBankError` - If save operation fails

---

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

**Parameters:**

- `file_name` (str) - Name of file (e.g., "projectBrief.md")
- `path` (Path) - Full path to file
- `exists` (bool) - Whether file currently exists
- `size_bytes` (int) - File size in bytes
- `token_count` (int) - Number of tokens in file
- `content_hash` (str) - SHA-256 hash of content
- `sections` (list | None) - List of section metadata dicts (optional)
- `links` (list | None) - List of link metadata dicts (optional)
- `transclusions` (list | None) - List of transclusion target paths (optional)

**Usage Example:**

```python
sections = [
    {"title": "Overview", "level": 1, "start_line": 1, "end_line": 10}
]
await index.update_file_metadata(
    file_name="projectBrief.md",
    path=Path("/project/memory-bank/projectBrief.md"),
    exists=True,
    size_bytes=2048,
    token_count=512,
    content_hash="abc123...",
    sections=sections,
)
```

---

#### get_file_metadata

```python
async def get_file_metadata(self, file_name: str) -> dict[str, object] | None
```

Get metadata for a specific file.

**Parameters:**

- `file_name` (str) - Name of file

**Returns:**

- `dict[str, object] | None` - Metadata dictionary or None if not found

---

#### get_all_files_metadata

```python
async def get_all_files_metadata(self) -> dict[str, dict[str, object]]
```

Get metadata for all files.

**Returns:**

- `dict[str, dict[str, object]]` - Dictionary mapping file names to metadata

---

#### list_all_files

```python
async def list_all_files(self) -> list[str]
```

Get list of all file names in index.

**Returns:**

- `list[str]` - List of file names

---

#### increment_read_count

```python
async def increment_read_count(self, file_name: str)
```

Increment read count for a file.

**Parameters:**

- `file_name` (str) - Name of file

**Purpose:** Tracks access patterns for optimization and analytics.

---

## Token and Dependency Protocols

### TokenCounterProtocol

Protocol for counting tokens using tiktoken encoding.

**Module:** `cortex.core.protocols.token`

**Used By:**

- TokenCounter - tiktoken-based implementation
- MetadataIndex - Updating token counts
- ContextOptimizer - Staying within token budgets
- ProgressiveLoader - Loading by token count

**Methods:**

#### count_tokens

```python
def count_tokens(self, text: str | None) -> int
```

Count tokens in text.

**Parameters:**

- `text` (str | None) - Text to count tokens in

**Returns:**

- `int` - Number of tokens

**Usage Example:**

```python
tokens = counter.count_tokens("This is example text.")
print(f"Token count: {tokens}")
```

---

#### count_tokens_with_cache

```python
def count_tokens_with_cache(self, text: str, content_hash: str) -> int
```

Count tokens with caching by content hash.

**Parameters:**

- `text` (str) - Text to count tokens in
- `content_hash` (str) - SHA-256 hash of text for cache key

**Returns:**

- `int` - Number of tokens

**Purpose:** Avoids redundant tokenization for unchanged content.

**Usage Example:**

```python
content, hash = await fs.read_file(path)
tokens = counter.count_tokens_with_cache(content, hash)
```

---

#### count_tokens_in_file

```python
async def count_tokens_in_file(self, file_path: Path) -> int
```

Count tokens in a file.

**Parameters:**

- `file_path` (Path) - Path to file

**Returns:**

- `int` - Number of tokens

**Raises:**

- `FileNotFoundError` - If file doesn't exist

---

### DependencyGraphProtocol

Protocol for managing file dependencies, computing loading orders, and detecting circular dependencies.

**Module:** `cortex.core.protocols.token`

**Used By:**

- DependencyGraph - Graph-based implementation
- ProgressiveLoader - Computing optimal loading order
- TransclusionEngine - Detecting circular transclusions
- StructureAnalyzer - Analyzing dependency complexity

**Methods:**

#### compute_loading_order

```python
def compute_loading_order(self, files: list[str] | None = None) -> list[str]
```

Compute optimal loading order for files using topological sort.

**Parameters:**

- `files` (list[str] | None) - Files to compute order for (None = all files)

**Returns:**

- `list[str]` - Ordered list of file names (dependencies first)

**Usage Example:**

```python
order = graph.compute_loading_order(["projectBrief.md", "activeContext.md"])
# Returns files in dependency order, e.g.:
# ["techContext.md", "projectBrief.md", "activeContext.md"]
```

---

#### get_dependencies

```python
def get_dependencies(self, file_name: str) -> list[str]
```

Get direct dependencies of a file.

**Parameters:**

- `file_name` (str) - File to get dependencies for

**Returns:**

- `list[str]` - List of dependency file names

---

#### get_dependents

```python
def get_dependents(self, file_name: str) -> list[str]
```

Get files that depend on this file.

**Parameters:**

- `file_name` (str) - File to get dependents for

**Returns:**

- `list[str]` - List of dependent file names

---

#### add_dynamic_dependency

```python
def add_dynamic_dependency(self, from_file: str, to_file: str)
```

Add a runtime-discovered dependency.

**Parameters:**

- `from_file` (str) - Source file
- `to_file` (str) - Target file

**Purpose:** For dependencies discovered during execution (not from static analysis).

---

#### has_circular_dependency

```python
def has_circular_dependency(self) -> bool
```

Check if graph has circular dependencies.

**Returns:**

- `bool` - True if cycles exist

---

#### detect_cycles

```python
def detect_cycles(self) -> list[list[str]]
```

Detect all circular dependency chains.

**Returns:**

- `list[list[str]]` - List of cycles, each cycle is a list of file names

**Usage Example:**

```python
cycles = graph.detect_cycles()
for cycle in cycles:
    print(f"Circular dependency: {' -> '.join(cycle)}")
```

---

#### to_dict

```python
def to_dict(self) -> dict[str, object]
```

Export graph to dictionary format.

**Returns:**

- `dict[str, object]` - Dictionary representation with structure:

  ```python
  {
      "graph": {"file1.md": ["file2.md", "file3.md"]},
      "reverse": {"file2.md": ["file1.md"]}
  }
  ```

---

#### build_from_links

```python
async def build_from_links(
    self,
    file_system: FileSystemProtocol,
    link_parser: object,
    memory_bank_path: Path,
) -> None
```

Build dependency graph from actual file links.

**Parameters:**

- `file_system` (FileSystemProtocol) - File system manager
- `link_parser` (object) - Link parser instance
- `memory_bank_path` (Path) - Path to memory bank directory

**Purpose:** Scans all files and extracts links/transclusions to build dependency graph.

---

## Linking Protocols

### LinkParserProtocol

Protocol for extracting markdown links and transclusion syntax from content.

**Module:** `cortex.core.protocols.linking`

**Used By:**

- LinkParser - Regex-based implementation
- DependencyGraph - Building dependency graph
- LinkValidator - Extracting links to validate
- TransclusionEngine - Finding transclusion targets

**Methods:**

#### parse_markdown_links

```python
def parse_markdown_links(self, content: str) -> list[dict[str, str]]
```

Parse markdown links `[text](target)` from content.

**Parameters:**

- `content` (str) - Markdown content

**Returns:**

- `list[dict[str, str]]` - List of link dictionaries with:
  - `text` (str) - Link text
  - `target` (str) - Link target (URL or path)
  - `line_number` (str) - Line number where link appears

**Usage Example:**

```python
content = "[See docs](./docs.md) and [External](https://example.com)"
links = parser.parse_markdown_links(content)
# [
#   {"text": "See docs", "target": "./docs.md", "line_number": "1"},
#   {"text": "External", "target": "https://example.com", "line_number": "1"}
# ]
```

---

#### parse_transclusions

```python
def parse_transclusions(self, content: str) -> list[dict[str, str]]
```

Parse transclusion syntax `{{include:path}}` from content.

**Parameters:**

- `content` (str) - Content to parse

**Returns:**

- `list[dict[str, str]]` - List of transclusion dictionaries with:
  - `target` (str) - Target file path
  - `line_number` (str) - Line number where transclusion appears

**Usage Example:**

```python
content = "{{include:shared/glossary.md}}\n\nMore content."
transclusions = parser.parse_transclusions(content)
# [{"target": "shared/glossary.md", "line_number": "1"}]
```

---

### TransclusionEngineProtocol

Protocol for resolving transclusion syntax by recursively including content from other files.

**Module:** `cortex.core.protocols.linking`

**Used By:**

- TransclusionEngine - Recursive resolver with cycle detection
- ValidationTools - Validating fully-resolved content
- ContextOptimizer - Getting complete file content
- MCP Tools - Serving resolved content

**Methods:**

#### resolve_file

```python
async def resolve_file(self, file_path: Path, max_depth: int | None = None) -> str
```

Resolve all transclusions in a file recursively.

**Parameters:**

- `file_path` (Path) - Path to file
- `max_depth` (int | None) - Maximum recursion depth (None = unlimited)

**Returns:**

- `str` - Content with all transclusions resolved

**Raises:**

- `CircularDependencyError` - If circular transclusion detected
- `FileNotFoundError` - If target file not found

**Usage Example:**

```python
# File: main.md contains: "{{include:section1.md}}"
# File: section1.md contains: "Content here."
resolved = await engine.resolve_file(Path("memory-bank/main.md"))
# Returns: "Content here."
```

---

#### clear_cache

```python
def clear_cache(self)
```

Clear transclusion resolution cache.

**Purpose:** Call when files change to ensure fresh resolutions.

---

### LinkValidatorProtocol

Protocol for validating markdown links and transclusions.

**Module:** `cortex.core.protocols.linking`

**Used By:**

- LinkValidator - Validates internal links and external URLs
- ValidationTools - Comprehensive validation
- QualityMetrics - Calculating completeness scores
- MCP Tools - Reporting broken links

**Methods:**

#### validate_file_links

```python
async def validate_file_links(
    self, file_path: Path, memory_bank_path: Path
) -> dict[str, object]
```

Validate all links in a file.

**Parameters:**

- `file_path` (Path) - Path to file
- `memory_bank_path` (Path) - Path to memory bank directory

**Returns:**

- `dict[str, object]` - Validation result with structure:

  ```python
  {
      "valid": True,  # False if any broken links
      "broken_links": [
          {
              "text": "Link text",
              "target": "./missing.md",
              "line_number": "5"
          }
      ],
      "broken_transclusions": [
          {
              "target": "missing.md",
              "line_number": "10"
          }
      ]
  }
  ```

**Usage Example:**

```python
result = await validator.validate_file_links(
    Path("memory-bank/main.md"),
    Path("memory-bank")
)
if not result["valid"]:
    print(f"Found {len(result['broken_links'])} broken links")
```

---

## Versioning Protocols

### VersionManagerProtocol

Protocol for creating file version snapshots, tracking history, and rolling back.

**Module:** `cortex.core.protocols.versioning`

**Used By:**

- VersionManager - File-based implementation
- FileSystemManager - Automatic versioning on writes
- RollbackManager - Restoring previous versions
- MCP Tools - Version history queries

**Methods:**

#### create_snapshot

```python
async def create_snapshot(
    self, file_name: str, content: str, metadata: dict[str, object] | None = None
) -> str
```

Create version snapshot of file content.

**Parameters:**

- `file_name` (str) - Name of file
- `content` (str) - File content to snapshot
- `metadata` (dict[str, object] | None) - Optional metadata to store with snapshot

**Returns:**

- `str` - Unique snapshot ID

**Usage Example:**

```python
snapshot_id = await version_mgr.create_snapshot(
    file_name="projectBrief.md",
    content=current_content,
    metadata={"reason": "before major refactoring"}
)
```

---

#### get_version_history

```python
async def get_version_history(self, file_name: str) -> list[dict[str, object]]
```

Get version history for a file.

**Parameters:**

- `file_name` (str) - Name of file

**Returns:**

- `list[dict[str, object]]` - List of version entries (newest first) with:
  - `snapshot_id` (str) - Unique snapshot identifier
  - `timestamp` (str) - ISO format timestamp
  - `metadata` (dict) - Snapshot metadata

**Usage Example:**

```python
history = await version_mgr.get_version_history("projectBrief.md")
for version in history:
    print(f"{version['timestamp']}: {version['snapshot_id']}")
```

---

#### rollback_to_version

```python
async def rollback_to_version(self, snapshot_id: str) -> dict[str, object]
```

Rollback file to specific version.

**Parameters:**

- `snapshot_id` (str) - Snapshot ID to rollback to

**Returns:**

- `dict[str, object]` - Restored file info with:
  - `file_name` (str) - Name of file
  - `content` (str) - Restored content
  - `restored_from` (str) - Snapshot ID used

**Raises:**

- `FileNotFoundError` - If snapshot not found

**Usage Example:**

```python
result = await version_mgr.rollback_to_version("snapshot_20240110_120000")
await fs.write_file(
    Path(f"memory-bank/{result['file_name']}"),
    result['content']
)
```

---

## Optimization Protocols

### RelevanceScorerProtocol

Protocol for scoring files and sections by relevance to a task description.

**Module:** `cortex.core.protocols.optimization`

**Used By:**

- RelevanceScorer - TF-IDF based implementation
- ContextOptimizer - Selecting relevant files
- ProgressiveLoader - Loading by relevance
- MCP Tools - Context optimization

**Methods:**

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

Score files by relevance to task.

**Parameters:**

- `task_description` (str) - Description of the task
- `files_content` (dict[str, str]) - Mapping of file names to content
- `files_metadata` (dict[str, dict[str, object]]) - Mapping of file names to metadata
- `quality_scores` (dict[str, float] | None) - Optional quality score multipliers

**Returns:**

- `dict[str, dict[str, float | str]]` - Mapping of file names to score breakdown:

  ```python
  {
      "projectBrief.md": {
          "relevance_score": 0.85,
          "tfidf_score": 0.78,
          "quality_boost": 1.09
      }
  }
  ```

**Usage Example:**

```python
scores = await scorer.score_files(
    task_description="implement authentication system",
    files_content={"projectBrief.md": "...", "techContext.md": "..."},
    files_metadata={...}
)
sorted_files = sorted(
    scores.items(),
    key=lambda x: x[1]["relevance_score"],
    reverse=True
)
```

---

#### score_sections

```python
async def score_sections(
    self, task_description: str, file_name: str, content: str
) -> list[dict[str, object]]
```

Score sections within a file by relevance.

**Parameters:**

- `task_description` (str) - Description of the task
- `file_name` (str) - Name of file
- `content` (str) - File content

**Returns:**

- `list[dict[str, object]]` - List of section scores (highest first) with:
  - `title` (str) - Section title
  - `score` (float) - Relevance score
  - `start_line` (int) - Starting line number
  - `end_line` (int) - Ending line number

**Usage Example:**

```python
sections = await scorer.score_sections(
    task_description="API design patterns",
    file_name="systemPatterns.md",
    content=file_content
)
# Returns top sections most relevant to API design
```

---

### ContextOptimizerProtocol

Protocol for optimizing context selection within token budgets.

**Module:** `cortex.core.protocols.optimization`

**Used By:**

- ContextOptimizer - Multi-strategy optimizer
- MCP Tools - load_context operations
- ProgressiveLoader - Budget-aware loading
- Client Applications - Context management

**Methods:**

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

Optimize context selection within token budget.

**Parameters:**

- `task_description` (str) - Description of task
- `files_content` (dict[str, str]) - Available files and content
- `files_metadata` (dict[str, dict[str, object]]) - Files metadata
- `strategy` (str) - Optimization strategy: "relevance", "dependency", or "hybrid"
- `token_budget` (int | None) - Maximum tokens allowed (None = no limit)
- `mandatory_files` (list[str] | None) - Files that must be included

**Returns:**

- `dict[str, object]` - Optimization result with structure:

  ```python
  {
      "selected_files": {
          "projectBrief.md": "file content...",
          "activeContext.md": "file content..."
      },
      "total_tokens": 5000,
      "files_included": ["projectBrief.md", "activeContext.md"],
      "files_excluded": ["techContext.md"],
      "strategy_used": "hybrid"
  }
  ```

**Usage Example:**

```python
result = await optimizer.optimize(
    task_description="implement user authentication",
    files_content=all_files,
    files_metadata=metadata,
    strategy="hybrid",
    token_budget=8000,
    mandatory_files=["projectBrief.md"]
)
print(f"Selected {len(result['selected_files'])} files")
print(f"Total tokens: {result['total_tokens']}")
```

---

## Loading Protocols

### ProgressiveLoaderProtocol

Protocol for loading Memory Bank context progressively based on priority, dependencies, or relevance.

**Module:** `cortex.core.protocols.loading`

**Used By:**

- ProgressiveLoader - Multi-strategy implementation
- ContextOptimizer - Budget-aware assembly
- MCP Tools - load_progressively operations
- Client Applications - Incremental loading

**Methods:**

#### load_by_priority

```python
async def load_by_priority(
    self,
    memory_bank_path: Path,
    priority_order: list[str] | None = None,
    token_budget: int | None = None,
) -> dict[str, object]
```

Load context progressively by priority order.

**Parameters:**

- `memory_bank_path` (Path) - Path to Memory Bank directory
- `priority_order` (list[str] | None) - Priority order (default: ["projectBrief.md", "activeContext.md", ...])
- `token_budget` (int | None) - Maximum tokens to load

**Returns:**

- `dict[str, object]` - Loading result with:
  - `loaded_files` (dict) - Mapping of file names to content
  - `total_tokens` (int) - Total tokens loaded
  - `files_skipped` (list) - Files skipped due to budget

---

#### load_by_dependencies

```python
async def load_by_dependencies(
    self,
    memory_bank_path: Path,
    start_files: list[str] | None = None,
    token_budget: int | None = None,
) -> dict[str, object]
```

Load context progressively following dependency order.

**Parameters:**

- `memory_bank_path` (Path) - Path to Memory Bank directory
- `start_files` (list[str] | None) - Starting files (auto-detect if None)
- `token_budget` (int | None) - Maximum tokens to load

**Returns:**

- `dict[str, object]` - Loading result (same structure as load_by_priority)

**Purpose:** Ensures dependencies are loaded before dependents.

---

#### load_by_relevance

```python
async def load_by_relevance(
    self,
    memory_bank_path: Path,
    task_description: str,
    token_budget: int | None = None,
) -> dict[str, object]
```

Load context progressively by relevance to task.

**Parameters:**

- `memory_bank_path` (Path) - Path to Memory Bank directory
- `task_description` (str) - Task description for relevance scoring
- `token_budget` (int | None) - Maximum tokens to load

**Returns:**

- `dict[str, object]` - Loading result (same structure as load_by_priority)

**Purpose:** Loads most relevant files first.

**Usage Example:**

```python
result = await loader.load_by_relevance(
    memory_bank_path=Path("memory-bank"),
    task_description="implement OAuth authentication",
    token_budget=10000
)
for file_name in result["loaded_files"]:
    print(f"Loaded: {file_name}")
```

---

### SummarizationEngineProtocol

Protocol for summarizing file content when full content exceeds token budgets.

**Module:** `cortex.core.protocols.loading`

**Used By:**

- SummarizationEngine - Multi-strategy summarizer
- ContextOptimizer - Fitting more content in budget
- ProgressiveLoader - Loading summarized versions
- MCP Tools - summarize_content operations

**Methods:**

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

**Parameters:**

- `file_path` (Path) - Path to file to summarize
- `strategy` (str) - Summarization strategy: "key_sections", "truncate", or "abstract"
- `target_reduction` (float) - Target reduction percentage (0-1)

**Returns:**

- `dict[str, object]` - Summarization result with:
  - `original_tokens` (int) - Original token count
  - `summary_tokens` (int) - Summary token count
  - `reduction` (float) - Actual reduction achieved
  - `summary` (str) - Summarized content
  - `strategy_used` (str) - Strategy applied

**Usage Example:**

```python
result = await engine.summarize_file(
    file_path=Path("memory-bank/techContext.md"),
    strategy="key_sections",
    target_reduction=0.6  # 60% reduction
)
print(f"Reduced from {result['original_tokens']} to {result['summary_tokens']} tokens")
```

---

#### extract_key_sections

```python
async def extract_key_sections(self, content: str, target_tokens: int) -> str
```

Extract key sections from content to meet token target.

**Parameters:**

- `content` (str) - Content to extract from
- `target_tokens` (int) - Target token count

**Returns:**

- `str` - Extracted content containing most important sections

**Purpose:** Intelligently selects sections by importance rather than truncating.

---

## Analysis Protocols

### PatternAnalyzerProtocol

Protocol for analyzing file access patterns, co-access correlations, and identifying unused files.

**Module:** `cortex.core.protocols.analysis`

**Used By:**

- PatternAnalyzer - Statistical analysis implementation
- InsightEngine - Generating usage-based insights
- RefactoringEngine - Identifying refactoring opportunities
- MCP Tools - Pattern analysis queries

**Methods:**

#### get_access_frequency

```python
async def get_access_frequency(
    self, time_window_days: int = 30
) -> dict[str, dict[str, int | float]]
```

Get file access frequency within time window.

**Parameters:**

- `time_window_days` (int) - Days to look back (default: 30)

**Returns:**

- `dict[str, dict[str, int | float]]` - Mapping of file names to statistics:

  ```python
  {
      "projectBrief.md": {
          "read_count": 45,
          "frequency": 1.5  # reads per day
      }
  }
  ```

---

#### get_co_access_patterns

```python
async def get_co_access_patterns(
    self, min_correlation: float = 0.5
) -> list[dict[str, object]]
```

Get files frequently accessed together.

**Parameters:**

- `min_correlation` (float) - Minimum correlation threshold (0-1)

**Returns:**

- `list[dict[str, object]]` - List of co-access patterns with:
  - `files` (list[str]) - Files accessed together
  - `correlation` (float) - Correlation score
  - `occurrences` (int) - Number of co-accesses

**Purpose:** Identifies files that should be consolidated or linked.

---

#### get_unused_files

```python
async def get_unused_files(
    self, days_threshold: int = 90
) -> list[dict[str, object]]
```

Get files not accessed recently.

**Parameters:**

- `days_threshold` (int) - Days since last access threshold

**Returns:**

- `list[dict[str, object]]` - List of unused files with:
  - `file_name` (str) - Name of file
  - `days_since_access` (int) - Days since last access
  - `last_access` (str) - Last access timestamp

---

### StructureAnalyzerProtocol

Protocol for analyzing Memory Bank file organization and detecting structural anti-patterns.

**Module:** `cortex.core.protocols.analysis`

**Used By:**

- StructureAnalyzer - Organization analysis
- InsightEngine - Structural insights
- RefactoringEngine - Reorganization suggestions
- MCP Tools - Structure analysis queries

**Methods:**

#### analyze_organization

```python
async def analyze_organization(self, memory_bank_path: Path) -> dict[str, object]
```

Analyze Memory Bank file organization.

**Parameters:**

- `memory_bank_path` (Path) - Path to Memory Bank directory

**Returns:**

- `dict[str, object]` - Organization analysis with:
  - `total_files` (int) - Total number of files
  - `max_depth` (int) - Maximum directory depth
  - `avg_depth` (float) - Average directory depth
  - `has_circular_deps` (bool) - Whether circular dependencies exist
  - `file_size_distribution` (dict) - Size statistics

---

#### detect_anti_patterns

```python
async def detect_anti_patterns(
    self, memory_bank_path: Path
) -> list[dict[str, object]]
```

Detect structural anti-patterns.

**Parameters:**

- `memory_bank_path` (Path) - Path to Memory Bank directory

**Returns:**

- `list[dict[str, object]]` - List of anti-patterns with:
  - `type` (str) - Anti-pattern type ("deep_nesting", "circular_dependency", etc.)
  - `severity` (str) - Severity level ("error", "warning", "info")
  - `description` (str) - Human-readable description
  - `affected_files` (list) - Files affected
  - `suggestion` (str) - How to fix

**Usage Example:**

```python
anti_patterns = await analyzer.detect_anti_patterns(Path("memory-bank"))
for pattern in anti_patterns:
    print(f"{pattern['severity']}: {pattern['type']}")
    print(f"  {pattern['description']}")
    print(f"  Suggestion: {pattern['suggestion']}")
```

---

## Refactoring Protocols

### RefactoringEngineProtocol

Protocol for generating and exporting refactoring suggestions.

**Module:** `cortex.core.protocols.refactoring`

**Used By:**

- RefactoringEngine - Suggestion generator
- MCP Tools - get_refactoring_suggestions operations
- InsightEngine - Actionable refactoring insights
- Client Applications - Presenting refactoring options

**Methods:**

#### generate_suggestions

```python
async def generate_suggestions(
    self,
    insight_data: dict[str, object],
    analysis_data: dict[str, object],
    max_suggestions: int | None = None,
) -> list[dict[str, object]]
```

Generate refactoring suggestions from analysis data.

**Parameters:**

- `insight_data` (dict[str, object]) - Insights from pattern analysis
- `analysis_data` (dict[str, object]) - Structural analysis data
- `max_suggestions` (int | None) - Maximum suggestions to generate

**Returns:**

- `list[dict[str, object]]` - List of refactoring suggestions (see RefactoringSuggestion dataclass)

---

#### export_suggestions

```python
async def export_suggestions(
    self, suggestions: list[dict[str, object]], format: str = "json"
) -> str
```

Export suggestions in specified format.

**Parameters:**

- `suggestions` (list[dict[str, object]]) - List of suggestions
- `format` (str) - Export format: "json", "markdown", or "text"

**Returns:**

- `str` - Formatted suggestions string

---

### ConsolidationDetectorProtocol

Protocol for detecting opportunities to consolidate duplicated content using transclusion.

**Module:** `cortex.core.protocols.refactoring`

**Used By:**

- ConsolidationDetector - Duplication detector
- RefactoringEngine - Consolidation suggestions
- DuplicationDetector - Identifying duplication patterns
- MCP Tools - analyze_consolidation operations

**Methods:**

#### detect_opportunities

```python
async def detect_opportunities(
    self,
    files: list[str] | None = None,
    suggest_transclusion: bool = True,
) -> list[dict[str, object]]
```

Detect consolidation opportunities.

**Parameters:**

- `files` (list[str] | None) - Files to analyze (all if None)
- `suggest_transclusion` (bool) - Whether to suggest transclusion syntax

**Returns:**

- `list[dict[str, object]]` - List of opportunities with:
  - `files` (list[str]) - Files with duplicated content
  - `duplicated_content` (str) - The duplicated content
  - `suggestion` (str) - Transclusion suggestion

---

#### analyze_consolidation_impact

```python
async def analyze_consolidation_impact(
    self, opportunity: dict[str, object]
) -> dict[str, object]
```

Analyze impact of a consolidation opportunity.

**Parameters:**

- `opportunity` (dict[str, object]) - Consolidation opportunity

**Returns:**

- `dict[str, object]` - Impact analysis with:
  - `files_affected` (int) - Number of files affected
  - `estimated_savings` (int) - Estimated token/byte savings
  - `maintenance_improvement` (str) - Maintenance improvement rating

---

### SplitRecommenderProtocol

Protocol for suggesting file splitting opportunities.

**Module:** `cortex.core.protocols.refactoring`

**Used By:**

- SplitRecommender - File split analyzer
- RefactoringEngine - Split suggestions
- StructureAnalyzer - Identifying oversized files
- MCP Tools - analyze_splits operations

**Methods:**

#### suggest_file_splits

```python
async def suggest_file_splits(
    self,
    files: list[str] | None = None,
    strategies: list[str] | None = None,
) -> list[dict[str, object]]
```

Suggest file splitting opportunities.

**Parameters:**

- `files` (list[str] | None) - Files to analyze (all if None)
- `strategies` (list[str] | None) - Strategies to use: ["size", "complexity", "cohesion"]

**Returns:**

- `list[dict[str, object]]` - List of split suggestions with:
  - `file` (str) - File to split
  - `reason` (str) - Why split is recommended
  - `suggested_splits` (list) - Suggested split points
  - `confidence` (float) - Confidence score

---

#### analyze_file

```python
async def analyze_file(self, file_path: str) -> dict[str, object]
```

Analyze a single file for splitting opportunities.

**Parameters:**

- `file_path` (str) - Path to file

**Returns:**

- `dict[str, object]` - File analysis with:
  - `file` (str) - File path
  - `size` (int) - File size
  - `should_split` (bool) - Whether split is recommended
  - `reason` (str) - Reason for recommendation
  - `split_points` (list) - Suggested split points

---

### ReorganizationPlannerProtocol

Protocol for creating comprehensive reorganization plans.

**Module:** `cortex.core.protocols.refactoring`

**Used By:**

- ReorganizationPlanner - Plan creator
- RefactoringEngine - Reorganization suggestions
- StructureAnalyzer - Optimizing organization
- MCP Tools - plan_reorganization operations

**Methods:**

#### create_reorganization_plan

```python
async def create_reorganization_plan(
    self,
    optimization_goal: str = "dependency_depth",
    max_depth: int | None = None,
) -> dict[str, object]
```

Create a reorganization plan.

**Parameters:**

- `optimization_goal` (str) - Goal: "dependency_depth", "access_patterns", or "size_distribution"
- `max_depth` (int | None) - Maximum directory depth

**Returns:**

- `dict[str, object]` - Reorganization plan with:
  - `goal` (str) - Optimization goal
  - `moves` (list) - List of file move operations
  - `estimated_improvement` (float) - Estimated improvement score

---

#### preview_reorganization

```python
async def preview_reorganization(
    self, plan: dict[str, object]
) -> dict[str, object]
```

Preview impact of reorganization plan.

**Parameters:**

- `plan` (dict[str, object]) - Reorganization plan

**Returns:**

- `dict[str, object]` - Preview results with:
  - `files_to_move` (int) - Number of files to move
  - `estimated_improvement` (float) - Improvement score
  - `risks` (list) - Potential risks

---

## Execution Protocols

### ApprovalManagerProtocol

Protocol for managing approval workflows for refactoring operations.

**Module:** `cortex.core.protocols.refactoring_execution`

**Used By:**

- ApprovalManager - Approval tracking
- RefactoringExecutor - Checking approval before execution
- MCP Tools - approve_refactoring operations
- Client Applications - Approval workflow UI

**Methods:**

#### request_approval

```python
async def request_approval(
    self, refactoring_id: str, details: dict[str, object]
) -> dict[str, object]
```

Request approval for refactoring.

**Parameters:**

- `refactoring_id` (str) - Unique refactoring identifier
- `details` (dict[str, object]) - Refactoring details

**Returns:**

- `dict[str, object]` - Approval request result with:
  - `refactoring_id` (str) - Identifier
  - `status` (str) - "pending"
  - `message` (str) - Status message

---

#### get_approval_status

```python
async def get_approval_status(self, refactoring_id: str) -> dict[str, object]
```

Get approval status for refactoring.

**Parameters:**

- `refactoring_id` (str) - Unique refactoring identifier

**Returns:**

- `dict[str, object]` - Approval status with:
  - `refactoring_id` (str) - Identifier
  - `status` (str) - "pending", "approved", "rejected", or "not_found"
  - `details` (dict) - Refactoring details

---

#### approve

```python
async def approve(self, refactoring_id: str) -> dict[str, object]
```

Approve refactoring execution.

**Parameters:**

- `refactoring_id` (str) - Unique refactoring identifier

**Returns:**

- `dict[str, object]` - Approval result with:
  - `refactoring_id` (str) - Identifier
  - `status` (str) - "approved"
  - `message` (str) - Confirmation message

---

### RollbackManagerProtocol

Protocol for rolling back refactoring operations and tracking rollback history.

**Module:** `cortex.core.protocols.refactoring_execution`

**Used By:**

- RollbackManager - Rollback operations
- RefactoringExecutor - Providing rollback capability
- MCP Tools - rollback_refactoring operations
- Client Applications - Undo functionality

**Methods:**

#### rollback_refactoring

```python
async def rollback_refactoring(self, execution_id: str) -> dict[str, object]
```

Rollback a refactoring operation.

**Parameters:**

- `execution_id` (str) - Execution identifier to rollback

**Returns:**

- `dict[str, object]` - Rollback result with:
  - `status` (str) - "rolled_back"
  - `files_restored` (int) - Number of files restored
  - `execution_id` (str) - Original execution ID

**Purpose:** Restores all files modified by the refactoring to their previous state.

---

#### get_rollback_history

```python
async def get_rollback_history(self) -> list[dict[str, object]]
```

Get history of rollback operations.

**Returns:**

- `list[dict[str, object]]` - List of rollback history entries (newest first) with:
  - `execution_id` (str) - Execution that was rolled back
  - `files` (list[str]) - Files restored
  - `timestamp` (str) - When rollback occurred

---

### LearningEngineProtocol

Protocol for learning from user feedback and adapting suggestion confidence scores.

**Module:** `cortex.core.protocols.refactoring_execution`

**Used By:**

- LearningEngine - Feedback tracker
- RefactoringEngine - Confidence-based ranking
- MCP Tools - submit_feedback and get_learning_stats operations
- Client Applications - Feedback collection

**Methods:**

#### record_feedback

```python
async def record_feedback(
    self,
    suggestion_id: str,
    accepted: bool,
    reason: str | None = None,
    additional_data: dict[str, object] | None = None,
) -> dict[str, object]
```

Record user feedback on a suggestion.

**Parameters:**

- `suggestion_id` (str) - Suggestion identifier
- `accepted` (bool) - Whether suggestion was accepted
- `reason` (str | None) - Optional reason for decision
- `additional_data` (dict[str, object] | None) - Optional additional feedback

**Returns:**

- `dict[str, object]` - Feedback record result with:
  - `status` (str) - "recorded"
  - `suggestion_id` (str) - Identifier

**Purpose:** Auto-adjusts confidence scores based on feedback.

---

#### adjust_suggestion_confidence

```python
async def adjust_suggestion_confidence(
    self,
    suggestion_type: str,
    pattern: str,
    adjustment: float,
) -> dict[str, object]
```

Adjust confidence for a suggestion pattern.

**Parameters:**

- `suggestion_type` (str) - Type of suggestion ("consolidation", "split", etc.)
- `pattern` (str) - Pattern identifier
- `adjustment` (float) - Confidence adjustment value (-1 to 1)

**Returns:**

- `dict[str, object]` - Adjustment result with:
  - `new_confidence` (float) - Updated confidence score

---

#### get_learning_insights

```python
async def get_learning_insights(self) -> dict[str, object]
```

Get learning insights and statistics.

**Returns:**

- `dict[str, object]` - Learning insights with:
  - `total_feedback` (int) - Total feedback records
  - `acceptance_rate` (float) - Overall acceptance rate
  - `top_patterns` (list) - Most successful patterns
  - `improvement_suggestions` (list) - Areas for improvement

---

## Rules Protocols

### RulesManagerProtocol

Protocol for managing shared rules repositories, indexing rules, and retrieving relevant rules.

**Module:** `cortex.core.protocols.rules`

**Used By:**

- RulesManager - Rules repository manager
- MCP Tools - Rules indexing and retrieval
- ContextOptimizer - Including relevant rules
- Client Applications - Rules-based assistance

**Methods:**

#### index_rules

```python
async def index_rules(self, force: bool = False) -> dict[str, object]
```

Index rules from configured folder.

**Parameters:**

- `force` (bool) - Force re-indexing even if cache is fresh

**Returns:**

- `dict[str, object]` - Indexing result with:
  - `status` (str) - "indexed" or "cached"
  - `rules_count` (int) - Number of rules indexed

**Purpose:** Scans rules directory and builds searchable index.

---

#### get_relevant_rules

```python
async def get_relevant_rules(
    self,
    task_description: str,
    max_tokens: int | None = None,
    min_relevance: float | None = None,
) -> dict[str, object]
```

Get rules relevant to a task.

**Parameters:**

- `task_description` (str) - Task description for relevance scoring
- `max_tokens` (int | None) - Maximum tokens to return
- `min_relevance` (float | None) - Minimum relevance score (0-1)

**Returns:**

- `dict[str, object]` - Relevant rules with:
  - `selected_rules` (list) - List of rules with content and relevance scores
  - `total_tokens` (int) - Total tokens in selected rules

**Usage Example:**

```python
rules = await rules_mgr.get_relevant_rules(
    task_description="implement API authentication",
    max_tokens=2000,
    min_relevance=0.7
)
for rule in rules["selected_rules"]:
    print(f"Rule: {rule['path']} (relevance: {rule['relevance']})")
```

---

## Implementation Guidelines

### Creating Protocol Implementations

To implement a protocol:

1. **No Inheritance Required:** Simply implement all protocol methods
2. **Type Safety:** Use type hints matching the protocol signature
3. **Async/Sync:** Match async/sync as defined in protocol
4. **Return Types:** Ensure return types match exactly

**Example:**

```python
from pathlib import Path
from cortex.core.protocols import FileSystemProtocol

class MyFileSystem:
    """Automatically satisfies FileSystemProtocol"""

    def validate_path(self, file_path: Path) -> bool:
        return file_path.is_relative_to(self.root)

    async def read_file(self, file_path: Path) -> tuple[str, str]:
        # Implementation
        return (content, hash)

    # Implement remaining methods...
```

### Testing Protocol Implementations

Use `isinstance()` to verify protocol satisfaction:

```python
from cortex.core.protocols import FileSystemProtocol

fs = MyFileSystem()
assert isinstance(fs, FileSystemProtocol)  # Structural subtyping check
```

### Protocol Benefits

1. **Loose Coupling:** No explicit inheritance dependencies
2. **Easy Testing:** Mock implementations without complex inheritance
3. **Flexibility:** Multiple implementations without base class constraints
4. **Type Safety:** Static type checking with mypy/pyright

---

## See Also

- [API Managers Reference](./managers.md) - Manager class implementations
- [API Types Reference](./types.md) - TypedDict and dataclass definitions
- [MCP Tools Reference](./tools.md) - MCP tool interfaces
- [Exceptions Reference](./exceptions.md) - Exception hierarchy
