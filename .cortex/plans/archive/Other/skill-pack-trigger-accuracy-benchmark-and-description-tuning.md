---
title: "Skill Pack Trigger Accuracy Benchmark and Description Tuning"
component: "tools"
work_type: optimize
status: PENDING
priority: Medium
created: 2026-08-06
depends_on: []
---

## Goal

Build a labeled benchmark that measures the precision and recall of `skill_pack(operation="discover")`, fix the zero-signal fallback that currently guarantees a false recommendation, and tune each pack's `description`, `when_to_use`, and `keywords` against the measured baseline.

## Context

`skill_pack(operation="discover")` decides which of the twelve manifests under `src/cortex/resources/skills/` to recommend for a given task. The whole mechanism rests on `_score_pack_for_task` in `src/cortex/tools/skill_pack/operations.py`, which is a naive substring scorer: `+2` when the pack name appears in the task text, `+1` per matching keyword, and `+1` when any single word of `when_to_use` appears in the task. Ranking is that integer score, tie-broken by pack name.

Two problems follow, and neither is currently measured.

First, there is a guaranteed false positive. `_do_discover` filters to packs scoring above zero, but when that filter yields nothing it falls back to `scored[0][1]` — the first pack in name order, with a score of zero. An agent asking about something no pack covers receives a confident recommendation derived from no signal at all. The result even carries the reason string "Keywords or description match" when the score is positive, so a zero-score fallback arrives with no reason and no indication that it was a guess.

Second, single-word matching against `when_to_use` is extremely loose. Common words in a `when_to_use` sentence match almost any task description, so the `+1` fires on noise. Combined with per-keyword `+1`, a pack with many keywords outranks a genuinely more relevant pack with few, purely as a function of manifest verbosity rather than fit.

Nothing measures any of this. There are no fixtures mapping a task description to the pack that should be recommended, so every edit to a manifest description is currently unverifiable — an author cannot tell whether a reworded `when_to_use` improved triggering or silently broke it.

`skills/skill-creator/scripts/improve_description.py` in the local `~/Repo/skills` checkout addresses exactly this problem for Anthropic's own skills: it optimizes a skill's description specifically for triggering accuracy, and the surrounding `run_eval.py` and `aggregate_benchmark.py` scripts measure it with variance analysis. The measurement discipline transfers directly even though Cortex's manifest format and scorer are its own.

`docs/DISCOVERY_ELICITATION_SPEC.md` in the local `~/Repo/jcode` checkout supplies the fixture discipline. It is the authoring contract for a paired eval asking the same shape of question — does the agent reach for the right capability given only its description — and its governing rule is the one this plan most needs: raising a trigger rate by writing a more insistent description is trivial and bad, so a run that reports recall without its paired false-positive rate is not a valid result. Its `gap`/`control`/`near-miss` taxonomy is adopted below.

## Measurement Contract

The benchmark measures one thing: whether a pack's **`description`, `when_to_use`, and `keywords`** are sufficient to trigger it on the tasks it covers and to stay silent on the tasks it does not. It is not a test of whether a pack's workflow works.

**Every fixture declares one `kind`.**

| kind | meaning | correct behavior | scored as |
|------|---------|------------------|-----------|
| `positive` | The task is genuinely served by the pack in `expected_pack`. | Recommend that pack at rank 1. | Hit if top-1 is `expected_pack`. |
| `control` | No pack applies; the task is served by ordinary tool use. | Recommend nothing. | Any recommendation is a false positive. |
| `near-miss` | The task sits squarely in one pack's subject area but is actually served by a *different* pack, or by a direct tool call needing no pack at all. | Recommend the covering pack, or nothing. | Recommending the tempting pack is a false positive, reported separately. |

`near-miss` is the adversarial half and the half that catches what the current plan would otherwise miss. The failure mode of manifest tuning is not silence — it is a pack whose reworded `when_to_use` starts winning tasks that belong to its neighbour. A fixture set of positives plus pure no-match controls cannot see that: every fixture still scores as a hit for *someone*. Only a case that names the tempting pack and the correct one exposes it.

A `near-miss` fixture **must** name what actually covers the task in a `covered_by` field — either another pack's name or the explicit marker for "no pack needed, direct tool use". If nothing covers it, the fixture is a `control`, not a `near-miss`. If the tempting pack is in fact the right answer, it is a `positive`.

**A benchmark run that reports recall or top-1 accuracy without its paired false-positive rates is not a valid result** and the runner must refuse to emit one. `control` and `near-miss` false positives are reported as separate figures, never pooled, because a near-miss failure is the more expensive one: it hands the agent a confidently wrong workflow rather than merely a redundant one.

**Invariance.** The score must move only when a manifest's `description`, `when_to_use`, or `keywords` change, or when the scorer changes. Adding a pack, editing a pack's `workflow`, or changing tool implementations must leave it flat. A number that drifts on unrelated edits is measuring the wrong thing.

**Stable ids.** Each fixture carries a permanent kebab-case `id`. Per-fixture results are tracked across manifest revisions — that history is what makes step 9's "which edit caused this regression" question answerable — so renaming an id destroys it. Retire a fixture by deleting it, never by repurposing its id.

Note on vocabulary: the project glossary defines "Skill" as a host-provided capability distinct from Cortex's prompts. Cortex's "skill pack" is a different thing — a manifest describing an MCP tool workflow — and is not currently a glossary term. This plan uses "skill pack" throughout and adds the term to the glossary.

## Scope

**in_scope**

- A labeled fixture set mapping task descriptions to the pack or packs that should be recommended, with a permanent `id` and a `kind` (`positive` / `control` / `near-miss`) on every fixture and a `covered_by` required on and only on `near-miss`.
- Negative fixtures: at least five `control` cases where no pack applies, and at least five `near-miss` cases drawn from adjacent pack pairs.
- A benchmark runner reporting precision, recall, and top-1 accuracy of `_score_pack_for_task` and `_do_discover` against those fixtures, paired with separately reported `control` and `near-miss` false-positive rates, and refusing to emit accuracy at all when either negative kind is absent.
- Fixing the zero-signal fallback so a no-match query reports no recommendation rather than an arbitrary pack.
- Making the reason string honest, including when a recommendation is weak or absent.
- Tuning `description`, `when_to_use`, and `keywords` across the twelve existing manifests to improve measured accuracy.
- Adding "skill pack" to `.cortex/wiki/glossary.md` with aliases and confusable terms.
- Recording the before and after benchmark numbers in the plan's completion notes.

**out_of_scope**

- Replacing the substring scorer with embeddings, an LLM ranker, or any model call at discovery time — discovery must stay fast and dependency-free.
- Changing the `SkillPackManifest` schema or the `workflow` execution path.
- Adding new skill packs or removing existing ones.
- Changing `skill_pack(operation="load")` or `operation="execute"`.
- Adopting `improve_description.py` as a runtime dependency; it is a reference for method, not code to vendor.
- Reconciling Cortex skill packs with the external Agent Skills format (separate assessment plan).

## Approach

Measure before touching anything. The first deliverable is the fixture set and the benchmark runner, producing a baseline number for the current scorer. Without that baseline every subsequent manifest edit is unfalsifiable, and manifest wording is exactly the kind of change that feels like an improvement while making things worse.

Fixtures must include negative cases, of both kinds. The zero-signal fallback bug is only visible when a task genuinely matches no pack, so a fixture set built solely from positive examples would score the current behavior as fine — that is what the `control` cases are for. But controls alone do not constrain step 9: manifest tuning fails by stealing a neighbour's tasks, not by going quiet, and against a positives-plus-controls set that failure is invisible because every fixture still resolves to some pack. The `near-miss` cases are what make the tuning step falsifiable, and they should be authored *before* any wording is touched, from adjacent pack pairs identified in step 1.

Pairing is enforced in the runner, not by convention. Accuracy is computed only when the fixture set contains at least one `control` and one `near-miss`; otherwise the runner returns the reason and no number. This is the single mechanism preventing step 9 from becoming a description-inflation ratchet, so it belongs in code.

Fix the fallback before tuning wording, because the fallback distorts every measurement taken while it is in place. The corrected behavior is to return an empty recommendation list with a clear reason when no pack scores above zero, and to keep the score visible in the result so a caller can distinguish a strong match from a marginal one.

Only then tune the manifests, re-running the benchmark after each change so improvements and regressions are both attributable. Borrow the method from `improve_description.py` — write the description to describe *when* the pack applies, not merely what it does — but apply it by hand against the benchmark rather than by generating descriptions with a model call.

Scoring-weight changes are permitted where the benchmark justifies them, in particular tightening the `when_to_use` match from any-single-word to a phrase or multi-word requirement. Any weight change must be shown to improve the measured numbers, not adopted on intuition.

## Implementation Steps

1. Read all twelve manifests under `src/cortex/resources/skills/` and record each pack's current `description`, `when_to_use`, and `keywords`. While reading, list the adjacent pack pairs — packs whose subject areas genuinely overlap — and carry that list into step 2 as the source of `near-miss` cases.
2. Write the labeled fixture set as JSON. Every fixture carries a permanent kebab-case `id`, a `kind`, and a realistic task description. Cover every pack with at least one `positive`, add at least five `control` cases matching no pack, and add at least five `near-miss` cases from the step 1 adjacency list, each naming the tempting pack in `expected_pack` and the real answer in `covered_by` (another pack name, or the explicit no-pack-needed marker).
3. Implement a benchmark runner that scores every fixture through `_score_pack_for_task` and `_do_discover` and reports, as distinct fields: top-1 accuracy and recall over `positive` fixtures, the `control` false-positive rate, the `near-miss` false-positive rate, and the full list of misclassified fixtures by id. When either negative kind is absent, the runner returns the reason and omits the accuracy fields entirely.
4. Run the benchmark and record the baseline numbers — all four figures, not just accuracy — including how many `control` fixtures receive a spurious recommendation today and how many `near-miss` fixtures resolve to the tempting pack.
5. Fix `_do_discover`: when no pack scores above zero, return an empty recommendation list with an explicit reason rather than `scored[0][1]`.
6. Make the per-pack reason string reflect the actual match, and include the numeric score in the result so callers can judge confidence.
7. Re-run the benchmark and record the post-fix numbers.
8. Tighten the `when_to_use` contribution in `_score_pack_for_task` from any-single-word to a multi-word or phrase match, and re-run the benchmark; keep the change only if the measured numbers improve.
9. Tune `description`, `when_to_use`, and `keywords` per manifest, re-running the full benchmark after each manifest so regressions are attributable to a single edit. An edit is kept only when top-1 accuracy improves **and** neither false-positive rate worsens; an accuracy gain paid for with a higher `near-miss` rate is a regression and is reverted.
10. Add a "Skill pack" entry to `.cortex/wiki/glossary.md` following the three-bullet entry schema, with "Not to be confused with" naming skill and prompt.
11. Write unit tests covering the corrected fallback, the reason strings, the score exposure, and the tightened matcher.
12. Run `run_quality_gate()` and `run_docs_gate()` and resolve every finding.

## Verification Checklist

- Step 2: confirm every one of the twelve packs appears as the expected answer in at least one `positive` fixture; grep the fixture file for each manifest `name`. Confirm all fixture ids are unique, that every `near-miss` names a `covered_by`, and that no `control` carries one.
- Step 3: confirm the runner is deterministic — run it twice and assert identical output. Then delete the `near-miss` fixtures temporarily and confirm the runner emits no accuracy figure at all rather than falling back to a positives-only number.
- Step 4: if the baseline `near-miss` false-positive rate is zero, treat the cases as too weak and strengthen them before proceeding — a set the current naive substring scorer already passes is not exercising anything.
- Step 5: re-read `_do_discover` and confirm no path returns a pack whose score is zero.
- Step 6: grep for the literal reason string "Keywords or description match" and confirm every remaining use corresponds to an actual positive match.
- Step 8: record both the pre-change and post-change benchmark numbers in the plan notes; revert if not improved.
- Step 9: after each manifest edit, confirm no previously passing fixture regressed.
- Step 10: re-read the glossary entry and confirm it follows the exact three-bullet schema used by surrounding entries.
- Step 12: re-read every file the gates modified.

## Dependencies

- None on other Cortex plans.
- No runtime dependencies added.
- Reference for method only: `~/Repo/skills/skills/skill-creator/scripts/improve_description.py` and `aggregate_benchmark.py`.
- Reference for method only: `~/Repo/jcode/docs/DISCOVERY_ELICITATION_SPEC.md` (MIT) — paired eval design, `gap`/`control`/`near-miss` taxonomy, `covered_by` requirement, stable-id and invariance rules. No code is taken from that repository.

## Success Criteria

- A labeled fixture set exists covering all twelve packs, plus at least five `control` and at least five `near-miss` cases; every fixture has a unique permanent id and every `near-miss` names its `covered_by`.
- The benchmark runner reports precision, recall, and top-1 accuracy deterministically, always paired with separately reported `control` and `near-miss` false-positive rates, and emits no accuracy figure when either negative kind is missing.
- The post-tuning `near-miss` false-positive rate is no worse than the recorded baseline, and both numbers are written down alongside the accuracy figures.
- A task matching no pack yields an empty recommendation with an explicit reason; zero spurious recommendations remain on no-match fixtures.
- Every recommendation carries a reason that reflects its actual match, and its numeric score is visible to the caller.
- Post-tuning top-1 accuracy is measurably higher than the recorded baseline, with both numbers written down.
- "Skill pack" is defined in the glossary.
- Test coverage for changed modules is at least 95%; both gates report zero errors.

## Testing Strategy

Target 95% coverage on changed code, AAA pattern, fully deterministic with no model calls.

- Unit — fallback: a task matching no pack returns an empty recommendation list and a reason indicating no match; assert the old arbitrary-pack behavior is gone.
- Unit — scoring: name match scores above keyword-only match; a pack with many keywords does not outrank a genuinely closer pack on verbosity alone.
- Unit — reason strings: positive match, weak match, and no match each produce a distinct and accurate reason.
- Unit — tightened matcher: a task sharing one common word with `when_to_use` no longer scores on that basis alone, while a genuine phrase match still does.
- Unit — fixture validation: `near-miss` without `covered_by` rejected; `control` with `covered_by` or with an `expected_pack` rejected; duplicate ids rejected; unknown `kind` rejected rather than silently defaulted.
- Unit — pairing enforcement: a fixture set with no `near-miss`, and one with no `control`, each yield a result carrying the reason and no accuracy fields; a complete set yields accuracy plus both false-positive rates as distinct fields, never pooled into one number.
- Unit — near-miss scoring: recommending the tempting pack counts as a false positive; recommending the `covered_by` pack, or nothing when `covered_by` is the no-pack marker, passes.
- Integration — benchmark: run the full fixture set and assert the reported metrics match hand-computed values for a small fixed subset, including both false-positive rates.
- Regression — invariance: add a throwaway pack manifest with an unrelated subject area and confirm every existing fixture's per-id result is unchanged; edit a pack's `workflow` without touching its description and confirm all four figures are unchanged.
- Negative — empty task description, whitespace-only description, and a description matching every pack; each is handled without a crash.
- Regression — `skill_pack` load and execute paths are unchanged; existing skill-pack tests pass unmodified.

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Fixtures encode the author's assumptions rather than real usage | Benchmark optimizes for the wrong target | Derive task descriptions from real prompt and workflow wording already in the repository; include no-match cases to prevent trivially passing |
| Removing the fallback leaves agents with no recommendation | Perceived regression in usefulness | Correct behavior is an honest empty result; the reason string tells the agent to proceed without a pack rather than guessing |
| Manifest tuning overfits to the fixtures | Better benchmark, no real improvement | Keep fixtures broad, tune wording toward when-to-use clarity rather than fixture keywords, and re-check misclassified lists rather than only the aggregate |
| Tuning raises recall by making descriptions more insistent | A pack starts winning its neighbour's tasks; benchmark improves while discovery degrades | `near-miss` fixtures over adjacent pack pairs; an edit is kept only when accuracy improves and neither false-positive rate worsens; pairing enforced in the runner so no positives-only number can be reported |
| `near-miss` cases are too easy and pass at baseline | False confidence in the pairing | Step 4 treats a zero baseline `near-miss` rate as evidence the cases are too weak and blocks progress until they are strengthened |
| Fixture ids renamed while tuning | Per-fixture history lost, so step 9 attribution breaks | Ids permanent, retired only by deletion; uniqueness asserted by test |
| Scoring-weight change regresses an unmeasured case | Silent loss of a working recommendation | Weight change is gated on measured improvement and reverted otherwise; full fixture set re-run after every edit |
| "Skill pack" versus glossary "Skill" confusion persists | Terminology drift in future plans | Explicit glossary entry with "Not to be confused with" naming skill and prompt |
| Benchmark rots as packs are added later | Coverage silently drops | Fixture completeness check in step 2 is written as a test asserting every manifest name appears at least once |

## Benchmark Results (completion notes)

Fixture set: 24 fixtures — 12 `positive` (one per pack), 5 `control`, 7 `near-miss`.
Baseline constants are locked in `tests/tools/test_skill_pack_trigger_benchmark.py`.

| Stage | Top-1 | Recall | Precision | Control FP | Near-miss FP |
|-------|-------|--------|-----------|------------|--------------|
| Baseline (old scorer + zero-signal fallback) | 0.9167 | 0.9167 | 0.4583 | 1.0000 | 0.2857 |
| After fallback fix + tightened matcher | 0.9167 | 1.0000 | 0.5500 | 0.2000 | 0.2857 |
| After manifest tuning (final) | 1.0000 | 1.0000 | 0.6667 | 0.0000 | 0.1429 |

Step 4 gate satisfied: baseline `near-miss` false-positive rate was 2/7, not zero, so the
adversarial cases were exercising the scorer and did not need strengthening.

Step 8 outcome: the tightened `when_to_use` matcher (any-single-word → non-stopword bigram)
plus `MIN_RECOMMEND_SCORE = 2` improved precision and control FP with no loss of top-1 or
recall, so the weight change was kept.

Residual, deliberately untuned: `nm-planning-vs-nopack` still resolves to the `planning`
pack. A substring scorer cannot separate a read-only question about a plan file from actual
planning work; every wording fix attempted either regressed `pos-planning-roadmap-entry` or
was fixture overfitting. Near-miss FP is 1/7, half the baseline.

Coverage note: per-module coverage for `scoring.py` and `benchmark.py` could not be measured
directly because `pytest-cov` conflicts with the `beartype` import hook in this repo
(`ImportError: cannot import name 'claw_state'` — pre-existing, unrelated to this plan).
Project-wide coverage from the quality gate is 0.9139; all 28 new tests pass.
