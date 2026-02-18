# CLAUDE

Guidance for Claude Code agents in this repository. See also `AGENTS.md`.

## Use Cortex MCP (MANDATORY)

This project runs a **Cortex MCP server**. All project knowledge, rules, and workflows are available through its tools. **Do not duplicate that information here or in prompts — always fetch it from Cortex MCP.**

**At the start of every non-trivial task:**

**For session orientation** (recommended first step):

```text
session_start(task_description=None)  # Get orientation brief (< 1000 tokens)
```

**For task-specific context**:

```text
load_context(task_description="<your goal>", token_budget=<appropriate>)
```

**Pattern**: `session_start()` → review brief → `load_context(task_description=brief.next_work_item, ...)` → work

Token budget guidance comes from `load_context` tool documentation and context-effectiveness analysis. Use task-appropriate budgets; see implement prompt for defaults.

**On the fix path**: When you encounter a problem and have to fix something (errors, test failures, quality/type issues), you **must** load context and rules before making changes—e.g. `load_context(task_description="Fixing errors and issues", token_budget=15000)` and get relevant rules—so fixes follow all project rules and guidelines. See AGENTS.md and the commit/implement prompts for details.

**For thinking and reasoning:** Use the `think` tool for quick deliberation moments (analyzing tool outputs, checking policy compliance, planning multi-step operations). For formal multi-step reasoning with revisions and branches, use `sequentialthinking`.

**For rules and standards:** Use Cortex rules/validation tools — do not read `.cortex/rules/` or `.cortex/synapse/` directly. Get structured data standards via `get_synapse_rules(task_description="[language] models, structured data")` or `rules(operation="get_relevant", task_description="structured data, tool parameters")`. For tool parameters and structured dispatch data use Pydantic BaseModel, not `dict[str, Any]`.

**For quality and tests:** Use `fix_quality_issues` and `execute_pre_commit_checks` — do not run language-specific formatters/linters/test runners directly (get standards via `get_synapse_rules`).

**For memory bank, plans, reviews:** Use dedicated Cortex MCP helpers — do not edit `.cortex/` files directly.

**Workflow and compound-engineering guidance:** Delivered by Cortex MCP (e.g. `load_context`, memory bank). Do not duplicate here — fetch from MCP.

**Note for AI agents**: When you need detailed workflows (commit, implement, fix-path, etc.), read the corresponding Synapse prompts and rules via Cortex MCP instead of adding guidance to `CLAUDE.md` or `AGENTS.md`.

## Compound Engineering

See [AGENTS.md](AGENTS.md#compound-engineering) for the compound-engineering goal and Plan→Work→Review→Compound loop.

## Safety (non-negotiable)

See [AGENTS.md](AGENTS.md#safety-non-negotiable) for safety rules.
