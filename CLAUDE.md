# CLAUDE

Guidance for Claude Code agents in this repository. See also `AGENTS.md`.

## Use Cortex MCP (MANDATORY)

This project runs a **Cortex MCP server**. All project knowledge, rules, and workflows are available through its tools. **Do not duplicate that information here or in prompts — always fetch it from Cortex MCP.**

**At the start of every non-trivial task:**

1. Call `session()` for orientation (< 1000 tokens)
2. Read `cortex://context` resource for project context
3. Read `cortex://rules` resource for coding standards

**Pattern**: `session()` → read resources → work

**Zero-arg tools**: All MCP tools work when called with empty `{}` arguments (Cursor's MCP bridge strips args). Tools read defaults from session config files or use sensible fallbacks. See [AGENTS.md](AGENTS.md#use-cortex-mcp-mandatory) for the full tool/resource reference.

**On the fix path**: When you encounter a problem and have to fix something (errors, test failures, quality/type issues), you **must** read `cortex://context` and `cortex://rules` resources before making changes. This ensures fixes follow all project rules and guidelines.

**For thinking and reasoning:** Use `think()`. Lightweight for quick deliberation; full mode with `thought_number`, `total_thoughts`, `next_thought_needed` for multi-step reasoning.

**For rules and standards:** Read `cortex://rules` resource — do not read `.cortex/rules/` or `.cortex/synapse/` directly. For tool parameters and structured dispatch data use Pydantic BaseModel, not `dict[str, Any]`.

**For quality and tests:** Use zero-arg tools: `run_quality_gate()`, `run_docs_gate()`, `fix_quality_issues()`. Do not run language-specific formatters/linters/test runners directly.

**For memory bank, plans, reviews:** Use dedicated Cortex MCP helpers (`manage_file()`, `plan()`, `update_memory_bank()`) — do not edit `.cortex/` files directly.

**Note for AI agents**: When you need detailed workflows (commit, implement, fix-path, etc.), read the corresponding Synapse prompts and rules via Cortex MCP instead of adding guidance to `CLAUDE.md` or `AGENTS.md`.

## Session Discipline

Use a single-goal session pattern to improve completion reliability:

- Confirm **one primary goal** early in the session and keep work scoped to that goal.
- If unrelated issues appear, note them and defer them to a separate follow-up session.
- If multiple unrelated fixes are already in progress, split execution into separate scoped passes instead of one mixed bundle.

## Execution continuity

Once you have enough information to act, continue execution without waiting for the user to say "ok, proceed" or similar.

- Do **not** stop after loading context or summarizing a plan; move directly into the next concrete step.
- During `/cortex/commit`, do **not** pause after Phase A passes to ask for confirmation; proceed through later phases and Step 12 automatically unless a check fails or genuine clarification is needed.
- Only stop for valid reasons: clarification about ambiguous requirements, unrecoverable errors, or when the current task is complete and you are delivering the final summary.

## Compound Engineering

See [AGENTS.md](AGENTS.md#compound-engineering) for the compound-engineering goal and Plan→Work→Review→Compound loop.

## Security

- **No hardcoded secrets**; no sensitive data in logs or memory bank.
- **Security documentation**: See [docs/security/best-practices.md](docs/security/best-practices.md) for threat model, input validation, file/git security, and deployment guidance.
- **Related audits**: [Error Recovery Audit](docs/security/error-recovery-audit-2026-02-25.md), [Secret/Credential Protection](docs/security/secret-credential-protection-2026-02-25.md).

## Safety (non-negotiable)

See [AGENTS.md](AGENTS.md#safety-non-negotiable) for safety rules.
