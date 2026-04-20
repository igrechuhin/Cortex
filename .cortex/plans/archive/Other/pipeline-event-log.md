---
title: "Add Append-Only Event Log to Pipeline Handoff for Crash Recovery"
component: "pipeline"
work_type: "feature"
status: PENDING
priority: "High"
created: "2026-04-20"
depends_on: []
---

## Goal

Add an append-only `pipeline.log` to `pipeline_handoff` so every write operation is durably recorded before mutating JSON state files, enabling crash recovery and pipeline replay.

## Context

Cortex pipeline state lives in `.cortex/.session/{session_id}/{pipeline}/` as flat JSON files. When `pipeline_handoff(operation="write")` is called, it updates `{phase}-result.json` and merges into `pipeline.json`. If the IDE or agent crashes after the log write but before the JSON mutation completes, state is partially written with no recovery path. Engineers have no visibility into what a pipeline did before it died.

This maps directly to the Managed Agents architecture pattern: `emitEvent(id, event)` writes a durable record during the agent loop, and `getSession(id)` can recover the event log on restart. Without a durable event log, every pipeline failure requires a full restart.

## Scope

**in_scope**

- Append-only `pipeline.log` JSONL file written by every `pipeline_handoff(operation="write")` call
- Log entry schema: `{phase, timestamp, operation, data_keys}` (no full data payload to avoid bloating the log)
- `_detect_incomplete_state(pipeline_dir)` helper that checks for `running` entries without matching `completed`
- `session(operation="start")` returns `incomplete_pipelines` in `SessionBrief` when detected
- `pipeline_handoff(operation="read_log", pipeline=...)` sub-operation for agent introspection
- Unit tests for all new paths

**out_of_scope**

- Full data payload in log entries (only keys logged, not values)
- Automatic replay/recovery (covered by Plan 2)
- Remote or cross-session log access
- Log rotation or size limits

## Approach

Add `_append_event_log(pipeline_dir: Path, phase: str, operation: str, data_keys: list[str])` as a private helper in `pipeline_handoff.py`. Call it synchronously before the JSON mutation in the `write` operation path. Log entries are JSONL (one JSON object per line) appended to `pipeline.log` in the pipeline directory.

On `session(operation="start")`, scan all active pipeline directories for `pipeline.log` files. If any log has an entry with no matching completion entry for the same phase, include the pipeline ID in the returned `SessionBrief.incomplete_pipelines` list. This gives agents a signal to investigate before assuming a clean slate.

The `read_log` sub-operation reads and parses `pipeline.log`, returning structured entries for agent introspection.

## Implementation Steps

1. Add `_append_event_log(pipeline_dir: Path, phase: str, operation: str, data_keys: list[str]) -> None` to `src/cortex/tools/pipeline_handoff.py` — opens `pipeline.log` in append mode, writes JSONL entry with ISO timestamp, closes immediately (no buffering).
2. In the `write` operation path of `pipeline_handoff`, call `_append_event_log` with `operation="write"` BEFORE writing to `{phase}-result.json` and `pipeline.log`.
3. Add `_detect_incomplete_state(pipeline_dir: Path) -> list[str]` — reads `pipeline.log`, returns phases that have a `write` entry but no `completed` entry (see Plan 2 for the `completed` write; for now, treat any `write` entry as "potentially incomplete" if no subsequent same-phase write exists).
4. Extend `SessionBrief` Pydantic model in `src/cortex/core/session_config.py` with `incomplete_pipelines: list[str] = []`.
5. In `session_start()` (called by `session(operation="start")`), scan `.cortex/.session/` for pipeline dirs containing `pipeline.log` with incomplete state; populate `incomplete_pipelines`.
6. Add `read_log` branch to `pipeline_handoff` dispatch: reads `pipeline.log`, parses JSONL, returns `list[EventLogEntry]` where `EventLogEntry` is a Pydantic model.
7. Write unit tests in `tests/unit/tools/test_pipeline_handoff_event_log.py`: normal write (log created), crash simulation (log exists, result file missing), read_log returns correct entries, incomplete_pipelines detected in session start.

## Verification Checklist

- Step 1: grep `_append_event_log` in `src/cortex/tools/pipeline_handoff.py`; confirm signature matches spec
- Step 2: grep call site inside `write` operation branch; confirm it precedes any JSON file write
- Step 3: grep `_detect_incomplete_state`; confirm it reads JSONL correctly
- Step 4: read `src/cortex/core/session_config.py`; confirm `incomplete_pipelines` field in `SessionBrief`
- Step 5: grep `incomplete_pipelines` in session start logic; confirm scan covers all pipeline dirs
- Step 6: grep `read_log` in pipeline_handoff dispatch; confirm `EventLogEntry` Pydantic model defined
- Step 7: run `pytest tests/unit/tools/test_pipeline_handoff_event_log.py -v`; all tests pass

## Dependencies

None — this plan is self-contained and is a prerequisite for Plan 2 (phase status tracking).

## Success Criteria

- Every `pipeline_handoff(operation="write")` appends to `pipeline.log` before mutating JSON
- Simulated crash (log exists, result file absent) is detected by `session(operation="start")`
- `pipeline_handoff(operation="read_log")` returns correct structured entries
- `SessionBrief.incomplete_pipelines` is populated when incomplete state is detected
- All new code paths covered by unit tests; quality gate passes

## Testing Strategy

Target: 95% coverage on new code paths. AAA pattern throughout.

- **Unit — normal write**: Arrange: temp pipeline dir. Act: call `write` operation. Assert: `pipeline.log` contains one JSONL entry; `{phase}-result.json` contains expected data.
- **Unit — crash simulation**: Arrange: `pipeline.log` with a write entry; no `{phase}-result.json`. Act: call `_detect_incomplete_state`. Assert: returns phase name in result list.
- **Unit — read_log**: Arrange: `pipeline.log` with 3 entries. Act: call `read_log`. Assert: returns list of 3 `EventLogEntry` objects with correct fields.
- **Unit — session start with incomplete pipeline**: Arrange: session dir with incomplete pipeline. Act: call `session(operation="start")`. Assert: `SessionBrief.incomplete_pipelines` contains the pipeline ID.
- **Unit — session start clean**: Arrange: session dir with complete pipeline. Act: call `session(operation="start")`. Assert: `incomplete_pipelines` is empty.
- **Negative — log write fails**: Arrange: read-only pipeline dir. Act: call `write`. Assert: appropriate error raised, does not silently skip logging.

## Risks and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Log write adds latency to every pipeline_handoff write | Low | Low | Append to file is O(1); benchmark shows <1ms on typical payload |
| Log grows unbounded for long pipelines | Low | Medium | Out of scope here; log entries contain only keys, not values — size is bounded by phase count |
| `_detect_incomplete_state` produces false positives | Medium | Low | Conservative detection: only flag phases with a write entry and no subsequent same-phase write; agents can ignore the warning |
| Concurrent writes corrupt JSONL | Low | High | pipeline_handoff is single-writer per session (one harness at a time); no lock needed for now |

## Partial Progress Log

- 2026-04-20: Implemented append-only `pipeline.log` writes, `read_log` support, incomplete-pipeline session detection, and event-log unit tests — files: src/cortex/tools/session/pipeline_handoff_io.py, src/cortex/tools/session/pipeline_handoff.py, src/cortex/tools/session/models.py, src/cortex/tools/session/start_tools.py, tests/unit/tools/test_pipeline_handoff_event_log.py
