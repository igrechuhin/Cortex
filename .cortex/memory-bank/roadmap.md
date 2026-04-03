# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### Fixes

### Quality & Reliability Improvements

- **Fix `_execute_transclusion_resolution` Reliability** — PENDING — `.cortex/plans/fix-transclusion-resolution-reliability.md`
  Reduce 16.6% error rate (1,062/6,415 calls) to < 2% by hardening root resolution, defensive
  validation, section-not-found fallback, and structured error logging.

- **Reduce Quality Gate Latency and Pre-commit Token Bloat** — PENDING — `.cortex/plans/reduce-quality-gate-latency-tokens.md`
  Cut `run_quality_gate` avg latency (56s) and response tokens (2,323) by gating cache clears,
  trimming passing-run responses, activating dirty-state skip logic, and adaptive polling.

### Security

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

- **Prune Dead/Near-Dead Tools and Reduce Token-Heavy Responses** — PENDING — `.cortex/plans/prune-dead-tools-reduce-token-bloat.md`
  Remove `list_plans`/`get_plan` from MCP surface (superseded by `plan()`), confirm
  `run_tool_optimization_workflow` is fully pruned, and trim `analyze` resource from 5,941 avg
  tokens to < 1,500 with session truncation.

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Improvements

### Features & Enhancements

- **Add Anthropic Prompt Cache-Control to MCP Resource Responses** — PENDING — `.cortex/plans/add-anthropic-prompt-cache-control.md`
  Inject `cache_control` markers into `cortex://rules` and `cortex://context` resource responses
  so the Anthropic API caches their KV state, cutting input-token costs by ~90% on cache reads.
  Includes a mandatory spike to verify FastMCP + Claude Code annotation forwarding before
  implementing, and raises Cortex in-process resource cache TTL from 30s to 300s.
