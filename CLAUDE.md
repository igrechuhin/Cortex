# CLAUDE

Guidance for Claude Code agents in this repository. See also `AGENTS.md`.

## Use Cortex MCP (MANDATORY)

This project runs a **Cortex MCP server**. All project knowledge, rules, and workflows are available through its tools. **Do not duplicate that information here or in prompts — always fetch it from Cortex MCP.**

**At the start of every non-trivial task:**

**For session orientation** (recommended first step):

```text
session(operation="start", task_description=None)  # Get orientation brief (< 1000 tokens)
```

**For task-specific context**:

```text
load_context(task_description="<your goal>", token_budget=<appropriate>)
```

**Pattern**: `session(operation="start")` → review brief → `load_context(task_description=brief.next_work_item, ...)` → work

**Parallel agents (Phase 58)**: See AGENTS.md (Multi-agent coordination) for task locking when multiple Cursor tabs work on the same project.

Token budget guidance comes from `load_context` tool documentation and context-effectiveness analysis. Use task-appropriate budgets.

**Context budget defaults (task-type)**:

| Task type | Token budget |
|-----------|--------------|
| implement/add, update/modify | 10,000 |
| fix/debug, other | 15,000 |
| small feature | 20,000–30,000 |
| optimization | 15,000 |
| narrow review/documentation | 7,000–8,000 |
| architecture/large design | 40,000–50,000 |

See implement prompt for full checklist and zero-budget guardrails.

**AgentRole awareness**: The `load_context` tool automatically detects agent roles (feature/quality/testing/docs/planning/debugging/review) from task descriptions and uses role-aware context selection. Roles influence file prioritization and context-effectiveness analysis provides role-specific budget recommendations. The detected role is logged in session logs for analysis. See AGENTS.md for role descriptions, detection keywords, default budgets, and file focus preferences. Role-aware budget recommendations are available in `analyze_context_effectiveness()` insights.

**On the fix path**: When you encounter a problem and have to fix something (errors, test failures, quality/type issues), you **must** load context and rules before making changes—e.g. `load_context(task_description="Fixing errors and issues", token_budget=15000)` and get relevant rules—so fixes follow all project rules and guidelines. See AGENTS.md and the commit/implement prompts for details.

**For thinking and reasoning:** Use the `think` tool. Lightweight: `think(thought="...")` for quick deliberation. Full mode: pass `thought_number`, `total_thoughts`, `next_thought_needed` for multi-step reasoning with revisions and branches.

**For rules and standards:** Use Cortex rules/validation tools — do not read `.cortex/rules/` or `.cortex/synapse/` directly. Get structured data standards via `get_synapse_rules(task_description="[language] models, structured data")` or `rules(operation="get_relevant", task_description="structured data, tool parameters")`. For tool parameters and structured dispatch data use Pydantic BaseModel, not `dict[str, Any]`.

**For quality and tests:** Use `fix_quality_issues` and `execute_pre_commit_checks` — do not run language-specific formatters/linters/test runners directly (get standards via `get_synapse_rules`).

**For memory bank, plans, reviews:** Use dedicated Cortex MCP helpers — do not edit `.cortex/` files directly.

**Workflow and compound-engineering guidance:** Delivered by Cortex MCP (e.g. `load_context`, memory bank). Do not duplicate here — fetch from MCP.

**Note for AI agents**: When you need detailed workflows (commit, implement, fix-path, etc.), read the corresponding Synapse prompts and rules via Cortex MCP instead of adding guidance to `CLAUDE.md` or `AGENTS.md`.

## Compound Engineering

See [AGENTS.md](AGENTS.md#compound-engineering) for the compound-engineering goal and Plan→Work→Review→Compound loop.

## Security

- **No hardcoded secrets**; no sensitive data in logs or memory bank.
- **Security documentation**: See [docs/security/best-practices.md](docs/security/best-practices.md) for threat model, input validation, file/git security, and deployment guidance.
- **Related audits**: [Error Recovery Audit](docs/security/error-recovery-audit-2026-02-25.md), [Secret/Credential Protection](docs/security/secret-credential-protection-2026-02-25.md).

## Safety (non-negotiable)

See [AGENTS.md](AGENTS.md#safety-non-negotiable) for safety rules.
