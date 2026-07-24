# CLAUDE

Guidance for Claude Code agents in this repository. See also `AGENTS.md`.

## Use Cortex MCP (MANDATORY)

**Cortex MCP server** holds all project knowledge, rules, and workflows. Never duplicate that here — fetch from Cortex MCP.

**Start of every non-trivial task:**

1. Call `session()` for orientation (< 1000 tokens)
2. Read `cortex://context` for project context
3. Read `cortex://rules` for coding standards

**Pattern**: `session()` → read resources → work

**Zero-arg tools**: All MCP tools accept empty `{}` (some MCP client bridges strip args). Tools read defaults from session config or use fallbacks. See [AGENTS.md](AGENTS.md#use-cortex-mcp-mandatory) for full tool/resource reference.

**Fix path**: Before fixing errors, test failures, or quality/type issues, read `cortex://context` and `cortex://rules` first.

**Thinking**: Use `think()`. Lightweight for quick deliberation; full mode with `thought_number`, `total_thoughts`, `next_thought_needed` for multi-step reasoning.

**Rules and standards**: Read `cortex://rules` — do not read `.cortex/rules/` or `.cortex/synapse/` directly. Use Pydantic BaseModel for tool parameters and structured dispatch data, not `dict[str, Any]`.

**Quality and tests**: Zero-arg tools only: `run_quality_gate()`, `run_docs_gate()`, `autofix()`. Do not run language-specific formatters/linters/test runners directly.

**Memory bank, plans, reviews**: Use `manage_file()`, `plan()`, `update_memory_bank()` — do not edit `.cortex/` files directly.

**AI agents**: For detailed workflows (commit, implement, fix-path, etc.), read Synapse prompts and rules via Cortex MCP instead of adding guidance to `CLAUDE.md` or `AGENTS.md`.

## Session Discipline

Single-goal sessions:

- Confirm **one primary goal** early; keep work scoped to it.
- Defer unrelated issues to follow-up sessions.
- Split multiple unrelated in-progress fixes into separate scoped passes.

## Execution continuity

Once you have enough information, continue without waiting for "ok, proceed".

- Do **not** stop after loading context or summarizing a plan; move to the next concrete step.
- During `/cortex/commit`, do **not** pause after Phase A; proceed through later phases and Step 12 automatically unless a check fails or clarification is needed.
- Valid stop reasons: ambiguous requirements needing clarification, unrecoverable errors, task complete.

## Compound Engineering

See [AGENTS.md](AGENTS.md#compound-engineering) for the Plan→Work→Review→Compound loop.

## Security

- **No hardcoded secrets**; no sensitive data in logs or memory bank.
- **Security docs**: [docs/security/best-practices.md](docs/security/best-practices.md) — threat model, input validation, file/git security, deployment.
- **Audits**: [Error Recovery Audit](docs/security/error-recovery-audit-2026-02-25.md), [Secret/Credential Protection](docs/security/secret-credential-protection-2026-02-25.md).

## Safety (non-negotiable)

See [AGENTS.md](AGENTS.md#safety-non-negotiable) for safety rules.
