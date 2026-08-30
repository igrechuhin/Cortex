---
title: "Fix Makefile env-check quoting and add smoke guard"
component: "build-tooling/Makefile"
work_type: fix
status: DONE
priority: High
created: 2026-03-20
depends_on: []
---

## Goal

Restore a reliable local environment preflight by fixing `make env-check` quoting and adding regression protection.

## Context

The review identified a quoting bug in `Makefile` inline Python that causes `SyntaxError`, blocking `env-check` and downstream local validation.

## Implementation Steps

1. Correct inline Python quoting in the `env-check` command.
2. Add a smoke validation path that executes `make env-check` in CI or preflight checks.
3. Ensure failure messages remain actionable for missing Python/uv prerequisites.

## Verification Checklist

- Step 1:
  - What to search for: `print(f\"` and env-check python snippet
  - Search scope: `Makefile`
  - Files to re-read: `Makefile`, `README.md`
- Step 2:
  - What to search for: `env-check` invocation in workflow/scripts
  - Search scope: `.github/workflows`, `scripts`, `Makefile`
  - Files to re-read: `.github/workflows/quality.yml`, `Makefile`
- Step 3:
  - What to search for: prerequisite failure text (`python`, `uv`)
  - Search scope: `Makefile` and setup docs
  - Files to re-read: `Makefile`, `README.md`

## Dependencies

- Existing CI workflow configuration and shell environment assumptions.

## Success Criteria

- `make env-check` exits successfully in normal bootstrap conditions.
- `make check` proceeds past preflight without syntax-related failures.
- Regression coverage exists for env-check command integrity.

## Testing Strategy (95% coverage target)

- Add/extend tests around command generation/parsing logic where available.
- Add CI smoke execution evidence for `make env-check`.
- Keep affected module/test coverage at or above 95% target for touched logic.
