# Agent-oriented structured logging

Cortex MCP tools can emit **structured log lines** (JSON on stderr) and attach a **markdown table** (`agent_log`) to selected tool responses so agents correlate failures with session context.

## Log line format

Each line is one JSON object matching the `LogEvent` Pydantic model (`src/cortex/tools/logging/models.py`):

| Field | Meaning |
| --- | --- |
| `event` | Event id (e.g. `quality_gate.passed`, `pipeline_handoff.write`) |
| `level` | `debug`, `info`, `warn`, or `error` |
| `component` | Tool name (e.g. `run_quality_gate`, `autofix`) |
| `trace_id` | Session-wide id (persisted under `trace_id` in `.cortex/.session/current-task.json` when possible) |
| `requirement_id` | Optional plan step (`requirement_id` or `selected_step` in session config) |
| `commit_hash` | Abbreviated `git` HEAD when available |
| `message` | Short human-readable text |
| `details` | Optional flat map (`str` / `int` / `bool` values) |

### Example stderr line

```json
{"event":"quality_gate.passed","level":"info","component":"run_quality_gate","trace_id":"a1b2c3d4e5f6","requirement_id":null,"commit_hash":"abc1234","message":"Quality gate passed","details":null}
```

## Session `trace_id`

- `session(operation="start")` ensures a `trace_id` exists and includes it on the returned `SessionBrief` as `trace_id`.
- Orchestrators may set `requirement_id` / `selected_step` in `.cortex/.session/current-task.json` for richer logs.

## Tool response: `agent_log`

When events were emitted, these tools add an **`agent_log`** string (markdown table) to the JSON result:

- `run_quality_gate`
- `autofix`

`pipeline_handoff` only emits to stderr (no `agent_log` field).

## Related modules

- `src/cortex/tools/logging/` — models, `emit`, `format_for_agent`, `session_context`, `instrumentation`
