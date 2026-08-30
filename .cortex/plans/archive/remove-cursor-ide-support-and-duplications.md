---
title: "Remove Cursor IDE support and duplications"
component: "structure"
work_type: refactor
status: DONE
priority: Medium
created: 2026-07-23
completed: "2026-07-23"
---

## Scope decisions (confirmed with user)

- Full removal of Cursor IDE workspace integration: `.cursor/` dir (agents/*.md, mcp.json, mcp_config.json, memory-bank/plans/synapse symlinks), `CursorResourceType`, `CursorIntegrationConfig*`, `CursorSymlinkManager`, `setup_cursor_integration()`, cursor-default/tradewing legacy-migration detection tied to `.cursor/plans`.
- `.cursorrules` legacy-rules-file import: drop entirely (not renamed generic).
- `.cortex/synapse/cursor-agents/` source dir: rename to `.cortex/synapse/agents/` (update task_classifier.py PROMPT keyword, compress/batch.py glob/root, prompts_agents.py, prompts.py, manifest references).
- `AGENTS.md` "## Cursor Cloud specific instructions" section: KEEP as-is (documents execution environment, not IDE integration — out of scope).
- Server trust: remove `"cursor"` from `_is_trusted_client_name()` trusted-prefix tuple in server.py (real behavior change).
- Generic MCP-client-quirk rationale comments (Cursor cited as example of clients that strip args / drop connections / suppress outputSchema) in core/*.py, tools/execution/pre_commit_*.py, tools/session/pipeline_handoff*.py: KEEP the defensive mechanisms, reword comments to generic "some MCP clients" language — do not delete logic.
- NEW: active cleanup — structure lifecycle (startup_repair / structure sync) must detect and remove leftover `.cursor/` artifacts in any host project directory that still has them from a prior Cortex version, not just stop generating new ones here.

## Inventory (from Explore agent report)

See conversation — ~50 src files, ~25 test files, ~40 doc files, root config (README.md, AGENTS.md, CLAUDE.md, .cspell.json, Makefile) reference "cursor". Entangled files requiring surgical (not wholesale) edits:

- structure/lifecycle/symlinks.py, structure_lifecycle.py, manager.py, lifecycle/health.py, lifecycle/startup_repair.py — symlink manager chain, rename Cursor-branded API to generic Claude-only + add legacy-cleanup step
- structure/migration_strategies.py, structure_migration.py — legacy detection heuristics
- tools/synapse/prompts_agents.py, prompts.py — dual .cursor/.claude sync → .claude only
- tools/config/status.py — `_check_codegraph_configured` keep `.mcp.json` fallback, drop `.cursor/mcp.json`; remove `cursor_integration_configured`
- tools/execution/quality_precommit_models.py — remove mirrored field

## Steps

1. Core structure system: path_resolver.py, structure/models.py, structure_config.py — delete Cursor types/fields.
2. Symlink manager chain: rewrite symlinks.py (Claude-only or delete if redundant), health.py, startup_repair.py, structure_lifecycle.py, manager.py — add active `.cursor/` leftover cleanup during repair/sync.
3. Migration strategies: migration_strategies.py, structure_migration.py — drop cursor-default detection/migration, keep tradewing/doc-mcp generic parts.
4. prompts_agents.py / prompts.py: sync to `.claude/agents` only; rename `cursor-agents` source dir → `agents/` across task_classifier.py, compress/batch.py.
5. tools/config/status.py, quality_precommit_models.py, setup/__init__.py, tools/structure/{main,operations,structure_docs,structure_models}.py, discovery/tool_registry.py, tools/context/scoped_context.py: remove Cursor-specific fields/branches/regex entries.
6. Drop `.cursorrules` default filename from optimization/config_defaults.py, optimization/models/_config.py, optimization/rules_indexer.py, optimization/rules_manager.py, rules/synapse_manager.py.
7. server.py trusted-client tuple; setup/prompts.py Step-3 Cursor section removal (+ docs/prompts/initialize.md, migrate.md mirrors).
8. Reword generic MCP-client-quirk comments (keep logic) in core/*.py, execution/pre_commit_*.py, session/pipeline_handoff*.py, bridge.py, main.py.
9. Delete `.cursor/` directory from this repo's working tree.
10. Tests: delete test_cursor_agent_sync.py, test_cursor_agents_brevity.py, test_cursor_symlink_manager.py; surgically edit test_structure_manager.py, test_structure_migration.py, test_startup_repair.py, test_config_status.py, tests/tools/test_structure.py, test_prompts_agents.py, test_rules_operations.py, test_rules_indexer.py, test_rules_manager.py, and lower-density files listed in inventory. Add new tests for active `.cursor/` leftover cleanup.
11. Docs: delete docs/prompts/archive/setup-cursor-integration.md; edit docs/guides/migration.md, troubleshooting.md, api/tools.md, getting-started.md, architecture/naming-conventions.md, api/config-defaults.json, configuration-reference.md, and remaining low-density doc files; README.md config example + migration table row; .cspell.json entry.
12. run_quality_gate() until green; update memory bank via commit pipeline.
</content>

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
