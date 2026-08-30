---
title: "Offline / network-restricted verification — bootstrap, docs, and triage matrix"
component: developer-experience
work_type: docs
status: PENDING
priority: Medium
created: 2026-03-21
depends_on: []
sources:
  - "Comprehensive Project Review — 2026-03-21 (audit)"
---

## Goal

Make it **obvious and reproducible** how to run quality checks when **PyPI / network fetch fails**, and how to **triage** “environment failed before tests” vs “tests failed.”

## Context

- Fresh environments may fail during `uv sync` / dependency download (tunnel, proxy, air-gap).
- `python -m compileall` passing does not substitute for pytest; teams need a documented path (wheelhouse, mirror, pre-built image).

## Implementation steps

1. **Document offline bootstrap** — In `docs/guides/troubleshooting.md` (or dedicated `docs/guides/offline-bootstrap.md`): `uv` wheelhouse / `UV_OFFLINE` / internal mirror patterns; submodule init; minimum Python/`uv` versions.
2. **Preflight command** — Add a short “verification preflight” subsection: e.g. `uv sync --frozen` vs `uv sync`, how to detect network failure in output, retry guidance.
3. **CI vs local parity** — Cross-link to `make check-ci-parity` / workflow docs; note what **requires** network in default CI.
4. **Triage matrix** — Table: symptom → likely cause → next command (e.g. SSL error → check cert bundle; resolution failed → offline sync).
5. **Optional devcontainer** — If feasible later: reference or add a devcontainer image with dependencies pre-resolved (separate sub-task; mark OPTIONAL in plan execution).

## Verification checklist (per step)

| Step | What to search for | Scope | Re-read |
|------|---------------------|--------|---------|
| 1 | offline, wheelhouse, air-gap | `docs/guides/` | troubleshooting TOC |
| 2 | preflight | same | AGENTS.md Cursor Cloud section |
| 4 | matrix, triage | new section | link from README “Development” |

## Dependencies

- None.

## Success criteria

- New contributor on a restricted network can follow docs to get a **test-running** env or explicitly know they need IT mirror support.
- Troubleshooting doc distinguishes dependency-fetch failures from test failures in **one screen** of reading.

## Testing strategy (95%+ coverage target for new code)

- Primarily documentation: **no new Python required** unless adding a tiny `scripts/` diagnostic — **avoid new top-level dirs** per workspace rules; prefer a `tests/` test that validates doc links or command snippets only if already patterned in repo.
