# Phase 7.10: MCP Tool Consolidation

**Status:** Planning
**Priority:** HIGH ⚠️
**Estimated Effort:** 4-6 hours
**Dependencies:** None

---

## Problem Statement

**Current State:** 52 MCP tools exposed by the server
**Industry Limit:** Cursor IDE has a hard limit of ~80 tools across ALL MCPs
**Issue:** We're consuming 65% of a single IDE's tool budget, leaving little room for other MCPs

This is a **critical usability issue** that must be addressed before Phase 7.9 completion.

---

## Current Tool Inventory

### Phase 1: Foundation (10 tools)

1. ✅ `initialize_memory_bank` - **ONE-TIME** setup
2. ✅ `read_memory_bank_file` - Core read operation
3. ✅ `write_memory_bank_file` - Core write operation
4. ✅ `get_file_metadata` - File info
5. ✅ `get_dependency_graph` - Dependency visualization
6. ✅ `get_version_history` - Version history
7. ✅ `rollback_file_version` - Version rollback
8. ✅ `check_migration_status` - **ONE-TIME** migration check
9. ✅ `migrate_memory_bank` - **ONE-TIME** migration
10. ✅ `get_memory_bank_stats` - Statistics

### Phase 2: DRY Linking (4 tools)

1. ✅ `parse_file_links` - Parse links
2. ✅ `resolve_transclusions` - Resolve includes
3. ✅ `validate_links` - Validate links
4. ✅ `get_link_graph` - Link visualization

### Phase 3: Validation (5 tools)

1. ✅ `validate_memory_bank` - Full validation
2. ✅ `check_duplications` - Duplication detection
3. ✅ `get_quality_score` - Quality metrics
4. ✅ `check_token_budget` - Token budget
5. ✅ `configure_validation` - Configuration

### Phase 4: Optimization (7 tools)

1. ✅ `optimize_context` - Context optimization
2. ✅ `load_progressive_context` - Progressive loading
3. ✅ `summarize_content` - Content summarization
4. ✅ `get_relevance_scores` - Relevance scoring
5. ✅ `configure_optimization` - Configuration
6. ✅ `index_rules` - Rules indexing
7. ✅ `get_relevant_rules` - Rules retrieval

### Phase 5.1: Analysis (3 tools)

1. ✅ `analyze_usage_patterns` - Usage analysis
2. ✅ `analyze_structure` - Structure analysis
3. ✅ `get_optimization_insights` - Insights

### Phase 5.2: Refactoring (4 tools)

1. ✅ `suggest_consolidation` - Consolidation suggestions
2. ✅ `suggest_file_splits` - Split suggestions
3. ✅ `suggest_reorganization` - Reorganization suggestions
4. ✅ `preview_refactoring` - Preview changes

### Phase 5.3-5.4: Execution & Learning (6 tools)

1. ✅ `approve_refactoring` - Approval workflow
2. ✅ `apply_refactoring` - Execute refactoring
3. ✅ `rollback_refactoring` - Rollback changes
4. ✅ `get_refactoring_history` - History
5. ✅ `provide_feedback` - Feedback submission
6. ✅ `configure_learning` - Configuration

### Phase 6: Shared Rules (4 tools)

1. ✅ `setup_shared_rules` - **ONE-TIME** setup
2. ✅ `sync_shared_rules` - Sync with remote
3. ✅ `update_shared_rule` - Update rule
4. ✅ `get_rules_with_context` - Context-aware rules

### Phase 8: Project Structure (6 tools)

1. ✅ `setup_project_structure` - **ONE-TIME** setup
2. ✅ `migrate_project_structure` - **ONE-TIME** migration
3. ✅ `setup_cursor_integration` - **ONE-TIME** setup
4. ✅ `check_structure_health` - Health check
5. ✅ `cleanup_project_structure` - Housekeeping
6. ✅ `get_structure_info` - Structure info

### Legacy (3 tools)

1. ⚠️ `get_memory_bank_structure` - **DEPRECATED**
2. ⚠️ `generate_memory_bank_template` - **DEPRECATED**
3. ⚠️ `analyze_project_summary` - **DEPRECATED**

### Guides (1 tool)

1. ✅ `memory_bank_guide` - Help/documentation

---

## Consolidation Strategy

### Target: Reduce from 52 → 25 tools (52% reduction)

### 1. Remove One-Time Tools → Convert to Prompts (7 tools removed)

**Rationale:** Setup/migration tools are used once per project. They don't need to be exposed as MCP tools.

**Convert to Prompts:**

- ❌ `initialize_memory_bank` → Prompt template
- ❌ `check_migration_status` → Prompt template
- ❌ `migrate_memory_bank` → Prompt template
- ❌ `setup_shared_rules` → Prompt template
- ❌ `setup_project_structure` → Prompt template
- ❌ `migrate_project_structure` → Prompt template
- ❌ `setup_cursor_integration` → Prompt template

**Implementation:**

- Create `/docs/prompts/` directory
- Add prompt templates for each one-time operation
- Include in documentation
- Remove tool implementations

**Savings:** -7 tools

---

### 2. Remove Legacy/Deprecated Tools (3 tools removed)

**Rationale:** These tools were superseded by better implementations.

**Remove:**

- ❌ `get_memory_bank_structure` → Use `get_structure_info` instead
- ❌ `generate_memory_bank_template` → Use `setup_project_structure` instead
- ❌ `analyze_project_summary` → No longer used

**Savings:** -3 tools

---

### 3. Group Related Tools (12 tools consolidated → 6 tools)

**Rationale:** Many tools perform similar operations on different entities. Group them under single parameterized tools.

#### 3.1 File Operations Group (3 → 1 tool)

**Consolidate:**

- `read_memory_bank_file`
- `write_memory_bank_file`
- `get_file_metadata`

**Into:**

```python
async def manage_file(
    operation: Literal["read", "write", "metadata"],
    file_name: str,
    content: str | None = None,
    project_root: str | None = None
) -> str:
```

**Savings:** -2 tools

#### 3.2 Analysis Group (3 → 1 tool)

**Consolidate:**

- `analyze_usage_patterns`
- `analyze_structure`
- `get_optimization_insights`

**Into:**

```python
async def analyze(
    target: Literal["usage", "structure", "insights"],
    project_root: str | None = None
) -> str:
```

**Savings:** -2 tools

#### 3.3 Refactoring Suggestions Group (3 → 1 tool)

**Consolidate:**

- `suggest_consolidation`
- `suggest_file_splits`
- `suggest_reorganization`

**Into:**

```python
async def suggest_refactoring(
    type: Literal["consolidation", "split", "reorganization"],
    project_root: str | None = None
) -> str:
```

**Savings:** -2 tools

#### 3.4 Validation Group (3 → 1 tool)

**Consolidate:**

- `validate_memory_bank`
- `check_duplications`
- `get_quality_score`

**Into:**

```python
async def validate(
    check: Literal["full", "duplications", "quality"],
    project_root: str | None = None
) -> str:
```

**Savings:** -2 tools

**Total Group Savings:** -8 tools

---

### 4. Merge Configuration Tools (4 tools → 1 tool)

**Rationale:** All configuration operations can be unified.

**Consolidate:**

- `configure_validation`
- `configure_optimization`
- `configure_learning`

**Into:**

```python
async def configure(
    component: Literal["validation", "optimization", "learning"],
    config: dict[str, object],
    project_root: str | None = None
) -> str:
```

**Savings:** -2 tools

---

### 5. Optimize Rarely Used Tools (Remove 3 tools)

**Rationale:** Some tools have very low usage and can be replaced by combinations of other tools.

**Remove:**

- ❌ `check_token_budget` → Use `get_memory_bank_stats` instead (includes token info)
- ❌ `get_refactoring_history` → Use `get_memory_bank_stats` instead
- ❌ `cleanup_project_structure` → Merge into `check_structure_health` with `fix: true` param

**Savings:** -3 tools

---

## Final Tool List (25 tools)

### Core Operations (5 tools)

1. ✅ `manage_file` - Read/write/metadata (consolidated)
2. ✅ `get_dependency_graph` - Dependency visualization
3. ✅ `get_version_history` - Version history
4. ✅ `rollback_file_version` - Version rollback
5. ✅ `get_memory_bank_stats` - Statistics (enhanced)

### DRY Linking (4 tools)

1. ✅ `parse_file_links` - Parse links
2. ✅ `resolve_transclusions` - Resolve includes
3. ✅ `validate_links` - Validate links
4. ✅ `get_link_graph` - Link visualization

### Validation & Quality (1 tool)

1. ✅ `validate` - Full/duplications/quality (consolidated)

### Optimization (4 tools)

1. ✅ `optimize_context` - Context optimization
2. ✅ `load_progressive_context` - Progressive loading
3. ✅ `summarize_content` - Content summarization
4. ✅ `get_relevance_scores` - Relevance scoring

### Rules Management (3 tools)

1. ✅ `index_rules` - Rules indexing
2. ✅ `get_relevant_rules` - Rules retrieval
3. ✅ `sync_shared_rules` - Sync with remote

### Analysis (1 tool)

1. ✅ `analyze` - Usage/structure/insights (consolidated)

### Refactoring (3 tools)

1. ✅ `suggest_refactoring` - Consolidation/split/reorganization (consolidated)
2. ✅ `preview_refactoring` - Preview changes
3. ✅ `apply_refactoring` - Execute refactoring (includes approve/rollback)

### Shared Rules (2 tools)

1. ✅ `update_shared_rule` - Update rule
2. ✅ `get_rules_with_context` - Context-aware rules

### Project Structure (2 tools)

1. ✅ `check_structure_health` - Health check (includes cleanup)
2. ✅ `get_structure_info` - Structure info

### Help (1 tool)

1. ✅ `memory_bank_guide` - Help/documentation

---

## Implementation Plan

### Step 1: Create Prompt Templates (2 hours)

- Create `docs/prompts/` directory
- Write prompt templates for 7 one-time operations
- Document in getting-started guide
- Test prompts with actual use cases

### Step 2: Remove Legacy Tools (30 minutes)

- Delete 3 legacy tool implementations
- Update documentation
- Remove from tool registry

### Step 3: Consolidate Tools (2 hours)

- Implement 6 consolidated tools
- Preserve all existing functionality
- Add comprehensive tests
- Ensure backward compatibility via parameters

### Step 4: Update Documentation (1 hour)

- Update API docs
- Update examples
- Create migration guide for users

### Step 5: Testing & Validation (1 hour)

- Test all 25 tools
- Verify functionality preservation
- Performance testing
- Integration tests

---

## Benefits

### For Users

- ✅ **65% fewer tools** to learn and remember
- ✅ **Simpler API** with logical groupings
- ✅ **More IDE budget** for other MCPs
- ✅ **Faster tool discovery** in IDE
- ✅ **Better organization** by purpose

### For Development

- ✅ **Easier maintenance** with fewer tools
- ✅ **Better code reuse** via consolidation
- ✅ **Clearer responsibilities** per tool
- ✅ **Reduced testing surface** area

### For Performance

- ✅ **Faster initialization** (fewer tools to register)
- ✅ **Lower memory footprint** (less overhead)
- ✅ **Better MCP protocol efficiency**

---

## Risks & Mitigations

### Risk 1: Breaking Changes

**Risk:** Users relying on old tool names

**Mitigation:**

- Provide clear migration guide
- Document all tool mappings
- Add deprecation warnings first (optional phase)

### Risk 2: Parameter Complexity

**Risk:** Consolidated tools may have complex parameter sets

**Mitigation:**

- Use TypedDict for complex parameters
- Provide clear parameter documentation
- Include parameter validation

### Risk 3: Testing Coverage

**Risk:** Consolidation may miss edge cases

**Mitigation:**

- Preserve all existing tests
- Add new tests for consolidated tools
- Test all parameter combinations

---

## Success Criteria

- ✅ Tool count: 52 → 25 (52% reduction)
- ✅ All 1,707 tests passing
- ✅ No functionality lost
- ✅ Documentation complete
- ✅ Performance maintained or improved
- ✅ Migration guide available

---

## Next Steps After This Phase

With tools consolidated to 25, we can:

1. Complete Phase 7.9 lazy loading (simpler with fewer tools)
2. Move to Phase 7.11 (Code style consistency)
3. Eventually reach Phase 8 (Security & Rules compliance)

---

**Created:** December 27, 2025
**Phase:** 7.10
**Priority:** HIGH ⚠️
**Next Phase:** Phase 7.9 (Full Lazy Loading) or Phase 7.11 (Code Style)
