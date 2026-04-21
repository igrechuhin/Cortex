# AGENTS

Workspace-wide rules for all IDE/AI agents in this repository.

## Use Cortex MCP (MANDATORY)

This project has a **Cortex MCP server** that provides tools for everything agents need. **Always use Cortex MCP tools instead of reading files or running commands directly.**

### Tools (13 — write/execute operations)

| Tool | Purpose |
|------|---------|
| `manage_file()` | Memory bank read/write (zero-arg reads activeContext.md) |
| `plan()` | Plan create/list/get/complete/register/archive_completed |
| `update_memory_bank()` | Roadmap/progress/activeContext mutations |
| `session()` | Session start, orientation, compact |
| `run_quality_gate()` | Phase A quality checks and Step 12 final gate (zero-arg) |
| `autofix()` | Auto-fix lint/format/types/markdown (zero-arg) |
| `think()` | Reasoning scratchpad |
| `ingest()` | Stage raw external sources under memory-bank for `/cortex/ingest` |
| `run_docs_gate()` | Phase B docs validation (zero-arg) |
| `pipeline_handoff()` | Inter-phase state exchange (init/write/read/clear) |
| `write_artifact()` | Allowlisted skill JSON and Synapse rule artifact writes |
| `compress_memory_bank()` | Compress project CLAUDE.md and memory-bank markdown to reduce session tokens |
| `memory_wal()` | Memory-bank WAL read, anomaly hints, snapshot/restore |

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
| Quality fixes | `autofix()` | Run language-specific formatters/linters manually |
| Tests and pre-commit | `run_quality_gate()` | Run pytest/ruff/black/pyright directly |
| Quality pipeline reference | [docs/api/tools.md — zero-arg quality tools](docs/api/tools.md#commit-and-quality-pipeline-zero-arg-mcp-tools) | Legacy parameterized pre-commit tools or job polling when the bridge strips args |
| Memory bank, roadmap, plans | `manage_file()`, `plan()`, `update_memory_bank()` | Edit `.cortex/` files directly |
| Project structure, paths | `cortex://structure` resource | Hardcode `.cortex/` paths |

**Tools vs Resources:** Use resources (`cortex://` URIs) for read-only operations. Use tools for writes and actions. All tools and resources are zero-arg safe (Cursor's MCP bridge strips args). See [docs/api/tools.md](docs/api/tools.md) for details.

### MCP unavailable: read-only audit fallback

MCP-first operation is mandatory for normal work. In **constrained or broken MCP environments** (no tools listed, repeated connection errors, client cannot start `uv run cortex`), agents may still perform a **read-only audit** if the scope and boundaries below are respected. Full procedure: [Troubleshooting — MCP unavailable: read-only audits](docs/guides/troubleshooting.md#mcp-unavailable-read-only-audits).

**Connectivity preflight (before treating MCP as down)**:

1. Confirm the Cortex server process can start: from repo root, `uv run cortex` (or your configured MCP command) and check client logs for a clean Initialize handshake.
2. In the client, verify tools/resources appear (not "0 tools") and optionally fetch `cortex://health/connection` when resources work.
3. If the failure is mid-session (e.g. `MCP error -32000: Connection closed`), retry once, then follow [MCP error -32000](docs/guides/troubleshooting.md#issue-mcp-error-32000-connection-closed) before declaring MCP unavailable.

**Allowed in read-only fallback (audits only)**:

- Read and analyze repository files with normal IDE tools (`Read`, `Grep`, `Glob`, terminal **read-only** commands such as `git status`, `git diff`, viewing logs).
- Produce findings, diffs, or review notes for a human or for a later MCP-enabled session.
- Load coding standards from checked-in docs that are already in the tree (e.g. `AGENTS.md`, `CLAUDE.md`) when `cortex://rules` is unreachable — **do not** bypass Synapse or `.cortex/synapse/rules/` policy by inventing standards; cite only what you can read from the repo.

**Prohibited in read-only fallback (unsafe without MCP)**:

- Any **stateful Memory Bank or pipeline writes**: `manage_file()`, `update_memory_bank()`, `plan()` mutations, `pipeline_handoff()` writes, `session(operation="compact")`, or **direct edits** under `.cortex/memory-bank/`, `.cortex/.session/`, or plan files to simulate compound-engineering updates.
- Invoking **implement** or **commit** pipelines as if Phase A/B passed when quality or docs gates did not run via MCP (or documented shell parity) in that environment.
- Claiming roadmap, progress, or validation sync without `run_docs_gate()` / `cortex://validation` in a healthy MCP session.

**After the audit**: Record in the deliverable that the session ran **without Cortex MCP** and list what was read-only vs blocked. Restore MCP (see troubleshooting runbook), then re-run gated workflows.

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

**Load context on the fix path (MANDATORY)**: When you encounter a problem and have to fix something (errors, test failures, quality issues, type/lint violations), you **must** load context and rules **before** making changes. Read `cortex://context` and `cortex://rules` resources. Only after context and rules are loaded, proceed with fixes. This ensures fixes follow all project rules and guidelines. See the commit and do prompts for concrete placement.

## Pipeline Architecture (simplified for reliability)

All pipelines (commit, do) run **inline** in the orchestrator — no subagents for commit phases, and only `implement-code` uses a subagent (for context isolation during heavy coding). This eliminates concurrent MCP access issues with Cursor.

**Zero-arg tools**: All MCP tools work with empty `{}` arguments (Cursor's MCP bridge strips args). Tools read config from session files or use sensible defaults. Key zero-arg tools:

- `run_quality_gate()` — Phase A quality gate and Step 12 final gate (write `{"force_fresh": true, "test_timeout": 600}` via `pipeline_handoff` first for Step 12)
- `run_docs_gate()` — Phase B docs validation
- `autofix()` — Auto-fix formatting/linting/types/markdown

**Pipeline state**: `pipeline_handoff(operation="write|read|init|clear", pipeline="...", phase="...")` exchanges structured JSON via `.cortex/.session/` files. Supports resumability after context compression.

## Commit pipeline

All phases run inline. Use zero-arg tools — do NOT use legacy pre-commit tools that require explicit phase/check arguments or async job polling (Cursor strips their args). See [docs/api/tools.md](docs/api/tools.md#deprecated-agent-entrypoints-legacy-names) for names to avoid.

- **Phase A**: `run_quality_gate()` — runs all quality checks end-to-end
- **Phase B**: `run_docs_gate()` — validates timestamps and sync
- **Step 12**: `pipeline_handoff(write, checks, {"force_fresh": true, "test_timeout": 600})` then `run_quality_gate()` — final gate with cache clear
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
- When enforcing new coding standards (e.g., Literal→enum, `| None` instead of `Optional`) or introducing repeated canonical layout tokens (such as wiki filenames), update `.cortex/synapse/rules/python` so the rule is reflected there and prefer enums or module constants over scattered string literals; internal tool dispatch and plan routing request models should use enums for operation discriminators, not raw strings.
- When fixing private/public access issues, prefer making the original symbol public (rename `_name` → `name` and update call sites) instead of adding public alias shims like `name = _name`. When a handoff or validation key is shown in prompts or other agent-visible text, prefer renaming away from a leading underscore (and updating allowlists) rather than exposing `_prefixed` identifiers in user-facing surfaces.
- Prompts must be language agnostic; avoid language- or tool-specific identifiers in prompt instructions (e.g. specific typechecker rule names).
- Treat overloaded terms (e.g. "clean") as prompt-specific; do not assume commit-pipeline git-clean semantics when a prompt defines issue-clean or workflow-clean semantics.
- When refactoring or bulk-simplifying prompts and docs, briefly explain why the change helps when it is non-obvious; re-check that sentence meaning and markdown markers (including **bold** labels and inline code) remain correct after edits.
- Prefer scan-friendly emoji status markers (✅/⚠️/❌) in prompts and summaries for success/warn/error; keep final summaries concise (typically at most four sentences), avoid heavy code blocks there, and use headings and bolded bullet labels per the markdown formatting guide. For heartbeat or liveness output, avoid opaque N/K-style counters when they convey no clear meaning; prefer a simple cumulative indicator (e.g. one dot per ping).
- When a roadmap item is large, always make concrete partial progress in the current session (smallest meaningful subtask plus tests/quality) and update plans/status as PARTIAL instead of stopping with no changes. For reflection, quality-gate adjuncts, and similar cross-cutting checks, prefer language-parameterized constants and language-specific checklists over Python-only naming or a single generic list.
- When tests, typecheck, or CI are not green, stop further product development and focus on restoring a fully green state before taking on new scope.
- The user explicitly does not want offline setup/bootstrap support; do not add `*-offline` commands, offline onboarding flows, or wheelhouse-based install guidance unless the user requests it again.

## Learned Workspace Facts

- Do not edit files under `.venv` or other third-party package directories; apply coding standards (e.g. enums, types) only to project source code. Prefer `python3` over `python` in shell commands when the `python` shim may point to a legacy interpreter.
- Append-only logs under `.cortex/memory-bank/` (e.g. `log.md`) should stay bounded; avoid unbounded append-only growth (rotation, caps, or archival as appropriate).
- Respect the project's defined structure; do not introduce new top-level directories or concepts (e.g., `scripts`) that deviate from it; avoid workflow or automation artifacts that pollute the project layout. Project wiki files belong under `.cortex/wiki/` (for example `schema.md`), not ad hoc sibling paths directly under `.cortex/`; when a wiki tree exists, selected artifacts can also be mirrored under `.cortex/wiki/analyses/` alongside memory-bank destinations.
- When tests need cursor/agent paths and project_root is the repo root, use a session-scoped temp directory instead of creating `_cursor` in the workspace.
- Archived plans must live under `.cortex/plans/archive` (not `.cortex/archived/plans`) so completed plans stay in the canonical archive tree. Step-mode planning may leave interim `draft-<slug>.md` files under `.cortex/plans/` (with a `CORTEX_STEP_PLAN_STATE` footer) until they are finalized to `<slug>.md`; remove session-only draft or scratch plan files after local MCP or planning-mode tests so `.cortex/plans/` does not accumulate throwaway artifacts. `.cursor/synapse` is a symlink to `.cortex/synapse`; Synapse prompts edited via either path refer to the same submodule files.
- When editing `roadmap.md` pending bullets, avoid bare dotted Python filenames, backticked paths such as `pre_commit_foo`/`pre_commit_bar`, and the root Node manifest name written as one token; the roadmap file-reference scanner can treat those as real paths and fail `roadmap_sync`. When a bullet should point at a real plan file, end the line with `Plan: .cortex/plans/<file>.md` (session tooling parses this). `plan(operation="register")` only accepts `section` values `blockers`, `active_work`, `future`, or `pending`.
- Synapse Python standards forbid `from typing import TYPE_CHECKING` and `if TYPE_CHECKING:` conditional imports; use normal imports (including under `tests/`) instead of that pattern.
- Phase A `run_quality_gate()` can reuse cached fingerprints so typecheck output may not match the current working tree; if pyright errors look stale versus local `pyright`, write `{"force_fresh": true}` via `pipeline_handoff(write, checks, ...)` then call `run_quality_gate()` once before treating results as ground truth. The gate still runs pyright over configured roots including `tests/`, so unrelated `tests/` diagnostics can keep the quality target red even when `src/` is clean. Always-green `main` triage: treat new reds as caused by the current change first (including under `tests/`) until you confirm a flake, environment, or rare upstream drift—not as silent legacy debt on `main`.
- The docs gate `roadmap_progress_consistency` check fails when `progress.md` contains any `PARTIAL` line but `roadmap.md` has no `PENDING` backlog bullet; keep at least one real `PENDING` item while unfinished work remains in progress, or resolve the PARTIAL entries. Roadmap backlog lines often use typographic dashes (em/en) before `PENDING`; matchers and validators must accept those characters, not only ASCII hyphens.
- When resolving Cortex, Synapse, repo-root, or `.cortex/wiki/` paths in Python tools, use the shared path resolver (`cortex.core.path_resolver` and related helpers) instead of hardcoded filesystem strings. Keep session-goal marker files such as `session-goal.md` under `.cortex/.session/` rather than directly under `.cortex/`.
- After changing validation or other Python modules the Cortex MCP server loads from the repo, restart the MCP server so `run_docs_gate` and in-process checks match the working tree; a long-running process can otherwise disagree with local `make check` results. If wiki auto-bootstrap is enabled but `.cortex/wiki` stays empty after restart, treat missing server-side wiki initialization as the first suspect before hand-creating files in a session.
- Local environment context artifacts under `.cortex/memory-bank` must be auto-created/updated and validated at startup, and default values must be derived from the current project/environment rather than copied from another project (e.g., TradeWing-specific assumptions).

## Cursor Cloud specific instructions

### Prerequisites

The VM update script handles: `uv sync --extra dev` (which also installs the `rumdl` CLI), and `git submodule update --init --recursive`. Python 3.13+ and `uv` must be pre-installed as system dependencies (the update script does not install them).

If dependency download fails (network, proxy, or SSL), use the preflight and triage flow in [Dependency and network verification](docs/guides/troubleshooting.md#dependency-and-network-verification) before treating failures as test regressions.

### Running the Cortex MCP server

- Default transport is **stdio** (reads JSON-RPC from stdin, writes to stdout): `uv run cortex`
- **Synapse submodule on startup**: From the detected project root, the server runs a best-effort, **non-fatal** `git pull --ff-only origin main` inside `.cortex/synapse` so Synapse matches remote `main` without non-fast-forward merges. If the submodule has local changes, they are **stashed** before the pull and **restored** afterward. It is **skipped** if the root is not a git checkout or if you set `CORTEX_SKIP_SYNAPSE_UPDATE=1`. Git errors or timeouts are logged and startup continues. If the submodule is missing or never initialized, run `git submodule update --init --recursive` from repo root first (same as CI/bootstrap scripts).
- For HTTP/SSE testing: `CORTEX_MCP_TRANSPORT=sse uv run cortex` (starts on port 8000 by default)
- The server is self-contained with no database or external API dependencies; all state is filesystem-based (`.cortex/` directory)

### Development commands

| Task | Command |
|------|---------|
| Install deps | `uv sync --extra dev` |
| Lint (ruff) | `.venv/bin/ruff check src/ tests/` |
| Format check | `.venv/bin/black --check src/ tests/` |
| Apply format / fixes | `make fix` (Black + Ruff import sort + Ruff `--fix` on `src/` and `tests/`) |
| Type check | `uv run pyright src/ tests/` |
| Tests (local, fast) | `make test` or `uv run python -m pytest tests/ -m "not slow" -n auto -q` |
| All checks (non-mutating) | `make check` (note: Makefile uses `gtimeout` which may not exist on Linux; use commands above directly) |
| CI parity (incl. pytest + coverage) | `make check-ci-parity` (requires `uv` on `PATH`; see README / troubleshooting) |

### Gotchas

- `make check` is **non-mutating** (Black `--check`, Ruff lint, typecheck, fast tests). Use `make fix` to apply formatting and auto-fixable lint. `make check-ci-parity` runs more of the same steps as [.github/workflows/quality.yml](.github/workflows/quality.yml). Targets use `.venv/bin/` paths where noted and work cross-platform.
- The git submodule `.cortex/synapse` must be initialized before running pre-commit hooks or scripts that reference `.cortex/synapse/scripts/python/`.
- All tests pass. Prefer `make test` (parallel, excludes `slow`) or `make check-ci-parity` before merge; avoid serial `pytest tests/` on the full tree (~6.6k tests).
- `uv sync --extra dev` installs both the `[project.optional-dependencies] dev` extras (pytest, etc.) and the `[dependency-groups] dev` group (black, ruff, pyright, detect-secrets).
