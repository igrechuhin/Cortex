# TradeWing–Cortex Integration: Debug Context

**PURPOSE**: Load all context needed to investigate and fix a Cortex MCP integration problem reported for the TradeWing project. The user will describe the specific problem after this context is loaded.

## Status legend (scan-friendly)

- ✅ **Success** (passed / complete)
- ⚠️ **Warning** (non-blocking; proceed but report)
- ❌ **Error** (blocking; must fix before proceeding)
- ⛔ **Hard gate** (rule violation if skipped)

⛔ **CRITICAL**: Execute ALL steps AUTOMATICALLY. Do NOT pause or summarize. Move directly into the problem description after Step 5.

---

## Step 1: Load Cortex Server Context

Call `session()` for MCP health and orientation.

Then read both resources:

- `cortex://context` — Cortex server architecture, tools, resources
- `cortex://rules` — coding standards that apply to any fix

---

## Step 2: Load Cortex Source Structure

The Cortex MCP server lives at `/Users/i.grechukhin/Repo/Cortex/`.
GitHub: `https://github.com/igrechuhin/Cortex`

Key source paths relevant to external project integration:

| Path | Purpose |
|------|---------|
| `src/cortex/core/project_root_resolver.py` | Resolves external project root via MCP `roots/list`; cached per server lifetime |
| `src/cortex/setup/lazy_prompt_registration.py` | Defers prompt registration until first `list_prompts`; uses `resolve_project_root_async()` |
| `src/cortex/server.py` | MCP server entry point; hooks lazy prompt handler |
| `src/cortex/core/session_config.py` | Session config reader; resources read task/context from here |
| `src/cortex/tools/` | All MCP tool implementations |
| `src/cortex/setup/prompts.py` | Synapse prompt registration; `sync_cursor_agents()` |
| `.cortex/prompts/` | Project-specific prompts (this file lives here) |
| `.cortex/synapse/` | Synapse submodule — rules, agents, prompts |

Read the files relevant to the reported problem before proposing any fix.

---

## Step 3: Load TradeWing Project State

The external project lives at `/Users/i.grechukhin/Repo/TradeWing/`.
GitHub: `https://github.com/igrechuhin/TradeWing`

**Tech stack**: Swift 6.1, SwiftPM, macOS 15.5+, MLX, GRDB/SQLite, gRPC Swift 2.
**Language**: NOT Python. Cortex quality gate tools (`run_quality_gate`, `fix_quality_issues`) target Python — they do not apply to TradeWing source code.

Read the following to understand current TradeWing state:

1. `/Users/i.grechukhin/Repo/TradeWing/CLAUDE.md` — workflow, commands, build system
2. `/Users/i.grechukhin/Repo/TradeWing/.cortex/memory-bank/activeContext.md` — current work
3. `/Users/i.grechukhin/Repo/TradeWing/.cortex/memory-bank/roadmap.md` — active plans

Also note the integration plan that was created:
`/Users/i.grechukhin/Repo/TradeWing/.cortex/plans/cortex-integration.v1.plan.md`

---

## Step 4: Snapshot TradeWing `.cortex/` Layout

Use `Glob` on `/Users/i.grechukhin/Repo/TradeWing/.cortex/` to confirm what is present vs. missing.

Known integration facts (do not re-verify, just record):

- `.cortex/synapse/` — Synapse git submodule present
- `.cortex/memory-bank/` — 7 core files migrated; `projectBrief.md` uses camelCase B
- `.cortex/plans/` — plans migrated from the prior location
- `.cortex/index.corrupted` — **exists** (index was corrupted; blocks `manage_file` reads until repaired)
- Legacy links should point to `.cortex/` counterparts
- `.cortex/config/` — 3 config JSON files should exist (`validation.json`, `optimization.json`, `usage_tracking.json`)

Flag anything that diverges from the above as a new finding.

---

## Step 5: Understand the Root Resolver Behavior for External Projects

The Cortex server is launched by Cursor/Claude Code with CWD = home dir or Cortex repo dir, NOT TradeWing. The project root resolver (`project_root_resolver.py`) uses MCP `roots/list` to find the correct workspace root at runtime.

This is the most common source of integration failures:

- If `roots/list` returns Cortex repo instead of TradeWing → all memory bank reads go to wrong project
- If `roots/list` times out or fails → server falls back to CWD (wrong)
- The root is cached after first resolution — a bad first call poisons the whole session

Read `src/cortex/core/project_root_resolver.py` now to understand the current resolution logic and cache behavior.

---

## Step 6: Investigate and Fix the Reported Problem

The user will now describe the specific problem. Using the context loaded above:

1. Identify the root cause in Cortex source code or TradeWing config
2. Read all relevant source files before making any change
3. Apply a targeted fix following `cortex://rules`
4. If the fix touches Cortex source: run `run_quality_gate()` after the change
5. If the fix requires a new Cortex feature or non-trivial change: create a plan with `plan(operation="create", title="...", content="...")` and register it in the roadmap

Do NOT make changes to TradeWing source files (`.swift`). Changes go to:

- Cortex server source (`/Users/i.grechukhin/Repo/Cortex/src/`)
- TradeWing `.cortex/` config/memory-bank files (via `manage_file()`)
- This prompt file if the context needs updating

---

## Notes

- **Fix path rule**: load `cortex://rules` before making any code change (already done in Step 1)
- **No auto-commit**: never commit to either repo without explicit user request
- **Cursor strips args**: all MCP tools work with `{}`. Pass explicit args when needed; fall back to `Write` if tool rejects them
- **TradeWing quality gate**: `run_quality_gate()` runs Python checks — do not run it against TradeWing Swift source
- **Index repair**: if `.cortex/index.corrupted` is still present, delete it and `index.json` from TradeWing `.cortex/`, then call `session()` to trigger rebuild before testing memory bank reads
