---
title: "Network-Resilience Onboarding: Offline Preflight and Quickstart Fallback"
component: documentation
work_type: infrastructure
status: DONE
priority: High
created: 2026-04-12
depends_on: []
---

## Network-Resilience Onboarding: Offline Preflight and Quickstart Fallback

## Goal

Add an explicit offline-readiness preflight check and surface a clear restricted-network fallback command sequence in `README.md` quickstart, so contributors in enterprise/proxy environments can complete setup without ad-hoc debugging.

## Context

### Finding (Review 2026-04-12, Issue #5 — High)

- Running `uv run pytest tests/ -q` failed because `uv_build` could not be fetched from `https://pypi.org/simple/uv-build/` in a network-restricted environment.
- `pyproject.toml` `build-system` requires `uv_build`.
- Offline guidance exists in docs, but standard verification path still hard-fails without pre-seeded artifacts.
- Slows incident response and contributor onboarding in enterprise/proxy environments.

**Related existing guidance**: search `docs/` for existing offline setup instructions before writing new content.

## Implementation Steps

### Step 1: Audit existing offline documentation

1. Search `docs/` for any offline, proxy, network-restricted, or wheelhouse guidance: `rg -rn "offline|wheelhouse|proxy|restricted|air.gap" docs/ README.md`.
2. Read all found sections fully.
3. Check `pyproject.toml` for `build-system.requires`, `tool.uv.offline`, or existing lock/wheelhouse config.
4. Check `.github/workflows/bootstrap-offline.yml` fully — this was modified recently per git status.
5. Identify: (a) what already exists, (b) what is missing or incomplete.

**Verification checklist:**

- `Glob` on `docs/**/*.md` for offline/proxy/network content files.
- Re-read `pyproject.toml` build-system section.
- Re-read `.github/workflows/bootstrap-offline.yml`.

### Step 2: Extend existing preflight with offline-readiness checks

**Existing infrastructure**: `scripts/preflight.sh` delegates to `src/cortex/cli/preflight.py` (registry reachability probe). Extend this module rather than creating a parallel script.

1. Add an `offline_readiness()` function to `src/cortex/cli/preflight.py` that checks:
   - `uv` is installed and version is compatible.
   - `uv_build` wheel is available in local cache (`uv cache dir`) or `vendor/` dir.
   - Lock file (`uv.lock` or `requirements.lock`) exists and is not stale vs `pyproject.toml`.
   - Required system tools (`git`, `python3`) are present.
2. Add a `--offline` flag to `main()` that runs `offline_readiness()` instead of (or in addition to) the registry probe.
3. On success: print `[OK] Offline readiness — all prerequisites satisfied.`
4. On failure: print specific missing items with remediation commands (e.g., `uv pip download uv-build --dest vendor/`).
5. Keep file ≤400 lines; add type hints.

**Verification checklist:**

- Script runs: `scripts/preflight.sh --offline` — exits 0 on a valid setup.
- Re-read `src/cortex/cli/preflight.py`; confirm all checks listed in item 1 are implemented.
- `run_quality_gate()` — script passes type/lint checks.

### Step 3: Add `Makefile` target for offline preflight

1. Check existing `Makefile` for a `preflight` target.
2. If absent, add a `preflight-offline` target that runs `scripts/preflight.sh --offline`.
3. Document this target in `README.md` quickstart (Step 4 references this).

**Verification checklist:**

- `make preflight-offline` executes the script without error.
- Re-read `Makefile` to confirm target is present.

### Step 4: Update README quickstart with offline fallback

1. Read current `README.md` quickstart/setup section.
2. Add a subsection **"Restricted-network / offline setup"** with:
   - Step 1: Run `scripts/preflight.sh --offline` (or `make preflight-offline`) to verify prerequisites.
   - Step 2: If `uv_build` is missing: `uv pip download uv-build --dest vendor/ && uv pip install --no-index --find-links vendor/ uv-build`.
   - Step 3: Use `uv sync --offline --frozen` instead of `uv sync` when network is unavailable.
   - Step 4: Run tests with `uv run --offline pytest tests/ -q`.
3. Keep the section concise (≤ 20 lines in the README).
4. Cross-reference any existing `docs/` offline guidance.

**Verification checklist:**

- `rg "offline\|restricted.network" README.md` — section found.
- Re-read changed README section; confirm commands are complete and correct.
- `run_docs_gate()` — green.

### Step 5: Update `.github/workflows/bootstrap-offline.yml`

1. Read the current workflow file fully.
2. Verify it seeds the `uv_build` wheel in the offline bootstrap step.
3. If missing: add a step that downloads `uv_build` to the wheelhouse before the install step.
4. Add a workflow comment documenting the offline contract.

**Verification checklist:**

- Re-read workflow file after changes.
- Verify `uv_build` is present in the seeding step.
- `rg "uv.build\|uv_build" .github/workflows/bootstrap-offline.yml` — at least one match.

### Step 6: Add an integration smoke-test for offline preflight

1. Create `tests/integration/test_offline_preflight.py`.
2. Test: run `scripts/preflight.sh --offline` in a subprocess; assert it exits 0 in the current environment.
3. Add a `@pytest.mark.integration` marker; exclude from fast unit suite if needed.

**Verification checklist:**

- `run_quality_gate()` — integration test passes.
- Re-read test file; confirm subprocess exit-code assertion is present.

## Dependencies

- `pyproject.toml` — build-system requirements (read-only reference)
- `.github/workflows/bootstrap-offline.yml` — CI bootstrap (update target)
- `README.md` — quickstart section (update target)
- `src/cortex/cli/preflight.py` — extend with `--offline` mode

## Success Criteria

- `scripts/preflight.sh --offline` exits 0 in a correctly configured environment and provides actionable output in an unconfigured environment.
- `README.md` "Restricted-network / offline setup" subsection exists with ≤20 lines, covering all 4 fallback steps.
- `.github/workflows/bootstrap-offline.yml` seeds `uv_build` before install step.
- New contributor setup in restricted network follows documented path without ad-hoc debugging (validated by manual walkthrough or integration test).
- `run_quality_gate()` and `run_docs_gate()` both green.

## Testing Strategy

- **Integration test** (`tests/integration/test_offline_preflight.py`): subprocess execution of `scripts/preflight.sh --offline`; assert exit 0. Target 95%+ coverage on new code in `src/cortex/cli/preflight.py`.
- **Static docs test**: `run_docs_gate()` validates README markdown structure.
- **CI**: `.github/workflows/bootstrap-offline.yml` updated so CI itself validates the offline path on every PR.
- No mocks needed for offline preflight — it checks real environment state.
