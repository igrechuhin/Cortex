---
title: "Content-Preserving WAL for AS-OF Reconstruction"
component: "memory"
work_type: "feature"
status: READY
priority: "Low"
created: "2026-07-19"
depends_on: ["unified-experience-store", "analyze-experience-graph-queries"]
---

## Goal

Extend the memory-bank WAL to store content deltas (not just hashes and byte counts) keyed by experience-store step numbers, enabling AS-OF reconstruction of what any memory-bank file said at the moment an agent made a given decision.

## Context

The Experience Graphs paper (arXiv:2606.29823) uses a step-numbered change log to reconstruct exactly what the agent knew at any point, preventing future-information leaks in analysis and training data. Cortex's WAL (`.cortex/wal/write_log.jsonl`) records only hashes and byte deltas — content cannot be reconstructed and there is no AS-OF view. The prior analysis marked this as the cheapest item to defer, worth building only after the analyze rewiring (plan `analyze-experience-graph-queries`) proves valuable — this plan should be executed only once that condition holds. Use cases: honest post-mortems ("what did the memory bank say when this decision was made") and debugging memory-bank drift.

## Scope

**in_scope**

- WAL record extension: store reverse deltas (or full small-file snapshots) sufficient to reconstruct prior content, plus experience-store `step_number` linkage.
- `as_of(file, step_number)` reconstruction API returning file content at that step.
- Retention/compaction policy for delta history (size-bounded).
- Integration point: analyze pipeline can request AS-OF views when presenting evidence.

**out_of_scope**

- Rewriting historical WAL entries (reconstruction starts from feature enablement).
- Versioning of files outside `.cortex/memory-bank/`.
- Git-based versioning replacement — WAL deltas complement, not replace, git history.

## Approach

Extend the WAL writer to compute a compact reverse delta (unified-diff or bsdiff-style for text) on each memory-bank write and append it to the log entry, tagged with the current experience-store step number. Implement reconstruction by walking backward from current content applying reverse deltas to the requested step. Bound growth with a compaction pass that collapses deltas older than the retention window into periodic snapshots.

## Implementation Steps

1. Extend the WAL entry model with `reverse_delta`, `delta_codec`, and `step_number` fields (schema-versioned, additive).
2. Implement delta computation on the memory-bank write path (text diff; full snapshot fallback above a size/binary threshold).
3. Link WAL entries to the experience store's current step number at write time.
4. Implement `as_of(file_name, step_number)` reconstruction with integrity verification against stored hashes.
5. Add compaction: collapse old deltas into snapshots; enforce a configurable size budget for the WAL.
6. Expose AS-OF reads to the analyze pipeline (typed API; no direct file access).
7. Tests: round-trip reconstruction across edit sequences, compaction correctness, hash verification.
8. Update memory bank docs (systemPatterns) for the new WAL format.

## Verification Checklist

- Step 1: locate all WAL readers (`rg "write_log" src/ tests/`) and confirm old entries without deltas still parse; re-read WAL module after edits.
- Step 2: verify every memory-bank write path goes through the delta writer (`rg "memory_wal|wal" src/`).
- Step 4: reconstruction output hash must equal the recorded hash for every step in tests.
- Step 7: `run_quality_gate()` green.

## Dependencies

- Plan: `unified-experience-store` (`.cortex/plans/unified-experience-store.md`) — provides step numbers.
- Plan: `analyze-experience-graph-queries` (`.cortex/plans/analyze-experience-graph-queries.md`) — proves the value gate for this deferred item.

## Success Criteria

- For a scripted sequence of N memory-bank edits, `as_of` reproduces byte-exact content (hash-verified) at every recorded step.
- Legacy WAL entries remain readable; mixed old/new logs work.
- WAL size stays within the configured budget under compaction (test with synthetic churn).
- Quality gate green; ≥95% coverage on new WAL modules.

## Testing Strategy

- Unit tests (AAA): delta encode/decode round-trips, snapshot fallback threshold, step-number tagging.
- Integration tests: multi-edit AS-OF reconstruction, compaction then reconstruction, analyze-pipeline consumption.
- Negative cases: corrupted delta entry (detected via hash mismatch), missing step, binary files.
- Target: ≥95% coverage on new modules.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| WAL growth from storing content | Reverse deltas + compaction with size budget; snapshot only above threshold |
| Corrupted delta silently yields wrong history | Hash verification on every reconstruction; fail loudly |
| Write-path latency increase | Delta computation is small-file text diff; benchmark; async where possible |
| Feature built before value is proven | depends_on gates execution behind the analyze rewiring outcome |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
