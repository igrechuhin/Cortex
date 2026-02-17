# Session Optimization: Pydantic Rule Visibility and Rule Discovery

**Source**: End-of-session analysis 2026-02-12 (session-optimization-2026-02-12T23-25.md).

**Problem**: During Phase 50 tool consolidation, the agent used `dict[str, Any]` for query_memory_bank and query_usage params. The project standard is Pydantic BaseModel for structured data (AGENTS.md, implement prompt, existing tools). The agent did not apply this until the user explicitly asked to "promote dict[str, Any] to Pydantic model(s)."

**Goal**: Ensure agents apply the Pydantic-for-params rule when implementing or refactoring MCP tools, without requiring user reminders.

---

## Recommendations from Analysis

1. **Strengthen Pydantic rule visibility for tool/params work**
   - Implement prompt (or "implement next roadmap step"): add explicit bullet under coding standards / Step 4: "For tool parameters and internal dispatch data use Pydantic BaseModel (e.g. QueryXParams), not dict[str, Any]. Apply when introducing or refactoring tool param objects."
   - AGENTS.md / CLAUDE.md: add one-line rule in standards table or workflow: "Structured params: use Pydantic models, not dict[str, Any]."

2. **Improve rule discovery for Pydantic**
   - If Pydantic standards live in Synapse: ensure task descriptions like "implement tool" or "refactor tool params" retrieve Python/Pydantic rules (rules indexing or get_synapse_rules).
   - When rules(operation="get_relevant") returns no rules: document in analyze prompt or memory-bank workflow that for coding-standard tasks the agent should also check get_synapse_rules(task_description="Pydantic models, structured data") or read AGENTS.md/CLAUDE.md for Pydantic guidance.

---

## Implementation Steps

1. **Implement prompt**: Add explicit Pydantic-for-params bullet (tool parameters and dispatch data → BaseModel, not dict[str, Any]) in coding standards or Step 4.
2. **AGENTS.md / CLAUDE.md**: Add one-line "Structured params: Pydantic models, not dict[str, Any]" in the standards table or workflow section.
3. **Rule discovery fallback**: In analyze prompt Pre-Analysis Checklist or in memory-bank-workflow / implement prompt: when rules return empty or task involves tool implementation/refactor, recommend get_synapse_rules or AGENTS.md for Pydantic/structured-data standards.
4. **Optional**: Add or update a Synapse rule (e.g. python/pydantic or general) that explicitly says "Tool params and internal structured data: use Pydantic BaseModel; avoid dict[str, Any] for new or refactored code."

---

## Status

PENDING

## Completion Criteria

- Implement prompt and AGENTS.md/CLAUDE.md updated so Pydantic-for-params is visible during tool implementation.
- Rule discovery fallback documented where relevant (analyze or implement workflow).
- Optional: Synapse rule updated/added and indexed for tool/Pydantic tasks.
