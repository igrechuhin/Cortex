---
title: "Fix: Add Missing Makefile Offline Targets"
component: "build"
work_type: "fix"
status: PENDING
priority: high
created: 2026-04-13
depends_on: []
---

## Fix: Add Missing Makefile Offline Targets

## Goal

`README.md` documents `make preflight-offline` and `make bootstrap-offline` as
the canonical offline-setup commands, but neither target exists in `Makefile`.
Any developer following the README in a restricted-network environment will get
`make: *** No rule to make target 'preflight-offline'. Stop.`

This plan adds both targets so README instructions are correct and runnable.

## Context

- `README.md:160` — instructs users to run `make preflight-offline`
  (fallback: `bash scripts/preflight.sh --offline`).
- `README.md:162` — instructs users to run `make bootstrap-offline`
  (uses `UV_NO_INDEX=1`, `UV_FIND_LINKS`, `uv sync --offline --frozen`).
- `Makefile` existing targets: `bootstrap`, `preflight`, `env-check`, `check`,
  `test`, `fix`, etc. Neither `preflight-offline` nor `bootstrap-offline` are
  present (verified 2026-04-13).
- `scripts/preflight.sh` exists and already accepts `--offline` flag.
- The archived plan `network-resilience-onboarding.md` planned these targets
  but they were never actually added to `Makefile`; the plan was marked COMPLETE
  in error (or the targets were added then removed).

## Implementation Steps

### Step 1 — Read `Makefile` and `scripts/preflight.sh`

1. `Read` the full `Makefile` to understand current target conventions (help
   text pattern, `.PHONY` declaration style, prerequisite chains).
2. `Read` `scripts/preflight.sh` to confirm the `--offline` flag is accepted
   and what it does.
3. Verify `scripts/bootstrap.sh` (or equivalent) exists and check its offline
   mode flag.

### Verification checklist 1

- [ ] Makefile has a `help` target with descriptive comments — use same style
- [ ] `scripts/preflight.sh` accepts `--offline` flag without error
- [ ] Offline bootstrap script path/flags are known

### Step 2 — Add `preflight-offline` target

Add after the existing `preflight:` target:

```makefile
preflight-offline:  ## Run preflight checks without network (verifies uv, git, python3, uv.lock, local wheel)
	bash scripts/preflight.sh --offline
```

Also add `preflight-offline` to the `.PHONY` line (or whichever phony
declaration pattern the file uses).

### Verification checklist 2

- [ ] `make preflight-offline` runs `bash scripts/preflight.sh --offline`
- [ ] Target appears in `make help` output
- [ ] `.PHONY` updated

### Step 3 — Add `bootstrap-offline` target

Add after the existing `bootstrap:` target, mirroring what README documents:

```makefile
bootstrap-offline:  ## Install dependencies without network index (requires pre-populated wheelhouse/)
	UV_NO_INDEX=1 UV_FIND_LINKS=$(CURDIR)/wheelhouse uv sync --offline --frozen
```

If `scripts/bootstrap.sh --offline` exists and is preferred, delegate to it
instead. Match the README description exactly (Step 3 README:162).

### Verification checklist 3

- [ ] `make bootstrap-offline` runs the offline `uv sync` invocation
- [ ] Error message is clear when `wheelhouse/` is absent
- [ ] Target appears in `make help` output
- [ ] `.PHONY` updated

### Step 4 — Smoke-test both targets locally

```bash
make preflight-offline   # should exit 0 in a normal dev environment
make bootstrap-offline   # acceptable to fail if wheelhouse/ absent — verify error is clear
```

Adjust error output / `set -e` behavior if the failure mode is confusing.

### Verification checklist 4

- [ ] `make preflight-offline` exits 0 in the repo with `.venv` present
- [ ] `make bootstrap-offline` prints a useful message when wheelhouse is missing
- [ ] No regressions to existing `make preflight` or `make bootstrap` targets

### Step 5 — Update wiki source snapshot

Re-ingest `README.md` so `.cortex/wiki/sources/readme-md-v*.md` snapshots
reflect that the documented targets now actually exist. Use
`manage_file(operation="ingest", ...)` or the commit-pipeline wiki ingest.

## Dependencies

- `scripts/preflight.sh --offline` must already work (confirmed existing).
- No source-code changes; Makefile only.

## Success Criteria

1. `make preflight-offline` exits 0 on a standard dev machine.
2. `make bootstrap-offline` executes the correct `uv sync` invocation and
   surfaces a clear error when the wheelhouse is missing.
3. Both targets appear in `make help` output.
4. `README.md` instructions are now runnable end-to-end without editing.
5. No existing Make targets are broken.

## Testing Strategy

- **Smoke test** (Step 4): run both new targets; assert correct exit codes /
  error messages. No unit tests required for Makefile targets.
- **Regression**: run `make help` and assert both new targets are listed.
- **Docs gate**: verify wiki sources are still consistent with README after
  re-ingest.

Coverage target: N/A (Makefile changes, no Python code).
