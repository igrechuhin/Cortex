# Prompts Split — Architecture Design

**Status:** Current (implemented in `src/cortex/tools/synapse/`)
**Last updated:** 2026-03-23

## Overview

The `prompts.py` facade module loads and registers MCP prompts at import time.
The implementation was split into four focused modules to stay within the 400-line
file limit and to separate distinct concerns.

## Module Responsibilities

```text
src/cortex/tools/synapse/
├── prompts.py              # Facade + import-time registration entry point
├── prompts_paths.py        # Path discovery and file I/O
├── prompts_content.py      # Static data: icons, tool names, field constants
├── prompts_registration.py # MCP registration logic (create, log, dispatch)
└── prompts_agents.py       # Claude agent file sync
```

### `prompts.py` — Facade

- Re-exports public symbols from the four modules under a single namespace.
- Provides thin wrappers (e.g. `process_prompt_info`, `register_prompts_from_path`)
  that inject the `_facade()` module reference so the registration functions can
  store state in the calling module's `__dict__`.
- Calls `register_synapse_prompts()` and `sync_claude_agents()` at import time.

### `prompts_paths.py` — Path discovery and I/O

Responsibilities:

- `get_prompts_paths()`: walks CWD and the module-anchor tree to find all
  `.cortex/synapse/prompts/` and `.cortex/prompts/` directories.
- `get_synapse_prompts_path()`: convenience wrapper that prefers the
  synapse-shaped root; falls back to `paths[0]` when no synapse root exists.
- `load_prompts_manifest(path)`: loads `prompts-manifest.json`; returns `None`
  and logs at DEBUG on any `(OSError, json.JSONDecodeError, UnicodeDecodeError,
  ValueError)` — intentionally silent to allow optional manifests.
- `load_prompt_content(path, category, filename)`: reads a prompt file with full
  path-traversal protection (absolute-path rejection, `..` rejection,
  `resolve()` + `relative_to(base_dir)` guard).

**Error handling contract**: exceptions are narrowed to known failure modes;
there is no `except Exception` in this module.

### `prompts_content.py` — Static data

Pure constants:

- `DEFAULT_PROMPT_ICON`, `SYNAPSE_PROMPT_ICONS`: emoji map for well-known prompts.
- `CORTEX_TOOL_NAMES`: set of tool names used for tool-ref rewriting.
- `MCP_TOOL_PREFIX`, `CLAUDE_CODE_TOOLS_FIELD`: strings injected into Claude Code
  agent frontmatter.

### `prompts_registration.py` — MCP registration

Responsibilities:

- `create_prompt_function(facade, name, content, description, icon_emoji)`:
  stores content in `facade.__dict__["_prompt_contents"]` and registers a
  decorated function via `mcp.prompt(icons=[...])`.
- `_try_publish_prompt(...)`: wraps `create_prompt_function` in a broad
  `except Exception` **at the MCP registration boundary only** — registration
  failures are non-fatal and must not crash server startup.
- `process_prompt_info(facade, prompt_info, prompts_path, category_name)`:
  dispatches one manifest entry through load → register.
- `register_prompts_from_path(facade, prompts_path)`: iterates a manifest's
  categories and entries, tolerates missing/malformed fields at every level.
- `register_synapse_prompts_impl(facade)`: top-level loop over all prompt roots.
- `register_synapse_prompts_for_facade(facade)`: public entry point used by
  `prompts.py`.

**Exception policy**: `_try_publish_prompt` intentionally catches `Exception`
because MCP decorator registration can fail for reasons outside our control
(e.g. duplicate name, server not yet initialised). All other functions use
explicit early-return guards instead.

### `prompts_agents.py` — Agent file sync

Responsibilities:

- `get_agents_source()`: locates `.cortex/synapse/claude-agents/` (the
  source-of-truth for subagent prompt files) by walking CWD then the
  module-anchor tree.
- `inject_tools_into_frontmatter(content)`: adds `tools: mcp__cortex__*` to
  YAML frontmatter and rewrites `` `tool_name(` `` references to their
  `mcp__cortex__` prefixed form, producing the Claude Code variant of each
  agent file.
- `sync_agents_to_target(source, target, label, transform)`: idempotently
  copies `.md` files; removes stale files; handles `OSError` with a warning log.
- `sync_claude_agents()`: called at import time; syncs
  `.cortex/synapse/claude-agents/` to `.claude/agents/` only (with the
  frontmatter/tool-ref transform applied).

## Data flow at import time

```text
prompts.py import
  ├── register_synapse_prompts()
  │     └── register_synapse_prompts_for_facade(facade)
  │           └── register_synapse_prompts_impl(facade)
  │                 ├── get_prompts_paths()          # prompts_paths.py
  │                 └── register_prompts_from_path() # prompts_registration.py
  │                       ├── load_prompts_manifest()
  │                       └── process_prompt_info()
  │                             ├── load_prompt_content()
  │                             └── _try_publish_prompt() → mcp.prompt()
  └── sync_claude_agents()                           # prompts_agents.py
        └── sync_agents_to_target(claude, transform=True)
```

## Path discovery strategy

Both `get_prompts_paths()` and `get_agents_source()` use the same two-pass
strategy:

1. Walk CWD and all parents — works when the MCP server runs from the project root.
2. Walk the module file's ancestor tree — fallback for non-standard working
   directories (e.g. spawned subprocesses).

## Multi-root prompt loading

Multiple prompt roots are supported (e.g. a project may have both
`.cortex/synapse/prompts/` and `.cortex/prompts/`). All discovered paths are
loaded; later registrations overwrite earlier ones if names collide, giving
project-specific prompts natural override precedence over shared Synapse prompts
when loaded last.

## Testing notes

- `test_synapse_prompts.py`: unit tests for path discovery, manifest loading,
  content loading, and registration logic via the `synapse_prompts` facade.
- `test_prompts_agents.py`: unit tests for agent file sync, frontmatter injection,
  and tool-ref rewriting.
- All path-traversal protections in `prompts_paths.py` are covered by dedicated
  tests (`test_rejects_path_traversal_attempt`, `test_rejects_absolute_path`,
  `test_returns_none_when_relative_to_raises_value_error`).
