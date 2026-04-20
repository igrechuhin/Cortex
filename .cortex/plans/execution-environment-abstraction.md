---
title: "Introduce Tool Dispatch Layer for Environment-Agnostic Quality Gate Execution"
component: "tools"
work_type: "refactor"
status: PENDING
priority: "Medium"
created: "2026-04-20"
depends_on: []
---

## Goal

Add a thin `ExecutionEnvironment` protocol so `run_quality_gate()`, `autofix()`, and `run_docs_gate()` can run against any project root (local, worktree, remote path) without changing orchestration logic.

## Context

Cortex's quality gate tools call subprocess commands (`ruff`, `pyright`, `pytest`, `black`) with hardcoded assumptions: the project root is always resolved via `get_or_resolve_project_root(ctx)` and commands are always run locally. This works today but breaks when you want to run agents against a git worktree, a remote path, or a different working directory.

This maps to the Managed Agents `execute(name, input) → string` pattern: the harness doesn't know whether the sandbox is a container, a phone, or a Pokémon emulator. Right now Cortex's "harness" (quality gate tools) is tightly coupled to "local subprocess in project root." Introducing an `ExecutionEnvironment` protocol decouples them, enabling worktree-isolated quality checks without touching orchestration.

## Scope

**in_scope**

- `ExecutionEnvironment` Protocol with `execute(tool: str, args: list[str], cwd: Path) -> ExecutionResult`
- `ExecutionResult` Pydantic model: `{returncode: int, stdout: str, stderr: str, duration_ms: int}`
- `LocalExecutionEnvironment` — wraps current subprocess logic
- `WorktreeExecutionEnvironment(worktree_path: Path)` — runs commands with `cwd=worktree_path`
- Refactor `run_quality_gate`, `autofix`, `run_docs_gate` to accept `env: ExecutionEnvironment | None = None` (default `LocalExecutionEnvironment`)
- Unit tests: mock environment, local environment, worktree path routing

**out_of_scope**

- Remote execution (SSH, Docker, cloud sandboxes)
- Async execution or parallel tool runs
- Changes to what commands are run (only where/how they're dispatched)
- Changes to quality gate result parsing logic

## Approach

Define `ExecutionEnvironment` as a `typing.Protocol` in a new `src/cortex/core/execution_env.py` module. The protocol has one method: `execute(tool: str, args: list[str], cwd: Path) -> ExecutionResult`.

`LocalExecutionEnvironment` calls `subprocess.run` with the given `cwd`. `WorktreeExecutionEnvironment` does the same but forces `cwd` to the worktree path regardless of what the caller passes (ensuring isolation).

Refactor the three quality gate tools to extract their subprocess calls into a private `_run_command(env, ...)` helper that delegates to `env.execute(...)`. The public tool signatures gain an optional `env` parameter; callers that don't pass one get `LocalExecutionEnvironment` as default.

No behavior changes — this is a pure refactor. Existing tests should pass without modification.

## Implementation Steps

1. Create `src/cortex/core/execution_env.py` with:
   - `ExecutionResult` Pydantic BaseModel: `returncode: int`, `stdout: str`, `stderr: str`, `duration_ms: int`
   - `ExecutionEnvironment` Protocol with `execute(tool: str, args: list[str], cwd: Path) -> ExecutionResult`
   - `LocalExecutionEnvironment` class implementing the protocol via `subprocess.run`
   - `WorktreeExecutionEnvironment(worktree_path: Path)` class — same but forces `cwd=self.worktree_path`
2. In `src/cortex/tools/quality_gate.py`, extract subprocess calls into `_run_command(env: ExecutionEnvironment, tool: str, args: list[str], cwd: Path) -> ExecutionResult`. Update `run_quality_gate` signature: `async def run_quality_gate(ctx, env: ExecutionEnvironment | None = None)`.
3. Repeat for `src/cortex/tools/autofix.py` → `autofix` gains `env` param.
4. Repeat for `src/cortex/tools/docs_gate.py` (or wherever `run_docs_gate` lives) → same pattern.
5. Export `ExecutionEnvironment`, `ExecutionResult`, `LocalExecutionEnvironment`, `WorktreeExecutionEnvironment` from `src/cortex/core/__init__.py`.
6. Unit tests in `tests/unit/core/test_execution_env.py`:
   - Mock environment: verify `execute` is called with correct args
   - LocalExecutionEnvironment: verify subprocess.run is called with correct cwd
   - WorktreeExecutionEnvironment: verify cwd is always worktree_path regardless of caller-provided cwd
   - run_quality_gate with mock env: verify no subprocess calls, uses env.execute
7. Run quality gate — confirm all existing tests still pass (no behavior regression).

## Verification Checklist

- Step 1: read `src/cortex/core/execution_env.py`; confirm Protocol, both implementations, ExecutionResult present
- Step 2: grep `_run_command` in `quality_gate.py`; confirm it accepts `ExecutionEnvironment` and delegates
- Step 3: grep `env: ExecutionEnvironment` in `autofix.py`; confirm optional param with default
- Step 4: grep `env: ExecutionEnvironment` in docs gate file; confirm same pattern
- Step 5: read `src/cortex/core/__init__.py`; confirm all 4 names exported
- Step 6: run `pytest tests/unit/core/test_execution_env.py -v`; all pass
- Step 7: run `run_quality_gate()` (zero-arg); confirm existing quality gate result unchanged

## Dependencies

None — this plan is independent of Plans 1 and 2 and can run in parallel.

## Success Criteria

- `ExecutionEnvironment` Protocol defined with `execute(tool, args, cwd) -> ExecutionResult`
- `run_quality_gate`, `autofix`, `run_docs_gate` all accept optional `env` parameter
- `WorktreeExecutionEnvironment` routes all subprocess calls to the given worktree path
- All existing quality gate tests pass without modification
- New unit tests achieve 95%+ coverage on `execution_env.py`

## Testing Strategy

Target: 95% coverage on `src/cortex/core/execution_env.py` and the `_run_command` helpers. AAA pattern throughout.

- **Unit — Protocol compliance**: Arrange: `LocalExecutionEnvironment` and `WorktreeExecutionEnvironment`. Act: isinstance check against Protocol. Assert: both satisfy the protocol.
- **Unit — LocalExecutionEnvironment**: Arrange: mock `subprocess.run`. Act: `env.execute("ruff", ["check", "."], cwd=Path("/project"))`. Assert: subprocess called with `cwd=Path("/project")`.
- **Unit — WorktreeExecutionEnvironment**: Arrange: worktree path `/tmp/wt`. Act: `env.execute("ruff", ["check", "."], cwd=Path("/project"))`. Assert: subprocess called with `cwd=Path("/tmp/wt")` (worktree path wins).
- **Unit — ExecutionResult**: Arrange: subprocess returns `returncode=0, stdout="ok"`. Act: build `ExecutionResult`. Assert: all fields populated including `duration_ms >= 0`.
- **Unit — run_quality_gate with mock env**: Arrange: mock env that returns `ExecutionResult(returncode=0, ...)`. Act: `run_quality_gate(ctx, env=mock_env)`. Assert: no real subprocess calls; result parsed from mock output.
- **Regression — existing quality gate**: Arrange: real project root. Act: `run_quality_gate()` with no `env` arg. Assert: result identical to pre-refactor baseline.

## Risks and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Behavior regression in existing quality gate calls | Low | High | Regression test (Step 7) runs full gate before reporting success |
| Protocol not recognized at runtime (structural subtyping) | Low | Medium | Add explicit `isinstance` check in unit tests; use `runtime_checkable` decorator on Protocol |
| WorktreeExecutionEnvironment cwd override breaks tools that need project root for config | Medium | Medium | Document that worktree must be a full project copy; out of scope to handle partial worktrees |
| Refactor expands scope to other subprocess calls in the codebase | Low | Low | Strict scope: only the three gate tools; grep for other subprocess calls and exclude explicitly |
