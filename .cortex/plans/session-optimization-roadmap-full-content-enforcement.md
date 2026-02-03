# Session Optimization (2026-02-03): Roadmap Full-Content Enforcement

**Status**: PENDING  
**Created**: 2026-02-03  
**Source**: `.cortex/reviews/session-optimization-2026-02-03T19-23.md`  
**Priority**: High

## Goal

Prevent roadmap truncation during plan creation by strengthening the create-plan prompt and memory-bank-updater so that `manage_file(file_name="roadmap.md", operation="write", content=...)` is never called with truncated or summarized content. Session analysis (2026-02-03T19-23) found that a plan-creation run overwrote the full roadmap with shortened content, requiring restore from git.

## Context

- **What happened**: During plan creation, the roadmap was updated via `manage_file(write, content=...)` with content that replaced full sections by a single “truncated for MCP write” line. That removed many existing roadmap entries until the full roadmap was restored from git and the new plan entry re-applied.
- **Existing guard**: Phase 63 (COMPLETE) added full-content-only rule and post-write verification in create-plan Step 6/7 and memory-bank-updater. The violation occurred because the agent still passed truncated content (e.g. due to size or simplification).
- **Related**: add_roadmap_entry MCP tool (pending) would reduce truncation risk by allowing single-entry inserts instead of full-file writes.

## Implementation Steps

### Step 1: Strengthen create-plan Step 6 anti-truncation language

**Target**: `.cortex/synapse/prompts/create-plan.md` (or equivalent), Step 6 (roadmap update).

**Tasks**:

1. Add an explicit **prohibition**: "Never pass a shortened, summarized, or placeholder version of the roadmap. The `content` parameter MUST be the complete file content as read in Step 6 (read roadmap). If the content would be larger than a safe payload, do not truncate; use the full content."
2. Add a **pre-write check**: "Before calling manage_file(write), confirm that the string length of `content` is at least as long as the roadmap content read in Step 6. If it is shorter, do not write; re-build the full content (current roadmap + new/updated entry only) and try again."
3. Optionally reference add_roadmap_entry: "When that tool is available, prefer add_roadmap_entry for adding a single new plan entry instead of full-content write."

**Acceptance**: Create-plan Step 6 text includes the prohibition and pre-write length check; agents are explicitly instructed not to truncate.

### Step 2: Memory-bank-updater agent instructions

**Target**: `.cortex/synapse/agents/memory-bank-updater.md` (or equivalent).

**Tasks**:

1. Add a bullet under "Roadmap update (plan creation)": "Never pass truncated or summarized roadmap content to manage_file(write). The content must be the full, unabridged roadmap text. If in doubt, content length must be >= length of the roadmap as last read."
2. Add recovery instruction: "If a previous write accidentally used truncated content, restore by reading the roadmap from version control (e.g. git show HEAD:path) or from backup, append the intended new/updated entry, then write the full result."

**Acceptance**: Memory-bank-updater instructions include the no-truncation rule and recovery note.

### Step 3: Optional – integration test

**Target**: `tests/integration/` (e.g. test_plan_creation_workflow_compliance or new file).

**Tasks**:

1. Add a test or scenario that asserts create-plan prompt (or agent instructions) contains the anti-truncation wording (e.g. "full content", "never truncate", or "content length" check). This guards against prompt drift.

**Acceptance**: Test exists and passes; prompt/agent text is asserted.

## Success Criteria

- Create-plan Step 6 and memory-bank-updater explicitly prohibit truncated roadmap content and require full-content.
- Pre-write length check (or equivalent) is documented so agents do not pass shortened content.
- No new roadmap truncation incidents when adding a single plan entry.

## Dependencies

- Phase 63 (create-plan full-content rule) – already in place; this plan tightens enforcement and adds verification.
- add_roadmap_entry MCP tool (pending) – would complement this by reducing need for full-content writes.

## Testing Strategy

- **Unit**: N/A (prompt/agent text changes).
- **Integration**: Assert create-plan and memory-bank-updater content contains the new anti-truncation and length-check language (string or regex match in prompt/agent file).
- **Manual**: Run create-plan flow once and confirm roadmap is updated with full content (no entries removed).

## Notes

- Session report: `.cortex/reviews/session-optimization-2026-02-03T19-23.md`.
- Phase 63: `.cortex/plans/archive/Phase63/phase-63-harden-create-plan-roadmap-writes.md`.
