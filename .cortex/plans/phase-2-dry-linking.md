# Phase 2: DRY Linking and Transclusion

**Status:** Not Started
**Dependencies:** Phase 1 Complete ✅
**Estimated Effort:** 4-6 hours implementation + 2-3 hours testing

---

## Overview

Phase 2 introduces **DRY (Don't Repeat Yourself) linking** through markdown link parsing and **transclusion** for content reuse. This eliminates duplication across Memory Bank files while maintaining readability and allowing selective content inclusion.

---

## Goals

### Primary Goals

1. **Parse Markdown Links**: Detect and track `[text](file.md#section)` references
2. **Support Transclusion**: Enable `{{include: file.md#section}}` syntax for content embedding
3. **Dynamic Dependencies**: Build dependency graph from actual links (not static)
4. **Circular Detection**: Prevent infinite loops in transclusion
5. **Link Resolution**: Resolve links at read time with caching

### Secondary Goals

1. **Link Validation**: Detect broken links and missing sections
2. **Partial Inclusion**: Support including only specific sections
3. **Nested Transclusion**: Allow included content to include other content
4. **Performance**: Cache resolved content to minimize overhead

---

## Architecture

### New Modules (3 modules)

```text
src/cortex/
├── link_parser.py          (~250 lines) - Parse markdown links
├── transclusion_engine.py  (~350 lines) - Resolve and include content
└── link_validator.py       (~200 lines) - Validate link integrity
```

### Modified Modules

```text
src/cortex/
├── dependency_graph.py     (+150 lines) - Dynamic dependency building
├── main.py                 (+200 lines) - New MCP tools for linking
└── metadata_index.py       (+100 lines) - Track link metadata
```

---

## Implementation Plan

### Module 1: Link Parser (`link_parser.py`)

**Purpose:** Parse markdown files to extract links and transclusion directives

#### Link Parser Features

- Parse standard markdown links: `[text](target.md)`, `[text](target.md#section)`
- Parse transclusion syntax: `{{include: file.md}}`, `{{include: file.md#section}}`
- Support multiple transclusion formats:
  - `{{include: file.md}}` - Include entire file
  - `{{include: file.md#heading}}` - Include specific section
  - `{{include: file.md#heading|lines=5}}` - Include first N lines only
  - `{{include: file.md#heading|recursive=false}}` - Disable nested transclusion
- Extract link metadata:
  - Source file and line number
  - Target file and section
  - Link type (reference vs transclusion)
  - Link text/description

#### Link Parser API Design

```python
class LinkParser:
    """Parse markdown files to extract links and transclusion directives."""

    def __init__(self):
        """Initialize parser with regex patterns."""
        self.link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        self.transclusion_pattern = re.compile(
            r'\{\{include:\s*([^}|]+)(?:\|([^}]+))?\}\}'
        )

    async def parse_file(self, content: str) -> Dict[str, List]:
        """
        Parse file content for links and transclusions.

        Returns:
            {
                "markdown_links": [
                    {
                        "text": "See projectBrief",
                        "target": "projectBrief.md",
                        "section": None,
                        "line": 15,
                        "type": "reference"
                    }
                ],
                "transclusions": [
                    {
                        "target": "systemPatterns.md",
                        "section": "Architecture",
                        "options": {"lines": 5, "recursive": true},
                        "line": 42,
                        "type": "transclusion"
                    }
                ]
            }
        """

    def parse_link_target(self, target: str) -> Dict[str, str]:
        """
        Parse link target into file and section.

        Args:
            target: "file.md#section" or "file.md"

        Returns:
            {"file": "file.md", "section": "section"}
        """

    def parse_transclusion_options(self, options_str: str) -> Dict:
        """
        Parse transclusion options.

        Args:
            options_str: "lines=5|recursive=false"

        Returns:
            {"lines": 5, "recursive": False}
        """
```

#### Link Parser Implementation Steps

1. Define regex patterns for links and transclusions
2. Implement `parse_file()` to extract all links
3. Implement `parse_link_target()` to split file#section
4. Implement `parse_transclusion_options()` for option parsing
5. Add line number tracking for error reporting
6. Write unit tests for all parsing scenarios

---

### Module 2: Transclusion Engine (`transclusion_engine.py`)

**Purpose:** Resolve transclusions and include content from other files

#### Transclusion Engine Features

- Resolve transclusion directives recursively
- Cache resolved content for performance
- Detect circular dependencies
- Support depth limits (prevent infinite recursion)
- Handle missing files/sections gracefully
- Track transclusion metadata

#### Transclusion Engine API Design

```python
class TransclusionEngine:
    """Resolve and include content from transclusion directives."""

    def __init__(
        self,
        file_system: FileSystemManager,
        max_depth: int = 5,
        cache_enabled: bool = True
    ):
        """
        Initialize transclusion engine.

        Args:
            file_system: File system manager for reading files
            max_depth: Maximum transclusion depth (default: 5)
            cache_enabled: Enable content caching (default: True)
        """
        self.fs = file_system
        self.max_depth = max_depth
        self.cache: Dict[str, str] = {}
        self.cache_enabled = cache_enabled
        self._resolution_stack: List[str] = []

    async def resolve_content(
        self,
        content: str,
        source_file: str,
        depth: int = 0
    ) -> str:
        """
        Resolve all transclusions in content.

        Args:
            content: Markdown content with transclusion directives
            source_file: Name of source file (for relative paths)
            depth: Current recursion depth

        Returns:
            Content with transclusions resolved

        Raises:
            CircularDependencyError: If circular transclusion detected
            MaxDepthExceededError: If max depth exceeded
        """

    async def resolve_transclusion(
        self,
        target_file: str,
        section: Optional[str] = None,
        options: Optional[Dict] = None,
        depth: int = 0
    ) -> str:
        """
        Resolve a single transclusion directive.

        Args:
            target_file: Target file name
            section: Optional section heading
            options: Transclusion options (lines, recursive, etc.)
            depth: Current recursion depth

        Returns:
            Resolved content
        """

    def extract_section(
        self,
        content: str,
        section_heading: str,
        lines_limit: Optional[int] = None
    ) -> str:
        """
        Extract a specific section from content.

        Args:
            content: Full file content
            section_heading: Heading to find (e.g., "Architecture")
            lines_limit: Optional limit on number of lines

        Returns:
            Section content
        """

    def detect_circular_dependency(
        self,
        target: str
    ) -> bool:
        """
        Check if target is in resolution stack.

        Args:
            target: Target file being resolved

        Returns:
            True if circular dependency detected
        """

    def clear_cache(self):
        """Clear resolved content cache."""
        self.cache.clear()

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "entries": len(self.cache),
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": self._cache_hits / (self._cache_hits + self._cache_misses)
        }
```

#### Transclusion Engine Implementation Steps

1. Implement basic transclusion resolution (no recursion)
2. Add circular dependency detection with resolution stack
3. Implement depth limiting
4. Add section extraction logic
5. Implement content caching with invalidation
6. Add recursive transclusion support
7. Handle transclusion options (lines, recursive, etc.)
8. Write comprehensive tests including edge cases

---

### Module 3: Link Validator (`link_validator.py`)

**Purpose:** Validate link integrity and detect broken references

#### Link Validator Features

- Validate all markdown links
- Check file existence
- Check section existence
- Detect broken links
- Generate validation reports
- Support auto-fix suggestions

#### Link Validator API Design

```python
class LinkValidator:
    """Validate link integrity across Memory Bank files."""

    def __init__(
        self,
        file_system: FileSystemManager,
        link_parser: LinkParser
    ):
        """Initialize link validator."""
        self.fs = file_system
        self.parser = link_parser

    async def validate_file(
        self,
        file_path: Path
    ) -> Dict[str, List]:
        """
        Validate all links in a file.

        Returns:
            {
                "valid_links": [...],
                "broken_links": [
                    {
                        "line": 15,
                        "target": "missing.md",
                        "error": "File not found",
                        "suggestion": "Create file or update link"
                    }
                ],
                "warnings": [
                    {
                        "line": 42,
                        "target": "file.md#nonexistent",
                        "warning": "Section not found",
                        "available_sections": ["Intro", "Details"]
                    }
                ]
            }
        """

    async def validate_all(
        self,
        memory_bank_dir: Path
    ) -> Dict:
        """
        Validate all links in all Memory Bank files.

        Returns:
            {
                "files_checked": 7,
                "total_links": 45,
                "valid_links": 42,
                "broken_links": 3,
                "validation_errors": [...],
                "validation_warnings": [...]
            }
        """

    async def check_file_exists(
        self,
        target_file: str
    ) -> bool:
        """Check if target file exists."""

    async def check_section_exists(
        self,
        file_path: Path,
        section_heading: str
    ) -> bool:
        """Check if section exists in file."""

    def generate_fix_suggestions(
        self,
        broken_link: Dict
    ) -> List[str]:
        """
        Generate suggestions for fixing broken link.

        Returns:
            List of suggestions (e.g., ["Create missing file", "Update link to existing.md"])
        """
```

#### Link Validator Implementation Steps

1. Implement file existence checking
2. Implement section existence checking
3. Add link validation logic
4. Generate validation reports
5. Add fix suggestions
6. Write tests for various broken link scenarios

---

### Module 4: Update Dependency Graph (`dependency_graph.py`)

**Changes:** Add dynamic dependency building from parsed links

#### New Features

- Build dependency graph from actual links (not static)
- Update graph when files change
- Track link types (reference vs transclusion)
- Calculate transitive dependencies
- Detect dependency cycles

#### API Additions

```python
class DependencyGraph:
    # ... existing methods ...

    async def build_from_links(
        self,
        memory_bank_dir: Path,
        link_parser: LinkParser
    ):
        """
        Build dependency graph from actual links in files.

        Scans all files, parses links, and builds dynamic graph.
        Replaces static DEPENDENCY_HIERARCHY.
        """

    def add_link_dependency(
        self,
        source_file: str,
        target_file: str,
        link_type: str = "reference"
    ):
        """
        Add a dependency from parsed link.

        Args:
            source_file: File containing the link
            target_file: File being linked to
            link_type: "reference" or "transclusion"
        """

    def get_transclusion_order(
        self,
        start_file: str
    ) -> List[str]:
        """
        Get order for resolving transclusions.

        Returns files in order such that dependencies are resolved first.
        """

    def detect_cycles(self) -> List[List[str]]:
        """
        Detect circular dependencies.

        Returns:
            List of cycles, each as a list of files
        """
```

---

### Module 5: Update Main.py (New MCP Tools)

#### New MCP Tools for Link Management (4 tools)

#### 1. `parse_file_links()`

```python
@mcp.tool()
async def parse_file_links(
    file_name: str,
    project_root: str = None
) -> str:
    """
    Parse and return all links in a Memory Bank file.

    Returns:
        JSON with markdown links and transclusion directives
    """
```

#### 2. `resolve_transclusions()`

```python
@mcp.tool()
async def resolve_transclusions(
    file_name: str,
    project_root: str = None,
    max_depth: int = 5
) -> str:
    """
    Read file with all transclusions resolved.

    Returns:
        Content with {{include: ...}} directives replaced with actual content
    """
```

#### 3. `validate_links()`

```python
@mcp.tool()
async def validate_links(
    file_name: str = None,
    project_root: str = None
) -> str:
    """
    Validate links in a file or all files.

    Args:
        file_name: Optional specific file (if None, validates all)

    Returns:
        Validation report with broken links and warnings
    """
```

#### 4. `get_link_graph()`

```python
@mcp.tool()
async def get_link_graph(
    project_root: str = None,
    include_transclusions: bool = True,
    format: str = "json"
) -> str:
    """
    Get dynamic dependency graph based on actual links.

    Args:
        include_transclusions: Include transclusion links (default: True)
        format: "json" or "mermaid"

    Returns:
        Link graph showing how files reference each other
    """
```

---

## Transclusion Syntax Specification

### Basic Transclusion

```markdown
# Active Context

## Current Focus

{{include: projectBrief.md#Goals}}

The above section is automatically included from projectBrief.md.
```

### Section-Specific Transclusion

```markdown
# System Patterns

## Architecture Overview

{{include: systemPatterns.md#Architecture}}
```

### Transclusion with Options

```markdown
# Progress

## Recent Changes

{{include: activeContext.md#Recent Changes|lines=10}}

Only the first 10 lines of the section are included.
```

### Disable Nested Transclusion

```markdown
{{include: file.md#section|recursive=false}}
```

### Full File Inclusion

```markdown
{{include: legacy-notes.md}}
```

---

## Dynamic Dependency Graph

### Before Phase 2 (Static)

```python
DEPENDENCY_HIERARCHY = {
    "memorybankinstructions.md": {"priority": 1, "dependencies": []},
    "projectBrief.md": {"priority": 2, "dependencies": ["memorybankinstructions.md"]},
    # ... hard-coded structure
}
```

### After Phase 2 (Dynamic)

```python
# Built automatically from actual links in files
async def build_graph():
    for file in memory_bank_files:
        links = await link_parser.parse_file(file)
        for link in links:
            graph.add_dependency(file, link.target, link.type)

    return graph
```

### Example Dynamic Graph

```text
memorybankinstructions.md (no dependencies)
  ↑
projectBrief.md (references memorybankinstructions.md)
  ↑
productContext.md (includes projectBrief.md#Goals)
  ↑
activeContext.md (references productContext.md, systemPatterns.md)
```

---

## Circular Dependency Detection

### Example Circular Reference

```text
File A includes File B
File B includes File C
File C includes File A  ← CIRCULAR!
```

### Detection Algorithm

```python
async def resolve_with_cycle_detection(file, depth=0):
    if file in resolution_stack:
        raise CircularDependencyError(
            f"Circular transclusion: {' -> '.join(resolution_stack)} -> {file}"
        )

    resolution_stack.append(file)
    try:
        content = await resolve_transclusions(file, depth)
        return content
    finally:
        resolution_stack.pop()
```

---

## Performance Considerations

### Caching Strategy

1. **Parse Cache**: Cache parsed link lists per file (invalidate on file change)
2. **Resolution Cache**: Cache resolved content per transclusion (invalidate on target change)
3. **Section Cache**: Cache extracted sections (invalidate on file change)

### Cache Invalidation

```python
# When file changes
file_watcher.on_change(file_path):
    # Invalidate caches for this file
    link_parser.invalidate_cache(file_path)
    transclusion_engine.invalidate_cache(file_path)

    # Invalidate caches for files that include this file
    for dependent in graph.get_dependents(file_path):
        transclusion_engine.invalidate_cache(dependent)
```

### Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Parse links | <20ms | Per file |
| Resolve transclusion | <50ms | Cached |
| Resolve transclusion | <200ms | First time (with file reads) |
| Validate links | <100ms | Per file |
| Build full graph | <500ms | 7 files |

---

## Testing Strategy

### Unit Tests

1. **Link Parser Tests**
   - Parse standard markdown links
   - Parse transclusion directives
   - Parse transclusion options
   - Handle malformed syntax
   - Extract line numbers

2. **Transclusion Engine Tests**
   - Simple transclusion
   - Nested transclusion (2-3 levels)
   - Circular dependency detection
   - Max depth limiting
   - Section extraction
   - Cache behavior

3. **Link Validator Tests**
   - Detect missing files
   - Detect missing sections
   - Generate fix suggestions
   - Validate entire project

4. **Dependency Graph Tests**
   - Build from links
   - Detect cycles
   - Calculate transitive dependencies
   - Get transclusion order

### Integration Tests

1. End-to-end transclusion resolution
2. File change → cache invalidation → re-resolution
3. Multiple files with cross-references
4. Validation → fix → re-validation workflow

### Edge Cases to Test

- Empty files
- Files with no links
- Self-references
- 3-way circular dependencies
- Deep nesting (>10 levels)
- Malformed transclusion syntax
- Unicode in file names
- Sections with special characters

---

## Migration Path

### Phase 1 → Phase 2 Transition

#### No Breaking Changes

- Existing files work without modification
- Static dependency graph still available as fallback
- Transclusion syntax is additive (optional)

#### Gradual Adoption

```markdown
1. Phase 2 deployed
2. Users start adding {{include: ...}} directives
3. System automatically builds dynamic graph
4. Legacy static graph deprecated but still functional
5. Phase 3: Remove static graph entirely
```

---

## Documentation Updates

### New User Guide Sections

1. **Link Syntax Guide**
   - Markdown links
   - Transclusion syntax
   - Transclusion options

2. **DRY Best Practices**
   - When to use transclusion vs. links
   - How to structure content for reuse
   - Avoiding circular dependencies

3. **Link Validation**
   - Running validation
   - Understanding validation reports
   - Fixing broken links

### API Documentation

- Document all 4 new MCP tools
- Add examples for each tool
- Document transclusion syntax
- Add troubleshooting guide

---

## Success Criteria

Phase 2 is complete when:

✅ **Link Parser**

- Parses markdown links
- Parses transclusion directives
- Extracts all link metadata

✅ **Transclusion Engine**

- Resolves simple transclusions
- Handles nested transclusions
- Detects circular dependencies
- Caches resolved content

✅ **Link Validator**

- Detects broken links
- Validates sections
- Generates fix suggestions

✅ **Dynamic Dependencies**

- Builds graph from links
- Updates on file changes
- Replaces static graph

✅ **MCP Tools**

- All 4 tools implemented
- All tools tested
- Documentation complete

✅ **Testing**

- Unit tests: >90% coverage
- Integration tests passing
- Edge cases handled

---

## Timeline Estimate

### Implementation (4-6 hours)

- Link Parser: 1 hour
- Transclusion Engine: 2 hours
- Link Validator: 1 hour
- Dependency Graph updates: 1 hour
- MCP Tools: 1 hour

### Testing (2-3 hours)

- Unit tests: 1.5 hours
- Integration tests: 1 hour
- Edge case testing: 0.5 hours

### Documentation (1 hour)

- User guides: 0.5 hours
- API docs: 0.5 hours

#### Total: 7-10 hours

---

## Risks and Mitigation

### Risk 1: Performance Impact

**Risk**: Transclusion resolution could slow down file reads
**Mitigation**:

- Aggressive caching
- Lazy resolution (only when requested)
- Performance benchmarks
- Max depth limits

### Risk 2: Circular Dependencies

**Risk**: Users create circular transclusions, causing infinite loops
**Mitigation**:

- Stack-based cycle detection
- Clear error messages
- Validation tool to detect cycles
- Documentation on best practices

### Risk 3: Complex Syntax

**Risk**: Transclusion syntax too complex for users
**Mitigation**:

- Keep syntax simple and familiar
- Provide clear examples
- Auto-complete in IDEs
- Validation with helpful errors

### Risk 4: Cache Invalidation

**Risk**: Stale cache serving outdated content
**Mitigation**:

- File watcher integration
- Content hash verification
- Manual cache clear command
- Cache TTL (optional)

---

## Future Enhancements (Phase 3+)

### Beyond Phase 2

1. **Partial Transclusion**
   - Include lines 10-20
   - Include matching paragraphs
   - Include by regex pattern

2. **Transclusion Transformations**
   - Apply formatting
   - Strip headings
   - Convert bullet points

3. **Link Auto-Fixing**
   - Automatically fix broken links
   - Suggest similar sections
   - Update after renames

4. **Visual Link Graph**
   - Interactive graph visualization
   - Highlight circular dependencies
   - Show unused files

5. **Smart Includes**
   - Include based on context
   - AI-suggested transclusions
   - Auto-update on changes

---

## Appendix: Example Use Cases

### Use Case 1: Shared Project Goals

**Before:**

```markdown
<!-- projectBrief.md -->
## Goals
- Implement feature X
- Improve performance
- Add tests

<!-- productContext.md -->
## Goals (duplicated)
- Implement feature X
- Improve performance
- Add tests
```

**After:**

```markdown
<!-- projectBrief.md -->
## Goals
- Implement feature X
- Improve performance
- Add tests

<!-- productContext.md -->
## Project Goals
{{include: projectBrief.md#Goals}}
```

### Use Case 2: Reusable Technical Details

```markdown
<!-- techContext.md -->
## Tech Stack
- Python 3.11+
- FastMCP
- Asyncio

<!-- systemPatterns.md -->
## Technologies Used
{{include: techContext.md#Tech Stack}}
```

### Use Case 3: Progress Tracking

```markdown
<!-- progress.md -->
## Recent Accomplishments
{{include: activeContext.md#Recent Changes|lines=5}}

Shows the 5 most recent changes from activeContext.md
```

---

**Last Updated:** December 19, 2025
**Status:** Ready for implementation
**Dependencies:** Phase 1 Complete ✅
