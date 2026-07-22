---
title: "Fix roadmap_sync reference regex for .json paths"
component: "validation"
work_type: "fix"
status: PENDING
priority: "Medium"
created: "2026-07-20"
depends_on: []
---

## Goal

Make the roadmap_sync validator parse `.json` file references correctly so mentioning a JSON file in `roadmap.md` no longer fails the docs gate with a false invalid-reference error.

## Context

The file-reference regex in `src/cortex/validation/roadmap_sync.py` (`parse_roadmap_references`) uses the extension alternation `(py|md|ts|js|tsx|jsx|go|rs|java|kt)` which lacks `json`. Any `.json` mention in `roadmap.md` is truncated to a phantom `.js` reference: `failure_based_evals.json` was parsed as `failure_based_evals.js`, marking `roadmap_sync` invalid during the 2026-07-20 `/cortex/do` fix phase. The workaround was rewording the roadmap entry to avoid the `.json` token; the validator itself remains broken for JSON paths.

## Implementation Steps

1. Update the extension alternation in `parse_roadmap_references` to include `json` and order alternatives longest-first (`json` before `js`; `tsx`/`jsx` before `ts`/`js`) or add a word boundary so extensions never match a prefix of a longer extension.
2. Add regression tests: roadmap content referencing `path/to/file.json` yields a `.json` reference (not `.js`); existing extensions still parse; a `.json` reference to an existing file passes `validate_roadmap_sync`.
3. Run quality gate; confirm docs gate `roadmap_sync` passes with a `.json` reference present in a fixture.

## Success Criteria

- `parse_roadmap_references` returns `file.json` for `.json` mentions; no phantom `.js` references.
- Regression tests cover `.json`, `.js`, `.tsx`, `.ts` parsing.
- Quality gate green.

## Testing Strategy

- Unit tests (AAA) in the existing roadmap_sync test module covering the regex change and end-to-end `validate_roadmap_sync` with a temporary project tree.

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
