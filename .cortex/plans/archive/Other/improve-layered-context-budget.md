---
title: "Improvement: Layered Context Budget (L0–L3 Tiering) for cortex://context"
component: context-loading
work_type: feature
status: PENDING
priority: High
created: 2026-04-14
depends_on: []
---

## Goal

Replace the current flat `cortex://context` resource load with a four-layer tiered system that delivers the right amount of memory at the right cost. The goal is to reduce cold-start token usage by ~60–70% while keeping retrieval accuracy the same or better.

Inspired by MemPalace's L0–L3 context stack, which achieves a 600–900 token wake-up for six months of project history (vs. loading all memory bank content at once).

## Context

## Current behaviour

`cortex://context` currently reads several memory-bank files (activeContext.md, progress.md, roadmap.md, etc.) in full and concatenates them into the context payload. This costs 3,000–10,000+ tokens every session regardless of what the agent actually needs.

## Target behaviour

| Layer | Name | Target size | Always loaded? | Content |
|-------|------|-------------|----------------|---------|
| L0 | Identity | ≤ 150 tokens | Yes | Project name, stack, primary goal, last commit summary |
| L1 | Essential story | ≤ 800 tokens | Yes | Auto-generated from top-weighted memory-bank entries: active work, recent decisions, open blockers |
| L2 | On-demand | ≤ 500 tokens each | No — loaded when topic is active | Per-plan or per-section detail: full plan file, roadmap section, relevant wiki page |
| L3 | Deep search | Unlimited | No — on explicit request | Full hybrid search across memory bank + wiki |

L0 + L1 always ship. L2 is pulled by agent-side topic detection or explicit `cortex://context?layer=2&topic=<slug>`. L3 is triggered by `think()` or explicit `/cortex/search`.

## Motivation

- MemPalace benchmarks show 96.6% retrieval accuracy with ~900-token wake-up vs. full document load.
- Current Cortex sessions consume 3–10K tokens just for context loading before any tool call.
- L2/L3 lazy loading means 80% of sessions never pay for detail they don't use.

## Implementation Steps

## Step 1: Define the layer data contracts

File: `src/cortex/resources/context/layers.py` (new file)

1. Create `ContextLayer` enum: `IDENTITY`, `ESSENTIAL`, `ON_DEMAND`, `DEEP_SEARCH`.
2. Create `LayerResult(BaseModel)` with fields: `layer: ContextLayer`, `tokens_estimate: int`, `content: str`, `sources: list[str]`.
3. Add `ContextConfig(BaseModel)` with `max_l1_tokens: int = 800`, `max_l2_tokens: int = 500`, `l1_source_limit: int = 5`.
4. No logic in this file — pure data contracts only.

**Verification**: `from cortex.resources.context.layers import ContextLayer, LayerResult, ContextConfig` — no import errors.

## Step 2: Implement L0 identity generator

File: `src/cortex/resources/context/l0_identity.py` (new file)

1. Read project name and stack from `pyproject.toml` (cached, no re-read per call).
2. Read last commit summary via `git log -1 --oneline` (subprocess, 2s timeout, fail-safe empty string).
3. Read primary goal from `.cortex/.session/session-goal.md` (first 2 lines only).
4. Assemble into a ≤ 150-token block; truncate to `max_l0_tokens=150` if needed.
5. Return `LayerResult(layer=IDENTITY, ...)`.

Function signature: `async def build_l0(project_root: Path, config: ContextConfig) -> LayerResult`

**Verification**: Unit test — mock git, assert output ≤ 150 tokens, assert `layer == IDENTITY`.

## Step 3: Implement L1 essential story generator

File: `src/cortex/resources/context/l1_essential.py` (new file)

1. Read memory bank index (activeContext.md, progress.md) using `manage_file` internals or direct file read.
2. Score each paragraph by recency (date mentions) + keyword density (blocker/active/decision/PENDING).
3. Select top-N paragraphs up to `max_l1_tokens` budget (greedy, highest-score first).
4. Prepend section headers for readability; append `[N more entries available in L2/L3]` footer.
5. Return `LayerResult(layer=ESSENTIAL, sources=[...filenames...])`.

Scoring function must be pure (no I/O) and ≤ 30 lines. Paragraph extraction must handle both bullet-list and prose formats.

**Verification**: Unit test with synthetic memory bank content; assert token count ≤ 800; assert top-scored paragraphs include the ones with "blocker" keyword.

## Step 4: Implement L2 on-demand loader

File: `src/cortex/resources/context/l2_on_demand.py` (new file)

1. Accept `topic: str` (plan slug, roadmap section name, or wiki page title).
2. Resolve topic to file path: check `.cortex/plans/{topic}.md`, then `.cortex/memory-bank/{topic}.md`, then `.cortex/wiki/{topic}.md`, then fuzzy match (first word match).
3. Read matched file, truncate to `max_l2_tokens` (prefer truncating at paragraph boundary).
4. Return `LayerResult(layer=ON_DEMAND, sources=[resolved_path])`.
5. Return empty `LayerResult` (not an error) when topic not found.

**Verification**: Unit test — topic="fastmcp-v3-phase2" resolves to plan file; topic="nonexistent" returns empty result without raising.

## Step 5: Implement L3 deep search

File: `src/cortex/resources/context/l3_deep_search.py` (new file)

1. Accept `query: str`.
2. Scan all `.cortex/memory-bank/*.md`, `.cortex/plans/*.md`, `.cortex/wiki/*.md` files.
3. For each file, score each paragraph against `query` using BM25 (see hybrid retrieval plan for shared scorer — depend on that or implement standalone `_bm25_score(query, text) -> float` here).
4. Return top-10 paragraphs sorted by score, each with source file + line range.
5. No token cap — caller decides how much to use.

**Verification**: Integration test — query="blocker" returns paragraphs from roadmap and activeContext; score order is deterministic for same input.

## Step 6: Wire layers into `cortex://context` resource

File: `src/cortex/resources/context_resource.py` (existing)

1. Parse optional query params from resource URI: `layer` (default: `l0+l1`), `topic` (for L2), `query` (for L3).
2. Always build L0 + L1 and include them in the response.
3. If `layer` includes `l2` and `topic` is set, append L2 result.
4. If `layer` includes `l3` and `query` is set, append L3 result.
5. Add `## Context layers loaded: [L0, L1]` header to response so agents can see what was loaded.
6. Add `## Available on demand: L2 (topic=<slug>), L3 (query=<search term>)` footer.

**Verification**: Read the resource with no params — response contains L0 block, L1 block, footer. Token count of default response ≤ 1200.

## Step 7: Add session config support for default layer

File: `src/cortex/core/session_config.py` (existing)

1. Add `context_layers: list[str] = ["l0", "l1"]` field to session config.
2. `cortex://context` reads `context_layers` from session config when no URI param is provided.
3. Agents can override per-call via URI param.

**Verification**: Set `context_layers: ["l0", "l1", "l2"]` in session config with a topic set; assert L2 content appears in context resource output.

## Step 8: Tests

Files: `tests/resources/test_context_layers.py`, `tests/resources/test_context_resource.py`

1. Unit tests for L0, L1, L2, L3 builders (mock filesystem, no real git).
2. Integration test for `cortex://context` default response: assert ≤ 1200 tokens, assert L0 and L1 headers present.
3. Integration test for L2: assert on-demand content appended when topic param set.
4. Token count helper: `count_tokens(text: str) -> int` using `len(text.split()) * 1.3` approximation (good enough for budget checks; no tiktoken dependency needed).

## Dependencies

- No blocking dependencies — can be implemented standalone.
- If the hybrid retrieval plan (BM25 scorer) lands first, L3 can import its scorer instead of duplicating.

## Success Criteria

- [ ] Default `cortex://context` response ≤ 1,200 tokens (down from 3,000–10,000 baseline).
- [ ] L2 on-demand loader resolves plan slugs, memory bank entries, and wiki pages.
- [ ] L3 deep search returns ranked paragraphs for any query string.
- [ ] All new files ≤ 400 lines, all functions ≤ 30 lines, no `Any` types.
- [ ] 95%+ test coverage for layers module.
- [ ] Existing `cortex://context` contract (content type, non-empty response) unchanged for callers that don't use new params.

## Testing Strategy

- **Unit**: L0 builder (mock git + session file), L1 scorer (synthetic paragraphs), L2 resolver (mock filesystem tree), L3 BM25 scorer (deterministic scoring).
- **Integration**: Resource endpoint with real memory-bank fixture; verify token budget and layer headers.
- **Regression**: All existing `cortex://context` callers still get non-empty responses; no KeyError on missing optional params.
- Target: 95% line coverage for all new files.
