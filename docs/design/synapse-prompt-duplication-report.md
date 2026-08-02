# Synapse Prompt Duplication Report

**Date**: 2026-08-02
**Plan**: Shared Prompt Reference Layer for Synapse Prompts
**Verdict**: **Do not extract.** Measured extractable share is **0.19%**, far below the
plan's own 15% abort threshold.

## Method

`scripts/measure_prompt_duplication.py` reads every `.cortex/synapse/prompts/*.md` file,
estimates tokens with the 4-chars-per-token heuristic, and finds every block of N or more
consecutive lines appearing in M or more distinct prompt files. The plan fixed the
extraction threshold at **three or more consuming prompts** (`--min-block 3 --min-files 3`),
so that setting is the decision-relevant one.

Reproduce with:

```bash
uv run python scripts/measure_prompt_duplication.py --min-block 3 --min-files 3
```

## Baseline

- **Total**: 2,771 lines / 39,894 estimated tokens across 13 prompt files.

| File | Lines | Tokens |
|------|-------|--------|
| `fix.md` | 437 | 9121 |
| `commit.md` | 457 | 7268 |
| `do.md` | 387 | 5615 |
| `review.md` | 324 | 4510 |
| `plan.md` | 246 | 3459 |
| `analyze.md` | 261 | 2642 |
| `post-prompt-hook.md` | 115 | 1579 |
| `do-loop.md` | 148 | 1368 |
| `init-wiki.md` | 106 | 1368 |
| `shape.md` | 93 | 1085 |
| `ask.md` | 75 | 959 |
| `explore.md` | 66 | 484 |
| `ingest.md` | 56 | 436 |

## Duplicate blocks at the plan threshold (>=3 lines, >=3 files)

Only three blocks qualify, totalling **76 redundant tokens (0.19% of baseline)**.

| Files | Tokens/copy | Redundant | First line | Occurrences (file:line) |
|-------|-------------|-----------|------------|-------------------------|
| 6 | 6 | 30 | *(blank line)* | analyze.md:224, commit.md:417, do.md:343, fix.md:388, plan.md:217, review.md:278 |
| 6 | 6 | 30 | ` ```markdown ` | analyze.md:225, commit.md:418, do.md:344, fix.md:389, plan.md:218, review.md:279 |
| 3 | 8 | 16 | `## Next` | analyze.md:241, commit.md:440, do.md:367 |

All three are fragments of the final-report template scaffold — a blank line, a fence
opener, and a section heading. There is no substantive shared prose.

## Sensitivity analysis

Relaxing the thresholds does not rescue the case:

| Min block | Min files | Blocks | Redundant tokens | % of baseline |
|-----------|-----------|--------|------------------|---------------|
| >=3 lines | >=3 files | 3 | 76 | 0.19% |
| >=2 lines | >=3 files | 1 | 30 | 0.08% |
| >=3 lines | >=2 files | 60 | 2377 | 5.96% |
| >=2 lines | >=2 files | 20 | 699 | 1.75% |

Even at `>=3 lines, >=2 files` — which violates the plan's own three-consumer rule and
would produce exactly the "indirection without benefit" fragments the plan's risk table
warns against — the ceiling is 5.96%.

The largest pairwise blocks are concentrated in two pairs:

| Files | Redundant | First line | Occurrences |
|-------|-----------|------------|-------------|
| 2 | 112 | manage_file zero-arg fallback bullet | commit.md:60, do.md:66 |
| 2 | 95 | `Record: mistake patterns, root causes, …` | analyze.md:55, post-prompt-hook.md:36 |
| 2 | 91 | `Session scope risk check: detect multi-goal sessions …` | analyze.md:57, post-prompt-hook.md:38 |
| 2 | 79 | ``Read the `cortex://analysis` resource …`` | analyze.md:39, post-prompt-hook.md:22 |
| 2 | 76 | `- Confirm **one primary goal** early in the session …` | analyze.md:19, commit.md:19 |
| 2 | 66 | ``- **For `validate`**: read the `cortex://validation` …`` | commit.md:59, do.md:67 |

## Why the premise did not hold

The plan assumed the orientation preamble, MCP error-handling block, path-resolution
block, execution-continuity gate, and final-report rules were duplicated near-verbatim
across most prompts. Measurement shows they are not:

- **Final-report rules** already live in `docs/guides/synapse-final-report-templates.md`;
  prompts reference that guide and only inline a short per-pipeline table, so the shared
  text is already factored out.
- **Orientation** is phrased per-prompt with pipeline-specific resources and gates, so no
  three prompts share three consecutive identical lines.
- **Cursor arg-stripping / path-resolution** guidance is genuinely shared by exactly two
  prompts (`commit.md`, `do.md`), below the extraction threshold.
- **Execution continuity** appears as prompt-specific stop conditions, not shared prose.

The one real pair-level cluster is `analyze.md` / `post-prompt-hook.md` (~430 redundant
tokens), which is a two-file overlap best handled, if ever, by one prompt referencing the
other — not by a manifest-driven include layer.

## Cost of proceeding anyway

Building the reference layer would require a `shared` manifest category, an include
resolver with cycle detection and path-traversal rejection, equivalence snapshots for all
13 prompts, and new tests — several hundred lines of load-bearing production code and a
new runtime failure mode (truncated prompts) — to recover under 80 tokens, or under 2,400
tokens in the threshold-violating variant. Both are dominated by the maintenance and
correctness risk.

## Recommendation

Close the plan as a recorded negative result. Keep
`scripts/measure_prompt_duplication.py` as a standing measurement tool: if prompt
duplication grows past 15% as new prompts are added, re-open the extraction plan with
fresh evidence.
