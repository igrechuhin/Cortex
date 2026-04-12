# Migration matrix: legacy quality MCP entrypoints

**Related plan:** [deprecation-legacy-quality-entrypoints.md](deprecation-legacy-quality-entrypoints.md)  
**Sunset:** 2026-07-01 (see `src/cortex/tools/execution/legacy_quality_mcp_compat.py`)

## Classified references (snapshot 2026-04-12)

| Location | Type | Replacement | Complexity |
|----------|------|-------------|------------|
| `src/cortex/tools/execution/pre_commit_preflight_helpers.py` | Internal Phase A preflight | `run_detached_phase_a_checks` (same engine as `run_quality_gate`) | Done |
| `src/cortex/tools/execution/pre_commit_tools*.py`, `pre_commit_phase_dispatch.py`, `pre_commit_detached.py` | Implementation of legacy tools + phase dispatch | Keep until sunset; new code uses zero-arg / detached runner | High |
| `src/cortex/core/mcp_stability_usage.py` | Pytest lightweight tool allowlist (string name) | Keep name aligned with registered MCP tool until removal | Low |
| `tests/unit/test_pre_commit_tools.py` | Tests legacy tool surface | Keep for contract tests until removal; prefer new tests on `run_quality_gate` | Medium |
| `tests/e2e/test_commit_pipeline.py` | E2E | `run_quality_gate()` + session `checks-task.json` | Done |
| `docs/api/tools.md` | Documentation | Sunset + migration table | Done |
| `.cortex/synapse/prompts/archive/*`, `.cortex/synapse/agents/*` | Archived / agent prompts | Update opportunistically; not on hot path for shipped Cursor commands | Low |

## Allowlist (must remain until public removal)

- MCP registration and dispatch for `execute_pre_commit_checks`, `start_quality_job`, `get_quality_job_status`
- Unit tests that assert behavior of those tools
- Usage analytics / tool registry entries keyed by canonical tool names
