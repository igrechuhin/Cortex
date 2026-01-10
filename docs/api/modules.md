# Cortex API Modules Documentation

Comprehensive documentation of all modules in the Cortex system, organized by development phase. Each phase builds upon the previous one to create a complete knowledge management and refactoring system.

## Table of Contents

- [Phase 1: Foundation](#phase-1-foundation)
- [Phase 2: DRY Linking](#phase-2-dry-linking)
- [Phase 3: Validation](#phase-3-validation)
- [Phase 4: Optimization](#phase-4-optimization)
- [Phase 5: Self-Evolution](#phase-5-self-evolution)
- [Phase 6: Shared Rules](#phase-6-shared-rules)
- [Phase 7: Architecture](#phase-7-architecture)
- [Phase 8: Structure](#phase-8-structure)
- [Supporting Modules](#supporting-modules)

---

## Phase 1: Foundation

Foundation phase provides core file system operations, metadata management, token counting, and dependency tracking.

### FileSystemManager

**Location:** `src/cortex/file_system.py`

**Description:**
Manages file I/O operations with safety features including file locking, content hashing, markdown section parsing, and path validation.

**Key Classes:**

- `FileSystemManager` - Core file system operations with safety guarantees

**Public Methods:**

```python
# Initialization
__init__(self, project_root: Path)

# File Operations
async def read_file(self, file_path: Path) -> tuple[str, str]
async def write_file(self, file_path: Path, content: str, expected_hash: str | None = None) -> str
async def file_exists(self, file_path: Path) -> bool
async def get_file_size(self, file_path: Path) -> int
async def get_modification_time(self, file_path: Path) -> float

# Path Validation
def validate_path(self, file_path: Path) -> bool

# Hash & Sections
def compute_hash(self, content: str) -> str
def parse_sections(self, content: str) -> list[dict[str, str | int]]

# Locking & Cleanup
async def ensure_directory(self, dir_path: Path)
async def cleanup_locks(self)
```

**Key Features:**

- SHA-256 hashing for conflict detection
- File locking with 5-second timeout
- Git conflict marker detection
- Markdown section parsing with line ranges
- Path validation against project root (prevents directory traversal)

**Dependencies:** `pathlib`, `aiofiles`, `hashlib`, `re`

**Example Usage:**

```python
fs_manager = FileSystemManager(Path("/project"))

# Read file with hash
content, content_hash = await fs_manager.read_file(Path("memory-bank/projectBrief.md"))

# Write with conflict detection
new_hash = await fs_manager.write_file(
    Path("memory-bank/activeContext.md"),
    "Updated content",
    expected_hash=content_hash
)

# Parse sections
sections = fs_manager.parse_sections(content)
```

---

### MetadataIndex

**Location:** `src/cortex/metadata_index.py`

**Description:**
Manages `.memory-bank-index` file with JSON-based storage, atomic writes, and corruption recovery. Serves as the single source of truth for all file metadata.

**Key Classes:**

- `MetadataIndex` - Central metadata management

**Public Methods:**

```python
# Initialization & Persistence
__init__(self, project_root: Path)
async def load(self) -> dict[str, object]
async def save()

# File Metadata
async def update_file_metadata(
    self,
    file_name: str,
    path: Path,
    exists: bool,
    size_bytes: int,
    token_count: int,
    content_hash: str,
    sections: list[dict[str, object]],
    change_source: str = "internal"
)
async def get_file_metadata(self, file_name: str) -> dict[str, object] | None
async def get_all_files_metadata(self) -> dict[str, dict[str, object]]
async def remove_file(self, file_name: str)

# Querying
async def list_all_files(self) -> list[str]
async def file_exists_in_index(self, file_name: str) -> bool
async def get_stats(self) -> dict[str, object]

# Version History
async def add_version_to_history(self, file_name: str, version_meta: dict[str, object])

# Dependencies & Analytics
async def update_dependency_graph(self, graph_dict: dict[str, object])
async def get_dependency_graph(self) -> dict[str, object]
async def get_file_metadata(self, file_name: str) -> dict[str, object] | None
async def increment_read_count(self, file_name: str)
async def update_usage_analytics()

# Testing/Debugging
def get_data(self) -> dict[str, object] | None
```

**Schema Version:** 1.0.0

**Index Structure:**

```json
{
  "schema_version": "1.0.0",
  "created_at": "ISO timestamp",
  "last_updated": "ISO timestamp",
  "project_root": "path",
  "memory_bank_dir": "path",
  "files": {
    "filename.md": {
      "path": "absolute/path",
      "exists": true,
      "size_bytes": 1024,
      "token_count": 500,
      "content_hash": "sha256:...",
      "read_count": 0,
      "write_count": 1,
      "current_version": 1,
      "version_history": [],
      "sections": [],
      "last_modified": "ISO timestamp",
      "last_read": "ISO timestamp"
    }
  },
  "dependency_graph": {
    "nodes": [],
    "edges": [],
    "progressive_loading_order": []
  },
  "usage_analytics": {
    "total_reads": 0,
    "total_writes": 0,
    "files_by_read_frequency": [],
    "files_by_write_frequency": [],
    "last_session_start": "ISO timestamp",
    "sessions_count": 0
  },
  "totals": {
    "total_files": 0,
    "total_size_bytes": 0,
    "total_tokens": 0,
    "last_full_scan": "ISO timestamp"
  }
}
```

**Key Features:**

- Atomic writes (write-to-temp, then rename)
- Automatic corruption recovery
- Usage analytics tracking
- Version history management
- Type-safe JSON handling with proper casting

---

### TokenCounter

**Location:** `src/cortex/token_counter.py`

**Description:**
Accurate token counting using tiktoken library for OpenAI-compatible models. Enables precise context budgeting.

**Key Classes:**

- `TokenCounter` - Token counting with caching

**Public Methods:**

```python
# Initialization
__init__(self, model: str = "cl100k_base")

# Token Counting
def count_tokens(self, text: str | None) -> int
def count_tokens_with_cache(self, text: str, content_hash: str) -> int
async def count_tokens_in_file(self, file_path: Path) -> int
def count_tokens_sections(self, content: str, sections: list[dict[str, object]]) -> dict[str, object]

# Analysis
def estimate_context_size(self, file_tokens: dict[str, int]) -> dict[str, object]
def parse_markdown_sections(self, content: str | None) -> list[dict[str, object]]
def content_hash(self, content: str | None) -> str

# Caching
def clear_cache()
def get_cache_size(self) -> int

# Properties
@property
def encoding() -> Encoding
```

**Supported Models:**

- `cl100k_base` - GPT-4, GPT-3.5-turbo, text-embedding-ada-002 (default)
- `p50k_base` - Codex models
- `o200k_base` - GPT-4o models

**Key Features:**

- Content-based caching for performance
- Per-section token counting with percentages
- Context size estimation with cost warnings
- Markdown section parsing
- SHA-256 content hashing

**Example Usage:**

```python
counter = TokenCounter(model="cl100k_base")

# Count tokens
tokens = counter.count_tokens("Some text content")

# Estimate context size
file_tokens = {"projectBrief.md": 500, "activeContext.md": 800}
estimate = counter.estimate_context_size(file_tokens)
# Returns: total_tokens, estimated_cost_gpt4, warnings

# Count per section
sections = counter.count_tokens_sections(content, section_metadata)
```

---

### DependencyGraph

**Location:** `src/cortex/dependency_graph.py`

**Description:**
Manages file dependency relationships and loading order. Combines static Memory Bank structure dependencies with dynamic link-based dependencies from Phase 2.

**Key Classes:**

- `DependencyGraph` - Dependency relationship management
- `FileDependencyInfo` (TypedDict) - Dependency metadata structure

**Public Methods:**

```python
# Initialization
__init__(self)

# Loading Order
def compute_loading_order(self, files: list[str] | None = None) -> list[str]
def get_minimal_context(self, target_file: str) -> list[str]

# Dependency Queries
def get_dependencies(self, file_name: str) -> list[str]
def get_dependents(self, file_name: str) -> list[str]
def get_transclusion_order(self, start_file: str) -> list[str]

# Categories
def get_file_category(self, file_name: str) -> str
def get_file_priority(self, file_name: str) -> int
def get_files_by_category(self, category: str) -> list[str]

# Dynamic Dependencies (Phase 2+)
def add_dynamic_dependency(self, from_file: str, to_file: str)
def remove_dynamic_dependency(self, from_file: str, to_file: str)
def clear_dynamic_dependencies(self, file_name: str | None = None)
async def build_from_links(self, memory_bank_dir: Path, link_parser: LinkParser)
def add_link_dependency(self, source_file: str, target_file: str, link_type: str = "reference")
def get_link_type(self, source_file: str, target_file: str) -> str | None

# Cycle Detection
def has_circular_dependency(self) -> bool
def detect_cycles(self) -> list[list[str]]

# Export & Analysis
def to_dict(self) -> dict[str, object]
def to_mermaid(self) -> str
def get_all_files(self) -> list[str]
def get_transclusion_graph(self) -> dict[str, object]
def get_reference_graph(self) -> dict[str, object]
def get_graph_dict(self) -> dict[str, object]
```

**Static Dependencies:**
Memory Bank files have predefined dependency relationships:

- `memorybankinstructions.md` (priority 0) - Meta information, loaded first
- `projectBrief.md` (priority 1) - Foundation
- `productContext.md`, `systemPatterns.md`, `techContext.md` (priority 2) - Context layers
- `activeContext.md` (priority 3) - Depends on context files
- `progress.md` (priority 4) - Status, depends on active context

**File Categories:**

- `meta` - Metadata and instructions
- `foundation` - Core project information
- `context` - Various context documents
- `active` - Current work context
- `status` - Progress tracking

**Key Features:**

- Topological sorting for optimal loading order
- Transitive dependency calculation for minimal context
- Cycle detection with DFS
- Link type tracking (reference vs. transclusion)
- Mermaid diagram export
- Hybrid static/dynamic dependency model

**Example Usage:**

```python
graph = DependencyGraph()

# Get loading order
order = graph.compute_loading_order()
# Returns: ["memorybankinstructions.md", "projectBrief.md", ...]

# Get minimal context for a file
context = graph.get_minimal_context("activeContext.md")
# Returns dependencies in correct order

# Check for cycles
has_cycles = graph.has_circular_dependency()
```

---

### VersionManager

**Location:** `src/cortex/version_manager.py`

**Description:**
Manages version history for memory bank files with full snapshots, automatic pruning, and rollback capability.

**Key Classes:**

- `VersionManager` - Version snapshot and history management

**Public Methods:**

```python
# Initialization
__init__(self, project_root: Path, keep_versions: int = 10)

# Snapshots
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
    change_description: str | None = None
) -> dict[str, object]

# Rollback
async def get_snapshot_content(self, snapshot_path: Path) -> str
async def rollback_to_version(
    self,
    file_path: Path,
    version: int
) -> tuple[str, dict[str, object]]

# Management
async def get_version_history(self, file_name: str) -> list[dict[str, object]]
async def list_all_snapshots(self) -> dict[str, list[str]]
async def cleanup_old_versions()
```

**Snapshot Storage:**

- Directory: `.memory-bank-history/`
- Naming: `{filename}_v{version}.md`
- Full content snapshots (not diffs)
- Version metadata includes: timestamp, hash, size, tokens, change type, description

**Key Features:**

- Automatic pruning to keep last N versions (default: 10)
- Full content snapshots for simplicity
- Change type tracking (created, modified, rollback)
- Section-level change tracking
- Metadata preservation

---

### Migration

**Location:** `src/cortex/migration.py`

**Description:**
Handles auto-migration between versions, schema upgrades, and data transformations.

**Key Classes:**

- `MigrationManager` - Version migration and schema upgrades

---

### FileWatcher

**Location:** `src/cortex/file_watcher.py`

**Description:**
Detects external changes to memory bank files for conflict detection and external modification tracking.

**Key Classes:**

- `FileWatcher` - File system change detection

---

### Exceptions

**Location:** `src/cortex/exceptions.py`

**Description:**
Custom exception hierarchy for Cortex with domain-specific error types.

**Exception Classes:**

```python
# Base
class MemoryBankError(Exception) - Base for all Memory Bank errors

# File Operations
class FileConflictError - File modified externally during write
class FileLockTimeoutError - Cannot acquire file lock
class GitConflictError - Git conflict markers detected
class FileOperationError - General file operation failure

# Index & Metadata
class IndexCorruptedError - Metadata index corrupted
class ValidationError - Validation failed
class TokenLimitExceededError - Token budget exceeded

# Migration
class MigrationFailedError - Migration operation failed

# Rules (Phase 4+)
class RulesError - Base for rules errors
class RulesIndexingError - Rule indexing failed
class SharedRulesError - Shared rules operation failed
class SharedRulesGitError - Git operation on shared rules failed

# Refactoring (Phase 5+)
class RefactoringError - Base for refactoring errors
class RefactoringValidationError - Refactoring validation failed
class RefactoringExecutionError - Refactoring execution failed
class RollbackError - Rollback operation failed
class ApprovalError - Approval management failed
class LearningError - Learning engine error

# Structure (Phase 8)
class StructureError - Base for structure errors
class StructureMigrationError - Structure migration failed
class SymlinkError - Symlink operations failed
```

---

## Phase 2: DRY Linking

Phase 2 implements transclusion and DRY (Don't Repeat Yourself) linking for including content across files without duplication.

### LinkParser

**Location:** `src/cortex/link_parser.py`

**Description:**
Extracts markdown links and transclusion directives from content for Phase 2 DRY linking.

**Key Classes:**

- `LinkParser` - Link and transclusion extraction

**Public Methods:**

```python
# Initialization
__init__(self)

# Parsing
async def parse_file(self, content: str) -> dict[str, list[dict[str, object]]]

# Link Analysis
def parse_link_target(self, target: str) -> tuple[str, str | None]
def has_transclusions(self, content: str) -> bool

# Link Detection
async def find_all_links(self, directory: Path) -> dict[str, object]
def extract_internal_links(self, content: str) -> list[dict[str, object]]
```

**Supported Link Formats:**

1. Markdown links: `[text](target.md)` or `[text](target.md#section)`
2. Transclusion directives: `{{include: file.md}}` or `{{include: file.md#section|options}}`

**Return Structure:**

```json
{
  "markdown_links": [
    {
      "text": "Link text",
      "target": "file.md",
      "section": null,
      "line": 15,
      "type": "reference"
    }
  ],
  "transclusions": [
    {
      "target": "file.md",
      "section": "Section Name",
      "options": {"lines": 5, "recursive": true},
      "line": 42,
      "type": "transclusion"
    }
  ]
}
```

**Key Features:**

- Extracts both markdown links and transclusion directives
- Filters internal links only (ignores HTTP/HTTPS/mailto)
- Tracks line numbers for error reporting
- Section anchor support
- Transclusion option parsing

---

### TransclusionEngine

**Location:** `src/cortex/transclusion_engine.py`

**Description:**
Resolves `{{include:}}` directives recursively with circular dependency detection and content caching.

**Key Classes:**

- `TransclusionEngine` - Transclusion resolution
- `CircularDependencyError` - Circular transclusion detected
- `MaxDepthExceededError` - Depth limit exceeded

**Public Methods:**

```python
# Initialization
__init__(
    self,
    file_system: FileSystemManager,
    link_parser: LinkParser,
    max_depth: int = 5,
    cache_enabled: bool = True
)

# Resolution
async def resolve_content(
    self,
    content: str,
    source_file: str,
    depth: int = 0
) -> str

async def resolve_transclusion(
    self,
    target_file: str,
    source_file: str,
    section: str | None = None,
    options: dict[str, object] | None = None
) -> str

# Caching
def clear_cache()
def get_cache_stats(self) -> dict[str, object]

# Dependencies
async def get_transclusion_dependencies(self, file_path: Path) -> list[str]
def detect_circular_dependency(self, source: str, target: str) -> bool
```

**Circular Dependency Detection:**

- Tracks resolution stack during recursive resolution
- Raises `CircularDependencyError` if cycle detected
- Maximum depth limit (default: 5) prevents infinite recursion

**Caching Strategy:**

- Key: (file, section, options_tuple)
- Value: resolved content
- Improves performance for repeated inclusions
- Cache statistics tracking

**Example Usage:**

```python
engine = TransclusionEngine(file_system, link_parser, max_depth=5)

# Resolve all transclusions in content
resolved = await engine.resolve_content(
    content,
    source_file="activeContext.md"
)

# Resolve single transclusion
single = await engine.resolve_transclusion(
    target_file="systemPatterns.md",
    source_file="activeContext.md",
    section="Architecture"
)
```

---

### LinkValidator

**Location:** `src/cortex/link_validator.py`

**Description:**
Validates link integrity and detects broken or invalid links across the memory bank.

**Key Classes:**

- `LinkValidator` - Link validation

**Public Methods:**

```python
# Validation
async def validate_links(self, file_path: Path) -> dict[str, object]
async def validate_all_links(self, memory_bank_dir: Path) -> dict[str, object]

# Analysis
def find_orphaned_files(self, all_files: list[str], all_links: list[dict[str, object]]) -> list[str]
def find_broken_links(self, links: list[dict[str, object]], all_files: list[str]) -> list[dict[str, object]]
```

---

## Phase 3: Validation

Phase 3 provides comprehensive validation, duplication detection, and quality metrics.

### SchemaValidator

**Location:** `src/cortex/schema_validator.py`

**Description:**
Validates Memory Bank files against defined schemas ensuring proper structure and required sections.

**Key Classes:**

- `SchemaValidator` - Schema validation
- `ValidationResult` (TypedDict) - Validation result structure
- `ValidationError` (TypedDict) - Error structure

**Public Methods:**

```python
# Initialization
__init__(self, config_path: Path | None = None)

# Validation
async def validate_file(self, file_name: str, content: str) -> ValidationResult
async def validate_all_files(self, files_content: dict[str, str]) -> dict[str, ValidationResult]

# Analysis
def get_file_schema(self, file_name: str) -> dict[str, object] | None
def suggest_missing_sections(self, file_name: str, content: str) -> list[str]
```

**Default Schemas:**
Each core Memory Bank file has required and recommended sections:

```python
"projectBrief.md":
  required: ["Project Overview", "Goals", "Core Requirements", "Success Criteria"]
  recommended: ["Constraints", "Key Decisions"]

"productContext.md":
  required: ["Product Overview", "Target Users", "Key Features"]
  recommended: ["User Stories", "Market Context"]

"activeContext.md":
  required: ["Current Focus", "Recent Changes", "Next Steps"]
  recommended: ["Active Decisions", "Important Patterns"]

"systemPatterns.md":
  required: ["Architecture", "Design Patterns", "Component Relationships"]
  recommended: ["Critical Paths", "Integration Points"]

"techContext.md":
  required: ["Technology Stack", "Dependencies", "Development Setup"]
  recommended: ["Build Process", "Testing Strategy"]

"progress.md":
  required: ["What Works", "What's Left"]
  recommended: ["Known Issues", "Recent Milestones"]
```

**Validation Result:**

```python
{
  "valid": bool,
  "errors": [
    {
      "type": "missing_required_section",
      "severity": "error",
      "message": "Missing required section: Goals",
      "suggestion": "Add '## Goals' section"
    }
  ],
  "warnings": [...],
  "score": 0-100  # Validation score
}
```

---

### DuplicationDetector

**Location:** `src/cortex/duplication_detector.py`

**Description:**
Detects duplicate or highly similar content across Memory Bank files and suggests refactoring opportunities.

**Key Classes:**

- `DuplicationDetector` - Duplicate detection

**Public Methods:**

```python
# Initialization
__init__(
    self,
    similarity_threshold: float = 0.85,
    min_content_length: int = 50
)

# Scanning
async def scan_all_files(self, files_content: dict[str, str]) -> dict[str, object]
def compare_sections(self, content1: str, content2: str) -> float

# Analysis
def find_exact_duplicates(self, sections: dict[str, list[tuple[str, str]]]) -> list[dict[str, object]]
def find_similar_content(self, sections: dict[str, list[tuple[str, str]]]) -> list[dict[str, object]]
def extract_sections(self, content: str) -> list[tuple[str, str]]
```

**Configuration:**

- `similarity_threshold` (default: 0.85) - Score 0.0-1.0 to flag as duplicate
- `min_content_length` (default: 50 chars) - Minimum chars to check

**Scan Result:**

```json
{
  "duplicates_found": 3,
  "exact_duplicates": [
    {
      "file1": "activeContext.md",
      "section1": "Architecture",
      "file2": "systemPatterns.md",
      "section2": "Architecture",
      "similarity": 1.0
    }
  ],
  "similar_content": [...]
}
```

**Key Features:**

- Section-level duplication detection
- Content normalization before comparison
- Similarity scoring using difflib
- Configurable thresholds
- Refactoring suggestions

---

### QualityMetrics

**Location:** `src/cortex/quality_metrics.py`

**Description:**
Calculates comprehensive quality scores and health metrics for Memory Bank files.

**Key Classes:**

- `QualityMetrics` - Quality metric calculation

**Public Methods:**

```python
# Initialization
__init__(
    self,
    schema_validator: SchemaValidator,
    metadata_index: MetadataIndex | None = None
)

# Scoring
async def calculate_overall_score(
    self,
    files_content: dict[str, str],
    files_metadata: dict[str, dict[str, object]],
    duplication_data: dict[str, object],
    link_validation: dict[str, object] | None = None
) -> dict[str, object]

async def score_file(
    self,
    file_name: str,
    content: str,
    metadata: dict[str, object]
) -> dict[str, object]

# Component Scores
async def _calculate_completeness(self, files_content: dict[str, str]) -> float
def _calculate_consistency(self, duplication_data: dict[str, object], link_validation: dict[str, object] | None) -> float
def _calculate_freshness(self, files_metadata: dict[str, dict[str, object]]) -> float
def _calculate_structure(self, files_content: dict[str, str]) -> float
def _calculate_token_efficiency(self, files_metadata: dict[str, dict[str, object]]) -> float
```

**Overall Score Calculation:**
Weighted combination of five factors:

- **Completeness** (25%) - All required sections present
- **Consistency** (25%) - No duplications, valid links
- **Freshness** (15%) - Recent updates
- **Structure** (20%) - Proper formatting, heading hierarchy
- **Token Efficiency** (15%) - Content density

**Result:**

```json
{
  "overall_score": 0-100,
  "grade": "A/B/C/D/F",
  "status": "healthy/warning/critical",
  "breakdown": {
    "completeness": 95.0,
    "consistency": 85.0,
    "freshness": 70.0,
    "structure": 90.0,
    "token_efficiency": 88.0
  },
  "issues": [...],
  "recommendations": [...]
}
```

---

### ValidationConfig

**Location:** `src/cortex/validation_config.py`

**Description:**
Configuration for validation strategies and thresholds.

---

## Phase 4: Optimization

Phase 4 provides intelligent context selection and progressive loading within token budgets.

### ContextOptimizer

**Location:** `src/cortex/context_optimizer.py`

**Description:**
Selects optimal content subsets that fit within token budgets while maximizing information value. Delegates to OptimizationStrategies.

**Key Classes:**

- `ContextOptimizer` - Context selection orchestration

**Public Methods:**

```python
# Initialization
__init__(
    self,
    token_counter: TokenCounter,
    relevance_scorer: RelevanceScorer,
    dependency_graph: DependencyGraph,
    mandatory_files: list[str] | None = None
)

# Optimization
async def optimize_context(
    self,
    task_description: str,
    files_content: dict[str, str],
    files_metadata: dict[str, dict[str, object]],
    token_budget: int,
    strategy: str = "dependency_aware",
    quality_scores: dict[str, float] | None = None
) -> OptimizationResult

async def optimize_sections(
    self,
    task_description: str,
    file_content: str,
    sections: list[dict[str, object]],
    token_budget: int,
    strategy: str = "relevance"
) -> dict[str, object]
```

**Strategies:**

- `priority` - Include files by priority order
- `dependency_aware` - Include dependencies of selected files
- `section_level` - Select individual sections
- `hybrid` - Combine multiple strategies

**Result:**

```python
OptimizationResult(
    selected_files: list[str],
    selected_sections: dict[str, list[str]],
    total_tokens: int,
    utilization: float,  # 0.0-1.0
    excluded_files: list[str],
    strategy_used: str,
    metadata: dict[str, object]
)
```

**Key Features:**

- Multi-strategy optimization
- Mandatory file inclusion
- Dependency-aware selection
- Section-level granularity
- Quality score consideration

---

### OptimizationStrategies

**Location:** `src/cortex/optimization_strategies.py`

**Description:**
Implementation of specific optimization strategies for context selection.

**Key Classes:**

- `OptimizationStrategies` - Strategy implementations
- `OptimizationResult` (dataclass) - Optimization result

---

### RelevanceScorer

**Location:** `src/cortex/relevance_scorer.py`

**Description:**
Scores files by relevance to a task description for intelligent prioritization.

**Key Classes:**

- `RelevanceScorer` - Task-based relevance scoring

**Public Methods:**

```python
# Initialization
__init__(self)

# Scoring
async def score_files(
    self,
    task_description: str,
    files_content: dict[str, str],
    files_metadata: dict[str, dict[str, object]],
    quality_scores: dict[str, float] | None = None
) -> dict[str, dict[str, float | str]]

async def score_file(
    self,
    task_description: str,
    file_name: str,
    content: str,
    metadata: dict[str, object]
) -> dict[str, float | str]
```

**Scoring Factors:**

- Content similarity to task description
- File metadata (size, access frequency)
- Quality metrics
- Dependency relationships

---

### ProgressiveLoader

**Location:** `src/cortex/progressive_loader.py`

**Description:**
Loads context incrementally respecting dependencies and token budgets.

**Key Classes:**

- `ProgressiveLoader` - Incremental context loading

---

### SummarizationEngine

**Location:** `src/cortex/summarization_engine.py`

**Description:**
Summarizes content to reduce token usage while preserving key information.

**Key Classes:**

- `SummarizationEngine` - Content summarization

---

### RulesManager

**Location:** `src/cortex/rules_manager.py`

**Description:**
Manages local rules (.cursor/rules/) for project-specific guidelines.

**Key Classes:**

- `RulesManager` - Local rules management

---

### RulesIndexer

**Location:** `src/cortex/rules_indexer.py`

**Description:**
Indexes rules from directories for efficient lookup and application.

**Key Classes:**

- `RulesIndexer` - Rules indexing and categorization

---

### OptimizationConfig

**Location:** `src/cortex/optimization_config.py`

**Description:**
Configuration for optimization strategies and parameters.

---

## Phase 5: Self-Evolution

Phase 5 implements pattern analysis, intelligent refactoring, and learning from feedback.

### PatternAnalyzer

**Location:** `src/cortex/pattern_analyzer.py`

**Description:**
Analyzes code and documentation patterns to identify inconsistencies and improvement opportunities.

**Key Classes:**

- `PatternAnalyzer` - Pattern identification and analysis

---

### StructureAnalyzer

**Location:** `src/cortex/structure_analyzer.py`

**Description:**
Analyzes project structure and organization patterns.

**Key Classes:**

- `StructureAnalyzer` - Structure analysis

---

### InsightEngine

**Location:** `src/cortex/insight_engine.py`

**Description:**
Generates insights about the memory bank content and recommendations.

**Key Classes:**

- `InsightEngine` - Insight generation

---

### RefactoringEngine

**Location:** `src/cortex/refactoring_engine.py`

**Description:**
Generates intelligent refactoring suggestions based on analysis and patterns.

**Key Classes:**

- `RefactoringEngine` - Refactoring suggestion generation
- `RefactoringSuggestion` (dataclass) - Suggestion structure
- `RefactoringAction` (dataclass) - Individual action
- `RefactoringType` (Enum) - Types of refactoring
- `RefactoringPriority` (Enum) - Priority levels

**Refactoring Types:**

```python
class RefactoringType(Enum):
    CONSOLIDATION = "consolidation"  # Merge related files
    SPLIT = "split"                   # Split large files
    REORGANIZATION = "reorganization" # Restructure layout
    TRANSCLUSION = "transclusion"    # Use DRY linking
    RENAME = "rename"                # Rename files
    MERGE = "merge"                  # Merge sections
```

**Priority Levels:**

```python
class RefactoringPriority(Enum):
    CRITICAL = "critical"      # Significant issues
    HIGH = "high"              # Important improvements
    MEDIUM = "medium"          # Moderate improvements
    LOW = "low"                # Nice to have
    OPTIONAL = "optional"      # Minor optimizations
```

**Public Methods:**

```python
# Generation
async def generate_suggestions(
    self,
    files_content: dict[str, str],
    files_metadata: dict[str, dict[str, object]],
    analysis_results: dict[str, object]
) -> list[RefactoringSuggestion]

async def generate_suggestion(
    self,
    suggestion_type: RefactoringType,
    affected_files: list[str],
    reasoning: str,
    actions: list[dict[str, object]],
    priority: RefactoringPriority = RefactoringPriority.MEDIUM
) -> RefactoringSuggestion
```

**Suggestion Structure:**

```python
RefactoringSuggestion(
    suggestion_id: str,
    refactoring_type: RefactoringType,
    priority: RefactoringPriority,
    title: str,
    description: str,
    reasoning: str,
    affected_files: list[str],
    actions: list[RefactoringAction],
    estimated_impact: dict[str, object],
    confidence_score: float  # 0-1
)
```

---

### ConsolidationDetector

**Location:** `src/cortex/consolidation_detector.py`

**Description:**
Detects opportunities to consolidate related content into single files.

**Key Classes:**

- `ConsolidationDetector` - Consolidation opportunity detection

---

### SplitRecommender

**Location:** `src/cortex/split_recommender.py`

**Description:**
Recommends splitting large files into focused, manageable pieces.

**Key Classes:**

- `SplitRecommender` - Split recommendations

---

### SplitAnalyzer

**Location:** `src/cortex/split_analyzer.py`

**Description:**
Analyzes content structure to identify good split points.

**Key Classes:**

- `SplitAnalyzer` - Split point analysis

---

### ReorganizationPlanner

**Location:** `src/cortex/reorganization_planner.py`

**Description:**
Plans large-scale restructuring of memory bank organization.

**Key Classes:**

- `ReorganizationPlanner` - Reorganization planning

---

### RefactoringExecutor

**Location:** `src/cortex/refactoring_executor.py`

**Description:**
Safely executes refactoring suggestions with rollback capability.

**Key Classes:**

- `RefactoringExecutor` - Refactoring execution

**Public Methods:**

```python
# Execution
async def execute_refactoring(
    self,
    suggestion: RefactoringSuggestion,
    file_system: FileSystemManager,
    metadata_index: MetadataIndex
) -> dict[str, object]

# Validation
async def validate_suggestion(
    self,
    suggestion: RefactoringSuggestion
) -> bool

# Rollback
async def rollback_refactoring(
    self,
    refactoring_id: str
) -> dict[str, object]
```

---

### ExecutionValidator

**Location:** `src/cortex/execution_validator.py`

**Description:**
Validates refactoring suggestions before execution.

**Key Classes:**

- `ExecutionValidator` - Pre-execution validation

---

### ApprovalManager

**Location:** `src/cortex/approval_manager.py`

**Description:**
Manages approval workflows for refactoring suggestions.

**Key Classes:**

- `ApprovalManager` - Approval management

**Public Methods:**

```python
# Approval
async def request_approval(
    self,
    suggestion: RefactoringSuggestion
) -> str  # approval_id

async def approve_suggestion(
    self,
    suggestion_id: str,
    approver: str,
    comment: str | None = None
) -> dict[str, object]

async def reject_suggestion(
    self,
    suggestion_id: str,
    approver: str,
    reason: str
) -> dict[str, object]

# Status
async def get_approval_status(self, suggestion_id: str) -> dict[str, object]
```

---

### RollbackManager

**Location:** `src/cortex/rollback_manager.py`

**Description:**
Manages safe rollback of executed refactorings.

**Key Classes:**

- `RollbackManager` - Rollback operations

**Public Methods:**

```python
# Rollback
async def rollback_refactoring(
    self,
    refactoring_id: str,
    file_system: FileSystemManager
) -> dict[str, object]

# Status
async def get_rollback_status(self, refactoring_id: str) -> dict[str, object]
async def list_rollbackable_refactorings(self) -> list[dict[str, object]]
```

---

### LearningEngine

**Location:** `src/cortex/learning_engine.py`

**Description:**
Learns from user feedback to improve suggestions over time.

**Key Classes:**

- `LearningEngine` - Learning and adaptation

**Public Methods:**

```python
# Feedback Recording
async def record_feedback(
    self,
    suggestion_id: str,
    suggestion_type: str,
    feedback_type: str,  # "helpful", "not_helpful", "incorrect"
    comment: str | None = None,
    suggestion_confidence: float = 0.5,
    was_approved: bool = False,
    was_applied: bool = False,
    suggestion_details: dict[str, object] | None = None
) -> dict[str, object]

# Pattern Learning
async def update_patterns(
    self,
    feedback: FeedbackRecord,
    suggestion_details: dict[str, object]
) -> None

# Analysis
async def get_learning_stats(self) -> dict[str, object]
async def get_successful_patterns(self) -> list[LearnedPattern]
async def get_failed_patterns(self) -> list[LearnedPattern]

# Adaptation
async def adjust_suggestion_thresholds(
    self,
    suggestion_type: str,
    performance_data: dict[str, object]
) -> None
```

**Feedback Types:**

- `helpful` - Suggestion was valuable
- `not_helpful` - Suggestion wasn't useful
- `incorrect` - Suggestion was wrong

---

### LearningDataManager

**Location:** `src/cortex/learning_data_manager.py`

**Description:**
Manages persistence and retrieval of learning data.

**Key Classes:**

- `LearningDataManager` - Learning data persistence
- `FeedbackRecord` (dataclass) - Feedback structure
- `LearnedPattern` (dataclass) - Learned pattern structure

---

### AdaptationConfig

**Location:** `src/cortex/adaptation_config.py`

**Description:**
Configuration for learning and adaptation strategies.

---

## Phase 6: Shared Rules

Phase 6 integrates shared rules via Git submodules for cross-project consistency.

### SharedRulesManager

**Location:** `src/cortex/shared_rules_manager.py`

**Description:**
Manages shared rules repositories via Git submodules for project consistency across teams.

**Key Classes:**

- `SharedRulesManager` - Shared rules management

**Public Methods:**

```python
# Initialization
async def initialize_shared_rules(
    self,
    repo_url: str,
    submodule_path: str = "rules/shared"
) -> dict[str, object]

# Synchronization
async def sync_shared_rules(self) -> dict[str, object]
async def fetch_updates(self) -> dict[str, object]
async def push_local_rules(self) -> dict[str, object]

# Rules Management
async def get_shared_rules(self) -> dict[str, object]
async def merge_rules(
    self,
    local_rules: dict[str, object],
    shared_rules: dict[str, object]
) -> dict[str, object]

# Status
async def get_shared_rules_status(self) -> dict[str, object]
```

---

### ContextDetector

**Location:** `src/cortex/context_detector.py`

**Description:**
Detects application context to apply appropriate shared rules.

**Key Classes:**

- `ContextDetector` - Context detection

---

## Phase 7: Architecture

Architecture phase provides core infrastructure and protocols for the system.

### Protocols

**Location:** `src/cortex/protocols.py`

**Description:**
Protocol definitions for structural subtyping (PEP 544). Enable better abstraction and reduce circular dependencies.

**Key Protocols:**

```python
class FileSystemProtocol(Protocol):
    """Protocol for file system operations."""
    def validate_path(self, file_path: Path) -> bool
    async def read_file(self, file_path: Path) -> tuple[str, str]
    async def write_file(self, file_path: Path, content: str, expected_hash: str | None = None) -> str
    def compute_hash(self, content: str) -> str
    def parse_sections(self, content: str) -> list[dict[str, str | int]]
    async def file_exists(self, file_path: Path) -> bool
    async def cleanup_locks(self)

class MetadataIndexProtocol(Protocol):
    """Protocol for metadata index operations."""
    async def load(self) -> dict[str, object]
    async def save(self)
    async def update_file_metadata(...)
    async def get_file_metadata(self, file_name: str) -> dict[str, object] | None
    async def get_all_files_metadata(self) -> dict[str, dict[str, object]]
    async def increment_read_count(self, file_name: str)
    async def update_dependency_graph(self, graph_dict: dict[str, object])
    async def get_dependency_graph(self) -> dict[str, object]

class TokenCounterProtocol(Protocol):
    """Protocol for token counting."""
    def count_tokens(self, text: str) -> int
    def count_tokens_with_cache(self, text: str, content_hash: str) -> int
    def estimate_context_size(self, file_tokens: dict[str, int]) -> dict[str, object]

class DependencyGraphProtocol(Protocol):
    """Protocol for dependency management."""
    def compute_loading_order(self, files: list[str] | None = None) -> list[str]
    def get_dependencies(self, file_name: str) -> list[str]
    def get_dependents(self, file_name: str) -> list[str]
    def has_circular_dependency(self) -> bool
    def to_dict(self) -> dict[str, object]
```

---

### Container

**Location:** `src/cortex/container.py`

**Description:**
Dependency injection container for service management and lifecycle.

**Key Classes:**

- `Container` - Service dependency injection

---

### GraphAlgorithms

**Location:** `src/cortex/graph_algorithms.py`

**Description:**
Graph algorithms for dependency analysis including cycle detection, topological sorting, and path finding.

**Key Classes:**

- `GraphAlgorithms` - Static graph algorithm methods

**Public Methods:**

```python
@staticmethod
def detect_cycles(
    nodes: list[str],
    get_dependencies_fn: Callable[[str], list[str]]
) -> list[list[str]]

@staticmethod
def has_cycle_dfs(
    node: str,
    visited: set[str],
    rec_stack: set[str],
    get_dependencies_fn: Callable[[str], list[str]]
) -> bool

@staticmethod
def topological_sort(
    nodes: list[str],
    get_dependencies_fn: Callable[[str], list[str]]
) -> list[str]

@staticmethod
def get_transitive_dependencies(
    start_node: str,
    get_dependencies_fn: Callable[[str], list[str]]
) -> set[str]

@staticmethod
def get_reachable_nodes(
    start_node: str,
    get_neighbors_fn: Callable[[str], list[str]]
) -> set[str]
```

**Algorithms:**

1. **Cycle Detection (DFS)** - O(V + E) detection of circular dependencies
2. **Topological Sort (Kahn's)** - O(V + E) ordering for dependency resolution
3. **Transitive Closure** - Find all indirect dependencies
4. **Reachability Analysis** - Find all reachable nodes from a start point

---

### LoggingConfig

**Location:** `src/cortex/logging_config.py`

**Description:**
Centralized logging configuration for the system.

---

### Responses

**Location:** `src/cortex/responses.py`

**Description:**
Standardized response formatting for MCP tools.

**Functions:**

```python
def success_response(data: dict[str, Any]) -> str:
    """Create standardized success response."""
    # Returns JSON with status="success"

def error_response(
    error: Exception,
    action_required: str | None = None,
    context: dict[str, Any] | None = None
) -> str:
    """Create standardized error response."""
    # Returns JSON with status="error", error details, and optional guidance
```

---

## Phase 8: Structure

Phase 8 manages standardized project structure with symlink integration for IDE support.

### StructureManager

**Location:** `src/cortex/structure_manager.py`

**Description:**
Manages standardized project structure including memory bank files, rules, plans, and Cursor IDE integration.

**Key Classes:**

- `StructureManager` - Project structure management

**Default Structure:**

```plaintext
.memory-bank/
├── knowledge/           # Memory bank documents
├── rules/              # Project rules
│   ├── local/         # Local project rules
│   └── shared/        # Shared rules (via git submodule)
├── plans/             # Active development plans
├── archived/          # Archived content
└── config/            # Configuration files

.cursor/               # Cursor IDE integration (symlinks)
├── memory-bank/      # → .memory-bank/knowledge/
├── rules/           # → .memory-bank/rules/
└── plans/           # → .memory-bank/plans/
```

**Public Methods:**

```python
# Initialization
__init__(self, project_root: Path)

# Setup
async def setup_project_structure(self) -> dict[str, object]

# Validation
async def validate_project_structure(self) -> dict[str, object]

# Symlinks
async def setup_cursor_symlinks(self) -> dict[str, object]
async def verify_symlinks(self) -> dict[str, object]

# Migration
async def migrate_structure(
    self,
    from_version: str,
    to_version: str
) -> dict[str, object]

# Reporting
async def get_structure_report(self) -> dict[str, object]
async def analyze_structure_quality(self) -> dict[str, object]
```

**Standard Knowledge Files:**

- `memorybankinstructions.md` - System instructions
- `projectBrief.md` - Project foundation
- `productContext.md` - Product context
- `activeContext.md` - Current work
- `systemPatterns.md` - Architecture
- `techContext.md` - Technical details
- `progress.md` - Progress tracking

---

### TemplateManager

**Location:** `src/cortex/template_manager.py`

**Description:**
Manages templates for memory bank files and plans.

**Key Classes:**

- `TemplateManager` - Template management

**Public Methods:**

```python
# Templates
async def get_templates(self) -> dict[str, str]
async def get_template(self, template_name: str) -> str
async def create_file_from_template(
    self,
    template_name: str,
    file_path: Path,
    variables: dict[str, str]
) -> dict[str, object]

# Template Management
async def list_available_templates(self) -> list[str]
async def register_custom_template(
    self,
    name: str,
    content: str
) -> dict[str, object]
```

**Template Modules (Phase 8):**

- `templates/memory_bank_instructions.py` - System instructions
- `templates/projectBrief.py` - Project foundation
- `templates/product_context.py` - Product context
- `templates/active_context.py` - Active context
- `templates/system_patterns.py` - Architecture patterns
- `templates/tech_context.py` - Technical context
- `templates/progress.py` - Progress template

---

## Supporting Modules

### Server

**Location:** `src/cortex/server.py`

**Description:**
MCP server instance for FastMCP integration.

```python
from mcp.server.fastmcp import FastMCP

# Create global server instance
mcp = FastMCP("memory-bank-helper")
```

**Purpose:**

- Central FastMCP server instance
- Tool registration point via `@mcp.tool()` decorator
- Resource handler registration

---

### Main

**Location:** `src/cortex/main.py`

**Description:**
Entry point for the MCP server with stdio transport and manager initialization.

**Functions:**

```python
async def get_managers() -> ManagersCollection:
    """Initialize all service managers."""

def main():
    """Entry point for MCP server."""
    # Initializes managers
    # Runs MCP server on stdio transport
```

---

### Resources

**Location:** `src/cortex/resources.py`

**Description:**
Resource definitions for MCP server including memory bank files and metadata.

---

### Guides

**Location:** `src/cortex/guides/`

Documentation guides for using the Memory Bank system:

- `guides/setup.py` - Setup instructions
- `guides/usage.py` - Usage guide
- `guides/benefits.py` - Benefits and value proposition
- `guides/structure.py` - Structure overview

---

### Managers Initialization

**Location:** `src/cortex/managers/initialization.py`

**Description:**
Orchestrates initialization of all service managers in dependency order.

**Key Function:**

```python
async def get_managers() -> ManagersCollection:
    """
    Initialize all service managers in correct order.

    Initialization order:
    1. FileSystemManager
    2. MetadataIndex
    3. TokenCounter
    4. DependencyGraph
    5. VersionManager
    6. MigrationManager
    7. FileWatcher
    8. LinkParser
    9. TransclusionEngine
    10. LinkValidator
    ... and more in dependency order
    """
```

---

## Cross-Module Dependencies

### Dependency Map

**Core Foundation (Phase 1):**

- FileSystemManager → None
- MetadataIndex → FileSystemManager
- TokenCounter → None
- DependencyGraph → GraphAlgorithms
- VersionManager → FileSystemManager
- Migration → FileSystemManager, MetadataIndex
- FileWatcher → FileSystemManager

**DRY Linking (Phase 2):**

- LinkParser → None
- TransclusionEngine → FileSystemManager, LinkParser
- LinkValidator → LinkParser

**Validation (Phase 3):**

- SchemaValidator → None
- DuplicationDetector → None
- QualityMetrics → SchemaValidator, MetadataIndex

**Optimization (Phase 4):**

- ContextOptimizer → TokenCounter, RelevanceScorer, DependencyGraph
- RelevanceScorer → None
- ProgressiveLoader → DependencyGraph, TokenCounter
- SummarizationEngine → TokenCounter
- RulesManager → FileSystemManager

**Self-Evolution (Phase 5):**

- PatternAnalyzer → None
- StructureAnalyzer → DependencyGraph
- InsightEngine → None
- RefactoringEngine → PatternAnalyzer, StructureAnalyzer
- ConsolidationDetector → DuplicationDetector
- SplitRecommender → QualityMetrics
- RefactoringExecutor → FileSystemManager, MetadataIndex, VersionManager
- ApprovalManager → None
- RollbackManager → VersionManager, FileSystemManager
- LearningEngine → LearningDataManager
- LearningDataManager → FileSystemManager

**Shared Rules (Phase 6):**

- SharedRulesManager → FileSystemManager
- ContextDetector → None

**Architecture (Phase 7):**

- GraphAlgorithms → None
- Protocols → None (pure interface definitions)
- Container → All services (dependency injection)
- LoggingConfig → None
- Responses → None

**Structure (Phase 8):**

- StructureManager → FileSystemManager
- TemplateManager → FileSystemManager

---

## Usage Patterns

### Initialization Pattern

```python
# Initialize core services in order
fs_manager = FileSystemManager(project_root)
metadata_index = MetadataIndex(project_root)
await metadata_index.load()

token_counter = TokenCounter()
dependency_graph = DependencyGraph()
version_manager = VersionManager(project_root)

# Initialize Phase 2+ services
link_parser = LinkParser()
transclusion_engine = TransclusionEngine(fs_manager, link_parser)

# Initialize Phase 3+ services
schema_validator = SchemaValidator()
quality_metrics = QualityMetrics(schema_validator)

# Initialize Phase 4+ services
relevance_scorer = RelevanceScorer()
context_optimizer = ContextOptimizer(
    token_counter,
    relevance_scorer,
    dependency_graph
)
```

### Error Handling Pattern

```python
try:
    content, hash = await fs_manager.read_file(file_path)
except FileNotFoundError:
    # Handle missing file
except PermissionError:
    # Handle path validation failure
except Exception as e:
    return error_response(e, action_required="Check file permissions")
```

### Response Pattern

```python
from .responses import success_response, error_response

# Success response
return success_response({
    "files_processed": 7,
    "total_tokens": 15000,
    "optimization_ratio": 0.85
})

# Error response
return error_response(
    ValueError("Invalid token budget"),
    action_required="Set token_budget to positive integer",
    context={"provided": -1000}
)
```

---

## Testing & Documentation

Each module includes:

- Type hints with 100% coverage
- Comprehensive docstrings
- Protocol definitions for interfaces
- Unit tests in `tests/unit/`
- Integration tests in `tests/integration/`

See `tests/` directory for examples and testing patterns.
