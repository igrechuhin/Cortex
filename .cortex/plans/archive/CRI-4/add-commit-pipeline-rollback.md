# Add Transactional Rollback to Commit Pipeline

**Status**: COMPLETED
**Priority**: Critical
**Complexity**: Medium
**Category**: Fix / Infrastructure
**Component**: synapse/prompts/commit
**Work Type**: fix
**Execution Order**: 4
**Depends On**: add-mcp-circuit-breaker-pattern (for checkpoint infrastructure)

## Goal

Add pre-pipeline state snapshotting and automated rollback offer when the commit pipeline fails mid-execution, preventing orphaned mutations from formatting fixes, quality fixes, and memory bank updates.

## Context

- The commit pipeline (commit.md) has 15+ steps that mutate state progressively: Steps 0-4 may apply formatting/quality fixes, Steps 5-8 update memory bank files, Steps 9-11 stage and commit.
- A failure at Step 10 leaves Steps 0-9 mutations in place with no undo. Sessions 7 and 17 show MCP drops at Step 12 leaving partial state.
- `manage_file` in `src/cortex/tools/files/crud_operations.py` already creates snapshots with version numbers and `snapshot_id`. This can be leveraged for memory bank rollback.
- Git stash can preserve the working tree state before pipeline mutations.

## Implementation Steps

### Step 1: Add pre-pipeline snapshot step to commit.md

**File**: `.cortex/synapse/prompts/commit.md` (before Step 0, after the resume check from circuit-breaker plan)

Add:

```markdown
### Step -0.5: Create rollback snapshot

1. Run `git stash push -m "cortex-commit-pipeline-snapshot-$(date +%Y%m%d%H%M%S)" --include-untracked`
2. Immediately `git stash pop` to restore working state (stash remains in reflog)
3. Record the stash ref in pipeline state via `checkpoint_write`: `snapshot_ref: "stash@{0}"`
4. Note: This creates a recoverable point. On failure, `git stash apply <ref>` restores pre-pipeline state.

**Alternative if no git changes yet**: If `git status` shows clean working tree, skip stash and record `snapshot_ref: "HEAD"`.
```

### Step 2: Add rollback offer on pipeline failure

**File**: `.cortex/synapse/prompts/commit.md` (in error handling / circuit-breaker section)

Add:

```markdown
### On Pipeline Failure (any step)

1. Report the failure clearly with step number and error.
2. Check `snapshot_ref` from pipeline state.
3. Offer: "Pipeline failed at Step {N}. Steps 0-{N-1} mutations are in your working tree. To rollback: `git checkout -- .` will revert file changes. Memory bank snapshots are available via `manage_file` versioning."
4. Do NOT auto-rollback — always offer and let the user decide.
```

### Step 3: Document memory bank snapshot recovery

**File**: `.cortex/synapse/agents/pipeline-state-tracker.md`

Add a section documenting that `manage_file` creates automatic snapshots and how to restore a previous version using `snapshot_id`.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `rollback` or `snapshot` | `.cortex/synapse/prompts/commit.md` | Snapshot step and rollback offer present |
| `snapshot_ref` | `.cortex/synapse/agents/pipeline-state-tracker.md` | Documented in state schema |

## Dependencies

- `add-mcp-circuit-breaker-pattern` (for pipeline-state-tracker checkpoint infrastructure and resume logic)

## Success Criteria

- Commit pipeline creates a recoverable snapshot before mutations.
- Pipeline failure offers clear rollback instructions.
- Memory bank snapshot recovery is documented.
- No auto-rollback without user consent.

## Testing Strategy

- **Coverage Target**: N/A (Synapse prompt changes only)
- **Manual verification**: Trigger a pipeline failure and verify snapshot ref is available.

## Risks & Mitigation

- **Risk**: `git stash push` + immediate `pop` might not preserve the stash in reflog on all git versions. **Mitigation**: Use `git stash create` (creates stash object without applying) + `git stash store` to keep it named.
