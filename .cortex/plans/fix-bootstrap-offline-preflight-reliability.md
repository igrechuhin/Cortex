---
title: "Add offline mode and preflight network/test failure differentiation for bootstrap"
component: build
work_type: fix
status: PENDING
priority: high
created: 2026-03-22
depends_on: []
sources:
  - "Codex audit: Bootstrap/Quality Gate Reliability in Restricted Environments (High)"
---

## Goal

Make the project bootstrappable in restricted-network environments (enterprise proxies, air-gapped CI) and add a preflight command that clearly distinguishes "network fetch failed" from "project test failed" so operators can diagnose setup problems without false-negative quality signals.

## Context

`pyproject.toml` declares `uv_build` as the build backend, which requires network resolution at build time. The primary bootstrap path (`uv sync --group dev --extra dev`) also assumes online package resolution. In constrained environments this blocks setup entirely, meaning quality gates and test signals cannot be generated at all — indistinguishable from test failures.

There is no preflight command that validates whether the environment can reach package registries before attempting a full sync.

## Implementation Steps

### Step 1 — Audit the full bootstrap surface

1. Read `pyproject.toml` — identify `[build-system]`, `[project.optional-dependencies]`, `[dependency-groups]`, and any `[tool.uv]` sections.
2. Read `Makefile` or `scripts/bootstrap.sh` (if present) — identify the bootstrap invocation chain.
3. Read `CONTRIBUTING.md` — note documented setup steps.
4. Read CI workflow files (`.github/workflows/*.yml`) — identify which jobs run `uv sync` and under what conditions.
5. Produce an inventory: all network-touching commands in the bootstrap path.

#### Verification Checklist — Step 1

| What to check | Search scope | Files to re-read |
|---|---|---|
| `[build-system]` requires identified | `pyproject.toml` | `pyproject.toml` |
| All CI bootstrap steps inventoried | `.github/workflows/` | Each workflow file |
| Documented setup steps noted | `CONTRIBUTING.md` | — |

### Step 2 — Implement preflight network check

1. Create `scripts/preflight.sh` (or `src/cortex/cli/preflight.py` if a CLI entry point is preferred).
2. The preflight command must:
   - Ping the configured PyPI/uv registry (e.g. `https://pypi.org/simple/` or `$UV_INDEX_URL`) with a short timeout (5s).
   - Print a clear result: `[OK] Registry reachable` or `[FAIL] Cannot reach registry: <reason>`.
   - Exit 0 on success, exit 2 on network failure (distinct from exit 1 for test failure).
3. Document the exit code contract in the script header.
4. Add `make preflight` target (or equivalent) to the top-level `Makefile`.

#### Verification Checklist — Step 2

| What to check | Search scope | Files to re-read |
|---|---|---|
| Exit codes 0/1/2 are distinct and documented | `scripts/preflight.sh` | — |
| `make preflight` runs the script | `Makefile` | — |
| Timeout is ≤10s (not blocking) | Script source | — |

### Step 3 — Document offline bootstrap path

1. In `CONTRIBUTING.md`, add a new section "Offline / Restricted-Network Setup" covering:
   - How to pre-download wheels into a local wheelhouse (`uv pip download --dest ./wheelhouse -r requirements.txt` or equivalent).
   - How to point `uv` at the local wheelhouse (`UV_INDEX_URL=file://$(pwd)/wheelhouse` or `--index-url`).
   - How to build `uv_build` from source if needed (or note the pinned version so it can be vendored).
   - Reference to `make preflight` for diagnosing network failures.
2. Add a `Makefile` target `bootstrap-offline` that runs `uv sync` with `--offline` flag and prints a clear error if the local wheelhouse is missing.

#### Verification Checklist — Step 3

| What to check | Search scope | Files to re-read |
|---|---|---|
| "Offline / Restricted-Network Setup" section present | `CONTRIBUTING.md` | — |
| `bootstrap-offline` target exists | `Makefile` | — |
| All referenced commands are accurate | Manual test in isolated venv | — |
| Markdown lint passes | `run_docs_gate()` | — |

### Step 4 — Add restricted-egress CI job

1. In `.github/workflows/`, add a new job `bootstrap-restricted` to an appropriate workflow (e.g. `ci.yml`).
2. The job must:
   - Run on a container/runner with outbound network blocked (use GitHub Actions `options: --network none` or equivalent).
   - Pre-populate the wheelhouse in a prior step (from a cached artifact or a separate online job).
   - Run `make bootstrap-offline` and assert it succeeds.
   - Run `make preflight` and assert exit code 2 (network unreachable — expected).
3. Gate the job on changes to `pyproject.toml` or `scripts/` to avoid cost on unrelated PRs.

#### Verification Checklist — Step 4

| What to check | Search scope | Files to re-read |
|---|---|---|
| New CI job defined correctly | `.github/workflows/` | New workflow snippet |
| Job only triggers on relevant path changes | Workflow `on.paths` | — |
| No secrets or credentials in job definition | Workflow file | — |
| Existing CI jobs unaffected | All other workflow files | — |

### Step 5 — Run quality gate and update memory bank

1. Call `run_quality_gate()` — must pass with zero errors.
2. Update `activeContext.md` with a completed entry for this plan.
3. Update `progress.md`.

## Dependencies

- None (self-contained to build, scripts, and CI layers).

## Success Criteria

- `make preflight` exits 2 (not 1) when registry is unreachable.
- `make bootstrap-offline` succeeds with a pre-populated wheelhouse.
- `CONTRIBUTING.md` has an "Offline / Restricted-Network Setup" section.
- A CI job validates offline bootstrap on path-change triggers.
- `run_quality_gate()` passes: zero errors, coverage ≥ 91%.

## Testing Strategy (95% coverage target)

- Unit tests for the preflight script: mock `urllib.request.urlopen` (or `httpx`) — test OK path, timeout path, connection-refused path; assert correct exit codes.
- Shell-level integration test (`tests/e2e/` or `scripts/test_preflight.sh`): run `preflight.sh` against a locally spawned mock HTTP server; assert exit 0.
- Existing bootstrap tests (if any) must remain green.
- Docs gate must pass on `CONTRIBUTING.md` changes (no MD lint violations).
