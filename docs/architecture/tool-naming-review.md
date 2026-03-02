# Tool Naming Review

**Status**: Review deliverable (2026-02-27)  
**Purpose**: Ensure tool names reflect their purpose per naming conventions.

## Criteria

Names must clearly indicate what the tool does. Per [naming-conventions.md](naming-conventions.md):

- **Imperative verbs** for side effects: `manage_file`, `fix_quality_issues`
- **`query_*`** for read-only consolidated dispatchers
- **`manage_*`** when the tool manages a resource (create/read/update/delete operations)
- **`run_*`** / **`execute_*`** when the tool executes a workflow or composite action

## Review Results

### Tools renamed (2026-02-27)

| Old name | New name | Rationale |
|----------|----------|-----------|
| `session_scripts` | `manage_session_scripts` | Purpose: capture, list, analyze, suggest, promote session scripts. Noun "session_scripts" does not convey the manage/capture/analyze action. `manage_*` aligns with `manage_file`, `manage_synapse` pattern. |
| `agent_workflow` | `run_composite_workflow` | Purpose: run composite workflows (quick_start, quality_check, safe_manage_file, suggest_workflow). "agent_workflow" is vague. `run_composite_workflow` states the action (run) and target (composite workflow). |

### Tools kept (name reflects purpose)

| Tool | Purpose | Notes |
|------|---------|-------|
| `manage_file` | Memory Bank file read/write/metadata/rollback | ✓ |
| `query_memory_bank` | Memory bank stats, version history, links, etc. | ✓ |
| `query_usage` | Usage stats, unused, report, anomalies | ✓ |
| `append_entry` | Append to progress.md or activeContext.md | ✓ |
| `load_context` | Load task-relevant context | ✓ |
| `plan` | Plan lifecycle (create, list, get, complete, register) | Noun acceptable per conventions |
| `roadmap` | Add/remove roadmap entries and sections | Noun acceptable |
| `rules` | Index rules, get relevant rules | Noun acceptable |
| `session` | Session lifecycle (start, register, deregister, compact) | Noun acceptable |
| `validate` | Run validation checks | ✓ |
| `configure` | Configure validation/optimization/learning | ✓ |
| `analyze` | Analyze Memory Bank, context, health | ✓ |
| `fix_quality_issues`, `fix_markdown_lint` | Fix quality/lint issues | ✓ |
| `execute_pre_commit_checks` | Run pre-commit checks | ✓ |
| `get_structure_info`, `get_relevance_scores` | Project structure; file relevance | Deferred per naming-conventions.md |

### Tools deferred (future consideration)

| Tool | Proposal | Rationale |
|------|----------|-----------|
| `get_structure_info` | `query_project_structure` | Widely used; rename would be breaking. Document as exception. |
| `get_relevance_scores` | `query_file_relevance` | Aligns with `query_*`; low priority. |
| `rules` | `manage_rules` | Verb consistency; established noun acceptable. |
| `synapse` | `manage_synapse` | Sync + update; `manage_*` would fit. Established noun acceptable. |

## Migration

For `session_scripts` → `manage_session_scripts` and `agent_workflow` → `run_composite_workflow`:

- Update tool implementation (function name)
- Update `categories.py`
- Update `tool_registry.py`
- Update `docs/api/tools.md`
- Update prompts (e.g. commit.md references)
- Update tests

Clients must use the new tool names. Old names will no longer be registered.

## References

- [Naming conventions](naming-conventions.md)
- [Naming inventory](naming-inventory-2026-02.md)
- [Tool optimization mapping](tool-optimization-mapping.md)
