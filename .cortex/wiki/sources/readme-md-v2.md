# Cortex - AI Memory & Context Management Server

Powered by [Enlighter](https://enlightby.ai) and [Hyperskill](https://hyperskill.org).

Learn how to setup and use Memory Bank directly in Cursor: <http://enlightby.ai/projects/37>

[![smithery badge](https://smithery.ai/badge/@igrechuhin/cortex)](https://smithery.ai/server/@igrechuhin/cortex)

[![Cortex MCP server](https://glama.ai/mcp/servers/@igrechuhin/cortex/badge)](https://glama.ai/mcp/servers/@igrechuhin/cortex)

## What it's for

Cortex is an MCP server that helps build and maintain a project Memory Bank so AI assistants always have up-to-date context, plans, and rules.
It follows the [Memory Bank pattern](https://docs.cline.bot/improving-your-prompting-skills/cline-memory-bank) and keeps your `.cortex/` files (roadmap, activeContext, progress, rules) in sync so agents can reliably run a **plan → do → commit** loop instead of ad-hoc edits.
Use Cortex when you want reproducible, high-quality AI-driven development that survives restarts, editor changes, and long-running projects.

## How to use it

1. **Install prerequisites**: Python 3.13+ and the Rust-based `rumdl` Markdown linter (installed via the Python dev environment; see [Prerequisites](#prerequisites)).
2. **Run the server**: Add the config snippet from [Running the Server](#running-the-server) to your `mcp.json` (most users pick **uvx**).
3. **Start with the plan → do → commit loop** (see below).
   In your IDE/assistant, ask the agent to orchestrate these commands:
   - Start a session (get an orientation brief)
   - Load task-specific context
   - Follow the **plan → do → commit** loop

For new projects, use the **initialize** prompt to create the Memory Bank and `.cortex/` structure.

### Plan → do → commit

This is the daily workflow:

| Step | What happens |
|------|--------------|
| **Plan** | Create or refine plans in `.cortex/plans/` and register them in `roadmap.md`. |
| **Do** | Apply the next PENDING roadmap step with tests and quality checks. |
| **Commit** | Run the full pre-commit pipeline and push only healthy commits. |

See [docs/prompts](docs/prompts/README.md) for setup/migration prompt details.

If Cortex MCP cannot be reached in your environment, you can still do a **read-only audit** of the repo under the boundaries in [AGENTS.md](AGENTS.md) (**MCP unavailable: read-only audit fallback**) and the runbook [MCP unavailable: read-only audits](docs/guides/troubleshooting.md#mcp-unavailable-read-only-audits).

## Features

- **Memory Bank** — structured project context that persists across sessions
- **Session & Context** — orientation briefs, token-budgeted context loading, end-of-session compaction
- **Validation & Quality** — schema validation, lint/format/type auto-fix, pre-commit checks
- **Plans & Roadmap** — plan lifecycle management tied to a roadmap
- **DRY Linking** — transclusion engine to embed content without duplication
- **Shared Rules (Synapse)** — cross-project rule and prompt sharing via Git submodule
- **Refactoring** — pattern analysis, suggestions, safe execution with rollback
- **Token Optimization** — context summarization and relevance scoring

## Prerequisites

- **Python 3.13+**
- **rumdl** — Markdown linter/formatter installed into the Python environment (for example via `uv sync --extra dev`, which adds the `rumdl` CLI to `.venv/bin/rumdl`)

## Running the Server

### With uvx (recommended)

```json
{
  "mcpServers": {
    "cortex": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/igrechuhin/Cortex.git",
        "cortex"
      ]
    }
  }
}
```

**First run / IDE timeouts:** `uvx --from git+…` must resolve GitHub `HEAD`, download dependencies, and build the package into uv’s cache. That can take minutes on a cold machine or right after `uv cache clean`. Some MCP clients time out during the first Initialize if the server is not ready yet. **Pre-warm once in a terminal** (same command you use in `mcp.json`), then start or reload the MCP client:

```bash
uvx --from git+https://github.com/igrechuhin/Cortex.git cortex --help
```

Details: [Getting started — Stable MCP setup](docs/getting-started.md#stable-mcp-setup-recommended), [Troubleshooting — uvx cold start](docs/guides/troubleshooting.md#issue-uvx-cold-start-mcp-timeout).

### With Smithery

```json
{
  "mcpServers": {
    "cortex": {
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@igrechuhin/cortex",
        "--key",
        "your_smithery_key"
      ]
    }
  }
}
```

### With Docker

```json
{
  "mcpServers": {
    "cortex": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "19283744/cortex:latest"
      ]
    }
  }
}
```

### Manually

Clone the repository, then:

```bash
bash scripts/bootstrap.sh
```

Optionally initialize the Synapse submodule for shared rules:

```bash
git submodule update --init --recursive
```

Add to your `mcp.json`:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "uv",
      "args": ["run", "cortex"]
    }
  }
}
```

## Developer commands

For local development, use these Make targets (after running `bash scripts/bootstrap.sh` once to create the virtualenv and install dependencies):

- **Restricted network / offline**: If `uv sync` or installs fail (proxy, air-gap, SSL), use [Offline and network-restricted verification](docs/guides/troubleshooting.md#offline-and-network-restricted-verification) to bootstrap a test-running environment and triage fetch vs test failures.
- **`make preflight`**: Probe PyPI or `UV_INDEX_URL` before `uv sync` when triaging connectivity; see [Offline bootstrap and preflight](docs/offline-bootstrap-preflight.md).

### Restricted-network / offline setup

1. Run `make preflight-offline` (or `bash scripts/preflight.sh --offline`) from the repo root to verify `uv`, `git`, `python3`, `uv.lock`, and a local `uv_build` wheel (cache, `vendor/`, or `wheelhouse/`).
2. If `uv_build` is missing: `uv pip download uv-build --dest vendor/ && uv pip install --no-index --find-links vendor/ uv-build` (or populate `wheelhouse/` as in [contributing — offline](docs/development/contributing.md#offline--restricted-network-setup)).
3. Install deps without the index: `uv sync --offline --frozen` (with `UV_NO_INDEX=1` and `UV_FIND_LINKS` pointing at your wheelhouse when using `make bootstrap-offline`).
4. Run tests offline: `uv run --offline pytest tests/ -q`. Long-form triage: [Offline and network-restricted verification](docs/guides/troubleshooting.md#offline-and-network-restricted-verification).

- **`make bootstrap`**: Run `scripts/bootstrap.sh` to create or update the `.venv` and install all dependencies.
- **`make check`**: Non-mutating local gate: verify Black on `src/` and `tests/`, Ruff lint, Pyright, then the fast test suite. Does not rewrite files; use `make fix` when checks fail for formatting or auto-fixable lint.
- **`make fix`**: Apply Black, Ruff import sorting (`I`), and Ruff `--fix` on `src/` and `tests/` (mutating).
- **`make check-ci-parity`**: Run a broader subset of the GitHub Actions [Code Quality](.github/workflows/quality.yml) workflow via `uv run` (synapse format/lint scripts, type checks, file/function limits, rumdl, pytest with coverage). Requires `uv` on your `PATH`. Still **not** identical to CI: spell check (`cspell`), the eval suite, Codecov, and health-check upload steps run only in Actions—see [Troubleshooting — Local make check vs CI](docs/guides/troubleshooting.md#local-make-check-vs-ci-parity).
- **`make test`**: Run the fast test suite (`pytest -q`) with timeouts.
- **`make test-full`**: Run the full test suite (including slower tests) with a longer timeout.
- **`make commit-check`**: Run the same checks as `make check` before using `/cortex/commit` in Cursor for the full commit pipeline. With Cortex MCP connected, Phase A / Step 12 use the zero-arg tools documented in [docs/api/tools.md](docs/api/tools.md#commit-and-quality-pipeline-zero-arg-mcp-tools).

## Key Tools

<!-- cortex-published-inventory: tools=12 resources=6 prompts-max=4 -->

Cortex exposes **12 MCP tools**, **6 static `cortex://` resources**, and **up to 4 setup prompts** (one always-on plus up to three configuration-dependent). Machine-readable inventory: [docs/_generated/tool-inventory.json](docs/_generated/tool-inventory.json) (must match `cortex.discovery.published_inventory`; CI enforces parity).

Published tools (canonical `TOOL_CATEGORIES` order — see [docs/api/tools.md](docs/api/tools.md#current-published-mcp-surface-canonical)):

| Tool | Purpose |
| ---- | ------- |
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

Read-only discovery uses **resources** (not in this table): `cortex://health/connection`, `cortex://structure`, `cortex://context`, `cortex://rules`, `cortex://validation`, `cortex://analysis`. Quick “do not” guidance: [AGENTS.md](AGENTS.md) quick reference.

## Prompts

Prompts are for setup and migration; for daily work use **plan → do → commit** tools.

| Situation | Prompt |
|-----------|--------|
| New project, no Memory Bank | `initialize` |
| Legacy Memory Bank under IDE `.cursor/` (`memory-bank/`) | `migrate` |
| Share rules across projects | `setup_synapse` |

Full prompt list: [docs/prompts](docs/prompts/README.md)

## Memory Bank Structure

The Memory Bank lives under `.cortex/` and works with any editor, LLM, or agent.

- `.cortex/memory-bank/` — core files: projectBrief, productContext, activeContext, systemPatterns, techContext, progress, roadmap
- `.cortex/plans/` — development plans linked to the roadmap
- `.cortex/synapse/` — shared rules and prompts (Git submodule)
- `.cortex/config/`, `.cortex/history/`, `.cortex/index.json` — configuration, history, and metadata

Legacy layouts are migrated by the `migrate` prompt; see [Getting started](docs/getting-started.md).

## Documentation

- [Getting started](docs/getting-started.md)
- [MCP Tools API](docs/api/tools.md)
- [Prompts](docs/prompts/README.md)
- [Troubleshooting](docs/guides/troubleshooting.md)
- [Advanced tool use](docs/guides/advanced-tool-use.md)
