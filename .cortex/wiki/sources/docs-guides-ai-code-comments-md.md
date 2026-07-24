# AI code comments and BELIEF annotations

This guide complements the synapse rule file `.cortex/synapse/rules/general/ai-code-comments.mdc` and the `ai_code_comments_rule` field on the `cortex://rules` resource.

## Why use them

Agent sessions lose context between turns. Short `# AI:` and `# BELIEF:` lines keep **intent** and **assumptions** in the same place as the code, so the next agent or reviewer does not have to reverse-engineer rationale from behavior alone.

## Good patterns

### Documenting non-obvious session behavior

`read_session_config` explains *why* the JSON shape exists — the MCP bridge drops tool arguments, so tools must read the session file:

```59:70:src/cortex/core/session_config.py
def read_session_config() -> SessionConfig:
    """Read current task config from session file, or return empty dict.

    Returns a dict with optional keys: task_description, pipeline, phase,
    operation, token_budget, file_name, check_type, trace_id, requirement_id,
    selected_step. All values are strings or ints. ``operation`` is used by
    ``pipeline_handoff`` to recover the intended operation (e.g. "init") when
    an MCP client strips all tool arguments. ``trace_id`` is persisted for structured
    agent logging (see ``cortex.tools.logging``). Optional keys ``reflection`` and
    ``force_reflection`` (booleans) enable the quality gate reflection pass when
    the MCP bridge strips ``run_quality_gate`` arguments.
    """
```

A matching `# AI:` line would look like:

```python
# AI: Session file is the single source of truth when an MCP client sends empty args.
def read_session_config() -> dict[str, object]:
    ...
```

### Explaining pipeline layout

The `pipeline_handoff` module docstring states where phase JSON lives so agents do not hunt the tree:

```1:14:src/cortex/tools/session/pipeline_handoff.py
"""Pipeline handoff tool — structured inter-phase communication via session files.

Each pipeline run (commit, implement, …) creates a session-scoped subfolder
under .cortex/.session/{session_id}/ and exchanges structured JSON between
pipeline phases through that folder.

## Simplified API (4 operations)

    pipeline_handoff(operation="init",  pipeline="commit")
    pipeline_handoff(operation="write", pipeline="commit", phase="checks",
                     data='{"status":"passed", "coverage": 0.94}')
    pipeline_handoff(operation="read",  pipeline="commit", phase="checks")
    pipeline_handoff(operation="read",  pipeline="commit")  # full state
    pipeline_handoff(operation="clear", pipeline="commit")
```

## Patterns to avoid

- Restating the next line in different words (`# AI: increment x` above `x += 1`).
- BELIEF lines that no longer match control flow after a refactor — update or remove them when behavior changes.
- Dense annotation stacks — prefer one clear note per region over many shallow ones.

## Quality gate

When reflection is enabled, the gate may emit a **warning** (not a failure) if a `# BELIEF:` line stays unchanged as context while other lines in the same hunk change. Autofix may append **suggestions** (not auto-edits) when a new public function appears in the diff without a nearby `# AI:` comment.
