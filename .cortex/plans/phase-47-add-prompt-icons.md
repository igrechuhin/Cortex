# Phase 47: Add Helper Icons to Prompts for Navigation

**Status**: PLANNING  
**Created**: 2026-01-17  
**Priority**: Medium  
**Estimated Effort**: 6-8 hours

## Overview

Add visual emoji icons to all Cortex MCP prompts to help users navigate between prompts in client applications. Icons provide visual representations that make it easier to identify and select prompts, improving user experience and discoverability.

**Reference**: <https://gofastmcp.com/servers/icons>

## Context

### Current State

- **8 static prompts** in `src/cortex/tools/prompts.py` (setup/migration prompts)
- **6+ dynamic prompts** loaded from `.cortex/synapse/prompts/` via `synapse_prompts.py`
- All prompts use `@mcp.prompt()` decorator without icons
- FastMCP 2.0 in use (migrated in Phase 41)
- No visual indicators to help users distinguish between prompts

### Related Work

- **Phase 41**: FastMCP 2.0 migration completed (supports icons)
- **Phase 45**: Add MCP annotations (icons complement annotations for better UX)
- **Phase 46**: Extract setup logic to separate MCP server (may affect prompt organization)

## Goals

1. **Add emoji icons** to all prompts (prefer emoji over image files)
2. **Improve prompt navigation** in MCP client interfaces
3. **Categorize prompts visually** using appropriate emoji for each prompt type
4. **Maintain backward compatibility** with existing prompt behavior
5. **Create reusable icon helper** for emoji-to-data-URI conversion

## FastMCP Icons Reference

From FastMCP documentation:

### Icon Format

Icons use the standard MCP Icon type:

- **`src`**: URL or data URI pointing to the icon image
- **`mimeType`** (optional): MIME type (e.g., "image/png", "image/svg+xml")
- **`sizes`** (optional): Array of size descriptors (e.g., ["48x48"], ["any"])

### Prompt Icons

```python
from mcp.types import Icon

@mcp.prompt(
    icons=[Icon(src="https://example.com/prompt-icon.png")]
)
def analyze_code(code: str):
    """Create a prompt for code analysis."""
    return f"Please analyze this code:\n\n{code}"
```

### Using Data URIs for Emoji

For emoji icons, we can use SVG data URIs:

```python
# SVG icon as data URI with emoji
svg_icon = Icon(
    src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCI+PHBhdGggZD0iTTEyIDJDNi40OCAyIDIgNi40OCAyIDEyczQuNDggMTAgMTAgMTAgMTAtNC40OCAxMC0xMFMxNy41MiAyIDEyIDJ6Ii8+PC9zdmc+",
    mimeType="image/svg+xml"
)
```

## Implementation Plan

### Step 1: Create Emoji Icon Helper Utility

**File**: `src/cortex/core/icon_helpers.py` (new file)

Create a helper module for generating emoji icons as SVG data URIs:

1. **Function**: `create_emoji_icon(emoji: str, size: int = 24) -> Icon`
   - Takes an emoji string (e.g., "🚀", "📝", "🔧")
   - Generates SVG with emoji text centered
   - Converts to base64 data URI
   - Returns `Icon` object with proper MIME type

2. **Function**: `create_emoji_icons(emoji: str, sizes: list[str] = None) -> list[Icon]`
   - Creates multiple icon sizes for responsive display
   - Default sizes: ["24x24", "48x48"]

3. **SVG Template**:

   ```svg
   <svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">
     <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-size="{size}px">{emoji}</text>
   </svg>
   ```

**Estimated Effort**: 2 hours

### Step 2: Define Icon Mapping for Static Prompts

**File**: `src/cortex/tools/prompts.py`

Create a mapping of prompt names to emoji icons:

```python
PROMPT_ICONS = {
    "initialize_memory_bank": "🏗️",  # Construction/building
    "setup_project_structure": "📁",  # Folder/structure
    "setup_cursor_integration": "⚙️",  # Settings/gear
    "populate_tiktoken_cache": "💾",  # Save/cache
    "setup_synapse": "🔗",  # Link/connection
    "check_migration_status": "🔍",  # Search/check
    "migrate_memory_bank": "🔄",  # Refresh/migrate
    "migrate_project_structure": "📦",  # Package/migration
}
```

**Estimated Effort**: 0.5 hours

### Step 3: Update Static Prompts with Icons

**File**: `src/cortex/tools/prompts.py`

Update all `@mcp.prompt()` decorators to include icons:

1. Import icon helper: `from cortex.core.icon_helpers import create_emoji_icon`
2. Update each prompt decorator:

   ```python
   @mcp.prompt(icons=[create_emoji_icon(PROMPT_ICONS["initialize_memory_bank"])])
   def initialize_memory_bank() -> str:
       ...
   ```

**Prompts to update**:

- `initialize_memory_bank` → 🏗️
- `setup_project_structure` → 📁
- `setup_cursor_integration` → ⚙️
- `populate_tiktoken_cache` → 💾
- `setup_synapse` → 🔗
- `check_migration_status` → 🔍
- `migrate_memory_bank` → 🔄
- `migrate_project_structure` → 📦

**Estimated Effort**: 1 hour

### Step 4: Define Icon Mapping for Dynamic Prompts

**File**: `src/cortex/tools/synapse_prompts.py`

Create a mapping of prompt names/categories to emoji icons:

```python
SYNAPSE_PROMPT_ICONS = {
    "commit": "💾",  # Save/commit
    "review": "👀",  # Review/eye
    "implement": "⚡",  # Lightning/implementation
    "plan": "📋",  # Clipboard/plan
    "validate": "✅",  # Checkmark/validation
    "populate_tiktoken_cache": "💾",  # Save/cache (if exists)
}
```

**Estimated Effort**: 0.5 hours

### Step 5: Update Dynamic Prompt Registration with Icons

**File**: `src/cortex/tools/synapse_prompts.py`

Update `create_prompt_function()` to include icons in the decorator:

1. Import icon helper: `from cortex.core.icon_helpers import create_emoji_icon`
2. Update function code generation to include icons:

   ```python
   func_code = f'''@mcp.prompt(icons=[create_emoji_icon("{emoji}")])
   def {name}() -> str:
       """{description}"""
       return _prompt_contents["{name}"]
   '''
   ```

3. Add logic to determine emoji based on prompt name/category:
   - Check `SYNAPSE_PROMPT_ICONS` mapping
   - Fallback to category-based emoji if name not found
   - Default emoji: "📝" (memo/note) if no match

**Estimated Effort**: 1.5 hours

### Step 6: Update Prompts Manifest (Optional Enhancement)

**File**: `.cortex/synapse/prompts/prompts-manifest.json`

Add optional `icon` field to prompt entries for explicit icon specification:

```json
{
  "file": "commit.md",
  "name": "Commit",
  "description": "...",
  "icon": "💾",
  "keywords": [...]
}
```

Update `process_prompt_info()` to read icon from manifest if present.

**Estimated Effort**: 1 hour

### Step 7: Testing and Verification

1. **Unit Tests**:
   - Test `create_emoji_icon()` generates valid Icon objects
   - Test SVG generation with different emojis
   - Test data URI format is correct
   - Test icon helper handles edge cases (empty emoji, special characters)

2. **Integration Tests**:
   - Verify prompts load with icons in MCP server
   - Test that icons appear in MCP client (Cursor)
   - Verify backward compatibility (prompts still work without icons)

3. **Manual Testing**:
   - Start MCP server and verify prompts appear with icons
   - Test in Cursor IDE to see icons in prompt list
   - Verify icons help with navigation

**Estimated Effort**: 1.5 hours

## Technical Design

### Icon Helper Implementation

```python
"""Icon helper utilities for creating emoji-based MCP icons."""

import base64
from typing import Literal

from mcp.types import Icon


def create_emoji_icon(
    emoji: str,
    size: int = 24,
    mime_type: Literal["image/svg+xml"] = "image/svg+xml",
) -> Icon:
    """Create an Icon from an emoji using SVG data URI.
    
    Args:
        emoji: Emoji character(s) to use as icon
        size: Icon size in pixels (default: 24)
        mime_type: MIME type for the icon (default: "image/svg+xml")
    
    Returns:
        Icon object with emoji rendered as SVG data URI
    """
    # Generate SVG with emoji
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-size="{size * 0.8}px">{emoji}</text>
</svg>'''
    
    # Encode to base64 data URI
    svg_bytes = svg_content.encode('utf-8')
    base64_svg = base64.b64encode(svg_bytes).decode('utf-8')
    data_uri = f"data:{mime_type};base64,{base64_svg}"
    
    return Icon(
        src=data_uri,
        mimeType=mime_type,
        sizes=[f"{size}x{size}"],
    )


def create_emoji_icons(
    emoji: str,
    sizes: list[str] | None = None,
) -> list[Icon]:
    """Create multiple Icon objects for different sizes.
    
    Args:
        emoji: Emoji character(s) to use as icon
        sizes: List of size descriptors (e.g., ["24x24", "48x48"])
    
    Returns:
        List of Icon objects for each size
    """
    if sizes is None:
        sizes = ["24x24", "48x48"]
    
    icons = []
    for size_desc in sizes:
        size = int(size_desc.split("x")[0])
        icons.append(create_emoji_icon(emoji, size=size))
    
    return icons
```

### Emoji Selection Rationale

**Setup Prompts**:

- 🏗️ `initialize_memory_bank` - Building/construction (initial setup)
- 📁 `setup_project_structure` - Folder (structure organization)
- ⚙️ `setup_cursor_integration` - Gear (configuration)
- 💾 `populate_tiktoken_cache` - Floppy disk (caching/storage)
- 🔗 `setup_synapse` - Link (connection/integration)

**Migration Prompts**:

- 🔍 `check_migration_status` - Magnifying glass (inspection)
- 🔄 `migrate_memory_bank` - Refresh arrows (migration)
- 📦 `migrate_project_structure` - Package (bulk migration)

**Development Prompts**:

- 💾 `commit` - Floppy disk (save/commit)
- 👀 `review` - Eyes (review/inspection)
- ⚡ `implement` - Lightning (fast implementation)
- 📋 `plan` - Clipboard (planning)
- ✅ `validate` - Checkmark (validation)

## Success Criteria

1. ✅ All static prompts have emoji icons
2. ✅ All dynamic prompts have emoji icons
3. ✅ Icons appear correctly in MCP client interfaces
4. ✅ Icon helper utility is reusable and well-tested
5. ✅ No breaking changes to existing prompt functionality
6. ✅ Icons improve prompt discoverability and navigation

## Dependencies

- FastMCP 2.0 (already migrated in Phase 41)
- MCP Icon type support (included in FastMCP 2.0)
- No external dependencies for emoji rendering (uses SVG)

## Risks & Mitigation

### Risk 1: Emoji Rendering Inconsistency

**Risk**: Different clients may render emoji differently in SVG
**Mitigation**: Use standard SVG text rendering, test in multiple clients

### Risk 2: Data URI Size

**Risk**: Base64-encoded SVG data URIs may be large
**Mitigation**: SVG is small (~200-300 bytes), well within acceptable limits

### Risk 3: Emoji Compatibility

**Risk**: Some emoji may not render correctly in all clients
**Mitigation**: Use common, well-supported emoji; test in target clients

### Risk 4: Dynamic Prompt Icon Resolution

**Risk**: Icon mapping may not cover all dynamic prompts
**Mitigation**: Implement fallback to category-based or default emoji

## Timeline

- **Step 1**: Create icon helper utility (2 hours)
- **Step 2**: Define icon mappings (0.5 hours)
- **Step 3**: Update static prompts (1 hour)
- **Step 4**: Define dynamic prompt icons (0.5 hours)
- **Step 5**: Update dynamic prompt registration (1.5 hours)
- **Step 6**: Update prompts manifest (optional, 1 hour)
- **Step 7**: Testing and verification (1.5 hours)

**Total**: 6-8 hours

## Notes

- Emoji icons are preferred over image files for simplicity and maintainability
- Icons can be easily changed by updating emoji strings
- SVG data URIs are self-contained and don't require external files
- Icon helper can be reused for tools and resources in future phases
- Consider adding icons to tools in a future phase (Phase 48+)

## Related Phases

- **Phase 41**: FastMCP 2.0 migration (enables icon support)
- **Phase 45**: Add MCP annotations (icons complement annotations)
- **Phase 46**: Extract setup logic (may affect prompt organization)
