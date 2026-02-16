# Phase 54: Session Start Initializer Pattern

**Status:** PENDING
**Created:** 2026-02-11
**Priority:** MEDIUM
**Estimated Effort:** 1 sprint
**Related:** Phase 51 (Context Loading), Compound Engineering Alignment

## Goal

Implement a `session_start` tool that combines orientation tasks (reading progress, checking git status, loading active context, health check) into a single call — reducing the tokens and time agents spend getting their bearings at the start of every session, inspired by Anthropic's "Effective Harnesses for Long-Running Agents."

## Context

From Anthropic's long-running agent harness article, every agent session starts with a structured orientation sequence:

1. `pwd` to see the working directory
2. Read git logs and progress files to get up to speed
3. Read the features/tasks list and choose what to work on next
4. Run a basic health check to catch any broken state

Currently in Cortex, agents must manually call 3-5 tools at session start:

- `load_context(task_description="...")` — often with a vague description
- `manage_file(file_name="activeContext.md", operation="read")` — to see recent work
- `manage_file(file_name="roadmap.md", operation="read")` — to see what's next
- Sometimes `get_memory_bank_stats()` — to check health
- Sometimes `validate(check_type="quality")` — to verify integrity

This wastes 3-5 tool calls and 10K+ tokens before productive work begins.

**Reference:** <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>

## Approach

1. Create a `session_start` tool that aggregates orientation data
2. Return a structured "session brief" with everything an agent needs
3. Include a lightweight health check
4. Suggest next work item from roadmap

## Implementation Steps

### Step 1: Design Session Brief Schema

- [ ] Create `SessionBrief` Pydantic model:

  ```python
  class SessionBrief(BaseModel):
      project_name: str
      current_focus: str  # From activeContext "## Current Focus"
      recent_completed: list[str]  # Last 3-5 completed items
      next_work_item: str | None  # First PENDING item from roadmap
      next_work_plan_path: str | None  # Path to plan file
      health: HealthSummary  # Quick health check results
      git_status: GitStatusSummary | None  # Uncommitted changes summary
      token_budget_status: str  # "healthy" / "warning" / "over_budget"
      session_suggestions: list[str]  # Actionable suggestions
  ```

- [ ] Design concise output format (target: < 1000 tokens)
- [ ] Unit tests for SessionBrief construction

### Step 2: Implement session_start Tool

- [ ] Create `session_start(task_description: str | None = None)` tool:
  - Reads activeContext.md "## Current Focus" and "## Recent Changes" sections
  - Reads roadmap.md to find first PENDING item
  - Runs lightweight health check (file count, token budget, any validation errors)
  - Optionally reads git status (uncommitted changes count)
  - If task_description provided, includes relevance scores for memory bank files
  - Returns SessionBrief
- [ ] Implement as single tool call replacing 3-5 manual calls
- [ ] Include "session_suggestions" with smart recommendations:
  - "You have uncommitted changes in 3 files — consider committing first"
  - "Token budget at 85% — consider compaction"
  - "Next roadmap item: Phase 50 — Tool Consolidation"
  - "activeContext.md was last updated 3 days ago — may need refresh"

### Step 3: Integrate with Prompts

- [ ] Update implement-next-roadmap-step prompt to use `session_start` as first action
- [ ] Update CLAUDE.md to recommend `session_start` at conversation beginning
- [ ] Add session_start to AGENTS.md workflow section
- [ ] Create examples showing session_start → targeted load_context → work pattern

### Step 4: Health Check Integration

- [ ] Include quick validation in session_start:
  - Memory bank file count and token totals
  - Any missing required files (projectBrief, activeContext, roadmap)
  - Token budget status (healthy/warning/over)
  - Last write timestamp for each file (detect stale files)
- [ ] If critical issues found, surface them prominently in session brief
- [ ] Include link to relevant fix tool (e.g., "Run fix_quality_issues to resolve")

### Step 5: Testing and Validation

- [ ] Unit tests for session_start tool (95%+ coverage)
- [ ] Integration test: session_start returns valid SessionBrief
- [ ] Measure orientation time: before (3-5 tool calls, ~15 seconds) vs after (1 call, ~3 seconds)
- [ ] Measure token savings: before (~10K tokens) vs after (~800 tokens)
- [ ] Verify session_start correctly identifies next work item from roadmap

## Dependencies

- Phase 51 (Section-Level Loading) — session_start can use section reads internally
- activeContext.md, roadmap.md — must follow expected format

## Success Criteria

1. Single `session_start` call replaces 3-5 manual orientation calls
2. Session brief is < 1000 tokens
3. Correctly identifies next work item from roadmap
4. Health check catches critical issues (missing files, over-budget tokens)
5. 95%+ test coverage

## Testing Strategy

- **Coverage Target:** 95%+
- **Unit Tests:** SessionBrief construction, next-work-item extraction from roadmap, health check logic, git status parsing, suggestion generation
- **Integration Tests:** Full session_start with real memory bank files
- **Edge Cases:** Empty roadmap, missing activeContext, no git repo, all items completed, corrupted memory bank files
- **AAA Pattern:** All tests follow Arrange-Act-Assert
- **Pydantic v2:** SessionBrief and sub-models for response validation

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| session_start too slow (aggregates many reads) | Medium | Parallelize reads, cache metadata, keep health check lightweight |
| Roadmap parsing fragile | Low | Use existing roadmap parsing from plan tools |
| Git status unavailable | Low | Make git_status optional, graceful fallback |
