# Plan: Sequential Thinking in Cortex MCP

**Status**: PENDING  
**Created**: 2026-01-31  
**Reference**: [MCP servers – sequentialthinking](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking)

---

## Goal

Implement sequential thinking functionality in Cortex MCP so that clients can use a **sequentialthinking** tool for stepwise, reflective problem-solving. The tool should mirror the behavior and API of the official MCP sequential thinking server (thought history, revisions, branches, structured output) while fitting Cortex’s Python MCP stack, timeout rules, and tool conventions.

---

## Context

- **User need**: Use sequential thinking from Cortex (e.g. in Cursor) for complex planning, design, and analysis without running a separate sequential thinking MCP server, by relying on the built-in `sequentialthinking` tool from Cortex MCP.
- **Reference implementation**: TypeScript server in `modelcontextprotocol/servers` (`src/sequentialthinking/index.ts`, `lib.ts`): single tool `sequentialthinking`, stateful thought history and branches, rich tool description, JSON output with `thoughtNumber`, `totalThoughts`, `nextThoughtNeeded`, `branches`, `thoughtHistoryLength`.
- **Cortex constraints**: Python 3.13+, async tools, `@mcp.tool()` + `@mcp_tool_wrapper(timeout=...)`, dependency injection, no global state in production (state must be scoped e.g. per server/session), 100% type hints, concrete types, files &lt;400 lines, functions &lt;30 lines.

---

## Approach

1. **New tool module**  
   Add a dedicated module (e.g. `src/cortex/tools/sequential_thinking.py`) that registers a single MCP tool and delegates to a pure, testable core.

2. **API alignment**  
   Match the reference input/output schema and semantics so that existing prompts and clients that assume the MCP sequential thinking contract keep working when pointed at Cortex.

3. **State handling**  
   Keep thought history and branches in memory for the lifetime of the MCP server process (single-client stdio usage). Optionally introduce a `session_id` in a later phase for multi-session or multi-client scenarios.

4. **Thin handler + pure logic**  
   Handler: validate input, call core, return MCP content. Core: update thought history and branches, compute response (no I/O). This keeps timeouts and async behavior correct and simplifies tests.

5. **Documentation and discoverability**  
   Tool docstring must include USE WHEN, EXAMPLES, and RETURNS per Cortex tool standards; optionally document the tool in `docs/api/tools.md` and README.

---

## Reference API Summary

**Input (from reference):**

- `thought` (string, required): Current thinking step.
- `nextThoughtNeeded` (bool, required): Whether another thought step is needed.
- `thoughtNumber` (int ≥ 1, required): Current thought index.
- `totalThoughts` (int ≥ 1, required): Estimated total thoughts (can be adjusted).
- `isRevision` (bool, optional): This thought revises previous thinking.
- `revisesThought` (int ≥ 1, optional): Which thought is being revised.
- `branchFromThought` (int ≥ 1, optional): Branching point thought number.
- `branchId` (string, optional): Branch identifier.
- `needsMoreThoughts` (bool, optional): More thoughts needed than initially estimated.

**Output (from reference):**

- `thoughtNumber` (int)
- `totalThoughts` (int)
- `nextThoughtNeeded` (bool)
- `branches` (list of branch IDs)
- `thoughtHistoryLength` (int)

**Behavior:**

- Append each call to a thought history; if `branchFromThought` and `branchId` are set, record the thought in a branch bucket.
- If `thoughtNumber > totalThoughts`, treat current estimate as updated (e.g. set `totalThoughts = thoughtNumber`).
- Return the structured output as JSON in MCP content (and optionally as structured content if the SDK supports it).

---

## Implementation Steps

### 1. Types and models

- Define TypedDicts (or dataclasses) for:
  - **Input**: `thought`, `next_thought_needed`, `thought_number`, `total_thoughts`, plus optional `is_revision`, `revises_thought`, `branch_from_thought`, `branch_id`, `needs_more_thoughts`. Use snake_case in Python; map to/from the MCP/camelCase names at the tool boundary if required.
  - **Output**: `thought_number`, `total_thoughts`, `next_thought_needed`, `branches`, `thought_history_length`.
- Place in a small models/typing module or at top of `sequential_thinking.py`; keep one public type per file if splitting.

### 2. Core logic (pure, synchronous)

- Implement a **SequentialThinkingCore** (or module-level state + pure functions) that:
  - Holds `thought_history: list[ThoughtData]` and `branches: dict[str, list[ThoughtData]]`.
  - Exposes a function like `process_thought(input: ThoughtInput) -> ThoughtOutput` that:
    - Adjusts `total_thoughts` if `thought_number > total_thoughts`.
    - Appends the thought to `thought_history`.
    - If `branch_from_thought` and `branch_id` are present, appends to `branches[branch_id]`.
    - Returns the output dict/list for the response.
  - No I/O, no async; all state passed in or held in an object that is injected (or a single server-scoped instance).

### 3. State lifecycle

- **Option A (recommended for v1)**: One shared in-memory core instance per Cortex server process (e.g. created at module load or first use). Matches reference behavior for single-client stdio.
- **Option B**: Optional `session_id` parameter; maintain a dict of cores keyed by `session_id` and clear or cap size per session. Defer to a follow-up unless required for multi-client.

### 4. MCP tool handler

- In `sequential_thinking.py` (or the chosen module):
  - Register one tool, e.g. `sequentialthinking` (name to match reference for client compatibility).
  - Use `@mcp.tool()` and `@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)` (or COMPLEX if policy prefers; each call is cheap).
  - Handler: parse/validate arguments (and map camelCase → snake_case if needed), call core `process_thought`, build MCP response with `content: [{"type": "text", "text": "<json of output>"}]`.
  - On core or validation errors, return an error response consistent with other Cortex tools (e.g. structured error in content or isError).

### 5. Tool description

- Provide a long description (in the tool registration) that includes:
  - **USE WHEN**: e.g. breaking down complex problems, multi-step planning, analysis with revision, unclear scope, need to filter irrelevant information.
  - **EXAMPLES**: e.g. “Plan a refactor”, “Debug a failing test”, “Design an API”.
  - **RETURNS**: Short description of the JSON shape (thoughtNumber, totalThoughts, nextThoughtNeeded, branches, thoughtHistoryLength).
- Reuse or adapt the reference tool description text for “When to use”, “Key features”, and “Parameters” so that clients get the same guidance.

### 6. Optional thought logging

- If desired, support an env var (e.g. `DISABLE_THOUGHT_LOGGING=true`) to skip logging formatted thoughts to stderr. Logging should be done outside the pure core (e.g. in the handler or a small helper) so the core stays pure.

### 7. Registration and packaging

- Import the new tool module in `src/cortex/tools/__init__.py` so the tool is registered when the server starts.
- Add the module to `__all__` and any package docs in `__init__.py`.

### 8. Documentation

- Update `docs/api/tools.md` (or equivalent) with the new tool: name, purpose, parameters, return shape, USE WHEN / EXAMPLES.
- Optionally add a short note in README under “Tool Names and MCP Capabilities” or “Available tools” (e.g. “Sequential thinking: `sequentialthinking` – stepwise reasoning and planning”).

---

## Dependencies

- None on other plans. Uses existing Cortex MCP stack (`mcp`, `mcp_tool_wrapper`, constants).

---

## Success Criteria

- Cortex exposes a tool named `sequentialthinking` with input/output compatible with the reference MCP sequential thinking server.
- Single-threaded, single-client usage: thought history and branches persist for the server process and behave as in the reference (append, branch recording, totalThoughts adjustment).
- All handler code is async and wrapped with `@mcp_tool_wrapper(timeout=...)`; core logic is pure and synchronous.
- TypedDicts (or equivalent) used for input/output; no `Any`; Python 3.13+ style types.
- Tool docstring includes USE WHEN, EXAMPLES, RETURNS.
- Unit tests achieve ≥95% coverage for the new module; integration test optionally calls the tool and asserts on response shape.

---

## Technical Design

- **Module**: `src/cortex/tools/sequential_thinking.py` (or split into `sequential_thinking.py` + `sequential_thinking_core.py` if &gt;400 lines).
- **State**: In-memory thought history and branches; one core instance per process for v1.
- **Timeout**: `MCP_TOOL_TIMEOUT_MEDIUM` (120s) unless policy assigns COMPLEX; each invocation is lightweight.
- **Naming**: Tool name `sequentialthinking` (camelCase) for protocol compatibility; Python internals snake_case.

---

## Testing Strategy (MANDATORY)

- **Coverage target**: Minimum 95% for the new tool module and core logic.
- **Unit tests**:
  - Core: `process_thought` with various inputs (first thought, revision, branch, need more thoughts, thought_number &gt; total_thoughts); assert output dict and internal state (history length, branches keys).
  - Handler: mock core or call real core; assert MCP response structure (content array, JSON parseable, contains thoughtNumber, totalThoughts, nextThoughtNeeded, branches, thoughtHistoryLength).
- **Edge cases**: thought_number 1, large thought_number; total_thoughts increase; empty thought string; optional params omitted; branch_id without branch_from_thought and vice versa (define expected behavior and test).
- **Integration**: One test that invokes the tool via the running server (or in-process) and checks response shape (and optionally that a second call increases thoughtHistoryLength). Use AAA pattern; no blanket skips.
- **Pydantic v2**: If tests validate JSON tool responses, use Pydantic v2 `BaseModel` and `model_validate_json()` / `model_validate()` per project standards (see e.g. `tests/tools/test_file_operations.py`).

---

## Risks & Mitigation

- **State across clients**: If Cortex ever runs with multiple concurrent clients, shared state could mix thoughts. Mitigation: v1 assumes single client; later add optional `session_id` and per-session state.
- **Memory growth**: Unbounded thought history could grow large. Mitigation: document that history is process-scoped; later add optional cap or TTL if needed.

---

## Timeline

- Implementation: 1–2 days (core + handler + tests + docs).
- No hard dependency on other roadmap items.

---

## Notes

- The reference implementation uses Zod for input/output; Cortex will use TypedDict and manual or Pydantic validation at the boundary.
- Optional console formatting (e.g. “Thought 1/5”) can be implemented in the handler or a small helper when not disabled by env; keep formatting out of the core for testability.
