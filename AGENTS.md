# AGENTS

Workspace-wide rules for all IDE/AI agents in this repository.

## Use Cortex MCP (MANDATORY)

This project has a **Cortex MCP server** that provides tools for everything agents need. **Always use Cortex MCP tools instead of reading files or running commands directly.**

| Need | Cortex MCP tool | Do NOT |
|---|---|---|
| Project context, architecture, decisions | `load_context` with two-step pattern: `load_context(depth="metadata_only")` → `manage_file(sections=[...])` for section-level drill-down. Use `strategy="progressive"` for incremental loading. | Read `.cortex/memory-bank/` files directly |
| Coding rules, standards, style | `rules(operation="get_relevant", ...)`, `get_synapse_rules(task_description="...")` | Read `.cortex/rules/` or `.cortex/synapse/` directly, hardcode language-specific rules |
| Structured params (tool params, dispatch data; use Pydantic BaseModel, not `dict[str, Any]`) | `get_synapse_rules(task_description="[language] models, structured data")` or `rules(operation="get_relevant", task_description="structured data, tool parameters")` | Hardcode structured data types (e.g., `dict[str, Any]`) |
| Type annotations (internal vs external) | Load rules before coding; use Pydantic models for internal data structures; `object` only for external interfaces (MCP tools) | Use `Any` type; use `object` for internal functions; skip loading rules |
| Markdown formatting (headings vs emphasis, MD036) | `get_synapse_rules(task_description="markdown formatting")`, [docs/guides/markdown-formatting.md](docs/guides/markdown-formatting.md) | Use bold for section titles (use `#`/`##`/`###` instead) |
| Quality fixes (lint, format, types) | `execute_pre_commit_checks(checks=["fix_quality"])` | Run language-specific formatters/linters manually (get standards via `get_synapse_rules`) |
| Tests and pre-commit checks | `execute_pre_commit_checks` | Run language-specific test runners directly (get standards via `get_synapse_rules`) |
| Memory bank, roadmap, plans, reviews | Dedicated MCP helpers (`manage_file` for all reads/writes) | Edit `.cortex/` files directly; do not use Write, StrReplace, or ApplyPatch on memory-bank paths—any edit (including one-line fixes) must use `manage_file(operation='read')` then `manage_file(operation='write', content=...)` |
| Project structure, paths | `get_structure_info` | Hardcode `.cortex/` paths |
| Cache JSON under `.cortex/.cache` | `cortex.core.cache_json_access.read_cache_json` / `write_cache_json` (internal); `manage_file` for reads | Read/write cache files directly; `cache_json` was internalized 2026-02-26 |

**Tools vs Resources:** For read-only operations (e.g. load context, stats, file content), prefer MCP Resources (`cortex://` URIs) when available. Read-only query tools: `query_memory_bank`, `query_usage`. Use Tools for writes (e.g. `manage_file`, `configure`). See [docs/api/tools.md](docs/api/tools.md) and [docs/architecture/naming-conventions.md](docs/architecture/naming-conventions.md) for naming rules.

**Workflow and compound-engineering:** Delivered by Cortex MCP; do not duplicate here — fetch via `load_context` / memory bank.

**Note for AI agents**: Do not add detailed workflow guides (including fix-path rules) to `AGENTS.md` or `CLAUDE.md`; always fetch commit/implement/fix-path behavior from Cortex MCP (Synapse prompts, rules, and memory bank).

## Type Annotations and Data Modeling

- Always load rules before coding to verify type annotation standards
- `Any` type is forbidden; for internal APIs, use Pydantic models if possible, otherwise use `object`
- Use `object` type for external interfaces (MCP tool parameters) and for internal APIs when Pydantic models aren't feasible
- Internal functions must use Pydantic BaseModel types (e.g., `ConnectionHealth`) instead of `dict[str, object]` when possible
- When logging Pydantic models, use `model.model_dump()` to convert to dict for logging purposes
- Check existing Pydantic models before creating new dict types for internal data structures
- Use `Literal` types only for external API boundaries (MCP tool parameters); internal Pydantic models must use enums

## Compound Engineering

Cortex aims to make each unit of engineering work easier than the last; communication and output should become more efficient over time. The workflow follows **Plan → Work → Review → Compound**:

- **Plan**: Plans in `.cortex/plans`, roadmap entries; load context at step start.
- **Work**: Implement prompt, commit pipeline, code and memory bank updates.
- **Review**: Pre-commit checks, validation, code review; session optimization analysis at end of session.
- **Compound**: Update memory bank (activeContext, progress, roadmap), run session optimization, capture what to do differently next time.

Updating activeContext (completed work), progress, and roadmap (future work) after significant changes is the **compound** step: it makes the next session easier by keeping context accurate and avoiding duplicate or conflicting entries. Running session optimization at end of session is the **Compound** step of the loop: it captures mistake patterns, root causes, and recommendations so the next session can avoid repeating them.

See the implement, commit, and analyze prompts (Synapse) for detailed workflow guidance and compound checklist.

## Workflow

1. **Get session orientation** (recommended) — call `session(operation="start")` for efficient orientation (< 1000 tokens). Returns current focus, next work item, health check, git status, and suggestions. Replaces 3-5 manual orientation calls.
2. **Scope the task** — restate the user's goal.
3. **Call Cortex MCP** — load context using two-step pattern (`load_context(depth="metadata_only")` → `manage_file(sections=[...])`), fetch rules, discover tools. Let Cortex choose what's relevant. **Pattern**: `session(operation="start")` → `load_context(task_description=brief.next_work_item, ...)` → work

**Context budget defaults (task-type)**:

| Task type | Token budget |
|-----------|--------------|
| implement/add, update/modify | 10,000 |
| fix/debug, other | 15,000 |
| small feature | 20,000–30,000 |
| optimization | 15,000 |
| narrow review/documentation | 7,000–8,000 |
| architecture/large design | 40,000–50,000 |

Zero-budget or zero-files `load_context` is only acceptable for trivial/no-op tasks. See implement prompt for full checklist and zero-budget guardrails.

**AgentRole awareness**: The `load_context` tool automatically detects agent roles from task descriptions and uses role-aware context selection. Roles influence file prioritization and can inform budget recommendations. Context-effectiveness analysis (`analyze(target="context")`) tracks statistics by role and provides role-specific insights. The detected role is logged in session logs for analysis.

**Supported roles**:

- **feature** — Implementing new features or enhancements (default fallback). Default budget: 20k. Focus: activeContext.md, roadmap.md, systemPatterns.md, techContext.md.
- **quality** — Code quality, formatting, linting (keywords: format, lint, quality, pre-commit, ruff, black, mypy). Default budget: 15k. Focus: techContext.md, systemPatterns.md.
- **testing** — Writing/fixing tests, coverage work (keywords: test, tests, pytest, fixture, coverage). Default budget: 15k. Focus: techContext.md, systemPatterns.md, progress.md.
- **docs** — Documentation updates (keywords: docs, documentation, readme, guide, tutorial, markdown). Default budget: 10k. Focus: projectBrief.md, productContext.md, activeContext.md.
- **planning** — Creating/updating plans and roadmap work (keywords: plan, roadmap, design, phase, investigate). Default budget: 20k. Focus: roadmap.md, activeContext.md, projectBrief.md.
- **debugging** — Bug investigation and fix/debug flows (keywords: fix, bug, error, failure, exception, debug). Default budget: 15k. Focus: activeContext.md, systemPatterns.md, techContext.md.
- **review** — Code review and analysis (keywords: review, code review, pr, pull request). Default budget: 15k. Focus: activeContext.md, roadmap.md, projectBrief.md.

Roles are automatically inferred from task descriptions using keyword heuristics; explicit role parameters are optional. The role is logged in `load_context` session logs and used for role-aware statistics in context-effectiveness analysis. See `cortex.optimization.agent_roles` for role detection logic and profiles. Role-aware budget recommendations are available in `analyze(target="context")` insights via `role_budget_recommendations` and `role_recommendations`.

1. **Think before acting** — use the `think` tool: lightweight `think(thought="...")` for quick deliberation; full mode (pass thought_number, total_thoughts, next_thought_needed) for multi-step reasoning.
2. **Edit code** — use IDE tools (`Read`, `Write`, `Grep`, `Glob`, `LS`) for source files.
3. **Verify** — use Cortex quality/test tools, not raw shell commands.

## Execution Continuity

Agents must keep going until the task is done or genuinely blocked; do not pause just to narrate or wait for "ok, proceed".

- **Valid stops**:
  - Clarification needed about ambiguous or conflicting requirements.
  - Unrecoverable error or missing dependency outside the agent’s control.
  - The current task is complete and a final summary is ready.
  - Multiple viable approaches with meaningful trade-offs where the user must choose.

- **Invalid stops**:
  - After loading context or summarizing the roadmap/plan.
  - After Phase A or other intermediate phases pass in `/cortex/commit`.
  - After restating a plan, checklist, or next steps without new questions.
  - Waiting for the user to say "ok, proceed" (or similar) when no new information is required.

**Load context on the fix path (MANDATORY)**: When you encounter a problem and have to fix something (errors, test failures, quality issues, type/lint violations), you **must** load context and rules **before** making changes. Call `load_context(task_description="Fixing errors and issues", token_budget=15000)` and, when applicable, `rules(operation="get_relevant", task_description="...")` (or read key standards from the rules path if rules are disabled). Only after context and rules are loaded, proceed with fixes. This ensures fixes follow all project rules and guidelines. See the commit and implement prompts for concrete placement.

**Multi-agent coordination (Phase 58)**: When multiple Cursor tabs or agents work on the same project, use task locking to avoid duplicate work. `session(operation="start")` returns `concurrent_sessions` and `locked_tasks`. Use `claim_task_lock(task_title, role)` before starting work on a roadmap item; use `release_task_lock(task_title)` when done. Use `list_active_tasks()` and `check_task_available_lock(task_title)` to see what other agents are working on. Locks auto-expire after 2 hours. See the implement prompt for the full claim/release workflow.

## Commit pipeline (phase-based)

The commit workflow is organized into phases (see `docs/design/commit-pipeline-phases.md`). Use phase helpers so `/cortex/commit` orchestrates instead of micromanaging:

- **Phase A**: `execute_pre_commit_checks(phase="A", ...)` — fix_errors, format, markdown lint, type_check, quality, tests. If it fails, stop and use `/cortex/fix-tests` or `/cortex/fix-quality`; do not debug inline.
- **Phase B**: `execute_pre_commit_checks(phase="B")` — after memory-bank/roadmap steps, validates timestamps and sync. If it fails, use `/cortex/docs-sync` then retry.
- **Zero-errors policy**: Any check with errors blocks commit; no exceptions. Apply fixes (or use the helper commands above) before proceeding.
- **Doc-only when tooling unavailable**: For documentation-only sessions, if the environment cannot run the quality gate (e.g. ruff/black not in path, type_check certificate failure), the implement prompt may allow proceeding with a "run full pre-commit before commit" note; see [Troubleshooting: Quality gate unavailable](docs/guides/troubleshooting.md#quality-gate-unavailable-in-environment).

## Session Compaction (Phase 56)

**End-of-session compaction**: The `analyze.md` prompt automatically calls `compact_session()` at the end of each session to:

- Reduce `activeContext.md` size by summarizing older Completed Work sections (keeps current date full)
- Apply progressive summarization to `progress.md` (full entries for 7 days, weekly summaries for 7-30 days, monthly summaries for 30+ days)
- Create session handoff JSON (`.cortex/.cache/session/last_handoff.json`) for next session continuity
- Generate pre-compaction snapshots for rollback safety

**Session handoff**: The handoff JSON is automatically loaded by `session(operation="start")` at the beginning of the next session, providing:

- Completed tasks from the previous session
- In-progress tasks with notes
- Key decisions made
- Blockers and next actions

**Manual compaction**: Agents can call `compact_session(summary="...")` directly if needed, but typically this is handled automatically by the analyze prompt.

## Safety (non-negotiable)

- No destructive git (`reset --hard`, force-push); no commits/pushes without explicit user request.
- No hardcoded secrets; no sensitive data in logs or memory bank.
- Continue until done or genuinely blocked; do not stop after planning work you can do now.

## Learned User Preferences

- When the user says to add something to a plan instead of coding (e.g. "Don't code now. Add it in plan"), add it to the plan and do not implement immediately.
- When naming modules within a package, drop redundant package-name prefixes (e.g., in cortex.tools.linking use graph_operations not link_graph_operations).
- When adding or changing tools, prefer consolidation and removal of redundant or poorly used tools over adding new ones; tool count should decrease as functionality improves, and strengthen tool descriptions and governance tests so agents naturally use the intended entrypoints.
- When enforcing new coding standards (e.g., Literal→enum), update `.cortex/synapse/rules/python` so the rule is reflected there.
- When refactoring, briefly explain why the new approach is better, especially when the change is non-obvious.
- When consolidating tools or updating tool descriptions, follow `docs/guides/tool-description-altitude-rubric.md` (target score ≥4).
- Tool names must reflect the purpose of the tool.
- Use emojis in responses if applicable.
- Keep final summaries concise (typically at most four sentences) and avoid heavy code blocks there; use headings and bolded bullet labels per the markdown formatting guide.
- When a roadmap item is large, always make concrete partial progress in the current session (smallest meaningful subtask plus tests/quality) and update plans/status as PARTIAL instead of stopping with no changes.

## Learned Workspace Facts

- Do not edit files under `.venv` or other third-party package directories; apply coding standards (e.g. enums, types) only to project source code.
- Respect the project's defined structure; do not introduce new top-level directories or concepts (e.g., `scripts`) that deviate from it; avoid workflow or automation artifacts that pollute the project layout.
- When tests need cursor/agent paths and project_root is the repo root, use a session-scoped temp directory instead of creating `_cursor` in the workspace.
- Archived plans must live under `.cortex/plans/archive` (not `.cortex/archived/plans`) so completed plans stay in the canonical archive tree.

## Cursor Cloud specific instructions

### Prerequisites

The VM update script handles: `uv sync --extra dev` (which also installs the `rumdl` CLI), and `git submodule update --init --recursive`. Python 3.13+ and `uv` must be pre-installed as system dependencies (the update script does not install them).

### Running the Cortex MCP server

- Default transport is **stdio** (reads JSON-RPC from stdin, writes to stdout): `uv run cortex`
- For HTTP/SSE testing: `CORTEX_MCP_TRANSPORT=sse uv run cortex` (starts on port 8000 by default)
- The server is self-contained with no database or external API dependencies; all state is filesystem-based (`.cortex/` directory)

### Development commands

| Task | Command |
|------|---------|
| Install deps | `uv sync --extra dev` |
| Lint (ruff) | `.venv/bin/ruff check src/ tests/` |
| Format check | `.venv/bin/black --check .` |
| Type check | `uv run pyright src/ tests/` |
| Tests | `uv run pytest tests/ -q` |
| All checks | `make check` (note: Makefile uses `gtimeout` which may not exist on Linux; use commands above directly) |

### Gotchas

- `make check` runs format + lint + typecheck + test. All targets use `.venv/bin/` paths and work cross-platform.
- The git submodule `.cortex/synapse` must be initialized before running pre-commit hooks or scripts that reference `.cortex/synapse/scripts/python/`.
- All tests pass. Run with `uv run pytest tests/ -q`.
- `uv sync --extra dev` installs both the `[project.optional-dependencies] dev` extras (pytest, etc.) and the `[dependency-groups] dev` group (black, ruff, pyright, detect-secrets).
