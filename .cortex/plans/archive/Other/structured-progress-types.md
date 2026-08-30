---
title: "Per-Tool Structured Progress Types"
component: core
work_type: refactor
status: DONE
priority: Medium
created: 2026-04-06
completed: 2026-04-09
depends_on: []
---

## Per-Tool Structured Progress Types

## Goal

Replace generic progress reporting (plain strings in `ctx.report_progress()`) with strongly-typed Pydantic progress models - one per tool category. Makes progress data machine-readable in Cursor's MCP UI and removes ambiguity of free-form status strings.

## Context

- Claude Code defines typed progress classes per tool: `BashProgress`, `AgentToolProgress`, `WebSearchProgress`, `MCPProgress`.
- Cortex calls `ctx.report_progress(current, total, message)` with a plain string `message`. Cursor renders this as raw text.
- Benefit: Cursor's MCP progress UI can display richer info (phase name, check count, duration) if the message is structured JSON.
- Scope: model definitions + `report_structured_progress()` helper. Migrating all existing call sites is incremental.

## Implementation Steps

### Step 1: Define progress model base and variants

Implemented in `src/cortex/core/progress_types.py`.

### Step 2: `report_structured_progress()` helper

Implemented in `src/cortex/core/progress_types.py`.

### Step 3: Migrate quality gate progress calls

Implemented in `src/cortex/tools/execution/pre_commit_tools_run_helpers.py`.

### Step 4: Migrate session tool progress calls

Implemented in `src/cortex/tools/session/dispatcher.py`.

### Step 5: Export from `cortex.core`

Implemented in `src/cortex/core/__init__.py`.

### Step 6: Tests

Implemented in `tests/unit/core/test_progress_types.py`.

## Success Criteria

1. All progress models serialize to valid JSON with `"tool"` discriminator field.
2. `report_structured_progress()` calls `ctx.report_progress()` with JSON message.
3. Quality gate progress and session dispatcher use typed progress.
4. Unit tests for progress model serialization and reporting behavior pass.
5. Pyright strict and quality checks pass.

## Partial Progress Log

- 2026-04-09: Implemented typed progress models/helper; migrated quality-gate and session progress callsites; added unit tests - files: src/cortex/core/progress_types.py, src/cortex/core/__init__.py, src/cortex/tools/execution/pre_commit_tools_run_helpers.py, src/cortex/tools/session/dispatcher.py, tests/unit/core/test_progress_types.py
- 2026-04-09: Completed final quality cleanup (dispatcher function-length refactor, coroutine typing in progress helper, duplicate log heading normalization) - files: src/cortex/tools/session/dispatcher.py, src/cortex/tools/execution/pre_commit_tools_run_helpers.py, tests/unit/core/test_progress_types.py, .cortex/memory-bank/log.md
