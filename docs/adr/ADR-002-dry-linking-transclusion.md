# ADR-002: DRY Linking via Transclusion Syntax

## Status

Accepted

## Context

Memory bank files often need to reference or include content from other files. This creates tension between two important principles:

1. **DRY (Don't Repeat Yourself)**: Avoid duplicating content across multiple files
2. **Readability**: Each memory bank file should be understandable on its own

Without a linking mechanism, we face these problems:

### Problem 1: Content Duplication

When the same information is needed in multiple files, developers tend to copy-paste:

```markdown
<!-- projectBrief.md -->
## Tech Stack
- Python 3.13+
- MCP SDK
- aiofiles for async I/O

<!-- techContext.md -->
## Tech Stack
- Python 3.13+
- MCP SDK
- aiofiles for async I/O
```

**Issues**:

- Changes must be made in multiple places
- Files drift out of sync over time
- Maintenance burden increases
- Source of truth unclear

### Problem 2: Fragmentation

To avoid duplication, developers create many small files and reference them by path:

```markdown
See tech-stack.md for our technology choices.
```

**Issues**:

- Readers must manually open multiple files
- Context switching disrupts flow
- Hard to get complete picture
- Tool support varies

### Problem 3: Link Rot

File paths change during refactoring, breaking references:

```markdown
See docs/architecture/tech-stack.md for details.
<!-- File moved to docs/technical/stack.md - link broken! -->
```

**Issues**:

- No automatic detection of broken links
- Manual link maintenance required
- Breaks reader experience
- Reduces documentation value

### Requirements

**Functional Requirements**:

- Include content from other files without duplication
- Validate link integrity automatically
- Support nested transclusions (file A includes B, B includes C)
- Detect circular dependencies
- Work with plain Markdown files
- Support both relative and absolute paths

**Non-Functional Requirements**:

- Syntax should be readable as plain Markdown
- Compatible with Markdown preview tools
- Minimal learning curve
- Fast resolution (<10ms for typical transclusion tree)
- Support for large files (>1MB)

### Domain Analysis

**Transclusion Concept**:
Transclusion (coined by Ted Nelson) is the inclusion of content from one document into another by reference. Unlike hyperlinks (which only reference), transclusion actually embeds content.

**Examples in Other Systems**:

- **WikiWikiWeb**: Pioneered wiki transclusion with `{{page_name}}`
- **MediaWiki**: `{{Template:Name}}` for templates, `{{:Page}}` for pages
- **AsciiDoc**: `include::path/to/file.adoc[]`
- **Pandoc**: `!include file.md`
- **MDX**: `import` statements and JSX components
- **Hugo**: Shortcodes like `{{< ref "page.md" >}}`

**Common Patterns**:

1. **Double curly braces**: `{{reference}}` - used by wikis, template engines
2. **Directive syntax**: `include::file` - used by documentation tools
3. **Bang syntax**: `!include` - used by preprocessors
4. **Import statements**: `import` - used by component systems

### Use Case Analysis

**Use Case 1: Shared Configuration**

```markdown
<!-- projectBrief.md -->
{{include:.cursor/config/tech-stack.md}}

<!-- techContext.md -->
{{include:.cursor/config/tech-stack.md}}
```

**Use Case 2: Progressive Detail**

```markdown
<!-- README.md -->
## Quick Start
{{include:docs/getting-started.md}}

## Architecture
{{include:docs/architecture-overview.md}}
```

**Use Case 3: Modular Documentation**

```markdown
<!-- systemPatterns.md -->
## Storage Layer
{{include:patterns/storage.md}}

## API Layer
{{include:patterns/api.md}}
```

**Use Case 4: Version-Specific Content**

```markdown
<!-- migration-guide.md -->
## Version 1.0 to 2.0
{{include:migrations/v1-to-v2.md}}
```

### Syntax Design Criteria

**Readability**:

- Should be obvious what the syntax does
- Works in plain Markdown viewers
- Doesn't clash with existing Markdown syntax
- Graceful degradation (shows path if not rendered)

**Parseability**:

- Unambiguous syntax
- Easy to implement parser
- Clear error messages
- Fast parsing (regex-friendly)

**Extensibility**:

- Room for future parameters (line ranges, sections)
- Could support filters/transforms
- Compatible with Markdown extensions

**Compatibility**:

- Doesn't break existing Markdown tools
- Works with Git diff/merge
- Syntax highlighting possible
- Linting tools can understand it

## Decision

We will implement transclusion using the **double curly brace syntax**:

```markdown
{{include:path/to/file.md}}
```

### Syntax Specification

**Basic Transclusion**:

```markdown
{{include:relative/path/to/file.md}}
```

**Absolute Path**:

```markdown
{{include:/absolute/path/to/file.md}}
```

**Current Directory**:

```markdown
{{include:./sibling-file.md}}
```

**Parent Directory**:

```markdown
{{include:../parent-level-file.md}}
```

**Nested Directories**:

```markdown
{{include:../../docs/architecture/overview.md}}
```

### Path Resolution Rules

1. **Relative paths** are resolved relative to the containing file's directory
2. **Absolute paths** are resolved relative to the memory bank root
3. **Path normalization** handles `.` and `..` correctly
4. **Symlinks** are resolved to their target
5. **Case sensitivity** follows the file system (case-insensitive on Windows/macOS)

### Parser Implementation

**LinkParser** (`src/cortex/linking/link_parser.py`):

```python
import re

TRANSCLUSION_PATTERN = re.compile(
    r'\{\{include:([^}]+)\}\}',
    re.MULTILINE
)

async def parse_links(content: str, source_path: str) -> list[Link]:
    """Extract transclusion links from content."""
    links = []
    for match in TRANSCLUSION_PATTERN.finditer(content):
        raw_path = match.group(1).strip()
        resolved_path = resolve_path(raw_path, source_path)
        links.append(Link(
            source=source_path,
            target=resolved_path,
            raw=raw_path,
            span=(match.start(), match.end())
        ))
    return links
```

**TransclusionEngine** (`src/cortex/linking/transclusion_engine.py`):

```python
async def resolve_transclusion(
    file_path: str,
    max_depth: int = 10
) -> str:
    """Resolve all transclusions recursively."""
    if max_depth <= 0:
        raise CircularDependencyError()

    content = await read_file(file_path)
    links = await parse_links(content, file_path)

    for link in links:
        # Recursively resolve transclusion
        included = await resolve_transclusion(
            link.target,
            max_depth - 1
        )
        # Replace transclusion with content
        content = content.replace(
            f"{{{{include:{link.raw}}}}}",
            included
        )

    return content
```

### Circular Dependency Detection

**Strategy**: Track visited files in resolution stack.

```python
async def resolve_transclusion(
    file_path: str,
    visited: set[str] | None = None
) -> str:
    """Resolve transclusions with cycle detection."""
    if visited is None:
        visited = set()

    if file_path in visited:
        raise CircularDependencyError(
            f"Circular dependency detected: {visited} -> {file_path}"
        )

    visited.add(file_path)
    content = await read_file(file_path)
    links = await parse_links(content, file_path)

    for link in links:
        included = await resolve_transclusion(link.target, visited.copy())
        content = content.replace(
            f"{{{{include:{link.raw}}}}}",
            included
        )

    return content
```

### Link Validation

**LinkValidator** (`src/cortex/linking/link_validator.py`):

Validates that:

1. Target file exists
2. Target is readable
3. No circular dependencies
4. Path is within allowed directories (security)

```python
async def validate_links(file_path: str) -> list[ValidationError]:
    """Validate all links in a file."""
    errors = []
    content = await read_file(file_path)
    links = await parse_links(content, file_path)

    for link in links:
        # Check file exists
        if not await file_exists(link.target):
            errors.append(ValidationError(
                file=file_path,
                line=get_line_number(content, link.span[0]),
                message=f"Target file not found: {link.target}"
            ))

        # Check for circular dependencies
        try:
            await resolve_transclusion(file_path)
        except CircularDependencyError as e:
            errors.append(ValidationError(
                file=file_path,
                message=str(e)
            ))

    return errors
```

### Integration with Memory Bank Tools

**1. File Reading**: `resolve_transclusion()` resolves all transclusions before returning content
**2. Validation**: `validate_memory_bank()` checks link integrity
**3. Dependencies**: `get_file_dependencies()` returns transclusion dependencies
**4. Quality Metrics**: Resolved content used for calculating metrics

## Consequences

### Positive

**1. DRY Principle**:

- Content defined once, included multiple times
- Single source of truth for shared content
- Changes propagate automatically
- Reduced maintenance burden

**2. Readability**:

- Each file can be read independently (when resolved)
- No need to manually follow references
- Complete context in one view
- Better user experience

**3. Validation**:

- Automatic link checking
- Circular dependency detection
- File existence validation
- Security checks (path traversal)

**4. Flexibility**:

- Supports relative and absolute paths
- Works with nested transclusions
- Path normalization handles edge cases
- Extensible syntax for future features

**5. Tool Compatibility**:

- Works with plain Markdown viewers (shows path)
- Git diff shows transclusion changes clearly
- No special tools required for editing
- Compatible with existing Markdown ecosystem

**6. Performance**:

- Fast parsing with regex
- Efficient caching of resolved content
- Minimal overhead for non-transcluded files
- Lazy resolution when needed

### Negative

**1. Complexity**:

- Additional layer of indirection
- Circular dependency detection required
- Path resolution logic needed
- Error handling more complex

**2. Debugging**:

- Errors may occur in transcluded files
- Stack traces span multiple files
- Harder to locate source of issues
- Need good error messages

**3. Version Control**:

- Diffs don't show transcluded content changes
- Reviewing requires understanding transclusions
- Merge conflicts possible in transclusion paths
- History tracking less straightforward

**4. Tooling Gaps**:

- Plain Markdown viewers don't resolve transclusions
- Syntax highlighting varies by editor
- Some tools show raw `{{include:...}}` syntax
- Need custom rendering for full experience

**5. Performance Edge Cases**:

- Large files can slow down resolution
- Deep nesting increases resolution time
- Circular dependency detection adds overhead
- Cache invalidation required on file changes

**6. Learning Curve**:

- New syntax to learn
- Understanding resolution order
- Debugging transclusion issues
- Path resolution rules

### Neutral

**1. Syntax Choice**:

- Double curly braces are familiar from templates
- Could clash with other tools using same syntax
- Future extensions may need new syntax
- Trade-off: familiarity vs uniqueness

**2. Path Resolution**:

- Relative paths more flexible but harder to understand
- Absolute paths clearer but less portable
- Both supported, but introduces choice
- Documentation needed for best practices

**3. Validation Strictness**:

- Strict validation catches errors early
- May be too strict for some workflows
- Configuration options needed
- Balance between safety and flexibility

## Alternatives Considered

### Alternative 1: Standard Markdown Links

**Approach**: Use regular Markdown links `[text](path.md)` and manually follow them.

**Syntax**:

```markdown
See [tech stack](tech-stack.md) for details.
```

**Pros**:

- Standard Markdown syntax
- Universal tool support
- Simple implementation
- No custom parser needed

**Cons**:

- Doesn't include content (just references)
- Readers must manually navigate
- No automatic validation
- Breaks DRY principle

**Rejection Reason**: Doesn't solve the core problem of content duplication. Links only reference, they don't transclude.

### Alternative 2: AsciiDoc Include Directive

**Approach**: Use AsciiDoc's `include::` directive.

**Syntax**:

```asciidoc
include::path/to/file.adoc[]
```

**Pros**:

- Standard in documentation tools
- Supports line ranges, tags
- Well-documented syntax
- Mature ecosystem

**Cons**:

- Requires AsciiDoc (not Markdown)
- Syntax not as readable
- More complex parser
- Less familiar to developers

**Rejection Reason**: Memory bank files are Markdown, not AsciiDoc. Switching formats would be disruptive.

### Alternative 3: Pandoc Include Syntax

**Approach**: Use Pandoc's include extension.

**Syntax**:

```markdown
!include file.md
```

**Pros**:

- Supported by Pandoc
- Simple syntax
- Markdown-compatible
- Widely used

**Cons**:

- Requires Pandoc for rendering
- Bang syntax less intuitive
- Limited parameter support
- Not standard Markdown

**Rejection Reason**: Bang syntax is less obvious than `{{include:...}}`. Requires Pandoc as dependency.

### Alternative 4: MDX Import Statements

**Approach**: Use JavaScript-style imports.

**Syntax**:

```mdx
import Content from './file.md'

<Content />
```

**Pros**:

- Familiar to developers
- Powerful component model
- Strong tooling support
- Type safety possible

**Cons**:

- Requires MDX (not plain Markdown)
- Complex parser needed
- JavaScript dependency
- Overkill for simple transclusion

**Rejection Reason**: Too complex for our needs. Requires JavaScript runtime.

### Alternative 5: Hugo Shortcodes

**Approach**: Use Hugo's shortcode syntax.

**Syntax**:

```markdown
{{< ref "file.md" >}}
```

**Pros**:

- Used in popular static site generator
- Extensible syntax
- Parameters supported
- Good documentation

**Cons**:

- Requires Hugo for rendering
- Angle brackets less common
- Not standard Markdown
- Framework-specific

**Rejection Reason**: Syntax is less intuitive. Tied to Hugo ecosystem.

### Alternative 6: Preprocessor Comments

**Approach**: Use HTML comments with preprocessor directives.

**Syntax**:

```markdown
<!-- include: path/to/file.md -->
```

**Pros**:

- Works in any Markdown viewer (comments hidden)
- No new syntax introduced
- Standard HTML comments
- Simple to parse

**Cons**:

- Invisible in rendered output (not always desired)
- Less obvious what's happening
- Comments can be stripped by tools
- Harder to see structure

**Rejection Reason**: Invisibility is a problem. Readers can't see transclusions.

### Alternative 7: Custom Markdown Extension

**Approach**: Define custom Markdown link syntax.

**Syntax**:

```markdown
[!include](path/to/file.md)
```

**Pros**:

- Looks like Markdown link
- Familiar syntax
- Easy to implement
- No special characters

**Cons**:

- Clashes with callout syntax in some Markdown flavors
- Ambiguous (link or transclusion?)
- Hard to distinguish from regular links
- Parser complexity

**Rejection Reason**: Too similar to existing syntax. Ambiguous intent.

### Alternative 8: XML Processing Instructions

**Approach**: Use XML processing instructions.

**Syntax**:

```markdown
<?include href="path/to/file.md"?>
```

**Pros**:

- Standard XML syntax
- Self-describing
- Parameter support
- Clear intent

**Cons**:

- Verbose syntax
- Not Markdown-native
- XML processing needed
- Unfamiliar to Markdown users

**Rejection Reason**: Too verbose. XML is out of place in Markdown.

## Implementation Notes

### Future Extensions

The syntax can be extended to support:

**1. Line Ranges**:

```markdown
{{include:file.md:10-20}}
```

**2. Section References**:

```markdown
{{include:file.md#section-name}}
```

**3. Filters/Transforms**:

```markdown
{{include:code.py | syntax=python | indent=4}}
```

**4. Conditional Inclusion**:

```markdown
{{include:env-specific.md if ENV=prod}}
```

### Performance Optimizations

**Caching Strategy**:

1. Cache resolved transclusions in memory
2. Invalidate cache on file changes
3. Use file hash for cache key
4. Lazy resolution (only when needed)

**Parallel Resolution**:
Multiple transclusions in same file can be resolved in parallel:

```python
async def resolve_transclusions_parallel(
    file_path: str
) -> str:
    content = await read_file(file_path)
    links = await parse_links(content, file_path)

    # Resolve all transclusions in parallel
    resolved = await asyncio.gather(*[
        resolve_transclusion(link.target)
        for link in links
    ])

    # Replace in order
    for link, included in zip(links, resolved):
        content = content.replace(
            f"{{{{include:{link.raw}}}}}",
            included
        )

    return content
```

### Error Handling

**Clear Error Messages**:

```
TransclusionError: Failed to resolve {{include:missing.md}}
  File: projectBrief.md, Line: 42
  Reason: Target file not found

  Searched paths:
    - /path/to/.cursor/memory-bank/missing.md
    - /path/to/missing.md
```

### Testing Strategy

**Unit Tests**:

- Path resolution logic
- Circular dependency detection
- Link parsing accuracy
- Error message clarity

**Integration Tests**:

- Nested transclusions
- Cross-directory references
- Symlink handling
- Large file performance

## References

- [Transclusion (Ted Nelson)](http://www.hyperland.com/TNtoc.html)
- [AsciiDoc Include](https://docs.asciidoctor.org/asciidoc/latest/directives/include/)
- [Pandoc Includes](https://github.com/owickstrom/pandoc-include-code)
- [MDX Imports](https://mdxjs.com/docs/using-mdx/#import)
- [WikiWikiWeb Transclusion](http://wiki.c2.com/?TransClusion)

## Related ADRs

- ADR-001: Hybrid Storage - How files are stored and accessed
- ADR-004: Protocol-Based Architecture - Link validation protocols
- ADR-008: Security Model - Path traversal protection

## Revision History

- 2024-01-10: Initial version (accepted)
