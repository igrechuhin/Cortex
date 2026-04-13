# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

- [ ] **BLOCKER: Fix mcp>=1.26.0 Structured-Output Crash on Startup** — server crashes at import with `PydanticUserError: run_quality_gateOutput is not fully defined`; root cause: mcp 1.26 auto-enables structured output for `ModelDict`-returning tools, Pydantic cannot resolve the recursive type alias; fix: pass `structured_output=False` in `typed_mcp_tool`. Plan: [../plans/fix-mcp-1-26-structured-output-crash.md](../plans/fix-mcp-1-26-structured-output-crash.md) (PENDING)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### FastMCP v3 Migration

- [ ] **FastMCP v3 — Phase 1: Dependency Swap and Import Migration** — swap `mcp>=1.26.0` bundled FastMCP for standalone `fastmcp>=3.0`; update all `from mcp.server.fastmcp` imports; verify `meta=` resource API and transport env vars; prerequisite for all subsequent phases. Plan: [../plans/fastmcp-v3-phase1-dependency-and-imports.md](../plans/fastmcp-v3-phase1-dependency-and-imports.md) (PENDING)
- [ ] **FastMCP v3 — Phase 2: Replace Internal Handler Patches with Official APIs** — remove all three `mcp._mcp_server.*` monkey-patches (`ListPromptsRequest`, `RootsListChangedNotification`, `_handle_request`) and replace with v3 lifespan hooks and official notification API. Plan: [../plans/fastmcp-v3-phase2-official-lifecycle-apis.md](../plans/fastmcp-v3-phase2-official-lifecycle-apis.md) (PENDING)
- [ ] **FastMCP v3 — Phase 3: Middleware for Disconnect Handling and Request Logging** — replace `MethodType` `_handle_request` patch with `DisconnectMiddleware`; add `LoggingMiddleware` at debug level; add `ResponseLimitMiddleware` for context-window safety. Plan: [../plans/fastmcp-v3-phase3-middleware.md](../plans/fastmcp-v3-phase3-middleware.md) (PENDING)
- [ ] **FastMCP v3 — Phase 4: Transport Configuration Cleanup** — pass `host`/`port` explicitly to `mcp.run()`; delete `apply_cortex_env_to_fastmcp()`; promote `streamable-http` as default for port-based mode. Plan: [../plans/fastmcp-v3-phase4-transport-cleanup.md](../plans/fastmcp-v3-phase4-transport-cleanup.md) (PENDING)
- [ ] **FastMCP v3 — Phase 5: New Features (Lifespan, Visibility, Auth, Transforms)** — server lifespan for DI; dynamic tool visibility for setup prompts; per-component auth on write tools; `ResourcesAsTools`/`PromptsAsTools` transforms; hot-reload dev mode. Plan: [../plans/fastmcp-v3-phase5-new-features.md](../plans/fastmcp-v3-phase5-new-features.md) (PENDING)

### Fixes

- [ ] **Fix: Add Missing Makefile Offline Targets** — README documents `make preflight-offline` and `make bootstrap-offline` but neither target exists in `Makefile`; onboarding breaks for restricted-network users. Plan: [../plans/fix-makefile-offline-targets.md](../plans/fix-makefile-offline-targets.md) (PENDING)
- [ ] **Fix: Stale Test-Count Metric in progress.md What Works Section** — "What Works" hardcodes `3702 tests, 90.36% coverage`; current suite is 5000+ tests; adds `StaleNumericClaimCheck` to `lint_memory_bank` to prevent future drift. Plan: [../plans/fix-stale-progress-metrics.md](../plans/fix-stale-progress-metrics.md) (PENDING)

### Quality & Reliability Improvements

### Security

### Documentation Cleanup (DRY)

### Refactoring

- [ ] **Refactor: Split Oversized `src/cortex/tools/session/brief.py` and `src/cortex/tools/optimization/handlers.py`** — both files are 700+ lines (well over the 400-line rule); split along existing responsibility boundaries into `brief_cap`, `brief_loaders`, `context_appenders`, `context_loaders`; no behaviour change. Plan: [../plans/refactor-oversized-modules.md](../plans/refactor-oversized-modules.md) (PENDING)

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Improvements

#### Knowledge Base & Wiki (High Priority)

#### Token Efficiency (High Priority)

### Features & Enhancements

#### Token Efficiency (Medium Priority)

#### Claude Code Harness Improvements (High Priority)

#### Planning & Brainstorming (High Priority)

#### Planning & Brainstorming (Medium Priority)

#### Wiki for Attached Projects (High Priority)

#### Planning & Brainstorming (Low Priority)
