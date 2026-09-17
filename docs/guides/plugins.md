# Cortex local plugins

Cortex assembles host-native local packages from a built wheel and canonical
Synapse sources. No marketplace publication, user-configuration installer, or
second orchestration engine is involved. The package never copies project state.

## Build

From a Cortex checkout with Synapse initialized:

```sh
uv build --wheel
uv run python -m cortex.setup.plugin_package \
  --synapse .cortex/synapse --docs docs \
  --wheel dist/cortex-0.2.0-py3-none-any.whl \
  --output /absolute/path/to/new-cortex-packages
```

The output directory must not exist. This deliberately prevents overwriting
customized installations. Each `claude/` and `codex/` directory is a standalone
local marketplace with `plugins/cortex/`. Both contain the wheel, canonical
Synapse content, report template, and generated skills. Build again from the same
inputs to reproduce the file contents; generated packages are not hand-maintained.

Claude uses `.claude-plugin/plugin.json`; Codex 0.153.4 uses
`.codex-plugin/plugin.json`. That Codex release explicitly skips hooks in portable
`plugin.json` packages. Its native MCP loader also does not interpolate plugin-root
variables, so the generated Codex MCP command contains an absolute path to the
wheel in this local distribution. **Keep the generated marketplace directory in
place while installed.** To relocate it, rebuild and reinstall from the new path.
This is local packaging, not a relocatable published-marketplace artifact.

Runtime prerequisites: `uv` on the host PATH, Python 3.13 or later (uv can acquire
it), and access to resolve the wheel's declared dependencies on first launch.
The bundled launcher uses `uv tool run --from <bundled-wheel> python -m
cortex.setup.plugin_server`, binding Cortex to the host's working directory before
server registration. It does not change into the package, search for a developer
checkout, or require a project `.venv`.
Initialize Cortex memory in each target workspace with the
existing Cortex setup workflow before expecting lifecycle persistence. Packages
supply read-only procedures, not a replacement project configuration.

## Install and discover

For isolated verification, set `CLAUDE_CONFIG_DIR` or `CODEX_HOME` to a disposable
configuration directory for every corresponding command. Do not point smoke tests
at real user configuration. Authentication is a separate prerequisite for actual
model invocation.

Claude Code:

```sh
claude plugin validate /absolute/path/to/new-cortex-packages/claude/plugins/cortex
claude plugin marketplace add /absolute/path/to/new-cortex-packages/claude
claude plugin install cortex@cortex-local
claude plugin details cortex@cortex-local
```

Commands are `/cortex:plan`, `/cortex:do`, `/cortex:review`, and `/cortex:commit`.
For temporary development loading, use
`claude --plugin-dir /absolute/path/to/claude/plugins/cortex`.

Codex:

```sh
codex plugin marketplace add /absolute/path/to/new-cortex-packages/codex
codex plugin add cortex@cortex-local
codex plugin list
```

Open native skill discovery and select the Cortex `plan`, `do`, `review`, or
`commit` skill. Codex uses skill invocation rather than promising Claude slash
syntax. Review and trust plugin hook definitions in `/hooks`; plugin installation
alone does not grant hook trust. Do not bypass this review for ordinary installs.

Skills contain canonical Markdown, not handwritten workflow copies. Their header
maps read-only Synapse and report-template references to installed assets,
including references from subsequently loaded canonical prompts. Project Git and
state paths remain project-owned; never write or run Git in the package. Native
Workflow-script runners are host-specific; use canonical Markdown procedures
when that tool is unavailable. Language-specific quality checks still require
the target project's toolchain. Discovery never authorizes commits or pushes;
each action requires explicit user authorization, overriding broader language in
a canonical procedure.

## Lifecycle contract

`SessionStart` uses a short command adapter for `startup` and `resume`. It validates
the host JSON and actual process directory, then calls Cortex's existing
`session_start` operation without launching a second MCP server. Claude never runs
MCP-tool hooks at startup/resume, so an MCP-only startup declaration would silently
miss these events.

`PreCompact` uses the already-connected `session` MCP tool with
`operation="hook"` and a validated `hook_event`:

- `trigger` is `manual` or `auto` only.
- Required common fields: `host` (`claude` or `codex`), `event`, absolute `cwd`,
  and nonempty `session_id`. Codex supplies `turn_id`; otherwise a readable absolute
  `transcript_path` is needed for its metadata fingerprint.
- Event workspace must resolve exactly to the initialized MCP workspace root.
  Subdirectories, different roots, malformed events, and unsupported events are
  rejected with a visible diagnostic; no workspace is inferred from package paths.
- The adapter has a 12-second deadline; host hooks have a 15-second timeout.
  Startup output is capped at 3,000 characters. Repeated startup/source events are
  suppressed within one process (a bounded 128-entry cache), not across separately
  launched command adapters.
- Pre-compaction preserves existing completed tasks, work in progress, blockers,
  decisions, and next actions. It stores at most 2,400 characters of
  `activeContext.md` in the existing handoff's `hook_snapshot` field. This is a real
  persisted memory-bank continuation, **not a transcript summary** or destructive
  memory compaction. Use `session(operation="compact", summary=...)` explicitly
  when a semantic summary or full memory compaction is wanted.
- Replay identities are stored in the existing handoff, not a new state store.
  A project file lock serializes native handoffs. Codex fingerprints use
  session/turn/trigger, so multiple compactions in the same turn collapse. Claude
  uses session/trigger/transcript size and mtime. Identical fingerprints are
  no-ops, including replay after a newer event; changed transcript metadata cannot
  distinguish a replay from a new event. **Strict exactly-once delivery is not
  guaranteed by either adapter.** Receipts survive ordinary compaction; deleting
  the handoff resets replay history.
- A successful write is read back before reporting success. Failure returns a
  native MCP error (`isError: true`), never a false saved-handoff claim.
  Claude 2.1.273 can echo successful MCP text, including `systemMessage` JSON,
  in manual `/compact` output; failure notices must use the native error channel.
  Startup command failures write diagnostics to stderr and exit with status 1.
  Native MCP hooks do not recursively trigger other hooks or spawn another server.

Pre-compaction requires an available MCP connection; missing servers/tools and
timeouts produce nonblocking host diagnostics, not a saved-handoff claim. No
automatic retry is promised. Review hook trust and save explicitly with
`session(operation="compact", summary=...)` before compaction when persistence
matters. `clear`, post-compaction startup, SessionEnd, per-prompt gates, and subagent
lifecycle hooks are not configured.

## Coexistence, update, disable, uninstall

Use **one Cortex MCP registration per workspace**. Before enabling the plugin,
disable only the old Cortex MCP entry through the host's MCP UI/CLI; preserve
other servers and user settings. The bundled server sets
`CORTEX_NATIVE_WORKFLOWS=1`, suppressing only the four corresponding legacy MCP
workflow prompts. Other prompts remain available. A separate legacy server does
not inherit that environment variable, so leaving it enabled creates duplicates.

Existing language post-edit hooks remain untouched. The plugin supplies no
post-edit, per-prompt, or quality-gate hook, so those hooks are not duplicated.
Remove any separately installed Cortex SessionStart/PreCompact adapter before
enabling this one; both hosts merge hook sources rather than replacing them.

Build updates into a new output directory; retain the previous package for
rollback. Refresh the host marketplace source to the new directory, then use
`claude plugin update cortex@cortex-local`, or refresh/reinstall the Codex local
plugin with its marketplace commands. Restart the host and review changed Codex
hook definitions. Keep wheel/plugin versions aligned; increment the package
version for a release. Do not edit generated cache files.

Claude supports `claude plugin disable cortex@cortex-local` and
`claude plugin uninstall cortex@cortex-local`. Codex supports disabling the plugin
in its plugin settings and `codex plugin remove cortex@cortex-local`. Remove the
`cortex-local` marketplace only if no longer used. These host operations remove
plugin-owned cache/configuration; Cortex's assembler never edits user settings.
Project `.cortex/memory-bank`, plans, handoffs, and session history remain in the
workspace. Restore a disabled legacy MCP entry if returning to legacy setup.

## Verification status and upstream contracts

Verified with Claude Code **2.1.273** and Codex CLI **0.153.4** in disposable host
configuration directories and two workspaces whose paths contain spaces:

- Both hosts installed and discovered four skills, two hooks, and one MCP server.
  Claude manifest validation passed.
- Native Codex invoked the packaged planning procedure and created/registered its
  smoke plan. Registration required the API key `section=pending`, not the heading
  text from the canonical prompt; this preexisting tool/prompt mismatch was reported.
- Codex startup returned the selected workspace's focus. Native pre-compaction
  persisted and read back a real handoff; a fresh-process resume restored it.
  Concurrent native servers read distinct workspace roadmaps.
- A temporary 0.2.0 → 0.2.1 fixture exercised Claude update and Codex's documented
  remove/reinstall update. Uninstall preserved ten state files and unrelated host
  settings. The repository version was not changed.

The accepted contract is **best-effort deduplication, not exactly-once delivery**.
Keep the existing fingerprints and handoff receipts: same-turn Codex compactions
can be skipped, while changed Claude transcript metadata can cause another write.
Startup orientation can repeat across command processes. These limitations are
explicitly accepted; no transcript parser, new state store, or retry loop is added.

Authenticated Claude verification subsequently passed with session-only plugin
loading and an explicit isolated MCP configuration using the bundled launcher.
The host discovered all four workflows, connected Cortex, and `/cortex:plan`
created and registered a real smoke plan. Startup supplied the workspace focus;
native `/compact` saved a handoff that fresh-process resume restored.
An injected persistence failure produced a visible non-blocking PreCompact
notice, compaction continued, and the prior handoff was preserved.
A separately configured startup hook and Cortex each ran once; both context
markers reached the model without invoking workflow or quality tools.

Lifecycle failures use native MCP errors (`isError: true`); startup command
failures use stderr and exit status 1. Run-specific gate metrics and the approved
acceptance change are recorded in the
[packaging plan](../../.cortex/plans/archive/Other/cortex-plugin-packaging-and-lifecycle-hooks.md).

Focused regressions:

```sh
uv run pytest tests/tools/test_plugin_lifecycle.py tests/tools/test_plugin_start.py tests/tools/test_plugin_package.py tests/tools/test_compaction_operations.py
```

Official references:

- [Claude plugin manifests and scoped MCP naming](https://code.claude.com/docs/en/plugins-reference)
- [Claude hooks and MCP hook timing](https://code.claude.com/docs/en/hooks)
- [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [Codex 0.153.4 loader: portable hooks are skipped](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core-plugins/src/loader.rs)
- [Codex 0.153.4 native MCP path handling](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/codex-mcp/src/plugin_config.rs)
- [Codex native hooks and trust](https://learn.chatgpt.com/docs/hooks)

The create-hook skill's Cursor-style lowercase hook examples are not the OpenAI
Codex CLI contract; these packages follow the official host references above.
