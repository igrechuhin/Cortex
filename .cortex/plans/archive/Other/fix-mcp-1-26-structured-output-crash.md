---
title: "BLOCKER: Fix mcp>=1.26.0 Structured-Output Crash on Startup"
component: "server"
work_type: "fix"
status: PENDING
priority: blocker
created: 2026-04-13
depends_on: []
---

## BLOCKER: Fix mcp>=1.26.0 Structured-Output Crash on Startup

## Goal

The Cortex MCP server crashes on import with:

```text
pydantic.errors.PydanticUserError: `run_quality_gateOutput` is not fully defined;
you should define `ModelDict`, then call `run_quality_gateOutput.model_rebuild()`.
```

This prevents the server from starting at all. Fix immediately.

## Root Cause (Confirmed)

`mcp>=1.26.0` added a `structured_output` parameter to `@mcp.tool()`. When
`structured_output=None` (the default), FastMCP **auto-enables structured
output** for any tool whose return type annotation looks like a Pydantic
model or a named type alias.

`run_quality_gate` (and likely other tools) is annotated `-> ModelDict` where:

```python
# src/cortex/core/models/_base.py:12
type ModelDict = dict[str, JsonValue]
```

This is a **Python 3.12 `type` statement** (PEP 695 type alias). FastMCP
v1.26 introspects the return annotation, sees `ModelDict`, attempts to build a
Pydantic model named `run_quality_gateOutput` from it. Pydantic then tries to
generate a JSON schema which requires `ModelDict` to be fully resolved — but
`ModelDict` recursively references `JsonValue` which uses forward references
(`list["JsonValue"]`, `dict[str, "JsonValue"]`), causing the `model_rebuild()`
failure.

The crash chain in the traceback:

```text
pre_commit_zero_arg_tools.py:328  @typed_mcp_tool(...)
mcp_stability.py:84               decorator(func)   ← calls mcp.tool()
mcp/server/fastmcp/server.py:494  self.add_tool(...)
mcp/server/fastmcp/tools/base.py:72  Tool.from_function(...)
mcp/func_metadata.py:413          model.model_json_schema(...)
pydantic/_internal/_mock_val_ser.py:67  raise PydanticUserError
```

## Affected Files

All tools decorated with `@typed_mcp_tool(...)` that return `ModelDict` or
any type that Pydantic cannot immediately resolve to a JSON schema.

Tools confirmed or highly likely affected (all use `@typed_mcp_tool` and return
`ModelDict`):

- `run_quality_gate` — line 338 of `pre_commit_zero_arg_tools.py`
- `run_docs_gate` — line ~362 of `pre_commit_zero_arg_tools.py`
- `autofix` — line ~399 of `pre_commit_zero_arg_tools.py`
- Any other `@typed_mcp_tool` tool returning `ModelDict`

## Fix Options

### Option A — Pin `mcp<1.26.0` (immediate workaround, not a fix)

Change `pyproject.toml`:

```toml
"mcp>=1.6.0,<1.26.0"
```

**Pro**: zero code change, instant.
**Con**: pins us to old SDK forever; blocks FastMCP v3 migration; only
defers the problem.

### Option B — Pass `structured_output=False` to `typed_mcp_tool` (recommended)

`typed_mcp_tool` in `mcp_stability.py` calls `_mcp.tool(annotations=annotations)`.
Add a `structured_output=False` kwarg:

```python
def typed_mcp_tool(
    *,
    annotations: ToolAnnotations | None,
    structured_output: bool = False,       # ← new, default False
) -> Callable[[TToolFunc], TToolFunc]:
    from cortex.server import mcp as _mcp
    decorator = _mcp.tool(annotations=annotations, structured_output=False)
    ...
```

**Pro**: one-line fix; all tools using `typed_mcp_tool` are fixed at once;
no behaviour change for callers (tools already return plain dicts, not Pydantic
models); aligns with existing tool contract.
**Con**: opts out of structured output globally for `typed_mcp_tool` tools.
Any future tool that intentionally wants structured output must opt in
explicitly.

### Option C — Fix the return type annotation

Change affected tool signatures from `-> ModelDict` to `-> dict[str, object]`
or wrap in `TYPE_CHECKING` guard. This makes FastMCP see a plain dict type and
not attempt schema generation.

**Pro**: type-accurate.
**Con**: touches many files; `ModelDict` is used project-wide; changes may
have broader type-checking implications.

**Recommendation**: implement Option B immediately (one-file fix, no
behaviour change), then consider Option C as a follow-up cleanup.

## Implementation Steps

### Step 1 — Confirm full list of affected tools

```bash
grep -rn "@typed_mcp_tool" src/cortex/ --include="*.py" -l
```

For each file, list every `@typed_mcp_tool`-decorated function and its return
type. Identify any that return `ModelDict` or another type alias that Pydantic
might attempt to schema-ify.

### Verification checklist 1

- [ ] Complete list of `@typed_mcp_tool` call sites obtained
- [ ] All affected return types identified

### Step 2 — Apply Option B: add `structured_output=False` to `typed_mcp_tool`

Edit `src/cortex/core/mcp_stability.py` function `typed_mcp_tool` (line 70):

```python
def typed_mcp_tool(
    *,
    annotations: ToolAnnotations | None,
) -> Callable[[TToolFunc], TToolFunc]:
```

Change the `decorator` line inside to:

```python
decorator = _mcp.tool(annotations=annotations, structured_output=False)
```

No signature change to `typed_mcp_tool` itself is needed — `structured_output`
is always `False` for all tools registered through this wrapper.

### Verification checklist 2

- [ ] `mcp_stability.py` passes `structured_output=False` to `_mcp.tool()`
- [ ] No other `@mcp.tool()` call sites in the codebase omit `structured_output`
  when returning `ModelDict`

### Step 3 — Check direct `@mcp.tool()` / `@mcp.resource()` call sites

Grep for direct decorator usage that does NOT go through `typed_mcp_tool`:

```bash
grep -rn "@mcp\.tool\|@mcp\.resource" src/cortex/ --include="*.py" | grep -v "typed_mcp_tool"
```

For any `@mcp.tool()` that returns `ModelDict` or a complex type alias, add
`structured_output=False` explicitly.

### Verification checklist 3

- [ ] All direct `@mcp.tool()` sites with `ModelDict` return type have
  `structured_output=False`

### Step 4 — Verify server starts

```bash
cd /Users/i.grechukhin/Repo/Cortex
uv run python -c "import cortex.server; print('OK')"
uv run cortex --help
```

### Verification checklist 4

- [ ] `import cortex.server` exits 0 with no traceback
- [ ] `uv run cortex` starts the server without crashing
- [ ] `list_tools` response includes `run_quality_gate`, `run_docs_gate`,
  `autofix`

### Step 5 — Quality gate

`run_quality_gate()`. All tests pass. No regressions.

### Verification checklist 5

- [ ] Existing tool registration tests pass
- [ ] Coverage ≥90%
- [ ] No new pyright errors

## Dependencies

None. This is an isolated one-line fix.

## Success Criteria

1. `uv run cortex` starts without error.
2. Cursor MCP client can connect successfully.
3. All tools respond normally.
4. Quality gate green.

## Testing Strategy

- **Smoke test** (Step 4): `import cortex.server` must not raise.
- **Regression**: existing `test_tool_inventory_parity.py` and tool
  registration tests must pass.
- **New regression test**: add a test in `tests/unit/test_server_startup.py`
  (or equivalent) that imports `cortex.server` and asserts the server
  instantiates without `PydanticUserError`.

Coverage target: maintain ≥90% baseline.
