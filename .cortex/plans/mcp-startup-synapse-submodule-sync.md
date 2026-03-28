---
title: "MCP startup: Synapse submodule sync"
component: mcp
work_type: feature
status: PENDING
priority: medium
created: 2026-03-28
depends_on: []
---

## Goal

When the Cortex MCP server process starts (`uv run cortex`), automatically ensure the `.cortex/synapse` git submodule is updated so agents load prompts and rules from the intended revision—without requiring a manual `git submodule update`.

## Context

- `src/cortex/main.py` documents that the server does not run tools on startup; Synapse content is imported at process start (`cortex.tools.synapse.prompts`). A stale or uninitialized submodule yields missing or outdated prompts/rules.
- `pre_commit_submodule_guard` and docs already emphasize submodule hygiene; startup sync must **not** silently destroy local submodule work or conflict with commit-time expectations.
- "Latest" is ambiguous: **superproject gitlink** (`git submodule update --init --recursive`) vs **remote tracking branch** (`git submodule update --remote`). Implementation must pick one policy (or gate with config) and document it.

## Implementation Steps

1. **Define semantics and safety** — Decide default behavior: init-only vs remote tip; document in `AGENTS.md` / troubleshooting if user-visible. Require **opt-out** (e.g. `CORTEX_SKIP_SYNAPSE_UPDATE=1`) for offline/air-gap. If submodule worktree is **dirty** or update fails (network, auth), log clearly and continue or fail fast per product choice.
2. **Add a small submodule helper** — Prefer a dedicated module under `src/cortex/` (e.g. near existing git/subprocess helpers) that runs bounded-timeout `git` subprocesses from `project_root`, returns structured result (success, skipped, error message). Reuse patterns from `pre_commit_submodule_guard.py` for timeouts and error strings where appropriate.
3. **Hook startup** — Invoke the helper once before `mcp.run()` in `_run_server_once()` (or shared path used by stdio/SSE) so every transport benefits. Avoid duplicate work in `CORTEX_AUTO_RESTART` inner loop if the same process stays up.
4. **Tests** — Unit tests with mocked `subprocess` / git: success path, skip when env set, dirty submodule yields expected branch, timeout/error does not crash the server if policy is non-fatal.
5. **Docs** — Short note in developer-facing docs: when sync runs, env to disable, and relationship to manual `git submodule update --init --recursive`.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|------------------|
| 1 | `CORTEX_SKIP`, submodule policy | `src/`, `docs/` | `main.py`, `AGENTS.md` |
| 2 | `subprocess`, `git`, timeout | `src/cortex/` | `pre_commit_submodule_guard.py` |
| 3 | `_run_server_once`, `mcp.run` | `src/cortex/main.py` | `main.py` |
| 4 | `pytest`, mock subprocess | `tests/` | New/updated test module |

## Dependencies

- Git available on PATH when MCP runs from repo root (existing assumption for quality gates).
- Network only if policy uses `--remote` or fetch.

## Success Criteria

- Fresh clone after `git submodule update --init` and routine pulls: MCP start leaves Synapse at the chosen revision policy without extra manual steps.
- Offline users can disable auto-sync via documented env.
- No silent data loss in a dirty `.cortex/synapse` worktree.

## Testing Strategy (95% coverage target)

- Cover helper branches (success, skip env, dirty, git failure, timeout) with mocks; integration test optional if a lightweight git fixture is already used elsewhere.
