# Phase 50: Rename optimize_context to load_context - COMPLETE (2026-01-20)

## Problem Statement

The current tool name `optimize_context` is misleading and causes agents to skip using it when they should.

### Evidence from Session Analysis (2026-01-20)

When asked to fix a CI failure, the agent:

1. **Skipped loading project context** - didn't read memory bank or rules
2. **Made changes without understanding project patterns** - risked incorrect fixes
3. **Justified skipping** by saying "task felt simple" and "optimize_context sounds optional"

### Why the Name is Misleading

| What "optimize_context" Suggests | What It Actually Does |
|----------------------------------|----------------------|
| Performance tuning | Loads relevant files |
| Optional enhancement | Essential first step |
| Compress existing context | Select and fetch context |
| Use when worried about tokens | Use to understand project |

### Impact

- Agents treat it as optional → skip it for "simple" tasks
- Agents don't load rules/patterns before making changes
- Leads to fixes that may not align with project standards

---

## Proposed Solution

Rename `optimize_context` to `load_context` (or similar intent-revealing name).

### Name Options

| Option | Pros | Cons |
|--------|------|------|
| `load_context` | Clear action, signals "do this first" | Doesn't convey intelligence/relevance |
| `load_relevant_context` | Describes what it returns | Longer name |
| `prepare_context` | Signals preparation step | Vague about what it does |
| `get_task_context` | Task-focused, clear action | Doesn't convey memory bank scope |
| `fetch_project_context` | Explicit about project scope | Long, "fetch" less common |

**Recommended: `load_context`**

- Short and clear
- Action-oriented (load = do something)
- Doesn't sound optional
- Matches similar tools: `load_progressive_context`

---

## Scope of Changes

### Files to Modify

Based on grep results, 55 files reference `optimize_context`:

#### Core Implementation (5 files)

- `src/cortex/tools/phase4_optimization_handlers.py` - MCP tool definition
- `src/cortex/tools/phase4_optimization.py` - Re-exports
- `src/cortex/tools/phase4_context_operations.py` - Implementation (`optimize_context_impl`)
- `src/cortex/optimization/context_optimizer.py` - Core class
- `src/cortex/core/protocols/optimization.py` - Protocol definition

#### Tests (4 files)

- `tests/unit/test_progressive_loader.py`
- `tests/unit/test_context_optimizer.py`
- `tests/tools/test_phase4_optimization.py`
- `tests/integration/test_mcp_tools_integration.py`
- `tests/integration/test_workflows.py`

#### Documentation (10+ files)

- `README.md`
- `CLAUDE.md`
- `docs/api/tools.md`
- `docs/api/modules.md`
- `docs/api/protocols.md`
- `docs/getting-started.md`
- `docs/mcp-tool-timeouts.md`
- `docs/adr/ADR-003-lazy-manager-initialization.md`
- `docs/adr/ADR-005-tool-consolidation.md`

#### Synapse (prompts/rules) (5+ files)

- `.cortex/synapse/prompts/analyze-context-effectiveness.md`
- `.cortex/synapse/prompts/implement-next-roadmap-step.md`
- `.cortex/synapse/prompts/prompts-manifest.json`
- `.cortex/synapse/rules/python/python-mcp-development.mdc`

#### Plans/History (30+ files)

- Various plan and history files in `.cortex/plans/` and `.cortex/history/`

---

## Implementation Plan

### Step 1: Rename Core Tool (Breaking Change)

1. Rename MCP tool in `phase4_optimization_handlers.py`:

   ```python
   @mcp.tool()
   async def load_context(  # was: optimize_context
       task_description: str,
       token_budget: int | None = None,
       strategy: str = "dependency_aware",
       project_root: str | None = None,
   ) -> str:
       """Load relevant context for a task within token budget.
       
       This tool should be called at the START of any task to:
       - Load memory bank files relevant to the task
       - Load applicable rules and patterns
       - Provide project context before making changes
       
       Args:
           task_description: Description of the task to perform
           token_budget: Maximum tokens to include (default from config)
           strategy: Loading strategy (dependency_aware, priority, hybrid)
           project_root: Project root path (default: current directory)
       
       Returns:
           JSON with selected files, their content, and relevance scores
       """
   ```

2. Keep internal class name `ContextOptimizer` (implementation detail)

3. Rename implementation function:
   - `optimize_context_impl` → `load_context_impl`

### Step 2: Update Re-exports

Update `phase4_optimization.py`:

```python
from cortex.tools.phase4_optimization_handlers import (
    load_context,  # was: optimize_context
    load_progressive_context,
    summarize_content,
    get_relevance_scores,
)

__all__ = [
    "load_context",  # was: optimize_context
    ...
]
```

### Step 3: Add Backward Compatibility Alias (Optional)

For gradual migration, temporarily keep alias:

```python
# Deprecated alias for backward compatibility
optimize_context = load_context  # Remove after migration
```

### Step 4: Update All References

Use search-and-replace with review:

- `optimize_context` → `load_context`
- `optimize_context_impl` → `load_context_impl`

### Step 5: Update Documentation

- Update tool descriptions to emphasize "use this first"
- Add guidance on when to use `load_context`
- Update analyze-context-effectiveness.md prompt

### Step 6: Update Tests

Rename test functions and update assertions.

---

## Verification Checklist

- [x] MCP tool renamed and functional
- [x] All imports updated
- [x] All tests pass (70+ tests)
- [x] Documentation updated (9 files)
- [x] Synapse prompts/rules updated
- [x] No broken references (internal method names preserved as planned)
- [x] Type checking passes (pyright) - 0 errors
- [x] Linting passes (ruff) - 0 errors

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking external integrations | Low | Medium | Add deprecation alias |
| Missed references | Medium | Low | Grep verification |
| Test failures | Medium | Low | Run full test suite |
| Documentation drift | Low | Low | Update all docs in same PR |

---

## Success Criteria

1. Tool renamed to `load_context`
2. All 55 file references updated
3. Tests pass (100%)
4. Type checking passes (0 errors)
5. Documentation reflects new name and purpose
6. Agents start using `load_context` as a first step

---

## Timeline

| Step | Effort |
|------|--------|
| Core rename | 30 min |
| Update references | 1 hour |
| Update tests | 30 min |
| Update documentation | 30 min |
| Verification | 30 min |
| **Total** | ~3 hours |

---

## Alternative Considered: Keep Name, Improve Documentation

Instead of renaming, we could:

- Update tool docstring to emphasize "use first"
- Add prominent notes in prompts
- Update AGENTS.md to mandate its use

**Rejected because**: The name itself creates the wrong mental model. Documentation can't fully overcome a misleading name.

---

## Decision

**Proceed with rename to `load_context`**

The misleading name actively causes agents to skip an essential step. A clear name change will:

1. Signal that context loading is a required first step
2. Align with user expectations
3. Reduce "I forgot to use it" incidents

---

## References

- Session analysis: 2026-01-20 commit procedure failure
- User feedback: "optimize_context is a misleading name"
- AGENTS.md: "Load applicable rules before actions"
