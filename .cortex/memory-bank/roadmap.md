# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### FastMCP v3 Migration

### Fixes

### Quality & Reliability Improvements

### Security

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

- Plan: [Fix: Add Missing Makefile Offline Targets](../plans/archive/Other/fix-makefile-offline-targets.md)

### Improvements

- [ ] **Improvement: Layered Context Budget (L0–L3 Tiering) for context resource** — Replace flat context loading with a 4-layer tiered system: L0 identity (~150 tokens), L1 essential story (~800 tokens, always loaded), L2 on-demand per topic, L3 deep search. Target: default response ≤ 1,200 tokens (down from 3–10K). Plan: [../plans/improve-layered-context-budget.md](../plans/improve-layered-context-budget.md) (PENDING)
- [ ] **Improvement: Temporal Memory with Validity Windows** — Add SQLite-backed temporal store with valid_from/valid_to fields so agents can query 'what was true on date X'. Includes contradiction detection and new memory_timeline MCP tool. Plan: [../plans/improve-temporal-memory.md](../plans/improve-temporal-memory.md) (PENDING)
- [ ] **Improvement: Typed Memory Classification for Memory Bank Entries** — Auto-classify every memory write into decision/preference/milestone/problem/status buckets using pure regex heuristics. Enables read_by_type retrieval and type-weighted L1 context scoring. Plan: [../plans/improve-typed-memory-classification.md](../plans/improve-typed-memory-classification.md) (PENDING)
- [ ] **Improvement: Hybrid BM25 + Keyword Retrieval for Memory Bank Search** — Add Okapi BM25 scorer (pure Python stdlib, no external deps) to all memory bank retrieval paths. Adds manage_file(operation='search') MCP operation with ranked paragraph results. Plan: [../plans/improve-hybrid-bm25-retrieval.md](../plans/improve-hybrid-bm25-retrieval.md) (PENDING)
- [ ] **Improvement: Memory Write-Ahead Log for Audit Trail and Rollback** — WAL that records every memory bank mutation to a dedicated write-log stream. Enables anomaly detection (shrink > 30%), snapshot, and restore. Adds memory_wal MCP tool. Plan: [../plans/improve-memory-write-ahead-log.md](../plans/improve-memory-write-ahead-log.md) (PENDING)

#### Knowledge Base & Wiki (High Priority)

#### Token Efficiency (High Priority)

### Features & Enhancements

#### Token Efficiency (Medium Priority)

#### Claude Code Harness Improvements (High Priority)

#### Planning & Brainstorming (High Priority)

#### Planning & Brainstorming (Medium Priority)

#### Wiki for Attached Projects (High Priority)

#### Planning & Brainstorming (Low Priority)
