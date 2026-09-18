# Protocol Reference

Complete reference for all 4 Protocol classes in Cortex.

## Overview

Cortex uses Protocol classes (PEP 544) for structural subtyping, enabling loose coupling and testability without explicit inheritance. Any class implementing the required methods automatically satisfies the protocol.

**Protocol Categories:**

| Category | Protocols | Purpose |
|----------|-----------|---------|
| [File System](#file-system-protocols) | 2 | File I/O and metadata management |
| [Token & Dependencies](#token-and-dependency-protocols) | 2 | Token counting and dependency tracking |

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
4. **Type Safety:** Static type checking with Pyright as the primary type checker (CI + local), with mypy available as an optional/local-only cross-check

---

## See Also

- [API Managers Reference](./managers.md) - Manager class implementations
- [API Types Reference](./types.md) - TypedDict and dataclass definitions
- [MCP Tools Reference](./tools.md) - MCP tool interfaces
- [Exceptions Reference](./exceptions.md) - Exception hierarchy
