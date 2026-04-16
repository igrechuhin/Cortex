---
title: "BELIEF Annotation Enforcement — Emit Guidance and Mid-Function Heuristics"
component: "synapse-annotations"
work_type: "feature"
status: "PENDING"
priority: "Medium"
created: "2026-04-16"
depends_on: []
---

## Goal

Ensure agents reliably emit `# BELIEF:` annotations by: (1) adding a "When to write BELIEF" section with 3–4 specific triggers to the rule file, (2) adding one BELIEF-emission instruction to the `implement-code` cursor-agent, and (3) extending the reflection heuristic to detect mid-function risky patterns (raw dict key access on untyped data, chained attribute access on optional-shaped values) in new diffs and emit a suggestion to add a BELIEF annotation.

## Context

The `# BELIEF:` convention is defined in `.cortex/synapse/rules/general/ai-code-comments.mdc` and the reflection heuristic in `src/cortex/tools/evaluation/reflection.py` warns when a stale BELIEF line is left unchanged in a hunk. However, two gaps prevent the convention from working end-to-end:

1. The rule file gives no concrete triggers — just "document assumptions." Agents can't act on vague guidance and so skip annotation.
2. The `implement-code` cursor-agent has no explicit instruction to emit a `# BELIEF:` line before code that assumes external state shape.
3. The autofix heuristic only catches stale BELIEF and missing tests on public functions; it never suggests adding BELIEF in the first place for risky mid-function patterns like `data["key"]` on untyped dicts or `obj.a.b.c` on data of externally-opaque shape.

All three gaps are additive and independently verifiable; no external dependencies block them.

## Scope

**in_scope**

- Add a "When to write BELIEF" section to `.cortex/synapse/rules/general/ai-code-comments.mdc` with exactly 3–4 specific triggers (dict key access on external data, chained attribute access on optional-shaped data, assumptions about ordering/state not enforced by types, configuration/environment values assumed to exist).
- Add one instruction line to `.cortex/synapse/cursor-agents/implement-code.md` Step 2 (Implement): before writing code that assumes external state shape, emit a `# BELIEF:` line documenting that assumption.
- Add one new heuristic function `_risky_mid_function_access(diff_text: str) -> list[CritiqueItem]` to `src/cortex/tools/evaluation/reflection.py` that detects: (a) dict key access via `["` on lines whose variable name is not typed as `TypedDict` in context, and (b) chained attribute access `\.(\w+)\.(\w+)` in added lines within Python files; emits a `CritiqueSeverity.WARNING` suggestion to add a BELIEF annotation.
- Update the Python section of `_LANGUAGE_SECTIONS` in `src/cortex/tools/reflection_constants.py` to document the new heuristic cue.
- Add unit tests covering: (a) raw dict key access triggers warning, (b) chained attribute access triggers warning, (c) typed access or simple single-level access does not fire, (d) non-Python diff does not fire.

**out_of_scope**

- Full static type analysis or TypedDict inference beyond simple regex heuristics.
- Changes to the overall reflection scoring or approval thresholds.
- Adding BELIEF heuristics for languages other than Python in this plan.
- Changes to any other cursor-agent prompts beyond `implement-code.md`.
- LLM-backed analysis of annotation quality.

## Approach

The three changes are loosely coupled and can be implemented in any order, but the rule-file and cursor-agent changes (items 2–3) are pure text edits and should land first. The reflection heuristic (item 1) is the only code change and follows the established pattern in `reflection.py` — a focused regex-based helper that runs in `_collect_diff_items` only when `"python"` is in `langs`.

For the heuristic, the approach uses two lightweight regex patterns on added lines (`+` prefix) in `.py` files:

- `_DICT_ACCESS_RE = re.compile(r'\b(\w+)\["')` — flags raw string-key dict access. The heuristic does not attempt full type inference; it fires whenever the access pattern appears, and the suggestion text tells the developer to add a BELIEF if the variable is external data.
- `_CHAINED_ATTR_RE = re.compile(r'\.\w+\.\w+')` — flags chained attribute access (at least two levels deep), which implies assumptions about the shape of returned/passed objects.

Both fire as `WARNING` (not `ERROR`) so they never block the quality gate; they are advisory only. The existing `_maybe_untested_public` function serves as the code-style template.

The rule-file section should list triggers as a numbered list rather than prose to keep them actionable. The cursor-agent instruction should be a single bullet in the existing Step 2 list.

## Implementation Steps

1. Edit `.cortex/synapse/rules/general/ai-code-comments.mdc`: add a `## When to write BELIEF` section after the existing "BELIEF Declaration Convention" section, listing 4 specific triggers as a numbered list.
2. Edit `.cortex/synapse/cursor-agents/implement-code.md`: in Step 2 (Implement), add one bullet: "Before writing code that accesses dict keys on external inputs, chains attribute access on optional-shaped data, or assumes configuration/environment values exist — add a `# BELIEF:` line documenting that assumption."
3. Add `_DICT_ACCESS_RE` and `_CHAINED_ATTR_RE` compiled patterns near the other compiled regex constants at the top of `src/cortex/tools/evaluation/reflection.py`.
4. Implement `_risky_mid_function_access(diff_text: str) -> list[CritiqueItem]` in `reflection.py` following the `_maybe_untested_public` pattern: iterate added lines in `.py` files only, check both patterns, return one deduplicated `WARNING` item per fired pattern per file.
5. Call `_risky_mid_function_access` from `_collect_diff_items` in the `if "python" in langs:` block.
6. Update the `"python"` entry in `_LANGUAGE_SECTIONS` in `src/cortex/tools/reflection_constants.py` to add the new cue line: `- **docs / annotations**: dict key access on untyped variables or chained attribute access in added lines triggers a suggestion to add a BELIEF annotation.`
7. Add unit tests in `tests/unit/tools/evaluation/test_reflection.py` covering: (a) dict access in added `.py` line fires warning, (b) chained `.attr.attr` in added `.py` line fires warning, (c) single-level `.attr` does not fire, (d) same patterns in a non-Python file do not fire.
8. Run quality gate; fix any failures inline (max 3 iterations).

## Verification Checklist

- **Rule file trigger section**: search `.cortex/synapse/rules/general/ai-code-comments.mdc` for `## When to write BELIEF` — must be present with at least 3 numbered items.
- **Cursor-agent instruction**: search `.cortex/synapse/cursor-agents/implement-code.md` for `# BELIEF:` — must appear in the Step 2 bullet list.
- **Heuristic function exists**: search `src/cortex/tools/evaluation/reflection.py` for `_risky_mid_function_access` — must be defined and called from `_collect_diff_items`.
- **Patterns compiled**: search `reflection.py` for `_DICT_ACCESS_RE` and `_CHAINED_ATTR_RE` — both must be present.
- **reflection_constants updated**: search `src/cortex/tools/reflection_constants.py` for `BELIEF` in the Python section — new cue line must be present.
- **Tests present and passing**: search `tests/unit/tools/evaluation/test_reflection.py` for `risky` or `dict_access` or `chained_attr` — at least 4 new test functions must be present; all must pass.
- **Re-read after changes**: re-read `reflection.py`, `reflection_constants.py`, `ai-code-comments.mdc`, `implement-code.md`, and `test_reflection.py` after each edit to confirm edits applied.

## Dependencies

- No external plans or blocked work. All three changes are self-contained.
- The existing `_collect_diff_items` call graph and `CritiqueItem` model in `reflection.py` are stable reference points.

## Success Criteria

- `.cortex/synapse/rules/general/ai-code-comments.mdc` contains a `## When to write BELIEF` section with at least 3 numbered, specific, actionable triggers.
- `.cortex/synapse/cursor-agents/implement-code.md` Step 2 contains an explicit instruction to emit `# BELIEF:` before assuming external state shape.
- `_risky_mid_function_access` fires a `WARNING` `CritiqueItem` on a diff that adds `data["key"]` or `obj.a.b` in a `.py` file, and does not fire on a diff with only simple attribute access or on non-Python files.
- All new unit tests pass; existing tests remain green; quality gate passes.

## Testing Strategy

Target: 95% line coverage on `_risky_mid_function_access` and the two new regex constants.

- **Unit — dict access fires**: diff adds `+    result = payload["user"]` in a `.py` file → expect one `WARNING` item with `"BELIEF"` in suggestion text.
- **Unit — chained access fires**: diff adds `+    name = response.data.user.name` in a `.py` file → expect one `WARNING` item.
- **Unit — single-level no-fire**: diff adds `+    x = obj.attr` in a `.py` file → expect no risky-access item.
- **Unit — non-Python no-fire**: same `["key"]` pattern in a `.ts` or `.md` diff file → expect no risky-access item.
- **Unit — deduplication**: multiple dict-access lines in the same diff file → expect exactly one item (not one per line).
- **Integration (existing harness)**: verify `test_analyze_diff_clean` still passes after adding the new heuristic with a clean diff containing no access patterns.
- **AAA pattern**: Arrange (build minimal diff string), Act (`analyze_diff(...)`), Assert (item presence, category, severity).

## Risks and Mitigation

| Risk | Mitigation |
|------|-----------|
| `_DICT_ACCESS_RE` fires too broadly (e.g., on type annotations or test fixtures) | Fire as `WARNING` only; agents treat it as advisory, not blocking; refine regex if false-positive rate is high |
| `_CHAINED_ATTR_RE` fires on method chains that are well-typed (e.g., fluent builders) | Same — advisory only; suggestion text explicitly says "if the variable is externally-typed data" |
| Cursor-agent instruction increases verbosity in generated code | Single bullet, bounded scope ("external state shape"); minimal friction |
| Rule file section becomes stale relative to code | Rule file and code are in sync at plan completion; future updates are tracked via existing BELIEF staleness heuristic |
