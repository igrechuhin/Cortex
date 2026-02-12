# AGENTS

Workspace-wide rules for all IDE/AI agents in this repository.

## Use Cortex MCP (MANDATORY)

This project has a **Cortex MCP server** that provides tools for everything agents need. **Always use Cortex MCP tools instead of reading files or running commands directly.**

| Need | Cortex MCP tool | Do NOT |
|---|---|---|
| Project context, architecture, decisions | `load_context` / `load_progressive_context` | Read `.cortex/memory-bank/` files directly |
| Coding rules, standards, style | Rules/validation tools, `get_synapse_rules` | Read `.cortex/rules/` or `.cortex/synapse/` directly |
| Markdown formatting (headings vs emphasis, MD036) | `get_synapse_rules(task_description="markdown formatting")`, [docs/guides/markdown-formatting.md](docs/guides/markdown-formatting.md) | Use bold for section titles (use `#`/`##`/`###` instead) |
| Quality fixes (lint, format, types) | `fix_quality_issues` | Run `black`, `ruff`, `isort` manually |
| Tests and pre-commit checks | `execute_pre_commit_checks` | Run `pytest` directly |
| Memory bank, roadmap, plans, reviews | Dedicated MCP helpers | Edit `.cortex/` files directly |
| Project structure, paths | `get_structure_info` | Hardcode `.cortex/` paths |
| Cache JSON under `.cortex/.cache` | `read_cache_json` / `write_cache_json` | Read/write cache files directly |

**Tools vs Resources:** For read-only operations (e.g. load context, stats, file content), prefer MCP Resources (`cortex://` URIs) when available. Tools with `get_*` names are read-only; use Tools for writes (e.g. `write_file`, `update_config`). See `docs/api/tools.md` and Phase 43 plan for naming conventions.

**Workflow and compound-engineering:** Delivered by Cortex MCP; do not duplicate here — fetch via `load_context` / memory bank.

**Note for AI agents**: Do not add detailed workflow guides (including fix-path rules) to `AGENTS.md` or `CLAUDE.md`; always fetch commit/implement/fix-path behavior from Cortex MCP (Synapse prompts, rules, and memory bank).

## Workflow

1. **Scope the task** — restate the user's goal.
2. **Call Cortex MCP** — load context, fetch rules, discover tools. Let Cortex choose what's relevant.
3. **Edit code** — use IDE tools (`Read`, `Write`, `Grep`, `Glob`, `LS`) for source files.
4. **Verify** — use Cortex quality/test tools, not raw shell commands.

## Commit pipeline (phase-based)

The commit workflow is organized into phases (see `docs/design/commit-pipeline-phases.md`). Use phase helpers so `/cortex/commit` orchestrates instead of micromanaging:

- **Phase A**: `run_preflight_checks()` — fix_errors, format, markdown lint, type_check, quality, tests. If it fails, stop and use `/cortex/fix-tests` or `/cortex/fix-quality`; do not debug inline.
- **Phase B**: `run_docs_and_memory_bank_sync()` — after memory-bank/roadmap steps, validates timestamps and sync. If it fails, use `/cortex/docs-sync` then retry.
- **Zero-errors policy**: Any check with errors blocks commit; no exceptions. Apply fixes (or use the helper commands above) before proceeding.

## Safety (non-negotiable)

- No destructive git (`reset --hard`, force-push); no commits/pushes without explicit user request.
- No hardcoded secrets; no sensitive data in logs or memory bank.
- Continue until done or genuinely blocked; do not stop after planning work you can do now.
