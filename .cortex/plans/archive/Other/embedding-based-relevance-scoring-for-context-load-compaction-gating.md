---
title: "Embedding-Based Relevance Scoring for Context Load/Compaction Gating"
component: "context-management"
work_type: "feature"
status: PENDING
priority: "Medium"
created: "2026-07-23"
depends_on: []
---

## Goal

Replace the plain size/position-based truncation in `src/cortex/tools/context/l0_identity.py::_truncate_to_budget` and `l2_on_demand.py::_truncate_paragraphs` with relevance-ranked truncation that prefers semantically important paragraphs/sections, using the embedding infrastructure already built for the experience store (`src/cortex/experience/hybrid_rank.py`, `embedding_index_core.py`, `recall.py`).

## Context

An external proposal ("Turn-Aware Context Gating / Information Density Engine") suggested scoring conversation turns for relevance instead of truncating positionally. Investigation (2026-07-23) found Cortex's current context-loading truncation (`l0_identity.py`, `l2_on_demand.py`) is purely size/count-based — it cuts by character/paragraph budget, not by content relevance. The recently shipped "Session Runtime Token-Spend Guard" (`.cortex/plans/archive/Other/session-runtime-token-spend-guard.md`) added runtime cumulative-spend tracking (`SessionSpendStatus`, `record_spend_tokens()`) but is warn-only and explicitly deferred compaction/eviction logic. Separately, `src/cortex/experience/` already has real embedding-based relevance scoring (`hybrid_rank.py`, `embedding_index_core.py`) used for experience-store task recall, but it is not wired into context loading or compaction decisions. No `CompactAfterTurns`-equivalent hook exists in Cortex — session compaction is owned by the Claude Code harness itself, not Cortex MCP, so this plan is scoped to what Cortex actually controls: what content it serves when `load_context`/`l0_identity`/`l2_on_demand` are asked to fit within a token budget.

**Why**: When memory-bank files or on-demand context sections exceed budget, truncating by raw position/size risks cutting the most relevant paragraph for the current task while keeping boilerplate — reusing existing embedding infra closes that gap without building new ML infrastructure.

**How to apply**: This plan augments existing budget-fitting logic; it does not replace the token-spend guard or introduce a new compaction trigger point.

## Scope

**in_scope**:

- A relevance-scoring function that, given a task/query description and a set of candidate paragraphs/sections, ranks them using the existing embedding index (`src/cortex/experience/embedding_index_core.py`) rather than positional order.
- Wiring that scoring function into `_truncate_to_budget` (`l0_identity.py`) and `_truncate_paragraphs` (`l2_on_demand.py`) as a ranking step applied before the existing budget cut, with a fallback to the current positional truncation when no task/query context is available or the embedding index is unavailable (e.g. cold start, no session goal set).
- Configuration to enable/disable relevance-ranked truncation independently of positional truncation, so it can be rolled back without code changes if it degrades output quality.
- Unit/integration tests comparing relevance-ranked vs. positional truncation output on representative memory-bank fixtures.

**out_of_scope**:

- Any change to the Claude Code harness's own conversation-history compaction (out of Cortex's control).
- A new `MaxBudgetTokens`-style runtime loop or `TaskLight`/`TaskFull`/`ReviewMode` phase classifier — that is separate scope from ranking within an existing budget cut.
- Extending the token-spend guard's warn-only behavior into active eviction/blocking — remains a future, separately-planned decision.
- Changes to the experience-store embedding model itself (reuse as-is).

## Approach

Add a thin ranking layer that calls into the existing embedding index to score candidate paragraphs/sections against the current session goal or task description (already available via `session()`/`pipeline_handoff` session-scope config), then sorts candidates by score before applying the existing character/paragraph budget cut in `l0_identity.py` and `l2_on_demand.py`. Keep the existing positional truncation as the fallback path so behavior degrades gracefully rather than failing when no query context or embedding index is present.

## Implementation Steps

1. Read `src/cortex/experience/hybrid_rank.py` and `embedding_index_core.py` to confirm the ranking API surface (inputs/outputs) that can be reused without modification.
2. Read `src/cortex/tools/context/l0_identity.py::_truncate_to_budget` and `l2_on_demand.py::_truncate_paragraphs` in full to understand current call signatures and budget-cut logic.
3. Add a `rank_candidates_by_relevance(query, candidates) -> list[RankedCandidate]` function (Pydantic `BaseModel` inputs/outputs, no `Any`) that wraps the existing embedding index.
4. Wire this function into `_truncate_to_budget` and `_truncate_paragraphs`, applied before the existing size cut, with a config flag and safe fallback to positional truncation.
5. Source the ranking query from the current session goal (`session()` primary_session_goal / `pipeline_handoff` session scope) where available; when absent, skip ranking and use positional truncation unchanged.
6. Add unit tests for the ranking function and integration tests verifying budget-cut output differs (and is more relevant) with ranking enabled vs. disabled on fixture data.
7. Run `run_quality_gate()` and confirm no regression in existing `l0_identity`/`l2_on_demand` test suites.

## Verification Checklist

- Step 1: search `src/cortex/experience/` for other consumers of `hybrid_rank`/`embedding_index_core` to confirm the reused API won't be broken for existing callers.
- Step 4: re-read `l0_identity.py`/`l2_on_demand.py` after edits to confirm the fallback path is reachable and covered by a test (no query context / no embedding index).
- Step 6: re-read new/changed test files to confirm AAA structure and that fixtures represent realistic memory-bank content (not toy strings only).
- Step 7: re-run `run_quality_gate()` after tests added; confirm coverage threshold met.

## Dependencies

- Relies on `src/cortex/experience/` embedding infra remaining stable; no changes needed there. No other pending plan blocks this — independent of the WAL/telemetry plan and the sandboxed self-modification plan.

## Success Criteria

- `_truncate_to_budget` and `_truncate_paragraphs` produce relevance-ranked output when a session goal/query is available, and unchanged positional output when it is not.
- A config flag allows disabling relevance ranking without code changes.
- No existing `l0_identity`/`l2_on_demand` test regresses.
- `run_quality_gate()` passes with new code covered.

## Testing Strategy

Target 95% coverage on new code. Unit tests (AAA pattern) for: `rank_candidates_by_relevance` scoring order on known-relevant vs. known-irrelevant fixture pairs, fallback behavior when the embedding index raises/unavailable, config-flag toggling. Integration tests: run `_truncate_to_budget`/`_truncate_paragraphs` against a realistic multi-section memory-bank fixture with a known task query and assert the retained section matches the semantically relevant one, not just the first N characters. Negative case: empty candidate list, single candidate, budget larger than all candidates combined (no truncation needed).

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Relevance ranking silently drops content a downstream consumer expected at a fixed position | Config flag defaults to disabled until validated; fallback to positional truncation is the safe default |
| Embedding index unavailable or slow at context-load time (hot path) | Ranking step must fail open to positional truncation on any error/timeout, never block context loading |
| Ranking quality degrades for content types the embedding model wasn't tuned for (e.g. YAML/JSON config) | Test fixtures must include non-prose content; if ranking underperforms there, scope fallback per-content-type |
| Coupling context-loading (hot path, called frequently) to experience-store internals not designed for this call frequency | Verify with Step 1 whether the embedding index API is safe for high-frequency reuse or needs caching |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
