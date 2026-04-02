# Quality and docs gate feedback loops

When `run_quality_gate()` or `run_docs_gate()` finishes, the MCP layer can persist a structured snapshot of failures to the **implement** pipeline handoff so the next `/cortex/do` run (or `session()` start) surfaces the same context without re-parsing full logs.

## Handoff location

- Pipeline: `implement`
- Phase: `gate_feedback`
- On-disk (under the active session id): `.cortex/.session/<session_id>/implement/gate_feedback-result.json`

Successful gates clear this phase by calling `pipeline_handoff` with `operation="clear"` on the `implement` pipeline, which removes the implement pipeline directory for that session.

## GateFeedback schema

`GateFeedback` is a Pydantic model in `src/cortex/tools/session/gate_feedback.py`. Fields:

| Field | Description |
| --- | --- |
| `gate` | `"quality"` or `"docs"` |
| `run_id` | Short id for correlating iterations |
| `timestamp` | ISO-8601 UTC time of the write |
| `errors` | List of `GateError` objects |
| `top_files` | Up to five deduplicated file paths (or placeholders such as `<type_check>`) |
| `summary` | One-line human-readable summary |

Each `GateError` includes:

| Field | Description |
| --- | --- |
| `file` | Path or check-scoped label |
| `line` | Optional line number |
| `check` | Check name (e.g. `type_check`) |
| `message` | Failure text |
| `fix_suggestion` | Optional hint |

### Example JSON

```json
{
  "gate": "quality",
  "run_id": "a1b2c3d4e5f6",
  "timestamp": "2026-04-02T12:00:00+00:00",
  "errors": [
    {
      "file": "<type_check>",
      "line": null,
      "check": "type_check",
      "message": "3 errors",
      "fix_suggestion": "errors=3"
    }
  ],
  "top_files": ["<type_check>"],
  "summary": "Quality gate failed with 1 issue group(s)."
}
```

## Orchestrator behavior

The `/cortex/do` prompt instructs the orchestrator to:

1. After `session()` health, read `pipeline_handoff(operation="read", pipeline="implement", phase="gate_feedback")`.
2. If feedback exists, print it first in the form: `> ⚠️ Gate failed on previous run: <summary>. Top files: <top_files>`.
3. Track `gate_iterations` against the same `run_id`; at five iterations, stop and report to the user instead of looping indefinitely.

The `session()` tool also exposes a `gate_feedback_summary` field when implement handoff contains `gate_feedback`, so agents see the signal without an extra read in some flows.

## Related code

- Models and persistence: `src/cortex/tools/session/gate_feedback.py`
- Quality gate hook: `src/cortex/tools/execution/pre_commit_zero_arg_tools.py` (`run_quality_gate`, `run_docs_gate`)
- Session brief: `src/cortex/tools/session/brief.py`
