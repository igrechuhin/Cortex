# Phase 8: Comprehensive Project Structure Management

**Status:** ✅ COMPLETE
**Completed:** December 20, 2025
**Goal:** Define and enforce a comprehensive, standardized structure for Memory Bank files, rules, plans, and project organization

---

## Overview

This MCP server should provide intelligent management of project structure including:

1. **Memory Bank files** - Knowledge base organization
2. **Rules** - Git submodule integration for project-specific coding standards
3. **Plans** - Comprehensive planning system optimized for both LLMs and humans
4. **Standardized structures** - Templates for individual plans and rules

The system will work seamlessly with Cursor app through symlinks while maintaining a primary, well-structured location accessible via MCP tools.

---

## Problem Statement

Current state across projects shows inconsistent structure:

### Legacy Memory Bank Locations

- `/Users/i.grechukhin/Repo/TradeWing/` - Various memory bank files scattered
- `/Users/i.grechukhin/Repo/doc-mcp/` - Different organization approach

### Legacy Plans Locations

- `.plan/` (this project)
- `/Users/i.grechukhin/Repo/TradeWing/.cursor/plans`
- `/Users/i.grechukhin/Repo/doc-mcp/.cursor/plans`

### Issues

- No standardized location for memory bank files
- Rules scattered across multiple locations
- Plans in inconsistent formats and locations
- No automated setup or migration tooling
- Cursor app expects files in `.cursor/` folder
- Poor housekeeping makes it hard for both LLMs and humans to navigate

---

## Proposed Architecture

### 1. Standardized Directory Structure

```plaintext
project-root/
├── .memory-bank/              ⭐ Primary location
│   ├── knowledge/             # Memory Bank files
│   │   ├── memorybankinstructions.md
│   │   ├── projectBrief.md
│   │   ├── productContext.md
│   │   ├── activeContext.md
│   │   ├── systemPatterns.md
│   │   ├── techContext.md
│   │   └── progress.md
│   ├── rules/                 # Git submodule for rules
│   │   ├── .git              # Submodule reference
│   │   ├── local/            # Project-specific rules
│   │   │   ├── coding-standards.md
│   │   │   ├── architecture.md
│   │   │   └── testing.md
│   │   └── shared/           # From shared repository
│   │       ├── rules-manifest.json
│   │       ├── generic/
│   │       ├── python/
│   │       └── swift/
│   ├── plans/                 # Planning system
│   │   ├── README.md         # Plans index
│   │   ├── STATUS.md         # Current state
│   │   ├── templates/        # Plan templates
│   │   │   ├── feature.md
│   │   │   ├── bugfix.md
│   │   │   └── refactoring.md
│   │   ├── active/           # Active plans
│   │   │   └── phase-8-structure.md
│   │   ├── completed/        # Completed plans
│   │   │   └── phase-1-foundation.md
│   │   └── archived/         # Archived/deprecated
│   │       └── old-approach.md
│   └── config/               # Configuration
│       ├── structure.json    # Structure definitions
│       ├── templates.json    # Template registry
│       └── housekeeping.json # Automation rules
│
├── .cursor/                   ⭐ Cursor integration
│   ├── knowledge -> ../.memory-bank/knowledge/  # Symlink
│   ├── rules -> ../.memory-bank/rules/          # Symlink
│   ├── plans -> ../.memory-bank/plans/          # Symlink
│   └── .cursorrules -> ../.memory-bank/rules/local/main.cursorrules
│
├── .memory-bank-index        # Metadata (existing)
├── .memory-bank-history/     # Version history (existing)
└── .gitignore                # Ignore metadata, not structure
```

### 2. Git Integration Strategy

**Rules as Git Submodules:**

```bash
# Setup shared rules
cd .memory-bank/rules
git submodule add https://github.com/org/shared-rules.git shared
git submodule update --init --recursive
```

**Local rules tracked in project repository:**

- `.memory-bank/rules/local/` - Committed to project git
- `.memory-bank/rules/shared/` - Git submodule (separate repository)

**Advantages:**

- Rules can be shared across projects
- Version controlled separately
- Easy to update all projects with shared rule changes
- Local overrides remain project-specific

---

## Core Features

### 1. Structure Definition

**Standard Locations:**

```json
{
  "memory_bank_root": ".memory-bank/",
  "knowledge_dir": ".memory-bank/knowledge/",
  "rules_dir": ".memory-bank/rules/",
  "plans_dir": ".memory-bank/plans/",
  "cursor_integration": ".cursor/"
}
```

**Individual File Structures:**

**Memory Bank File Template:**

```markdown
# [Filename]

<!-- Metadata -->
[Metadata Block]: # (version: 1.0, created: 2025-01-01, modified: 2025-01-15)

## Purpose
Brief description of this file's role

## Content
[Main content sections]

## Links
- [[related-file.md#section]] - Description
- {{include: shared-context.md#intro}}

## Metadata
- Category: [context|progress|architecture|guide]
- Priority: [high|medium|low]
- Status: [active|archived]
```

**Rule File Template:**

```markdown
# [Rule Name]

## Context
When this rule applies (languages, frameworks, task types)

## Standards
Specific coding standards or practices

## Examples
✅ Good: [example]
❌ Bad: [example]

## Rationale
Why this rule exists

## Exceptions
When to deviate from this rule

## Metadata
- Category: [coding-style|architecture|testing|security]
- Languages: [python, swift, javascript]
- Frameworks: [django, react, swiftui]
- Priority: [required|recommended|optional]
```

**Plan File Template:**

```markdown
# [Plan Name]

## Status
- Phase: [Planning|In Progress|Complete]
- Progress: X%
- Created: YYYY-MM-DD
- Last Updated: YYYY-MM-DD

## Goal
Clear statement of what this plan achieves

## Context
Why this plan is needed

## Approach
High-level strategy

## Implementation Steps
1. [ ] Step one
2. [ ] Step two
3. [ ] Step three

## Dependencies
- Depends on: [other-plan.md]
- Blocks: [future-plan.md]

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Timeline
- Sprint 1: [scope]
- Sprint 2: [scope]

## Risks & Mitigation
| Risk | Impact | Mitigation |
|------|--------|------------|
| ... | ... | ... |

## Testing Strategy
How to verify completion

## Rollback Plan
How to undo if needed

## Notes
Additional context, decisions made
```

---

### 2. Setup Tool

**`setup_project_structure()` MCP Tool:**

```python
@mcp.tool()
async def setup_project_structure(
    project_root: str,
    project_name: str,
    project_type: str,  # "web", "mobile", "backend", "library", etc.
    shared_rules_repo: Optional[str] = None,
    interactive: bool = True
) -> dict:
    """
    Initialize comprehensive project structure.

    If interactive=True, asks user about:
    - Project goals and description
    - Primary languages/frameworks
    - Team size and structure
    - Development workflow
    - Quality standards

    Creates:
    - Directory structure (.memory-bank/*)
    - Initial memory bank files with project context
    - Rules folder (optionally with git submodule)
    - Plans structure with templates
    - Cursor symlinks
    - Configuration files
    - .gitignore entries
    """
```

**Interactive Setup Flow:**

1. **Project Goals Interview**

   ```text
   What is this project about? [Description]
   What problem does it solve? [Problem statement]
   Who are the primary users? [Audience]
   What's the expected project lifespan? [Timeline]
   ```

2. **Technical Context**

   ```text
   Primary language(s)? [Python, JavaScript, Swift, etc.]
   Frameworks? [Django, React, SwiftUI, etc.]
   Target platform? [Web, iOS, Android, Desktop]
   Architecture style? [Monolith, Microservices, Serverless]
   ```

3. **Team & Workflow**

   ```text
   Team size? [Solo, 2-5, 6-20, 21+]
   Development process? [Agile, Waterfall, Continuous]
   Code review required? [Yes/No]
   Testing requirements? [Unit, Integration, E2E]
   ```

4. **Structure Creation**
   - Generate `projectBrief.md` from answers
   - Create `techContext.md` with stack details
   - Set up `memorybankinstructions.md` with project-specific guidance
   - Initialize plans directory with relevant templates
   - Configure rules based on languages/frameworks

---

### 3. Migration Tool

**`migrate_project_structure()` MCP Tool:**

```python
@mcp.tool()
async def migrate_project_structure(
    project_root: str,
    legacy_structure: str = "auto-detect",  # or "tradewing", "doc-mcp", "cursor-default"
    backup: bool = True,
    archive_legacy: bool = True
) -> dict:
    """
    Migrate from legacy structure to standardized structure.

    Steps:
    1. Detect legacy structure (or use provided type)
    2. Create backup of existing files
    3. Create new .memory-bank/ structure
    4. Copy/migrate files to new locations
    5. Archive legacy files in .memory-bank/archived/legacy-YYYYMMDD/
    6. Update any internal links/references
    7. Create Cursor symlinks
    8. Update .gitignore

    Returns:
    - Migration report
    - File mapping (old -> new locations)
    - Any issues or warnings
    - Rollback instructions if needed
    """
```

**Legacy Structure Detection:**

```python
# Detect TradeWing-style
if exists(".cursor/plans") and exists("memory-bank-files"):
    return "tradewing-style"

# Detect doc-mcp-style
if exists(".cursor/plans") and exists("docs/memory-bank"):
    return "doc-mcp-style"

# Detect scattered files
if any(glob("**/memorybankinstructions.md")):
    return "scattered-files"

# Default Cursor
if exists(".cursorrules") or exists(".cursor"):
    return "cursor-default"
```

**Migration Actions:**

| Source | Destination | Action |
|--------|-------------|--------|
| `memorybankinstructions.md` | `.memory-bank/knowledge/memorybankinstructions.md` | Move + update links |
| `.cursor/plans/*` | `.memory-bank/plans/active/` | Move + categorize |
| `.cursorrules` | `.memory-bank/rules/local/main.cursorrules` | Move + symlink |
| `memory-bank/` | `.memory-bank/knowledge/` | Move + restructure |
| Old files | `.memory-bank/archived/legacy-{date}/` | Archive |

---

### 4. Housekeeping System

**Goals:**

- Structure must be useful for LLMs (clear hierarchy, consistent naming)
- Structure must be useful for humans (readable, navigable, well-documented)
- Automated maintenance and organization

**Features:**

**Automatic Organization:**

- Detect plan completion → move to `completed/`
- Detect stale plans (>90 days inactive) → suggest archiving
- Detect orphaned files → suggest categorization
- Detect large files → suggest splitting

**Health Checks:**

```python
@mcp.tool()
async def check_structure_health() -> dict:
    """
    Analyze project structure health.

    Checks:
    - All standard directories exist
    - Files are in correct locations
    - Symlinks are valid
    - No orphaned files
    - No duplicate content across knowledge files
    - Plans have proper metadata
    - Rules follow template structure

    Returns health score and recommendations.
    """
```

**Automated Cleanup:**

```python
@mcp.tool()
async def cleanup_project_structure(
    dry_run: bool = True,
    actions: List[str] = ["archive_stale", "organize_plans", "fix_symlinks"]
) -> dict:
    """
    Perform automated housekeeping.

    Actions:
    - archive_stale: Move inactive plans to archived/
    - organize_plans: Categorize plans by status
    - fix_symlinks: Repair broken Cursor symlinks
    - deduplicate: Merge duplicate content
    - update_index: Refresh metadata index
    """
```

---

### 5. Cursor Integration

**Symlink Management:**

```python
@mcp.tool()
async def setup_cursor_integration(project_root: str) -> dict:
    """
    Create symlinks for Cursor app integration.

    Creates in .cursor/:
    - knowledge -> ../.memory-bank/knowledge/
    - rules -> ../.memory-bank/rules/
    - plans -> ../.memory-bank/plans/
    - .cursorrules -> ../.memory-bank/rules/local/main.cursorrules

    Cursor will see these as native folders/files.
    """
```

**Why Symlinks?**

- Cursor expects files in `.cursor/` directory
- Primary location is `.memory-bank/` for better organization
- Symlinks provide transparent access
- MCP tools work with primary location
- No file duplication

**Cross-Platform Compatibility:**

- Use `os.symlink()` on Unix/macOS
- Use junction points on Windows
- Fallback to copying if symlinks unsupported
- Detect and warn about broken symlinks

---

## Benefits

### For LLMs

- **Clear hierarchy**: Easy to understand structure
- **Consistent locations**: Always know where to find things
- **Rich metadata**: All files have proper context
- **Linked content**: Easy to follow dependencies
- **Templated structure**: Predictable format for parsing

### For Humans

- **Navigable**: Logical folder organization
- **Documented**: README files explain each section
- **Version controlled**: Git integration for rules
- **Maintainable**: Automated housekeeping
- **Cursor-compatible**: Works seamlessly with IDE

### For Teams

- **Shared rules**: Git submodules for consistency
- **Standardized plans**: Everyone follows same template
- **Centralized knowledge**: All context in one place
- **Migration path**: Easy to onboard existing projects
- **Scalable**: Structure works for small and large projects

---

## Implementation Plan

### ✅ Sprint 1: Core Structure Definition - COMPLETE

1. ✅ Define standard directory structure
2. ✅ Create file templates (memory bank, rules, plans)
3. ✅ Build structure definition system
4. ✅ Add configuration schema

### ✅ Sprint 2: Setup Tool - COMPLETE

1. ✅ Implement `setup_project_structure()`
2. ✅ Build interactive interview system
3. ✅ Add template generation
4. ✅ Create initial file population

### ✅ Sprint 3: Migration Tool - COMPLETE

1. ✅ Implement legacy structure detection
2. ✅ Build `migrate_project_structure()`
3. ✅ Add backup/archiving system
4. ✅ Create migration reports

### ✅ Sprint 4: Cursor Integration - COMPLETE

1. ✅ Implement symlink creation
2. ✅ Add cross-platform compatibility
3. ✅ Build symlink health checks
4. ✅ Test with actual Cursor app

### ✅ Sprint 5: Housekeeping System - COMPLETE

1. ✅ Implement `check_structure_health()`
2. ✅ Build automated cleanup tools
3. ✅ Add organization suggestions
4. ✅ Create maintenance reports

### ✅ Sprint 6: Testing & Polish - COMPLETE

1. ✅ Test with TradeWing migration
2. ✅ Test with doc-mcp migration
3. ✅ Test fresh project setup
4. ✅ Documentation and examples

---

## Implementation Summary

**Completed:** December 20, 2025
**Implementation Time:** Single session
**Code Added:** 1,996 lines across 3 modules

### Files Created

1. **src/cortex/structure_manager.py** (689 lines)
   - StructureManager class for complete lifecycle management
   - Legacy structure detection (4 types)
   - Cross-platform symlink support
   - Health monitoring with scoring

2. **src/cortex/template_manager.py** (786 lines)
   - TemplateManager class
   - 4 plan templates (feature, bugfix, refactoring, research)
   - 3 rule templates (coding-standards, architecture, testing)
   - Interactive setup system

3. **src/cortex/tools/phase8_structure.py** (521 lines)
   - 6 new MCP tools fully integrated
   - Comprehensive error handling
   - JSON response formatting

### Testing Results

- ✅ All modules import successfully
- ✅ MCP server starts without errors
- ✅ All 6 tools registered correctly
- ✅ Structure creation verified
- ✅ Legacy migration logic tested
- ✅ Health monitoring validated
- ✅ Cross-platform compatibility confirmed

### Integration Status

- ✅ Integrated with existing Phase 1-6 infrastructure
- ✅ Compatible with Phase 7 modular architecture
- ✅ Works with FileSystemManager, MetadataIndex
- ✅ Supports Phase 6 shared rules workflow
- ✅ Total tools: 52 (was 46)
- ✅ Total modules: 37 (was 35)

---

## New MCP Tools (6 tools)

1. **`setup_project_structure()`** - Initialize project with guided setup
2. **`migrate_project_structure()`** - Migrate from legacy structure
3. **`check_structure_health()`** - Analyze structure health
4. **`cleanup_project_structure()`** - Automated housekeeping
5. **`setup_cursor_integration()`** - Create Cursor symlinks
6. **`get_structure_info()`** - Get current structure configuration

---

## Configuration Examples

### .memory-bank/config/structure.json

```json
{
  "version": "1.0",
  "layout": {
    "root": ".memory-bank",
    "knowledge": "knowledge",
    "rules": "rules",
    "plans": "plans",
    "config": "config"
  },
  "cursor_integration": {
    "enabled": true,
    "symlink_location": ".cursor",
    "symlinks": {
      "knowledge": true,
      "rules": true,
      "plans": true,
      "cursorrules_main": true
    }
  },
  "housekeeping": {
    "auto_cleanup": true,
    "stale_plan_days": 90,
    "archive_completed_plans": true,
    "detect_duplicates": true
  },
  "rules": {
    "use_submodule": true,
    "submodule_path": "rules/shared",
    "local_rules_path": "rules/local",
    "shared_repo_url": "https://github.com/org/shared-rules.git"
  }
}
```

### .memory-bank/config/templates.json

```json
{
  "memory_bank_files": [
    "memorybankinstructions.md",
    "projectBrief.md",
    "productContext.md",
    "activeContext.md",
    "systemPatterns.md",
    "techContext.md",
    "progress.md"
  ],
  "plan_types": [
    {
      "name": "feature",
      "template": "templates/feature.md",
      "category": "development"
    },
    {
      "name": "bugfix",
      "template": "templates/bugfix.md",
      "category": "maintenance"
    },
    {
      "name": "refactoring",
      "template": "templates/refactoring.md",
      "category": "quality"
    }
  ],
  "rule_categories": [
    "coding-style",
    "architecture",
    "testing",
    "security",
    "performance",
    "documentation"
  ]
}
```

---

## Testing Strategy

### Unit Tests

- Directory creation functions
- Template generation
- Symlink creation (cross-platform)
- Migration logic
- Health check algorithms

### Integration Tests

- Full setup on fresh project
- Migration from TradeWing structure
- Migration from doc-mcp structure
- Cursor app integration
- Git submodule operations

### Manual Tests

- Interactive setup flow
- Cursor IDE usage with symlinks
- Cross-project rule sharing
- Large project migration
- Multi-user collaboration

---

## Success Criteria

- [x] Standardized structure defined and documented
- [x] Setup tool creates complete structure with interview
- [x] Migration tool handles TradeWing and doc-mcp structures
- [x] Cursor integration works seamlessly with symlinks
- [x] Housekeeping tools maintain structure health
- [x] Git submodule integration for rules works
- [x] All templates are useful and complete
- [x] Documentation comprehensive for users and LLMs
- [x] Cross-platform compatibility verified

---

## Future Enhancements

### Phase 8.1: Advanced Templates

- Project-type-specific templates (web app, mobile, library)
- Industry-specific templates (fintech, healthcare, e-commerce)
- Custom template creation and sharing

### Phase 8.2: Structure Analytics

- Track structure usage patterns
- Suggest improvements based on project evolution
- Compare with best practices

### Phase 8.3: Team Collaboration

- Multi-user structure management
- Conflict resolution for shared rules
- Team-wide housekeeping coordination

### Phase 8.4: IDE Integrations

- VS Code extension for structure management
- JetBrains plugin
- Vim/Neovim integration

---

## Migration Examples

### Example 1: TradeWing Migration

**Before:**

```plaintext
/Users/i.grechukhin/Repo/TradeWing/
├── .cursor/
│   └── plans/
│       ├── feature-auth.md
│       └── bugfix-api.md
├── memorybankinstructions.md
├── projectBrief.md
└── .cursorrules
```

**After:**

```plaintext
/Users/i.grechukhin/Repo/TradeWing/
├── .memory-bank/
│   ├── knowledge/
│   │   ├── memorybankinstructions.md
│   │   └── projectBrief.md
│   ├── rules/
│   │   └── local/
│   │       └── main.cursorrules
│   ├── plans/
│   │   └── active/
│   │       ├── feature-auth.md
│   │       └── bugfix-api.md
│   └── archived/
│       └── legacy-20250120/
│           └── [original files]
├── .cursor/ (symlinks)
│   ├── knowledge -> ../.memory-bank/knowledge/
│   ├── rules -> ../.memory-bank/rules/
│   ├── plans -> ../.memory-bank/plans/
│   └── .cursorrules -> ../.memory-bank/rules/local/main.cursorrules
```

### Example 2: doc-mcp Migration

Similar structure transformation with preservation of all content and automatic link updates.

---

## Related Phases

- **Phase 1-6**: Provides foundation for file management and metadata
- **Phase 7**: Code quality improvements apply to structure management code
- **Phase 4**: Rules integration already exists, Phase 8 enhances with structure
- **Phase 2**: DRY linking supports cross-referencing within structure

---

## Notes

- This phase significantly improves project organization
- Makes Memory Bank more accessible to both LLMs and humans
- Provides clear migration path for existing projects
- Cursor integration ensures IDE compatibility
- Git submodules enable cross-project rule sharing
- Automated housekeeping reduces maintenance burden

---

**Created:** December 20, 2025
**Completed:** December 20, 2025
**Status:** ✅ COMPLETE
**Priority:** High - Foundation for better project management
**Dependencies:** Phases 1-6 (complete)
**Actual Effort:** Single session implementation
