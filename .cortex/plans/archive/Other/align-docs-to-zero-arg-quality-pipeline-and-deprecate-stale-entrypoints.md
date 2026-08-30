---
title: "Align docs to zero-arg quality pipeline and deprecate stale entrypoints"
component: "README + docs/guides + AGENTS workflow docs"
work_type: docs
status: DONE
priority: High
created: 2026-03-20
depends_on: []
---

## Goal

Eliminate workflow/documentation drift by converging all contributor guidance on the current zero-arg quality pipeline.

## Context

Review evidence shows disagreements between README, AGENTS guidance, and troubleshooting content around `run_quality_gate` versus older tool entrypoints.

## Implementation Steps

1. Define canonical quality-pipeline source of truth and reference it from onboarding docs.
2. Update README quality/workflow sections to match current zero-arg pipeline.
3. Update troubleshooting docs to remove or explicitly mark deprecated entrypoints.
4. Add lightweight docs consistency validation for deprecated quality command references.

## Verification Checklist

- Step 1:
  - What to search for: `execute_pre_commit_checks`, `run_quality_gate`, `run_docs_gate`
  - Search scope: `README.md`, `AGENTS.md`, `docs/guides/*.md`
  - Files to re-read: `README.md`, `AGENTS.md`, `docs/api/tools.md`
- Step 2:
  - What to search for: local quality gate instructions
  - Search scope: `README.md`
  - Files to re-read: `README.md`
- Step 3:
  - What to search for: stale troubleshooting flow references
  - Search scope: `docs/guides/troubleshooting.md`
  - Files to re-read: `docs/guides/troubleshooting.md`
- Step 4:
  - What to search for: deprecated quality entrypoints in docs
  - Search scope: `README.md`, `docs/**`
  - Files to re-read: docs validation script output and touched docs

## Dependencies

- Agreement on canonical tooling surface (`docs/api/tools.md` recommended).

## Success Criteria

- README, AGENTS, and troubleshooting pages reference the same quality entrypoints.
- Deprecated entrypoints are either removed or explicitly marked as legacy.
- Consistency checks catch future drift.

## Testing Strategy (95% coverage target)

- Add/adjust docs validation tests to cover deprecated-entrypoint detection logic.
- Validate markdown/docs gate passes for updated docs artifacts.
- Maintain >=95% coverage for any touched docs-validation code paths.
