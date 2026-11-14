---
status: DONE
---

# Approved Project Access

## Goal

Enable a project agent to read exact approved text files, query approved SQLite profile datasets, and launch existing approved project calculations without arbitrary SQL or shell execution. Reuse manage_file with an explicit project_access operation; keep the 14-tool surface.

## Scope and safety

Disabled by default. Require an externally supplied policy and matching SHA-256 pinned in server environment, bound to the resolved project root. Do not activate TradeWing, change its router, copy its exporter, run production experiments, train, trade, deploy, commit, or push.

## Steps

1. Inspect existing entrypoints and project rules.
2. Add typed policy/request validation, descriptor-relative no-symlink file access and bounded secret-screened reads.
3. Add structured SELECT-only dataset queries over bounded stable SQLite snapshots; refuse active WAL sources.
4. Add pinned existing-script job execution, finite approved parameters, exclusive per-task output reservation, durable status and no automatic retry after uncertain launch.
5. Exercise fixture files, SQLite and harmless jobs through the published entrypoint; run Cortex quality and docs gates.
6. Document opt-in installation and TradeWing verification; record remaining activation step.

## Validation

Local temporary fixtures only. Cover disabled access, wrong root/hash, traversal, symlinks, secret paths/content, query injection and limits, script tampering, duplicate/concurrent starts, errors/timeouts and durable status.

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
