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

Token budget guide: 10k (small update), 15k (fix/debug), 20-30k (feature), 40-50k (architecture).

**For thinking and reasoning:** Use the `think` tool for quick deliberation moments (analyzing tool outputs, checking policy compliance, planning multi-step operations). For formal multi-step reasoning with revisions and branches, use `sequentialthinking`.

**For rules and standards:** Use Cortex rules/validation tools — do not read `.cortex/rules/` or `.cortex/synapse/` directly.

**For quality and tests:** Use `fix_quality_issues` and `execute_pre_commit_checks` — do not run formatters/linters/pytest directly.

**For memory bank, plans, reviews:** Use dedicated Cortex MCP helpers — do not edit `.cortex/` files directly.

**Workflow and compound-engineering guidance:** Delivered by Cortex MCP (e.g. `load_context`, memory bank). Do not duplicate here — fetch from MCP.

**Note for AI agents**: When you need detailed workflows (commit, implement, fix-path, etc.), read the corresponding Synapse prompts and rules via Cortex MCP instead of adding guidance to `CLAUDE.md` or `AGENTS.md`.

## Safety (non-negotiable)

- No destructive git; no commits/pushes without explicit user request.
- No hardcoded secrets; no sensitive data in logs or memory bank.
- Continue until done or genuinely blocked.
