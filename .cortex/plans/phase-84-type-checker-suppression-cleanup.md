# Phase 84: Remaining Type-Checker Suppression Cleanup

**Status**: PENDING
**Priority**: Medium
**Complexity**: Medium
**Category**: Fix / Quality

## Goal

Eliminate or document the 27 remaining `# type: ignore` / `# pyright: ignore` suppressions in `src/`.

## Context

- Phase 76 removed TypedDict, TYPE_CHECKING imports, and most suppressions.
- 27 suppressions remain across 7 files, falling into two categories:
  1. `reportUnknownParameterType` on `*args/**kwargs: JsonValue` in MCP stability wrappers (10 total).
  2. `reportUntypedFunctionDecorator` / `reportCallIssue` / `reportUnknownVariableType` on `@mcp.tool()` decorators and Pydantic `Field()` defaults (17 total).
- Chat sessions noted these as "recognized pyright limitations" needing dedicated follow-up.

## Remaining Suppressions

### Category 1: MCP stability wrappers (10)

- `core/mcp_stability.py`: lines 244, 249, 276, 277, 335, 336, 359, 361
- `core/mcp_stability_usage.py`: lines 109, 110

### Category 2: Decorators and Pydantic Field (17)

- `tools/session/models.py`: lines 125, 208 (`reportUnknownVariableType` on Field)
- `tools/session/connection_health.py`: lines 19, 23 (`@mcp.tool()`)
- `tools/usage/production_monitoring_models.py`: lines 65, 68, 77 (`reportUnknownVariableType`)
- `tools/structure/main.py`: lines 154, 157, 186, 189 (`@mcp.tool()`)
- `tools/structure/tool_search.py`: lines 26, 30 (`@mcp.tool()`)
- `tools/execution/pre_commit_tools.py`: lines 256, 262 (`@mcp.tool()`)
- `tools/execution/composite_tools.py`: lines 186, 189 (`@mcp.tool()`)

## Implementation Steps

### Step 1: Address MCP stability `*args/**kwargs` (Category 1)

- Investigate if `*args: object, **kwargs: object` or Protocol-based typing can replace `JsonValue`.
- If the MCP wrapper contract requires `JsonValue`, determine if a cast or `@overload` can satisfy pyright.
- If genuinely unsolvable, convert to a single documented suppression with a comment explaining why.

### Step 2: Address `@mcp.tool()` decorator suppressions (Category 2a)

- Check if the MCP SDK has type stubs or a newer version with proper typing.
- If not, create a thin typed wrapper: `def typed_mcp_tool(...) -> Callable[..., Any]` that satisfies pyright.
- Alternatively, add a single `# pyright: ignore` with a comment linking to the MCP SDK typing gap.

### Step 3: Address Pydantic `Field()` suppressions (Category 2b)

- Check if `Field(default_factory=list)` instead of `Field(default=[])` resolves `reportUnknownVariableType`.
- If it's a Pydantic v2 + pyright interaction, document it as a known limitation.

### Step 4: Consolidate remaining suppressions

- For any that cannot be resolved, ensure each has a comment explaining **why** it's needed.
- Create a tracking issue or section in AGENTS.md for upstream fixes.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `# type: ignore` | `src/` (not tests/) | Documented count (target: ≤5) |
| `# pyright: ignore` | `src/` (not tests/) | Documented count (target: ≤5) |

## Dependencies

- None.

## Success Criteria

- Suppressions reduced from 27 to ≤10 (ideally ≤5).
- Every remaining suppression has a comment explaining why it's needed.
- Zero type errors in pyright.
- All tests pass.

## Testing Strategy

- **Coverage Target**: N/A (type annotations only).
- **Unit Tests**: Existing tests pass unchanged.
- **Type Checking**: `pyright src/` passes with 0 errors.

## Risks & Mitigation

- **Risk**: MCP SDK doesn't support proper typing. **Mitigation**: Create typed wrappers or document as upstream gap.
- **Risk**: Pydantic Field typing is a pyright limitation. **Mitigation**: Use `default_factory` pattern.

## Timeline

- Estimated: 3–4 hours.
