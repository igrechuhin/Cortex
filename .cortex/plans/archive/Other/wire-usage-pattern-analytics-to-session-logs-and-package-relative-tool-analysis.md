---
title: "Wire Usage-Pattern Analytics to Session Logs and Package-Relative Tool Analysis"
component: "analysis"
work_type: fix
status: PENDING
priority: High
created: 2026-09-05
depends_on: []
execution: agent
status: PENDING
---

## Goal

Make `cortex://analysis` return real data for the `usage_patterns` and `tools` targets in any consuming project, by projecting usage patterns from the session logs that are already written and by resolving the tool-analysis directory from the installed package instead of a hardcoded `src/cortex/tools` path.

## Context

`cortex://analysis` with target `usage_patterns` is read-only in practice: `PatternAnalyzer` loads `.cortex/access-log.json`, and the only writer of that file is `PatternAnalyzer.record_access()`, which has no production caller anywhere in `src/` (verified by grep: hits are confined to `tests/unit/test_pattern_analyzer.py`, `tests/test_phase5_1.py`, and `tests/integration/test_phase5_6_8_workflows.py`). The file therefore never exists, `_load_access_log` returns an empty log, and all four analyzers (`get_access_frequency`, `get_co_access_patterns`, `get_task_patterns`, `get_unused_files`) report nothing. The `track_usage_patterns` config flag reaches `pattern_analyzer.py:104` and is never read again — a dead knob documented in `docs/api/configuration-reference.md`.

The data the analyzers want already exists. `.cortex/.session/context-session-<id>.json` records every `load_context` call with `timestamp`, `task_description`, and `selected_files` — exactly file access frequency, co-access (files selected together in one call), and task patterns. `AccessRecord` in `pattern_types.py` already carries `timestamp`, `file`, `task_description`, and `context_files`, so the projection needs no schema change, and `session_logger.py:275` already exposes a `context-session-*.json` listing helper.

Separately, `_run_tools_analysis` in `health_check_operations.py:129` sets `tools_dir = project_root / "src" / "cortex" / "tools"`. That is the layout of the Cortex repository itself, so the `tools` target reports zeros in every consuming project — the post-prompt hook (`post-prompt-hook.md` Step 6) sets exactly this target and always records "no usage data".

This plan replaces the dead write path with a projection over the existing session logs (one source of truth, retroactive over sessions already on disk) and makes tool analysis package-relative.

## Scope

**in_scope**

- New projection module that builds an `AccessLog` from `.cortex/.session/context-session-*.json`
- `PatternAnalyzer` sourcing its data from that projection instead of `access-log.json`
- Honouring `track_usage_patterns` (disabled → empty log) and `pattern_window_days` in the projection
- Removing the dead write path: `record_access`, `_save_access_log`, `_load_access_log`, `access_log_path`, `cleanup_old_data`, and `normalize_access_log` if it becomes unreferenced
- Package-relative `tools_dir` resolution in `_run_tools_analysis`
- Updating the tests that exercise the removed write path, plus `benchmarks/analysis_benchmarks.py`
- Documentation updates where behaviour is described (`docs/api/configuration-reference.md`, analyzer docstrings)

**out_of_scope**

- Changing `post-prompt-hook.md` or any other Synapse prompt (both targets return real data once this lands; no prompt edit is needed)
- Adding experience-store or WAL signals to the hook's Steps 4–6
- Any change to the experience store (`.cortex/experience/experience.db`) or memory WAL
- Making `session(health_check)` analyze registered MCP tools instead of files on disk
- Pruning or rotating `.cortex/.session/` logs

## Approach

Add `src/cortex/analysis/session_access_source.py` with a single public function that reads the session logs via the existing `list_session_logs` helper and returns a list of `AccessRecord`: one record per `(load_context call, selected file)`, where `context_files` is the remaining files of that same call and `task_description` is the call's own description. Records outside the configured window are dropped at read time, and log files are filtered by mtime before parsing so a project with hundreds of sessions does not pay for parsing all of them.

`PatternAnalyzer.__init__` then builds its `AccessLog` by replaying those records through the existing `_update_file_stats`, `_update_co_access_patterns`, and `_update_task_patterns` helpers. Reusing the helpers keeps aggregate semantics identical to the write path being deleted, so the four query methods and their tests keep their current meaning. When `track_usage_patterns` is false the projection is skipped and an empty log is returned, which finally gives the flag an effect.

Construction currently does synchronous file I/O, and this keeps that shape (the analyzer is built per request by `container_analysis.py` / `factory_analysis.py`); the mtime pre-filter plus the window bound is what keeps it cheap. Tool analysis is fixed by deriving the directory from the imported `cortex.tools` package rather than from `project_root`, which makes the tool budget meaningful wherever Cortex is installed.

## Implementation Steps

1. Add `src/cortex/analysis/session_access_source.py`: `build_access_records(project_root: Path, window_days: int) -> list[AccessRecord]`. Use `list_session_logs` from `core/session_logger.py`, skip files whose mtime is older than the window, parse each with the existing `SessionLog` model, and expand every `load_context_calls` entry into one `AccessRecord` per `selected_files` entry with the sibling files as `context_files`. Tolerate corrupt or schema-invalid files by skipping them, never raising.
2. Add a private `_build_access_log(records)` on `PatternAnalyzer` that starts from `create_default_access_log()` and replays each record through `_update_file_stats`, `_update_co_access_patterns`, and `_update_task_patterns`, appending to `accesses`.
3. Replace the `_load_access_log()` call in `PatternAnalyzer.__init__` with the projection, gated on `track_usage_patterns` and bounded by `pattern_window_days`. Remove `self.access_log_path`.
4. Delete `_load_access_log`, `_save_access_log`, `record_access`, and `cleanup_old_data` from `pattern_analyzer.py`, and drop the now-unused re-exports in its `__all__`. Delete `normalize_access_log` from `pattern_normalization.py` only if grep confirms no remaining reference.
5. Fix `_run_tools_analysis` in `src/cortex/tools/session/health_check_operations.py`: resolve `tools_dir` from the imported `cortex.tools` package path instead of `project_root / "src" / "cortex" / "tools"`. Add an `# AI:` comment stating why the path is package-relative.
6. Update `src/cortex/benchmarks/analysis_benchmarks.py` to stop calling `record_access`; have it write session-log fixtures instead, or delete the benchmark case if it no longer measures anything real.
7. Update the affected tests: rewrite `tests/unit/test_pattern_analyzer.py` and the `record_access` call sites in `tests/test_phase5_1.py` and `tests/integration/test_phase5_6_8_workflows.py` to seed `.cortex/.session/context-session-*.json` fixtures instead of calling the deleted writer.
8. Update `docs/api/configuration-reference.md` (and the `.cortex/wiki/sources/` mirror) so the `track_usage_patterns` row describes the session-log source, and refresh the `analyze_impl` docstring note that says usage patterns "requires file access history".
9. Run `run_quality_gate()` and `run_docs_gate()`; fix what they report.

## Verification Checklist

- Step 1–3: grep `access_log_path` and `access-log.json` across `src/` — expect zero hits outside deleted code; re-read `pattern_analyzer.py` after edits.
- Step 4: grep `record_access`, `cleanup_old_data`, `normalize_access_log`, `create_default_access_log` across `src/` and `tests/` — every surviving hit must be intentional; re-read `pattern_normalization.py` and `pattern_analyzer.py`.
- Step 5: grep `src.*cortex.*tools` under `src/cortex/tools/session/` — expect no hardcoded repo-layout path; re-read `health_check_operations.py`.
- Steps 6–7: grep `record_access` across `tests/` and `src/cortex/benchmarks/` — expect zero hits.
- Step 8: grep `track_usage_patterns` across `docs/` and `.cortex/wiki/sources/` — every hit must describe the session-log source.
- Step 9: read the gate output in full; no suppressions added.
- End-to-end: read `cortex://analysis` with `analysis_target` set to `usage_patterns` in this repository and confirm non-empty `access_frequency` and `co_access_patterns`; then with `tools` and confirm a non-zero tool count.

## Dependencies

None. The session-log format, `AccessRecord` schema, and `list_session_logs` helper all exist today.

## Success Criteria

- `cortex://analysis` with target `usage_patterns` returns non-empty `access_frequency`, `co_access_patterns`, and `task_patterns` in this repository without any new file being written first.
- `cortex://analysis` with target `tools` returns a non-zero registered tool count when Cortex is installed as a package outside its own repository.
- `track_usage_patterns: false` produces an empty usage-pattern payload; `true` produces data.
- No code path reads or writes `.cortex/access-log.json`; the dead writer and its aggregates are gone.
- `run_quality_gate()` and `run_docs_gate()` pass with no new suppressions.

## Testing Strategy

Target 95% coverage on new and changed code, AAA pattern throughout.

- Unit, `session_access_source.py`: a session log with two `load_context` calls projects to the expected records with correct `context_files` siblings; a log outside the window is excluded; a corrupt JSON file and a schema-invalid file are both skipped without raising; an empty session directory yields an empty list.
- Unit, `PatternAnalyzer`: projection replay reproduces the same `file_stats`, `co_access_patterns`, and `task_patterns` aggregates the deleted `record_access` path produced for equivalent input; `track_usage_patterns=False` yields an empty log; `get_unused_files` reports files never selected.
- Unit, `_run_tools_analysis`: with a `project_root` that has no `src/cortex/tools` directory, the analysis still finds the installed tool modules.
- Negative: window of zero days yields no records; a session log whose `selected_files` is empty contributes no records and no co-access edge.
- Integration: build the analyzer through `container_analysis.py` against a temp project seeded with session-log fixtures and assert the `usage_patterns` JSON payload is populated end to end.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Parsing many session logs slows analyzer construction | Filter log files by mtime against the window before parsing; the window default is 30 days |
| Deleting `record_access` breaks an out-of-tree consumer | It is an internal analyzer method with no production caller in this repository; note the removal in the completion entry |
| Projection aggregates drift from the deleted write path's semantics | Replay through the existing `_update_*` helpers rather than reimplementing aggregation, and assert equivalence in a unit test |
| Package-relative `tools_dir` breaks when Cortex runs from a source checkout | Resolving from the imported package works for both editable installs and site-packages; covered by the `_run_tools_analysis` unit test |
| `load_context` is rarely called by pipelines, so the projection stays thin | Out of scope here, but recorded: the same projection gains data automatically as more pipelines call `load_context` |
