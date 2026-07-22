---
title: "Vector-Seeded Experience Recall in Session Start"
component: "retrieval"
work_type: "feature"
status: BLOCKED
priority: "Medium"
created: "2026-07-19"
depends_on: ["unified-experience-store"]
---

## Goal

Add task-description embeddings alongside the existing BM25 retrieval so that when a new fix/implement session starts, Cortex retrieves similar prior tasks from the experience store and surfaces their highest-fitness outcomes and known dead ends in `session()` / context loading.

## Context

The Experience Graphs paper (arXiv:2606.29823) attributes its 10× speedup and 52% token savings to cross-session reuse via vector-seeded graph retrieval: embed the new task description, find similar prior tasks, then walk relational links to their highest-fitness, non-buggy nodes. Cortex retrieval today is BM25-only (`retrieval/bm25.py`) — keyword matching cannot find "a task like this one." With the experience store in place (plan `unified-experience-store`), similar-task recall can surface proven fixes ("last time this pyright error class appeared, the fix that passed the gate was X") and dead ends ("autofix loop on markdown lint failed 3× via approach Y"), composing with the existing progressive_loader token-budget logic.

## Scope

**in_scope**

- Local embedding generation for task descriptions (small local model or lightweight embedding library; no external API dependency by default).
- Embedding index stored in SQLite alongside the experience store; incremental upsert when tasks are recorded.
- Similar-task query: embed new goal → top-k similar prior tasks → walk to highest-fitness and failed nodes.
- Recall surface: compact "prior experience" block in `session()` output and/or context loading, within existing token budgets.
- Hybrid ranking: combine vector similarity with BM25 where both are available.

**out_of_scope**

- Experience-store schema (plan: unified-experience-store).
- Rewiring `/cortex/analyze` (separate plan).
- Cloud embedding services as a required dependency; remote providers may be optional config.
- Re-embedding the whole memory bank/wiki (task descriptions and experience nodes only).

## Approach

Introduce an `EmbeddingIndex` module with a pluggable encoder behind a typed interface (default: local model), persisting vectors in SQLite (BLOB + cosine similarity, scale is small enough for brute-force scan). On task creation in the experience store, embed and upsert. At session start, embed the goal, retrieve top-k similar tasks, walk their node graphs for best/worst outcomes, and render a budgeted summary block through the progressive loader.

## Implementation Steps

1. Select and integrate a local embedding backend behind a typed `Encoder` protocol (dependency-injected; deterministic fake for tests).
2. Implement `EmbeddingIndex` (SQLite persistence, upsert, top-k cosine query) with Pydantic models.
3. Hook task recording in the experience store to embed and index task descriptions.
4. Implement `recall_similar_tasks(goal, k)`: vector search → graph walk to highest-fitness and failed sibling nodes → typed recall result.
5. Add hybrid scoring with BM25 results where both indexes cover the corpus.
6. Render the recall block in `session()` output under a strict token budget via progressive_loader.
7. Config flags: enable/disable recall, k, similarity threshold, budget.
8. Tests and memory-bank documentation updates.

## Verification Checklist

- Step 1: confirm the chosen backend adds no heavyweight mandatory dependency (`rg` pyproject diff; check install size); re-read pyproject after changes.
- Step 3: verify every task-creation path indexes exactly once (`rg "record_task|ExperienceTask" src/`).
- Step 6: check `session()` token count stays within budget (existing token accounting tests); re-read session orientation module after edits.
- Step 8: `run_quality_gate()` green.

## Dependencies

- Plan: `unified-experience-store` (`.cortex/plans/unified-experience-store.md`) — provides tasks/nodes/fitness to recall.

## Success Criteria

- Given a store with prior tasks, a semantically similar new goal (different keywords) retrieves the right prior task in top-k (fixture-based test).
- Recall block includes at least: similar task title, best-fitness outcome summary, and any repeated-failure dead end.
- `session()` token budget respected (recall block ≤ configured budget; measured in tests).
- Recall disabled flag produces byte-identical `session()` behavior to today.
- Quality gate green; ≥95% coverage on new modules.

## Testing Strategy

- Unit tests (AAA): encoder protocol with deterministic fake, index upsert/query, cosine ranking, budget truncation.
- Integration tests: end-to-end record → embed → recall on fixtures; hybrid BM25+vector ordering; disabled-flag path.
- Negative cases: empty store, embedding failure fallback to BM25-only, oversized descriptions.
- Target: ≥95% coverage on new modules.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Local embedding model bloats install or startup | Lazy-load encoder; optional extra in pyproject; fallback to BM25-only when unavailable |
| Irrelevant recalls waste context tokens | Similarity threshold + strict budget; surface nothing below threshold |
| Embedding drift across model versions | Store encoder id/version with vectors; reindex on version change |
| Brute-force scan too slow as store grows | Acceptable at dev-tool scale; add ANN index only if measured p95 exceeds target |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
