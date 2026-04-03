# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-04-03)

- **Quality gate and linking stack (PARTIAL)** - Pre-commit quality pipelines and zero-arg governance tests refactored; reflection evaluation tightened; transclusion operations and rules operations updated with expanded regression coverage.

- ✅ **Transclusion reliability (PARTIAL)** - COMPLETE (2026-04-03) - Hardened `resolve_transclusions` root selection and error typing; added JSON warning logs for uncaught exceptions in the resolution path.

- ✅ **Fix `_execute_transclusion_resolution` Reliability** - COMPLETE (2026-04-03) - Structured failure logging, memory-bank root fallback, PathError/FileNotFoundError validation, section-not-found full-file fallback, resource omits original_content by default; regression tests and quality gate green. Production error-rate verification remains via usage analytics.

- ✅ **Reduce Quality Gate Latency and Pre-commit Token Bloat** - COMPLETE (2026-04-03) - Conditional cache clear on `force_fresh`, trimmed passing gate responses, `agent_log` omitted on pass, `PipelineDirtyTracker` after successful gate, adaptive poll intervals, `checks.skipped` / `checks.executed` logs, `preflight_passed` from Phase A plus markdown; tests and `run_quality_gate` verified. Success criteria 1–3 (50-day latency/tokens/skip rate) remain operational analytics.

- ✅ **Prune dead tools / analyze truncation (PARTIAL)** - COMPLETE (2026-04-03) - cortex://analysis now passes default truncation parameters; context effectiveness responses can include truncated=true and caps on stats tail; list_plans/get_plan are plain async helpers.

- ✅ **Prune Dead/Near-Dead Tools and Reduce Token-Heavy Responses** - COMPLETE (2026-04-03) - Finished analyze resource size bounds: context stats now expose truncated when recent_entries tail is capped; unit test coverage. Prior work already removed list_plans/get_plan from MCP, added cortex://analysis defaults, and updated docs/tests.

- ✅ **Anthropic cache hints on MCP resources (PARTIAL)** - COMPLETE (2026-04-03) - cortex://rules and cortex://context now register cache_control in resource meta (ephemeral TTLs) and use 300s in-process TTL caches; tests in tests/unit/test_mcp_resource_cache_control.py. Manual API token verification and Claude Code forwarding remain.

- ✅ **Add Anthropic Prompt Cache-Control to MCP Resource Responses** - COMPLETE (2026-04-03) - Registered cache_control hints on cortex://rules (1h) and cortex://context (5m) via FastMCP @mcp.resource(meta); 300s in-process TTL caches for both resources; unit tests for meta and cache hits; constants documented.

## Completed Work (2026-04-02)

- **Summary (2026-04-02)** - 1 entries archived.

## Completed Work (2026-04-01)

- **Summary (2026-04-01)** - 1 entries archived.

## Completed Work (2026-03-31)

- **Summary (2026-03-31)** - 1 entries archived.

## Completed Work (2026-03-30)

- **Summary (2026-03-30)** - 1 entries archived.

## Completed Work (2026-03-29)

- **Summary (2026-03-29)** - 1 entries archived.

## Completed Work (2026-03-28)

- **Summary (2026-03-28)** - 1 entries archived.

## Completed Work (2026-03-27)

- **Summary (2026-03-27)** - 1 entries archived.

## Completed Work (2026-03-26)

- **Summary (2026-03-26)** - 1 entries archived.

## Completed Work (2026-03-25)

- **Summary (2026-03-25)** - 1 entries archived.

## Completed Work (2026-03-24)

- **Summary (2026-03-24)** - 1 entries archived.

## Completed Work (2026-03-23)

- **Summary (2026-03-23)** - 1 entries archived.

## Completed Work (2026-03-22)

- **Summary (2026-03-22)** - 1 entries archived.

## Completed Work (2026-03-21)

- **Summary (2026-03-21)** - 1 entries archived.

## Completed Work (2026-03-20)

- **Summary (2026-03-20)** - 1 entries archived.

## Completed Work (2026-03-16)

- **Summary (2026-03-16)** - 1 entries archived.

## Completed Work (2026-03-14)

- **Summary (2026-03-14)** - 1 entries archived.

## Completed Work (2026-03-13)

- **Summary (2026-03-13)** - 1 entries archived.

## Completed Work (2026-03-12)

- **Summary (2026-03-12)** - 1 entries archived.

## Completed Work (2026-03-11)

- **Summary (2026-03-11)** - 1 entries archived.

## Completed Work (2026-03-10)

- **Summary (2026-03-10)** - 1 entries archived.

## Completed Work (2026-03-09)

- **Summary (2026-03-09)** - 1 entries archived.

## Completed Work (2026-03-08)

- **Summary (2026-03-08)** - 1 entries archived.

## Completed Work (2026-03-07)

- **Summary (2026-03-07)** - 1 entries archived.

## Completed Work (2026-03-06)

- **Summary (2026-03-06)** - 1 entries archived.

## Completed Work (2026-03-05)

- **Summary (2026-03-05)** - 1 entries archived.

## Completed Work (2026-03-04)

- **Summary (2026-03-04)** - 1 entries archived.

## Completed Work (2026-03-03)

- **Summary (2026-03-03)** - 1 entries archived.

## Completed Work (2026-03-02)

- **Summary (2026-03-02)** - 1 entries archived.

## Completed Work (2026-03-01)

- **Summary (2026-03-01)** - 1 entries archived.

## Completed Work (2026-02-28)

- **Summary (2026-02-28)** - 1 entries archived.

## Completed Work (2026-02-27)

- **Summary (2026-02-27)** - 1 entries archived.

## Completed Work (2026-02-26)

- **Summary (2026-02-26)** - 1 entries archived.

## Completed Work (2026-02-25)

- **Summary (2026-02-25)** - 1 entries archived.

## Completed Work (2026-02-24)

- **Summary (2026-02-24)** - 1 entries archived.

## Completed Work (2026-02-23)

- **Summary (2026-02-23)** - 1 entries archived.

## Completed Work (2026-02-22)

- **Summary (2026-02-22)** - 1 entries archived.

## Completed Work (2026-02-21)

- **Summary (2026-02-21)** - 1 entries archived.

## Completed Work (2026-02-20)

- **Summary (2026-02-20)** - 1 entries archived.

## Completed Work (2026-02-19)

- **Summary (2026-02-19)** - 1 entries archived.

## Completed Work (2026-02-18)

- **Summary (2026-02-18)** - 1 entries archived.

## Completed Work (2026-02-17)

- **Summary (2026-02-17)** - 1 entries archived.

## Completed Work (2026-02-16)

- **Summary (2026-02-16)** - 1 entries archived.

## Completed Work (2026-02-13)

- **Summary (2026-02-13)** - 1 entries archived.

## Completed Work (2026-01-14)

- **Summary (2026-01-14)** - 1 entries archived.

## Completed Work (2026-02-12)

- **Summary (2026-02-12)** - 1 entries archived.

## Completed Work (2026-02-11)

- **Summary (2026-02-11)** - 1 entries archived.

## Completed Work (2026-02-10)

- **Summary (2026-02-10)** - 1 entries archived.

## Completed Work (2026-02-09)

- **Summary (2026-02-09)** - 1 entries archived.

## Completed Work (2026-02-07)

- **Summary (2026-02-07)** - 1 entries archived.

## Current Focus

Next implementation slice: **[QG-S1] Add EXTENSION_SCRIPT_MAP** per [roadmap.md](roadmap.md) Blockers and `.cortex/plans/swift-qg-s1-add-extension-script-map.plan.md`.

## Recent Changes

Memory-bank guardrail (2026-04-01): when `roadmap_progress_consistency` fails, never create synthetic reconciliation/verification backlog entries. Only keep concrete, implementation-ready roadmap items tied to real deliverables.

Synapse sync timing (2026-03-28): submodule update runs when lazy prompts first register, after `resolve_project_root_async`, aligning sync with MCP roots (not only process CWD).

MCP startup Synapse sync (2026-03-29): dirty submodule worktrees are stashed around `git pull --ff-only origin main` inside `.cortex/synapse` (replacing superproject `git submodule update --init --recursive`); structured outcomes cover stash/push/pop edge cases; see AGENTS.md and `docs/guides/troubleshooting.md` MCP preflight.

Submodule hygiene for commits (2026-03-20): `pre_commit_submodule_guard` blocks Phase A when a submodule worktree is dirty or the gitlink is out of sync; covered by `test_pre_commit_submodule_guard.py` and pre-commit tool fixture patches.

Blocker (2026-02-09): Plan prompt and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
