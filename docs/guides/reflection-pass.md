# Reflection pass (quality gate)

The reflection pass is an **optional** step that runs after the primary quality gate checks succeed. It performs a **heuristic** review of `git diff HEAD` (logic, security, coverage signals) and attaches a structured result to the gate response. It does not replace tests, typechecking, or lint.

## Enabling

Configure the commit pipeline `checks` phase (same file `run_quality_gate` reads):

```json
{
  "coverage_threshold": 0.9,
  "test_timeout": 300,
  "force_fresh": true,
  "reflection": true
}
```

`force_reflection: true` is treated the same as `reflection: true` for enabling the pass. You can also set `reflection` or `force_reflection` in `.cortex/.session/current-task.json` when the MCP bridge strips tool arguments.

Requires `CORTEX_SESSION_ID` and the session layout expected by `read_pipeline_phase_config`, or session-file keys fall back to defaults (`reflection: false`).

## Language-aware checklist and heuristics

Paths in the diff (`+++ b/...` / `diff --git`) are mapped to languages (for example `.py` → Python, `.swift` → Swift). The checklist text passed into analysis includes the **shared** category list plus **only the sections for languages present in the diff**. The static `cortex://rules` resource still exposes the **full** multi-language catalog via `reflection_checklist`.

Python-only heuristics (incomplete `try`/`except`, `src/` defs without tests) run only when a `.py` path is present. Language-agnostic signals (TODO markers, secret-like literals) run on any diff.

When reflection runs, the gate result also includes `reflection_languages`: an ordered list of detected language ids (for example `["python"]`, `["swift", "go"]`).

## Response shape

When reflection runs, the gate result includes `reflection_languages` and `reflection_result`:

```json
{
  "preflight_passed": true,
  "reflection_languages": ["python"],
  "reflection_result": {
    "items": [
      {
        "category": "logic",
        "severity": "warning",
        "location": "diff",
        "description": "...",
        "suggestion": "..."
      }
    ],
    "score": 95,
    "summary": "Heuristic reflection passed (score 95). 1 warning(s), 0 error-level finding(s).",
    "approved": true
  }
}
```

If any item has `"severity": "error"`, `approved` is false and `preflight_passed` is set to false so the gate fails like any other check failure.

## Interpretation

- **score**: 0–100; reduced by error- and warning-level findings.
- **categories**: `logic`, `security`, `edge_case`, `test_coverage`, `docs`.
- **Rules context**: `cortex://rules` includes a `reflection_checklist` field describing categories and typical triggers.

## Limitations

Heuristics can miss real bugs and may warn on acceptable code. Use reflection as a structured prompt for review, not as a definitive verdict.
