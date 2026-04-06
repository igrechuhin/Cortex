---
title: "Per-Tool Structured Progress Types"
component: core
work_type: refactoring
status: PENDING
priority: medium
created: 2026-04-06
depends_on: []
---

## Per-Tool Structured Progress Types

## Goal

Replace generic progress reporting (plain strings in `ctx.report_progress()`) with strongly-typed Pydantic progress models — one per tool category. Makes progress data machine-readable in Cursor's MCP UI and removes ambiguity of free-form status strings.

## Context

- Claude Code defines typed progress classes per tool: `BashProgress`, `AgentToolProgress`, `WebSearchProgress`, `MCPProgress`.
- Cortex calls `ctx.report_progress(current, total, message)` with a plain string `message`. Cursor renders this as raw text.
- Benefit: Cursor's MCP progress UI can display richer info (phase name, check count, duration) if the message is structured JSON.
- Scope: model definitions + `report_structured_progress()` helper. Migrating all existing call sites is incremental.

## Implementation Steps

### Step 1: Define progress model base and variants

**File**: `src/cortex/core/progress_types.py` (new, ≤ 150 lines)

```python
class BaseProgress(BaseModel):
    tool: str
    phase: str
    message: str   # human-readable fallback

class QualityGateProgress(BaseProgress):
    tool: Literal["quality_gate"] = "quality_gate"
    checks_completed: int
    checks_total: int
    current_check: str
    errors_found: int = 0

class CommitProgress(BaseProgress):
    tool: Literal["commit"] = "commit"
    phase_label: str
    step: int
    total_steps: int

class PipelineProgress(BaseProgress):
    tool: Literal["pipeline"] = "pipeline"
    pipeline: str
    operation: str

class SessionProgress(BaseProgress):
    tool: Literal["session"] = "session"
    operation: str

class DocsGateProgress(BaseProgress):
    tool: Literal["docs_gate"] = "docs_gate"
    files_checked: int
    issues_found: int

AnyProgress = QualityGateProgress | CommitProgress | PipelineProgress | SessionProgress | DocsGateProgress
```

**Verification**: grep `QualityGateProgress`; confirm pyright strict passes.

### Step 2: `report_structured_progress()` helper

**File**: `src/cortex/core/progress_types.py` (same file)

```python
def report_structured_progress(
    ctx: MCPContext | None,
    progress: AnyProgress,
    current: int,
    total: int,
) -> None:
    message = progress.model_dump_json()
    if ctx is not None:
        ctx.report_progress(current=current, total=total, message=message)
    else:
        logging.getLogger(__name__).debug("[progress] %s", progress.message)
```

- Lazy `MCPContext` import to avoid circular imports.

**Verification**: grep `report_structured_progress`.

### Step 3: Migrate quality gate progress calls

**File**: `src/cortex/tools/execution/pre_commit_pipeline.py`

- Replace `ctx.report_progress(...)` calls with `report_structured_progress(ctx, QualityGateProgress(...), ...)`.
- Keep `phase_callback` mechanism unchanged.

**Verification**: grep `report_progress` in `pre_commit_pipeline.py`; confirm no bare string calls remain.

### Step 4: Migrate session tool progress calls

**File**: `src/cortex/tools/session/dispatcher.py`

- Replace bare `ctx.report_progress(...)` in `start`, `register`, `compact`, `deregister` with `SessionProgress`.

**Verification**: grep `report_progress` in `tools/session/`.

### Step 5: Export from `cortex.core`

**File**: `src/cortex/core/__init__.py`

- Export all 5 progress models + `AnyProgress` + `report_structured_progress` (alphabetically sorted).

**Verification**: grep exports in `__init__.py`.

### Step 6: Tests

**File**: `tests/unit/core/test_progress_types.py` (new)

- `TestQualityGateProgress::test_serializes_to_json`
- `TestQualityGateProgress::test_errors_found_default_zero`
- `TestCommitProgress::test_phase_label_field`
- `TestPipelineProgress::test_pipeline_field`
- `TestSessionProgress::test_operation_field`
- `TestReportStructuredProgress::test_calls_ctx_report_progress`
- `TestReportStructuredProgress::test_none_ctx_does_not_raise`
- `TestReportStructuredProgress::test_message_is_valid_json`
- `TestPreCommitPipeline::test_quality_gate_progress_emitted`

Coverage target: 95%+.

## Dependencies

- No new external dependencies — Pydantic 2 already required.
- Internal: `pre_commit_pipeline.py`, `session/dispatcher.py`.

## Success Criteria

1. All progress models serialize to valid JSON with `"tool"` discriminator field.
2. `report_structured_progress()` calls `ctx.report_progress()` with JSON message.
3. `pre_commit_pipeline.py` and session dispatcher use typed progress.
4. All 9 tests pass; coverage ≥ 95%.
5. Pyright strict: no `Any`, all union branches typed.
6. No regression in existing pipeline tests.

## Testing Strategy

- Model tests: pure in-memory, no I/O.
- `report_structured_progress` tests: `unittest.mock.MagicMock` for ctx.
- Integration test: real tmp project for pipeline phase.
- AAA pattern throughout.
- Run via `run_quality_gate()` after implementation.
