# Cortex - AI Memory & Context Management Server

Powered by [Enlighter](https://enlightby.ai) and [Hyperskill](https://hyperskill.org).

Learn how to setup and use Memory Bank directly in Cursor: <http://enlightby.ai/projects/37>

[![smithery badge](https://smithery.ai/badge/@igrechuhin/cortex)](https://smithery.ai/server/@igrechuhin/cortex)

[![Cortex MCP server](https://glama.ai/mcp/servers/@igrechuhin/cortex/badge)](https://glama.ai/mcp/servers/@igrechuhin/cortex)

## What it's for

Cortex is an MCP server that helps build and maintain a project Memory Bank so AI assistants always have up-to-date context, plans, and rules.
It follows the [Memory Bank pattern](https://docs.cline.bot/improving-your-prompting-skills/cline-memory-bank) and keeps your `.cortex/` files (roadmap, activeContext, progress, rules) in sync so agents can reliably run a **plan → implement → commit** loop instead of ad-hoc edits.
Use Cortex when you want reproducible, high-quality AI-driven development that survives restarts, editor changes, and long-running projects.

## How to use it

1. **Install prerequisites**: Python 3.13+ and Node.js with `markdownlint-cli2` (see [Prerequisites](#prerequisites)).
2. **Run the server**: Add the config snippet from [Running the Server](#running-the-server) to your `mcp.json` (most users pick **uvx**).
3. **Start with the plan → implement → commit loop** (see below).
   In your IDE/assistant, ask the agent to orchestrate these commands:
   - Start a session (get an orientation brief)
   - Load task-specific context
   - Follow the **plan → implement → commit** loop

For new projects, use the **initialize** prompt to create the Memory Bank and `.cortex/` structure.

### Plan → implement → commit

This is the daily workflow:

| Step | What happens |
|------|--------------|
| **Plan** | Create or refine plans in `.cortex/plans/` and register them in `roadmap.md`. |
| **Implement** | Apply the next PENDING roadmap step with tests and quality checks. |
| **Commit** | Run the full pre-commit pipeline and push only healthy commits. |

See [docs/prompts](docs/prompts/README.md) for the implement and commit prompt details.

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
- **Node.js and npm** — for `markdownlint-cli2` (`npm install -g markdownlint-cli2`)

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
npm install -g markdownlint-cli2
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

## Key Tools

Cortex exposes **27 public MCP tools**. The most important ones by workflow:

| Workflow | Tools |
|----------|-------|
| **Session** | `session_start`, `load_context`, `compact_session` |
| **Memory Bank** | `manage_file`, `query_memory_bank` |
| **Quality** | `validate`, `execute_pre_commit_checks`, `fix_quality_issues` |
| **Plans** | `plan`, `roadmap`, `register_plan_in_roadmap` |
| **Rules** | `rules`, `get_synapse_rules`, `synapse` |
| **Analysis** | `analyze`, `think` |

Full reference: [docs/api/tools.md](docs/api/tools.md) | Discovery: `search_tools(query="...")`

## Prompts

Prompts are for setup and migration; for daily work use **plan → implement → commit** tools.

| Situation | Prompt |
|-----------|--------|
| New project, no Memory Bank | `initialize` |
| Legacy `.cursor/memory-bank/` format | `migrate` |
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
