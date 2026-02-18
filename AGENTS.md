# AGENTS

Workspace-wide rules for all IDE/AI agents in this repository.

## Use Cortex MCP (MANDATORY)

This project has a **Cortex MCP server** that provides tools for everything agents need. **Always use Cortex MCP tools instead of reading files or running commands directly.**

| Need | Cortex MCP tool | Do NOT |
|---|---|---|
| Project context, architecture, decisions | `load_context` with two-step pattern: `load_context(depth="metadata_only")` → `manage_file(sections=[...])` for section-level drill-down. Use `strategy="progressive"` for incremental loading. | Read `.cortex/memory-bank/` files directly |
| Coding rules, standards, style | `rules(operation="get_relevant", ...)`, `get_synapse_rules(task_description="...")` | Read `.cortex/rules/` or `.cortex/synapse/` directly, hardcode language-specific rules |
| Structured params (tool params, dispatch data; use Pydantic BaseModel, not `dict[str, Any]`) | `get_synapse_rules(task_description="[language] models, structured data")` or `rules(operation="get_relevant", task_description="structured data, tool parameters")` | Hardcode structured data types (e.g., `dict[str, Any]`) |
| Markdown formatting (headings vs emphasis, MD036) | `get_synapse_rules(task_description="markdown formatting")`, [docs/guides/markdown-formatting.md](docs/guides/markdown-formatting.md) | Use bold for section titles (use `#`/`##`/`###` instead) |
| Quality fixes (lint, format, types) | `fix_quality_issues` | Run language-specific formatters/linters manually (get standards via `get_synapse_rules`) |
| Tests and pre-commit checks | `execute_pre_commit_checks` | Run language-specific test runners directly (get standards via `get_synapse_rules`) |
| Memory bank, roadmap, plans, reviews | Dedicated MCP helpers | Edit `.cortex/` files directly |
| Project structure, paths | `get_structure_info` | Hardcode `.cortex/` paths |
| Cache JSON under `.cortex/.cache` | `read_cache_json` / `write_cache_json` | Read/write cache files directly |

**Tools vs Resources:** For read-only operations (e.g. load context, stats, file content), prefer MCP Resources (`cortex://` URIs) when available. Read-only query tools: `query_memory_bank`, `query_usage`. Use Tools for writes (e.g. `manage_file`, `configure`). See `docs/api/tools.md` and Phase 43 plan for naming conventions.

**Workflow and compound-engineering:** Delivered by Cortex MCP; do not duplicate here — fetch via `load_context` / memory bank.

**Note for AI agents**: Do not add detailed workflow guides (including fix-path rules) to `AGENTS.md` or `CLAUDE.md`; always fetch commit/implement/fix-path behavior from Cortex MCP (Synapse prompts, rules, and memory bank).

## Compound Engineering

Cortex aims to make each unit of engineering work easier than the last; communication and output should become more efficient over time. The workflow follows **Plan → Work → Review → Compound**:

- **Plan**: Plans in `.cortex/plans`, roadmap entries; load context at step start.
- **Work**: Implement prompt, commit pipeline, code and memory bank updates.
- **Review**: Pre-commit checks, validation, code review; session optimization analysis at end of session.
- **Compound**: Update memory bank (activeContext, progress, roadmap), run session optimization, capture what to do differently next time.

Updating activeContext (completed work), progress, and roadmap (future work) after significant changes is the **compound** step: it makes the next session easier by keeping context accurate and avoiding duplicate or conflicting entries. Running session optimization at end of session is the **Compound** step of the loop: it captures mistake patterns, root causes, and recommendations so the next session can avoid repeating them.

See the implement, commit, and analyze prompts (Synapse) for detailed workflow guidance and compound checklist.

## Workflow

1. **Get session orientation** (recommended) — call `session_start()` for efficient orientation (< 1000 tokens). Returns current focus, next work item, health check, git status, and suggestions. Replaces 3-5 manual orientation calls.
2. **Scope the task** — restate the user's goal.
3. **Call Cortex MCP** — load context using two-step pattern (`load_context(depth="metadata_only")` → `manage_file(sections=[...])`), fetch rules, discover tools. Let Cortex choose what's relevant. **Pattern**: `session_start()` → `load_context(task_description=brief.next_work_item, ...)` → work.
4. **Think before acting** — use the `think` tool for quick deliberation moments (analyzing tool outputs, checking policy compliance, planning multi-step operations). For formal multi-step reasoning, use `sequentialthinking`.
5. **Edit code** — use IDE tools (`Read`, `Write`, `Grep`, `Glob`, `LS`) for source files.
6. **Verify** — use Cortex quality/test tools, not raw shell commands.

**Load context on the fix path (MANDATORY)**: When you encounter a problem and have to fix something (errors, test failures, quality issues, type/lint violations), you **must** load context and rules **before** making changes. Call `load_context(task_description="Fixing errors and issues", token_budget=15000)` and, when applicable, `rules(operation="get_relevant", task_description="...")` (or read key standards from the rules path if rules are disabled). Only after context and rules are loaded, proceed with fixes. This ensures fixes follow all project rules and guidelines. See the commit and implement prompts for concrete placement.

## Commit pipeline (phase-based)

The commit workflow is organized into phases (see `docs/design/commit-pipeline-phases.md`). Use phase helpers so `/cortex/commit` orchestrates instead of micromanaging:

- **Phase A**: `run_preflight_checks()` — fix_errors, format, markdown lint, type_check, quality, tests. If it fails, stop and use `/cortex/fix-tests` or `/cortex/fix-quality`; do not debug inline.
- **Phase B**: `run_docs_and_memory_bank_sync()` — after memory-bank/roadmap steps, validates timestamps and sync. If it fails, use `/cortex/docs-sync` then retry.
- **Zero-errors policy**: Any check with errors blocks commit; no exceptions. Apply fixes (or use the helper commands above) before proceeding.
- **Doc-only when tooling unavailable**: For documentation-only sessions, if the environment cannot run the quality gate (e.g. ruff/black not in path, type_check certificate failure), the implement prompt may allow proceeding with a "run full pre-commit before commit" note; see [Troubleshooting: Quality gate unavailable](docs/guides/troubleshooting.md#quality-gate-unavailable-in-environment).

## Session Compaction (Phase 56)

**End-of-session compaction**: The `analyze.md` prompt automatically calls `compact_session()` at the end of each session to:

- Reduce `activeContext.md` size by summarizing older Completed Work sections (keeps current date full)
- Apply progressive summarization to `progress.md` (full entries for 7 days, weekly summaries for 7-30 days, monthly summaries for 30+ days)
- Create session handoff JSON (`.cortex/.cache/session/last_handoff.json`) for next session continuity
- Generate pre-compaction snapshots for rollback safety

**Session handoff**: The handoff JSON is automatically loaded by `session_start()` at the beginning of the next session, providing:

- Completed tasks from the previous session
- In-progress tasks with notes
- Key decisions made
- Blockers and next actions

**Manual compaction**: Agents can call `compact_session(summary="...")` directly if needed, but typically this is handled automatically by the analyze prompt.

## Safety (non-negotiable)

- No destructive git (`reset --hard`, force-push); no commits/pushes without explicit user request.
- No hardcoded secrets; no sensitive data in logs or memory bank.
- Continue until done or genuinely blocked; do not stop after planning work you can do now.
