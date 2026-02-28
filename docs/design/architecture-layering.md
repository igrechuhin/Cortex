# Architecture Layering

Layer boundaries, protocol usage, and dependency rules (Phase 9.2).

## Layer Diagram

```text
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Entry (main, server, tools)                            │
│ - MCP tool handlers, request routing                            │
│ - NO business logic; delegates to Layer 2                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2: Manager Initialization (managers/)                     │
│ - get_managers(), ManagerRegistry, LazyManager                  │
│ - Constructs Layer 3 instances via DI                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3: Business Logic (core/, optimization/, refactoring/)    │
│ - FileSystemManager, ContextOptimizer, ProgressiveLoader        │
│ - Uses protocols at boundaries                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4: Storage (filesystem, .cortex/, .cortex/index.json)     │
│ - Markdown files, JSON caches, version snapshots                │
└─────────────────────────────────────────────────────────────────┘
```

## Protocol Boundaries

### Cross-Module Interfaces

All cross-module dependencies **must** use protocols (PEP 544) instead of concrete classes:

| Boundary | Protocol | Implementor |
|----------|----------|-------------|
| File I/O | `FileSystemProtocol` | `FileSystemManager` |
| Metadata | `MetadataIndexProtocol` | `MetadataIndex` |
| Token counting | `TokenCounterProtocol` | `TokenCounter` |
| Context optimization | `ContextOptimizerProtocol` | `ContextOptimizer` |
| Progressive loading | `LoaderProtocol` | `ProgressiveLoader` (via attributes) |

### Loader Protocol (Partial—Phase 9.2)

`LoaderProtocol` (in `optimization/progressive_loader_protocols.py`) uses concrete types for its attributes. Protocol definitions are aligned; switching to protocol types is deferred until type checker invariance is resolved (ProgressiveLoader passes self to helpers expecting LoaderProtocol; Pyright rejects when attributes are protocol-typed).

**Alignments applied (2026-02-26):**

1. **FileSystemProtocol vs FileSystemManager**
   - `parse_sections`: Protocol return type aligned to `list[SectionMetadata]`.
   - `write_file`: `create_version: bool = True` added to implementation.
   - `memory_bank_dir: Path` added to protocol.

2. **ContextOptimizerProtocol vs ContextOptimizer**
   - `optimize_context` method added to protocol to match implementation.

3. **MetadataIndexProtocol**
   - Implementation already matches; no changes needed.

## Dependency Rules

1. **Layer N** may import from **Layer N+1** only via protocols.
2. **Layer N** must not import concrete implementations from sibling modules when a protocol exists.
3. **Protocol definitions** live in `core/protocols/` (or module-local for narrow use).

## Known Global State

The following use module-level mutable state; each has a rationale and future path:

| Location | Pattern | Rationale | Status |
|----------|---------|-----------|--------|
| `sequential_thinking.py` | `_injected_core` + `configure_sequential_thinking_core()` | Core injected at composition root (main.py); lazy fallback for tests | Phase 9.2: constructor injection at startup |
| `mcp_stability_config.py` | Frozen config sets | Immutable after load; effectively constants | No change needed |

See [ADR-009: SequentialThinking Singleton](../adr/ADR-009-sequential-thinking-singleton.md) for details.

## References

- [ADR-004: Protocol-Based Architecture](../adr/ADR-004-protocol-based-architecture.md)
- [Architecture Overview](../architecture.md)
