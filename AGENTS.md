# AGENTS

## Agent Operating Guidelines

- **Scope first**: Confirm user intent, map to allowed operations, and avoid touching unrelated files. Ask clarifying questions only when necessary to unblock progress.
- **Rules compliance**: Load applicable rules (workspace, memory bank, file-type) before actions; honor "avoid shell grep" by using `rg`/IDE tools; follow memory-bank workflow after significant changes.
- **Safety rails**: Never run destructive git commands, never leak secrets, and respect sandbox limits. Use `gtimeout` wrappers for long-running commands.
- **Tooling preference**: Use standard IDE tools (`Read`, `ApplyPatch`, `Write`, `Grep`, `Glob`, `LS`) for file operations; MCP filesystem tools are optional fallbacks only when explicitly requested or when standard tools unavailable; prefer ripgrep over shell `grep`; default to `.venv` binaries for Python tooling.
- **Plan archiving**: Archive completed plans under `.cursor/plans/archive/PhaseX/MilestoneY/` matching plan's Phase/Milestone; use `mkdir -p` and `mv` with absolute paths if needed.
- **Change discipline**: Keep functions ≤30 lines (logical lines, excluding doc comments & blank lines) and files ≤400 lines (excluding license headers & imports); one public type per file; private constants at file level; pure helpers at file level; preserve async correctness; ensure clear input validation and domain-specific errors.
- **Dependency injection**: All external dependencies MUST be injected via initializers; NO global state or singletons in production code.
- **Documentation sync**: Update memory bank (`.cursor/memory-bank/` - activeContext/progress/roadmap) after meaningful changes; add roadmap entries for any TODOs introduced; all TODO comments MUST be tracked in roadmap.md.
- **Memory bank location**: All memory bank files MUST be in `.cursor/memory-bank/` directory; core files: projectBrief.md, productContext.md, systemPatterns.md, techContext.md, activeContext.md, progress.md, roadmap.md.
- **Performance posture**: Avoid O(n²) regressions; record metrics where required; keep tests under 10s per case.
- **No auto-commit**: Never create commits or push without explicit user request; follow documented commit workflow when requested.
- **MCP tool error handling**: When encountering unexpected results from Cortex MCP tools, immediately create an investigation plan at `.cortex/plans/` and link it as a blocker (ASAP priority) in `.cortex/memory-bank/roadmap.md`. This ensures all tool issues are tracked and addressed systematically.
- **Execution continuity (CRITICAL)**: Continue execution until one of these valid stopping conditions is met: (1) Question to user that is REQUIRED to proceed, (2) Job is fully done and verified, (3) Out of context and cannot proceed, (4) Unrecoverable error requiring user intervention. Do NOT stop for partial completion, intermediate steps, retryable errors, or uncertainty that can be resolved by exploring the codebase. Premature stopping is a CRITICAL violation.

## Expectations for LLM Agents in This Repo

- **Security**: Validate paths/URIs, avoid hardcoded secrets, use parameterized queries, and sanitize logs. Reject traversal, control chars, and encoded slashes per existing helpers.
- **Testing**: Follow AAA pattern (MANDATORY); no blanket skips (MANDATORY); justify every skip with clear reason and linked ticket; target 100% pass on `.venv/bin/pytest` with `gtimeout` guards; add coverage for new public APIs and toggles; unit tests for all critical business logic and every public API surface (MANDATORY); minimum 90% coverage for new code.
- **Type hints**: 100% coverage required; NEVER use `Any` type (use Protocols, TypedDict, or `object` instead); use Python 3.13+ built-ins (`list[str]`, `dict[str, int]`, `tuple[str, int]`, `set[str]`, `T | None`) instead of `typing` module types (MANDATORY); use concrete types instead of `object` wherever possible - investigate actual return types and use them (MANDATORY).
- **Formatting**: Run `./.venv/bin/black .` and `./.venv/bin/isort .` before commits; don't hand-format against Black/isort.
- **Async correctness**: Use async for I/O, avoid blocking in event loop; offload CPU/file I/O; apply timeouts and structured concurrency.
- **MCP specifics**: Register handlers on the MCP server instance, use `stdio_server()` as an async context manager without arguments, and prevent server objects from being used as async iterables.
- **Memory bank**: Location `.cursor/memory-bank/` (MANDATORY); use YY-MM-DD timestamps only; validate with the ripgrep helper script; keep entries reverse-chronological; update after significant changes (MANDATORY).
- **Git hygiene**: No commits/pushes without explicit user request (MANDATORY); stage only related changes; never rebase/reset/force-push; follow documented commit workflow when requested.
- **File operations**: Use standard tools (`Read`, `ApplyPatch`, `Write`, `Grep`, `Glob`, `LS`) by default; MCP filesystem tools are optional fallbacks only when explicitly requested or when standard tools unavailable.
- **Python 3.13+ features**: Use modern built-ins - `list[str]` not `typing.List[str]`, `dict[str, int]` not `typing.Dict[str, int]`, `tuple[str, int]` not `typing.Tuple[str, int]`, `set[str]` not `typing.Set[str]`, `T | None` not `Optional[T]`, `asyncio.timeout()` not `asyncio.wait_for()`, `itertools.batched()`, `contextlib.chdir()`, `@cache`, `except*`, `typing.Self`, `Required`/`NotRequired` (MANDATORY); avoid `typing` module types when Python 3.13+ built-ins are available.
- **Concrete types**: Use concrete types instead of `object` wherever possible - investigate actual return types (e.g., `list[RefactoringSuggestion]`, `RollbackResult`, `dict[str, str | None]`) and use them instead of generic `object` (MANDATORY).
- **Type specificity**: Make types MORE specific, not less - prefer `dict[str, str]` over `dict[str, object]`, don't replace concrete types with generic ones (MANDATORY).
- **Avoid abstractions**: Don't use `Mapping` or other abstractions when `dict` works - use `dict` directly (MANDATORY).

## Cursor + MCP Development Practices

- **Interpreter selection**: When using Cursor or other IDEs, always point the Python interpreter to `.venv/bin/python` so type information and MCP tools match the runtime.
- **Typed MCP boundaries**: Define all MCP handlers with explicit parameter and return types, using `TypedDict`/dataclasses for JSON payloads instead of untyped `dict`.
- **Thin handlers, pure helpers**: Keep `@mcp.tool` handlers as thin async orchestrators that delegate to small, pure helper functions for business logic.
- **JSON modeling**: Model request/response shapes with `TypedDict` hierarchies where keys are known; only use `dict[str, object]` at true protocol edges.
- **Refactor strategy**: Prefer refactoring pure helpers (not handlers) when using automated tools, to preserve async behavior and protocol contracts.
