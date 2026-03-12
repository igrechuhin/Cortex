# ADR-009: SequentialThinking Singleton

## Status

Accepted

## Context

The `think` MCP tool (full mode) maintains thought history and branches across multiple tool invocations. Each invocation appends a thought; the history persists for the duration of the client session.

### Deployment Model

Cortex runs as an MCP server with:

- **stdio transport**: One process per client; one client per process.
- **SSE/HTTP transport**: One process may serve multiple clients over time, but each request is effectively sequential per connection.

Under stdio (the default), there is exactly one client per process. A single `SequentialThinkingCore` instance per process is sufficient.

## Decision

Use a module-level singleton for `SequentialThinkingCore`:

```python
_core: SequentialThinkingCore | None = None

def _get_core() -> SequentialThinkingCore:
    global _core
    if _core is None:
        _core = SequentialThinkingCore()
    return _core
```

### Rationale

1. **Single-client assumption**: stdio runs one client per process; no need for per-session or per-request cores.
2. **Simplicity**: No DI plumbing through tool registration; tools call `_get_core()` directly.
3. **Testability**: `reset_core_for_testing()` clears the singleton between tests.

### Trade-offs

| Pros | Cons |
|------|------|
| Simple implementation | Global mutable state |
| No extra DI wiring | Not suitable for multi-tenant HTTP without per-request core |
| Easy to test via reset | Violates strict "zero global state" goal |

## Constructor Injection (Phase 9.2)

Constructor injection is implemented for the stdio deployment:

1. **`configure_sequential_thinking_core(core: SequentialThinkingCore | None)`** - Inject or clear the core.
2. **Composition root**: `main.py` calls `configure_sequential_thinking_core(SequentialThinkingCore())` at startup before `mcp.run()`.
3. **`_get_core()`** returns the injected core; lazy fallback for tests after `reset_core_for_testing()`.
4. **Module-level `_injected_core`** - Injected at startup, not lazily created in production.

## Future Path: Multi-Tenant / Request-Scoped

If Cortex needs multi-tenant or per-session cores (e.g., HTTP with concurrent requests):

1. Store core in request-scoped or connection-scoped context.
2. Pass core into the tool handler via DI or context.
3. Extend `configure_sequential_thinking_core` for per-request override.

## Consequences

- **Phase 9.2**: Documented as known global state in `docs/design/architecture-layering.md`.
- **No immediate change**: Current design is acceptable for stdio; future work can add DI when multi-tenant support is required.

## Related

- Phase 9.2: Architecture Refinement (protocol boundaries, DI audit)
- [Architecture Layering](../design/architecture-layering.md)
