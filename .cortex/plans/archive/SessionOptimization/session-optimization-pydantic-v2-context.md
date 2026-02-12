# Session Optimization: Pydantic v2 Context & Rules Improvements

**Status**: PENDING  
**Created**: 2026-02-11  
**Priority**: Session optimization (Phase D follow-up)  
**Estimated Effort**: 4–6 hours  
**Source**: End-of-session analysis `session-optimization-2026-02-11T12-29.md`

## Goal

Ensure that Pydantic v2 usage patterns are consistently available through `load_context` and Synapse rules so that future refactors (like the usage timeline models) automatically pick up the correct conventions, and fix analytics gaps where `load_context` calls appear with zero token budget or no selected files.

## Context

### Why This Plan

The session that implemented Claude-mem inspired usage analytics changes also refactored `get_usage_timeline` to use Pydantic v2 models. During that refactor, the dedicated Pydantic task ran without loaded memory-bank context (token budget 0, no selected files) and there were no Pydantic-specific rules indexed. The agent relied on ad-hoc code inspection and global knowledge, which risks drift from project standards.

### Current State

- `load_context` is wired to prioritize `activeContext.md`, `techContext.md`, `roadmap.md`, `progress.md`, `systemPatterns.md`, and `productContext.md`, and context effectiveness analytics show good overall behavior.
- Pydantic v2 usage is present in code (e.g., `ToolUsageEvent`, `ToolUsageStats`, and sequential thinking tool models), but project-wide guidance is only implicitly documented (progress/activeContext entries) rather than in a dedicated section of `techContext.md` / `systemPatterns.md` or in Synapse rules.
- `rules(operation="get_relevant", ...)` currently returns `rules_count = 0` and uses a `.cursorrules` folder with `indexed_files = 0`, so no coding standards are being pulled into context for this task.
- One `load_context` call for the Pydantic v2 refactor shows `token_budget = 0` and `files_selected = 0` even though the task was non-trivial, suggesting either a logging/instrumentation gap or a failed call that was not surfaced.

## Implementation Steps

### Step 1: Anchor Pydantic v2 Guidelines in Memory Bank (Medium Effort)

**Deliverable**: A "Pydantic v2 usage" subsection in `techContext.md` (and/or `systemPatterns.md`) that defines how this project uses Pydantic v2 for MCP tools and models.

- Document preferred imports and patterns (e.g. `BaseModel`, `model_config`, `model_dump`, `model_validate`, `field_serializer` / `field_validator`) with v2 semantics.
- Clarify how Pydantic models should be used for MCP tool IO (input/output models, JSON-friendly serialization with `model_dump()` / `model_dump_json()`), including any constraints for public API stability.
- Reference existing uses (usage analytics models, sequentialthinking models) so future work can stay consistent.
- Ensure the new section is small and token-efficient so `load_context` can include it without budget issues.

**Success**: `techContext.md` (and/or `systemPatterns.md`) contains a concise Pydantic v2 section that `load_context` can surface for tasks mentioning "Pydantic" or model refactors.

**Dependencies**: None.

---

### Step 2: Add Pydantic v2 Synapse Rules and Enable Rules Indexing (Medium Effort)

**Deliverable**: One or more Synapse rule files (e.g. `python/pydantic-v2-usage.mdc`) that capture Pydantic v2 best practices, and a working rules index so `rules(operation="get_relevant", ...)` can return them for relevant tasks.

- Create a Python category rule file for Pydantic v2 usage (field naming, config, serialization, error handling, and migration from v1 where relevant).
- Wire the rule to emphasize using `model_dump()` instead of `.dict()`, v2-style `model_config`, and avoiding v1-only APIs.
- Update optimization/validation config so `rules_enabled` is true and the `rules_folder` path points at the actual rules directory (from `get_structure_info().paths.rules`).
- Run `rules(operation="index")` and then `rules(operation="get_relevant", ...)` to confirm Pydantic rules are discoverable for tasks mentioning "Pydantic" or "BaseModel".

**Success**: `rules(operation="get_relevant", task_description="Pydantic v2 refactor")` returns at least one high-relevance Pydantic rule; rules index shows non-zero `indexed_files`.

**Dependencies**: Step 1 optional but recommended for consistent guidance between memory bank and rules.

---

### Step 3: Harden load_context Usage and Analytics for Refactor Tasks (Medium Effort)

**Deliverable**: Guardrails and analytics that prevent non-trivial refactor tasks from running without memory-bank context, and better logging when `load_context` is called with zero budget or selects no files.

- Update the implement/refactor prompts (and any internal helpers) to enforce a minimum token budget for refactor tasks (e.g. 5,000–10,000 tokens) and fail fast instead of silently proceeding when the budget is 0.
- Treat `token_budget = 0` or `files_selected = 0` as an error state in usage analytics, with explicit messages in logs/analysis so it is visible and debuggable.
- Add a small unit test (or integration test) that simulates a refactor task using `load_context` and asserts that at least one of `activeContext.md` / `techContext.md` / `systemPatterns.md` is selected.
- Ensure context-effectiveness analytics correctly record the requested `token_budget` and selected files so future /cortex/analyze runs can distinguish genuine context misses from instrumentation issues.

**Success**: For refactor tasks like "Refactor usage_analytics to use Pydantic v2 models", the logs show a non-zero budget, at least a few high-value memory-bank files loaded, and no entries with `files_selected = 0` unless the call failed explicitly.

**Dependencies**: None, but benefits from Steps 1–2 so the loaded context actually carries Pydantic guidance.

---

### Step 4: Regression Coverage for Pydantic v2 Usage in Usage Analytics (Low–Medium Effort)

**Deliverable**: Tests and docs that lock in the desired Pydantic v2 behavior for usage analytics models so future refactors dont regress to dict-based or v1-style patterns.

- Add focused tests that assert `get_usage_timeline` returns JSON derived from Pydantic v2 models (e.g. constructing `UsageTimelineEntry` instances and using `model_dump()` for serialization).
- Include a short comment or docstring in the relevant model/code pointing back to the Pydantic v2 memory-bank and rule entries created in Steps 1–2.
- Optionally, add a brief note in `progress.md` or `activeContext.md` under the completed work for this session linking to the Pydantic v2 improvements so they remain discoverable in future audits.

**Success**: Tests fail if usage analytics regress away from Pydantic v2 patterns (e.g. reintroducing `dict[str, object]` or v1-only APIs), and code comments/docs clearly reference the canonical guidance in memory bank and rules.

**Dependencies**: Steps 1–3 recommended first so tests align with finalized guidance.
