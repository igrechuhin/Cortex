---
title: "Falsifiable Prediction Gate and Graded Miss Ledger"
component: experience
work_type: feature
status: PENDING
priority: High
created: 2026-08-31
depends_on: []
execution: agent
status: PENDING
---

## Goal

Make agent beliefs falsifiable and graded: let a Cortex session record a small, structured prediction before it edits code, grade every open prediction automatically against the next `run_quality_gate()` result, and store each hit/miss as dated evidence in the experience store, surfaced in the session brief.

## Context

`/Users/igrechuhin/Repo/arc-skill` solves 25 hidden-rule ARC-AGI-3 games with one doctrine: **a paid action is refused unless it carries a falsifiable claim, and the next frame grades that claim.** Across the campaign 7,627 predictions were graded and 443 missed; every one of the 25 games contained at least one miss, and the misses were the useful part — each one dates the exact action where the agent's model of the world and reality came apart. Two secondary findings matter here: single unbatched probes missed 37.1% of the time versus 2.9% for batched sequences of already-verified mechanics, and a one-page notes file with `Verified` / `Assumed` / `Refuted` sections was the only state that survived 115 context compactions.

Cortex has the halves but never joins them:

- **Beliefs are written but never graded.** `# BELIEF:` annotations (`.cortex/synapse/rules/general/ai-code-comments.mdc`) record assumptions in code. Nothing ever checks whether one held. A stale-BELIEF heuristic in `src/cortex/tools/evaluation/reflection.py` warns when the text goes unedited — it does not test the claim.
- **The grading frame already exists.** `run_quality_gate()` produces exactly the "next frame" a claim can be contradicted by. `feedback_from_quality_result()` in `src/cortex/tools/session/gate_feedback.py` already parses it into structured `GateError` rows (file, line, check, message).
- **The recording substrate already exists.** `record_gate_result()` (`src/cortex/experience/gate_hook.py`) runs on every quality gate from `src/cortex/tools/execution/pre_commit_zero_arg_tools.py:359` and attaches pass/fail fitness to the experience store. It is a single choke point through which every grading frame already passes.

So the prediction, the comparison, and the miss ledger are the only missing pieces. This plan adds those three and nothing else. The larger arc-skill ideas that depend on them — halting a batched step sequence at the first miss, refusing an edit outright at the `post_edit_hook` boundary, an executable-model tier — are deliberately deferred to follow-up plans, because each is worthless until predictions are actually being graded.

## Scope

**in_scope**

- A claim vocabulary of exactly seven structured forms, each contradictable by a quality-gate result or a git diff, plus free text graded as an implied `change`.
- `session(operation="predict", prediction=..., task_description=...)` to open one or more claims against the current session.
- Automatic grading of all open claims for the session at the next `run_quality_gate()`, inside the existing `record_gate_result()` call — no new call site.
- Three verdicts: `HIT`, `MISS`, `UNGRADED` (the frame carried no evidence either way), recorded honestly rather than forced into hit/miss.
- Persistence of claims and verdicts through the existing `ExperienceNode` + `store_artifact` path — no experience-store schema migration.
- A capped `predictions` line in the `session()` start brief: count of open claims plus the most recent misses.
- Doctrine: a Synapse rule for when to predict, one instruction line in the `implement-code` cursor-agent, and a documented `Refuted` section convention for `activeContext.md`.
- Unit tests for parsing, grading (all seven forms, both outcomes, plus ungradable), and the recorder path.

**out_of_scope**

- Halting a batched implementation sequence at the first miss (follow-up plan).
- Hard refusal of an edit at the `post_edit_hook` / PostToolUse boundary — this slice nudges, it does not block.
- Any executable-model / A\*-search tier analogous to arc-skill's `rules` tier.
- Automatic demotion of `Verified` notes to `Assumed` after a context change.
- Grading against anything other than a quality-gate result and a git diff (no runtime telemetry, no production signals).
- Changing the existing `# BELIEF:` comment convention or its reflection heuristic.

## Approach

The design follows arc-skill's own co-design rule — every doctrine line must be something the harness can grade — and Cortex's laziest available path to it: the grading frame and the recording hook both already exist, so the work is a vocabulary, a comparison function, and one added call.

**Vocabulary.** Mirror `arc_skill/predictions.py`: a regex table mapping claim text to typed claims, free text falling through to an implied `change`, and an empty prediction rejected outright ("an empty prediction predicts nothing"). The forms are chosen so each is decidable from a gate result or a diff:

| Form | Meaning | Graded from |
|---|---|---|
| `gate clean` | the next quality gate passes with zero errors | gate result |
| `gate fails <check>` | that named check still fails | gate checks |
| `error gone <check>@<path>` | that specific gate error disappears | `GateError` list delta |
| `test <nodeid> passes` \| `fails` | pytest node outcome | test check output |
| `coverage >= <pct>` | coverage at or above threshold | coverage check |
| `touches <path>` \| `noop <path>` | that file changes / does not | git diff |
| `change` \| `noop` | something / nothing in the diff | git diff |

Several claims join with `;`, each graded independently, one wrong part making the whole prediction a miss — as in arc-skill, where a compound claim is only as true as its weakest part.

**Grading.** A `GradingFrame` is assembled from the quality-gate result (reusing `feedback_from_quality_result` for the error rows) plus the set of changed files. `grade_claims(claims, frame)` returns a verdict per claim. Where the frame lacks the evidence — a `test` claim when no test check ran — the verdict is `UNGRADED`, never a silent pass. This mirrors arc-skill's `rules replay`, which reports gaps rather than pretending a fit.

**Persistence.** Claims and verdicts are stored the way `record_gate_fitness` already stores outcomes: an `ExperienceNode` whose `label` carries the claim, whose `artifact_ref` points at a stored JSON payload holding claim text, rationale, verdict, and the frame excerpt that decided it. This needs no schema change and inherits the existing best-effort, never-raises contract — a recording failure must never break a quality gate.

**Enforcement honesty.** arc-skill's gate is hard because the harness owns the button. Cortex does not own the editor's Edit tool, so this slice enforces by nudge: `run_quality_gate()` reports when it graded nothing because nothing was predicted, and the brief surfaces open claims. A genuinely hard gate is available later at `post_edit_hook`, and is scoped out here on purpose.

## Implementation Steps

1. **Create `src/cortex/experience/claims.py`** — Pydantic `Claim`, `ClaimKind`, `Verdict`, `ClaimVerdict`, and `GradingFrame` models; a `_PATTERNS` regex table for the seven forms; `parse_claims(text) -> list[Claim]` raising on empty input and on a malformed claim whose first word is a known keyword; free text becoming an implied `change`. Keep functions ≤30 lines and the file ≤400 lines.
2. **Add grading to `claims.py`** — `frame_from_gate_result(result, changed_files) -> GradingFrame`, reusing `feedback_from_quality_result` for error rows; `grade_claims(claims, frame) -> list[ClaimVerdict]` with one small grader per claim kind dispatched from a table, returning `UNGRADED` whenever the frame lacks the deciding evidence. Split into a second module (`claim_grading.py`) if the 400-line limit is approached.
3. **Extend `src/cortex/experience/recorder.py`** — `record_prediction(root, session_id, claims, because)` and `record_verdicts(root, session_id, verdicts)`, both modelled on `record_gate_fitness`: best-effort, swallowing storage errors, logging at WARNING with the session id as trace id, incrementing `_failure_count` on failure. Add `open_predictions(root, session_id)` returning claims recorded since the last grading.
4. **Grade inside `src/cortex/experience/gate_hook.py`** — after the existing `record_gate_fitness` call in `record_gate_result`, load open predictions for the session, build the frame from `result` plus changed files, grade, and record verdicts. Wrap in the same never-raises guarantee; a grading failure must leave the gate result untouched.
5. **Add the `predict` operation to `src/cortex/tools/session/dispatcher.py`** — one new optional `prediction: str | None` parameter on the `session` tool, with `task_description` carrying the rationale (`--because`); dispatch `op == "predict"` to a handler that parses claims, records them, and returns the parsed claim list so a malformed claim is rejected before any edit. Preserve zero-arg behaviour: `session()` with no arguments must still start a session.
6. **Surface predictions in the brief** — extend `src/cortex/tools/session/brief.py` with a `predictions` field: open-claim count plus the most recent misses (claim, verdict, date), capped through the existing `brief_cap` path so the brief stays under budget.
7. **Nudge on an unpredicted gate** — when `record_gate_result` finds no open predictions for the session, include a short one-line notice in the gate response pointing at `session(operation="predict", ...)`. Advisory only; it must never change gate pass/fail.
8. **Write the doctrine** — add `.cortex/synapse/rules/general/predict-before-you-edit.mdc` (when to predict, the seven forms, batch only verified mechanics, never batch exploration, a miss is the valuable outcome); add one instruction line to `.cortex/synapse/cursor-agents/implement-code.md` Step 2 requiring a prediction before an edit batch; document the `Refuted` section convention for `activeContext.md` in the same rule file.
9. **Tests** — `tests/experience/test_claims.py` (parsing: every form, compound claims, empty, malformed, free text), `tests/experience/test_claim_grading.py` (each form hit, miss, and ungradable), `tests/experience/test_gate_hook_grading.py` (grading fires on a gate result; a recorder failure does not break the gate), `tests/unit/session/test_session_predict.py` (dispatch, malformed rejection, zero-arg preserved).
10. **Run `run_quality_gate()` and `run_docs_gate()`** until both pass, then update the memory bank through `update_memory_bank()`.

## Verification Checklist

- **Step 1–2**: search `src/cortex/experience/` for existing claim/verdict names to avoid collision (`rg "class (Claim|Verdict|GradingFrame)" src`); re-read `src/cortex/tools/session/gate_feedback.py` after writing `frame_from_gate_result` to confirm the `GateError` field names used (`file`, `line`, `check`, `message`) still match.
- **Step 3**: re-read `src/cortex/experience/recorder.py` after editing; confirm the new functions follow the `record_gate_fitness` never-raises pattern and that `_failure_count` is incremented on the failure path.
- **Step 4**: re-read `src/cortex/experience/gate_hook.py` and `src/cortex/tools/execution/pre_commit_zero_arg_tools.py:359`; confirm no new call site was added and the awaited result of `record_gate_result` is still ignored safely.
- **Step 5**: re-read `src/cortex/tools/session/dispatcher.py` and `models.py`; confirm the operation table, the validation branch, and the tool schema all list `predict`, and that no required parameter was introduced.
- **Step 6**: re-read `src/cortex/tools/session/brief.py` and `brief_cap.py`; confirm the new field passes through the cap and the brief stays within its token budget (`session()` output under 1000 tokens).
- **Step 7**: grep `rg "no open predictions" src tests` to confirm the notice is emitted from exactly one place and asserted in a test.
- **Step 8**: re-read the new `.mdc` rule and confirm it is discoverable through `cortex://rules` rather than only on disk.
- **Step 9–10**: `run_quality_gate()` and `run_docs_gate()` both report zero errors; new modules meet the 90%+ coverage threshold.

## Dependencies

- None blocking. The plan builds only on code already present in `main`: `src/cortex/experience/{recorder,gate_hook,store_artifact}`, `src/cortex/tools/session/{dispatcher,brief,gate_feedback}`, and `src/cortex/tools/execution/pre_commit_zero_arg_tools.py`.
- Related prior work that this plan deliberately does not modify: the archived `AI Code Comments and BELIEF Annotations` and `BELIEF Annotation Enforcement` plans. Those record beliefs; this one grades them.

## Success Criteria

- `session(operation="predict", prediction="gate clean; touches src/cortex/experience/claims.py")` returns the two parsed claims and records them; an empty or malformed prediction is rejected with the claim-vocabulary help text.
- A subsequent `run_quality_gate()` grades every open claim for the session and records one verdict per claim, with no change to the gate's own pass/fail result.
- All three verdicts are reachable: a claim the frame confirms is `HIT`, one it contradicts is `MISS`, and one it carries no evidence for is `UNGRADED` — never a silent pass.
- A forced exception inside the prediction recorder leaves the quality-gate result byte-identical to a run without predictions.
- `session()` start output lists open-claim count and recent misses, and stays under its 1000-token budget.
- `run_quality_gate()` and `run_docs_gate()` both pass; new modules are at or above the coverage threshold.
- Every new module obeys the repository limits: no `Any`, full type hints, Pydantic 2 models, functions ≤30 lines, files ≤400 lines.

## Testing Strategy

Target 95% coverage on the new modules, AAA pattern throughout, `pytest` only.

- **Unit — parsing**: each of the seven forms parsed to the right typed claim; compound `a; b; c` splitting; whitespace and case tolerance; empty string raising; a malformed claim beginning with a known keyword raising with the help text; free text yielding an implied `change`.
- **Unit — grading**: for each form, one frame that confirms it (`HIT`), one that contradicts it (`MISS`), and one that lacks the evidence (`UNGRADED`); a compound claim where one part fails grading as a miss overall.
- **Integration — gate hook**: a fabricated quality-gate result plus recorded open predictions produces the expected verdicts through `record_gate_result`; the "no open predictions" notice appears exactly when none were recorded.
- **Negative / resilience**: recorder raising `OSError` is swallowed, logged, and counted, leaving the gate result unchanged; a session with no experience store present degrades to a no-op.
- **Regression**: zero-arg `session()` still starts a session; the brief remains under its token cap with the maximum number of surfaced misses.

## Risks and Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Prediction recording breaks a quality gate | High — blocks every commit pipeline | Reuse the established never-raises recorder contract; add an explicit test that a forced recorder exception leaves the gate result unchanged |
| A vocabulary too small to express real intent, so agents write free text and grading degenerates to "something changed" | Medium — the ledger stops teaching | Keep the seven forms, but count free-text-only predictions and surface that count in the brief, so the vocabulary gap is measured rather than assumed |
| Nudge-only enforcement means predictions are simply skipped | Medium — the feature is present but unused | The gate reports when it graded nothing; the follow-up plan can escalate to a hard `post_edit_hook` refusal once the miss ledger shows the gate is worth enforcing |
| The brief grows past its token budget as verdicts accumulate | Medium — degrades every session start | Route the new field through the existing `brief_cap` path and assert the budget in a regression test |
| Verdicts accumulate unboundedly in the experience store | Low | Verdicts are ordinary experience nodes and inherit the store's existing lifecycle and compaction path; no new retention mechanism |
| The quality gate is a coarse frame — a claim about behaviour a gate cannot see grades `UNGRADED` forever | Low | `UNGRADED` is a first-class verdict and is counted; a persistent `UNGRADED` rate is the signal that a richer frame is worth building |
