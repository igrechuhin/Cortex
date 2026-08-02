---
title: "Shared Prompt Reference Layer for Synapse Prompts"
component: "synapse-prompts"
work_type: "refactor"
status: PENDING
priority: "Medium"
created: "2026-08-02"
depends_on: []
---

## Goal

Extract boilerplate duplicated across the Synapse prompt files into a `.cortex/synapse/prompts/_shared/` reference layer, referenced by manifest rather than copy-pasted, reducing total prompt tokens by a measured amount without changing any prompt's behavior.

## Context

The Synapse prompts total 2,989 lines across 13 files. Several blocks are duplicated near-verbatim in most of them: the orientation preamble (`session()` → `cortex://context` → `cortex://rules`), the MCP error-handling and circuit-breaker block, the path-resolution block, the execution-continuity gate, and the final-report format rules.

The aihero.dev skills pack attributes a 63% token reduction in its v1.0 to exactly this split: user-invocable skills versus *reference* skills that other skills invoke and that never appear in a user-facing list. Cortex already applies this idea to rules (`cortex://rules`, `rules/_templates`) but not to prompts.

Two files in `prompts/` are a related smell: `REFACTORING_GUIDE.md` (149 lines) and `REFACTORING_SUMMARY.md` (178 lines) sit alongside executable prompts without being prompts. They are development notes and belong under `docs/`, not in the prompt directory where they inflate any directory-wide read.

## Scope

**in_scope**

- New `.cortex/synapse/prompts/_shared/` directory holding extracted reference fragments
- Extraction of duplicated blocks: orientation preamble, MCP error handling, path resolution, execution continuity, final-report format
- Manifest support for a `shared` category and a per-prompt `includes` list
- Relocation of `REFACTORING_GUIDE.md` and `REFACTORING_SUMMARY.md` out of `prompts/` to `docs/`
- Before/after token measurement recorded in the plan's completion note
- Tests for manifest parsing and fragment resolution

**out_of_scope**

- Any change to prompt *semantics* — this is a pure extraction; behavior must be byte-equivalent after resolution
- The `.wf.js` workflow files (`commit.wf.js`, `do.wf.js`, `fix.wf.js`)
- Rules or wiki content
- The new `shape.md` prompt (separate plan; it should consume the shared layer once both land)

## Approach

Work in three passes. First, measure: script a token count per prompt file and produce a duplication report identifying every block appearing in three or more files, so extraction targets are chosen from evidence rather than intuition. Second, extract the highest-yield blocks into `_shared/` fragments with stable names, and replace each occurrence with an include directive. Third, teach the manifest and the prompt-loading path to resolve includes, so a consumer reading a prompt gets the fully composed text.

Resolution happens at load time, not authoring time, which keeps the on-disk prompts short while the agent still receives complete instructions. The correctness bar is strict equivalence: for every prompt, the resolved text must match the pre-refactor text modulo whitespace. That check is mechanizable and becomes the primary test.

The file relocation is independent and can land first as a trivial low-risk slice.

## Implementation Steps

1. Write a one-off measurement script under `scripts/` that reports per-file token counts for `.cortex/synapse/prompts/*.md` and records the baseline total.
2. Produce a duplication report: identify every block of three or more consecutive lines appearing in three or more prompt files.
3. Move `REFACTORING_GUIDE.md` and `REFACTORING_SUMMARY.md` to `docs/guides/`; update any inbound references found by grep.
4. Create `.cortex/synapse/prompts/_shared/` and extract the highest-yield blocks from the report into named fragments (for example `orientation.md`, `mcp-error-handling.md`, `path-resolution.md`, `execution-continuity.md`, `final-report.md`).
5. Add a `shared` category and a per-prompt `includes: []` field to `prompts-manifest.json`.
6. Implement include resolution in the prompt-loading path: read fragments, splice at the include marker, fail loudly on an unknown fragment name.
7. Replace duplicated blocks in each prompt with include markers, one prompt per commit-sized change.
8. Add an equivalence test asserting each resolved prompt matches its pre-refactor snapshot modulo whitespace.
9. Re-run the measurement script; record the before/after totals and the percentage reduction.
10. Run `run_quality_gate()` and `run_docs_gate()` until clean.

## Verification Checklist

- Step 2: confirm the duplication report is written to a file and cites concrete line ranges, not summaries.
- Step 3: grep the repository for `REFACTORING_GUIDE` and `REFACTORING_SUMMARY`; confirm zero stale references remain.
- Step 4-5: re-read `prompts-manifest.json`; confirm valid JSON and that every fragment on disk is declared.
- Step 6: grep the prompt-loading path for the fragment reader; confirm unknown-fragment failure is raised, not silently skipped.
- Step 7: after each prompt is converted, re-read it and confirm every include marker resolves.
- Step 8: confirm snapshots were captured *before* extraction began, not regenerated afterward.
- Step 9: confirm both baseline and final token totals are recorded.

## Dependencies

None hard. Should land before the `shape.md` plan's prompt is finalized so `shape.md` can consume the shared layer from the start rather than being retrofitted; if `shape.md` lands first, retrofitting it is a step of this plan.

## Success Criteria

- `.cortex/synapse/prompts/_shared/` exists with at least four extracted fragments, each used by three or more prompts
- Every prompt's resolved text matches its pre-refactor snapshot modulo whitespace
- `REFACTORING_GUIDE.md` and `REFACTORING_SUMMARY.md` no longer live under `prompts/`, with no stale references
- Measured token reduction across `prompts/*.md` is recorded with before and after figures
- An unknown fragment name fails loudly rather than silently resolving to empty
- `run_quality_gate()` and `run_docs_gate()` both pass
- New code paths reach the 95% coverage target

## Testing Strategy

Target 95% coverage on changed lines, AAA pattern, `tests/prompts/test_shared_fragments.py`.

- Unit — positive: fragment resolves and splices at the marker; a prompt with multiple includes resolves all of them; a prompt with no includes is returned unchanged.
- Unit — negative: unknown fragment name raises; fragment path traversal rejected; circular include detected and rejected; empty fragment file handled explicitly.
- Snapshot/equivalence: for every prompt in the manifest, resolved text equals the pre-refactor snapshot modulo whitespace. This is the load-bearing test.
- Manifest: `prompts-manifest.json` parses; every declared fragment exists on disk; every on-disk fragment is declared.
- Docs: markdown lint over `_shared/*.md`.

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Extraction silently changes a prompt's meaning | Agents misbehave in ways tests do not catch | Equivalence snapshots captured before any extraction; strict modulo-whitespace match is the primary gate |
| Include resolution fails at runtime, agent gets a truncated prompt | Silent capability loss, very hard to diagnose | Unknown fragment raises loudly; manifest test asserts declared and on-disk fragments match both ways |
| Over-extraction produces fragments used by only one prompt | Indirection without benefit; harder to read | Extraction threshold fixed at three or more consuming prompts, chosen from the duplication report |
| Token reduction is marginal and the churn is not worth it | Wasted effort | Step 1 measures the baseline first; if the duplication report shows under 15% extractable, stop and record the finding instead of proceeding |
| Circular includes | Infinite loop at load time | Cycle detection with an explicit error; covered by a negative test |

## Measurement Outcome (2026-08-02) — ABORT CONDITION TRIGGERED

Steps 1-3 executed. Step 2's duplication report is at
[docs/design/synapse-prompt-duplication-report.md](../../docs/design/synapse-prompt-duplication-report.md).

At this plan's own extraction threshold (blocks of >=3 consecutive lines shared by >=3
prompts), the extractable share of the 39,894-token prompt corpus is **76 tokens =
0.19%** — three blocks, all fragments of the final-report scaffold (a blank line, a
` ```markdown ` fence opener, and `## Next`). Even relaxing to >=2 consuming prompts, which
violates the plan's three-consumer rule, caps the yield at 5.96%.

This is below the 15% floor set in the Risks table ("if the duplication report shows under
15% extractable, stop and record the finding instead of proceeding"). **Steps 4-9 are
therefore not executed.** No `_shared/` directory, no manifest `includes` field, and no
include resolver were created.

Delivered:

- `scripts/measure_prompt_duplication.py` — standing measurement tool (per-file token
  counts + cross-file duplicate-block detection with configurable thresholds).
- `tests/unit/test_measure_prompt_duplication.py` — unit tests for the tool.
- `docs/design/synapse-prompt-duplication-report.md` — the evidence report with concrete
  file:line ranges and sensitivity analysis.
- Step 3 relocation confirmed already complete: the refactoring notes live at
  `docs/guides/synapse-prompt-refactoring-guide.md` and
  `docs/guides/synapse-prompt-refactoring-summary.md`; no stale references under
  `prompts/`.

Re-open trigger: re-run the script if the prompt corpus grows substantially; extraction
becomes worthwhile only if measured duplication exceeds 15%.

## Change History

*No revisions recorded yet — enrich or edit implementation steps to append history.*
