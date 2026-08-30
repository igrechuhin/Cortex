---
title: "Split make quality flows into non-mutating check and fix modes"
component: "Makefile + CI parity quality workflow"
work_type: refactor
status: PENDING
priority: High
created: 2026-03-20
depends_on: ["Align docs to zero-arg quality pipeline and deprecate stale entrypoints"]
---

## Goal

Ensure local quality commands communicate and enforce behavior clearly: `check` is non-mutating, `fix` is mutating, and parity expectations are explicit.

## Context

Current local `make check` can mutate files and does not fully mirror CI checks, causing local-green / CI-red churn.

## Implementation Steps

1. Redefine `make check` as non-mutating checks only.
2. Introduce `make fix` for format/autofix behavior.
3. Add `make check-ci-parity` for critical CI-equivalent checks feasible locally.
4. Update documentation with parity guarantees and known CI-only checks.

## Verification Checklist

- Step 1:
  - What to search for: `check:` target dependencies invoking mutating formatters
  - Search scope: `Makefile`
  - Files to re-read: `Makefile`
- Step 2:
  - What to search for: target naming and mutating command grouping
  - Search scope: `Makefile`
  - Files to re-read: `Makefile`, `README.md`
- Step 3:
  - What to search for: CI check list (`quality.yml`) and local parity target
  - Search scope: `.github/workflows`, `Makefile`
  - Files to re-read: `.github/workflows/quality.yml`, `Makefile`
- Step 4:
  - What to search for: parity explanation and caveats
  - Search scope: `README.md`, docs guides
  - Files to re-read: `README.md`, `docs/guides/troubleshooting.md`

## Dependencies

- Coordination with canonical workflow docs to prevent naming drift.

## Success Criteria

- `make check` does not modify files.
- `make fix` performs mutating remediation.
- Developers can run `make check-ci-parity` to reduce CI-only surprises.

## Testing Strategy (95% coverage target)

- Add/adjust tests for Makefile command expectations where test harness exists.
- Validate command outcomes in CI smoke jobs.
- Preserve >=95% coverage in touched validation/tooling logic.
