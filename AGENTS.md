# AGENTS

Workspace-wide rules for all IDE/AI agents in this repository.

## Use Cortex MCP (MANDATORY)

This project has a **Cortex MCP server** that provides tools for everything agents need. **Always use Cortex MCP tools instead of reading files or running commands directly.**

### Tools (10 — write/execute operations)

| Tool | Purpose |
|------|---------|
| `session()` | Session start, orientation, compact |
| `manage_file()` | Memory bank read/write (zero-arg reads activeContext.md) |
| `plan()` | Plan create/list/get/complete/register/archive_completed |
| `update_memory_bank()` | Roadmap/progress/activeContext mutations |
| `pipeline_handoff()` | Inter-phase state exchange (init/write/read/clear) |
| `run_quality_gate()` | Phase A quality checks (zero-arg) |
| `run_quality_gate_fresh()` | Step 12 final gate (zero-arg, clears cache) |
| `run_docs_gate()` | Phase B docs validation (zero-arg) |
| `fix_quality_issues()` | Auto-fix lint/format/types/markdown (zero-arg) |
| `think()` | Reasoning scratchpad |

### Resources (6 — read-only, all static/zero-arg)

| URI | Purpose |
|-----|---------|
| `cortex://health/connection` | Health check |
| `cortex://structure` | Path/structure discovery |
| `cortex://context` | Context loading (task from session config) |
| `cortex://rules` | Coding standards (task from session config) |
| `cortex://validation` | Timestamps/roadmap sync validation |
| `cortex://analysis` | End-of-session analysis (target from session config) |

### Quick reference

| Need | Use | Do NOT |
|---|---|---|
| Project context | `cortex://context` resource or `manage_file()` | Read `.cortex/memory-bank/` files directly |
| Coding rules, standards | `cortex://rules` resource | Read `.cortex/rules/` or `.cortex/synapse/` directly |
| Type annotations | Read rules via `cortex://rules` before coding; Pydantic models for internal data; `object` only for MCP tool params | Use `Any` type; skip loading rules |
| Markdown formatting | [docs/guides/markdown-formatting.md](docs/guides/markdown-formatting.md) | Use bold for section titles (use `#`/`##`/`###` instead) |
| Quality fixes | `fix_quality_issues()` | Run language-specific formatters/linters manually |
| Tests and pre-commit | `run_quality_gate()` | Run pytest/ruff/black/pyright directly |
| Memory bank, roadmap, plans | `manage_file()`, `plan()`, `update_memory_bank()` | Edit `.cortex/` files directly |
| Project structure, paths | `cortex://structure` resource | Hardcode `.cortex/` paths |

**Tools vs Resources:** Use resources (`cortex://` URIs) for read-only operations. Use tools for writes and actions. All tools and resources are zero-arg safe (Cursor's MCP bridge strips args). See [docs/api/tools.md](docs/api/tools.md) for details.

**Note for AI agents**: Do not add detailed workflow guides to `AGENTS.md` or `CLAUDE.md`; fetch commit/implement/fix-path behavior from Cortex MCP (Synapse prompts, rules, and memory bank).

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

1. **Get session orientation** (recommended) — call `session()` for orientation (< 1000 tokens). Returns current focus, next work item, health check, git status, and suggestions.
2. **Scope the task** — restate the user's goal.
3. **Load context and rules** — read `cortex://context` resource for project context and `cortex://rules` for coding standards. Both are zero-arg (read task from session config). **Pattern**: `session()` → read resources → work.
4. **Think before acting** — use `think()` for quick deliberation or multi-step reasoning.
5. **Edit code** — use IDE tools (`Read`, `Write`, `Grep`, `Glob`, `LS`) for source files.
6. **Verify** — use `run_quality_gate()` (zero-arg), not raw shell commands.

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

**Load context on the fix path (MANDATORY)**: When you encounter a problem and have to fix something (errors, test failures, quality issues, type/lint violations), you **must** load context and rules **before** making changes. Read `cortex://context` and `cortex://rules` resources. Only after context and rules are loaded, proceed with fixes. This ensures fixes follow all project rules and guidelines. See the commit and implement prompts for concrete placement.

## Pipeline Architecture (simplified for reliability)

All pipelines (commit, implement) run **inline** in the orchestrator — no subagents for commit phases, and only `implement-code` uses a subagent (for context isolation during heavy coding). This eliminates concurrent MCP access issues with Cursor.

**Zero-arg tools**: All MCP tools work with empty `{}` arguments (Cursor's MCP bridge strips args). Tools read config from session files or use sensible defaults. Key zero-arg tools:

- `run_quality_gate()` — Phase A quality gate
- `run_quality_gate_fresh()` — Phase A with cache clear (Step 12)
- `run_docs_gate()` — Phase B docs validation
- `fix_quality_issues()` — Auto-fix formatting/linting/types/markdown

**Pipeline state**: `pipeline_handoff(operation="write|read|init|clear", pipeline="...", phase="...")` exchanges structured JSON via `.cortex/.session/` files. Supports resumability after context compression.

## Commit pipeline

All phases run inline. Use zero-arg tools — do NOT use `execute_pre_commit_checks(phase=...)` or `start_quality_job + get_quality_job_status` (Cursor strips their args).

- **Phase A**: `run_quality_gate()` — runs all quality checks end-to-end
- **Phase B**: `run_docs_gate()` — validates timestamps and sync
- **Step 12**: `run_quality_gate_fresh()` — final gate with cache clear
- **Zero-errors policy**: Any check with errors blocks commit
- **Doc-only when tooling unavailable**: See [Troubleshooting](docs/guides/troubleshooting.md#quality-gate-unavailable-in-environment).

## Session Compaction (Phase 56)

**End-of-session compaction**: The `analyze.md` prompt automatically calls `session(operation="compact")` at the end of each session to:

- Reduce `activeContext.md` size by summarizing older Completed Work sections (keeps current date full)
- Apply progressive summarization to `progress.md` (full entries for 7 days, weekly summaries for 7-30 days, monthly summaries for 30+ days)
- Create session handoff JSON (`.cortex/.cache/session/last_handoff.json`) for next session continuity
- Generate pre-compaction snapshots for rollback safety

**Session handoff**: The handoff JSON is automatically loaded by `session(operation="start")` at the beginning of the next session, providing:

- Completed tasks from the previous session
- In-progress tasks with notes
- Key decisions made
- Blockers and next actions

**Manual compaction**: Agents can call `session(operation="compact")` directly if needed, but typically this is handled automatically by the analyze prompt.

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
- Use emojis in responses when they increase info density; otherwise avoid them.
- If you explicitly request emojis for a given response, prioritize that request over stored preferences.
- Keep final summaries concise (typically at most four sentences) and avoid heavy code blocks there; use headings and bolded bullet labels per the markdown formatting guide.
- When a roadmap item is large, always make concrete partial progress in the current session (smallest meaningful subtask plus tests/quality) and update plans/status as PARTIAL instead of stopping with no changes.
- For continual-learning updates, process transcripts incrementally via `.cursor/hooks/state/continual-learning-index.json`, update matching `AGENTS.md` bullets in place (not append-only), and return exactly `No high-signal memory updates.` when no meaningful changes exist.

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
