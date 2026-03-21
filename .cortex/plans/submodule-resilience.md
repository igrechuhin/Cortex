---
title: "Improve submodule preflight resilience and error messaging"
component: ci
work_type: enhancement
status: PENDING
priority: medium
created: 2026-03-21
depends_on: []
---

## Goal

Improve the developer experience when the Synapse submodule is missing or dirty, with clear error messages, auto-init suggestions, and graceful degradation for non-Synapse-dependent checks.

## Context

- `scripts/check_synapse.sh` already gates `make test`, `make check`, `make check-ci-parity` with a clear error message and `CORTEX_ALLOW_MISSING_SYNAPSE=1` escape hatch.
- CI workflow `quality.yml:64-65` runs the same check.
- However: contributors who skip `git submodule update --init --recursive` hit a wall immediately with no auto-recovery.
- The commit pipeline also has `precommit_block_response()` in the detached worker (`pre_commit_worker.py:294`) that checks submodule hygiene.
- Comprehensive review notes this as "frequent operational footgun" for fresh clones.

## Implementation Steps

### Step 1: Add auto-init prompt to check_synapse.sh

- **File**: `scripts/check_synapse.sh`
- After the error message, add: "Run this now? [y/N]" interactive prompt (only when stdin is a terminal, not CI)
- If yes, run `git submodule update --init --recursive` and re-check
- In non-interactive mode (CI), just fail with the existing error

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Interactive prompt in check_synapse | `scripts/check_synapse.sh` | check_synapse.sh |
| TTY detection logic | check_synapse.sh | check_synapse.sh |

### Step 2: Add submodule status to quality gate output

- **File**: `src/cortex/tools/execution/pre_commit_worker.py` (or `pre_commit_helpers_quality.py`)
- When `precommit_block_response()` fires, include the remediation command in the error message returned to the MCP tool
- Currently returns: `{"blocked": true, "reason": "..."}` — add `"remediation": "git submodule update --init --recursive"`

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `precommit_block_response` | `src/cortex/tools/execution/` | pre_commit_worker.py |
| Remediation field in response | Same | Same |

### Step 3: Add bootstrap.sh submodule auto-init

- **File**: `scripts/bootstrap.sh`
- Before `uv sync`, add: check if `.cortex/synapse/scripts/` exists; if not, run `git submodule update --init --recursive`
- This makes `make bootstrap` a single command that always works from a fresh clone

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Submodule init in bootstrap | `scripts/bootstrap.sh` | bootstrap.sh |

## Dependencies

None.

## Success Criteria

- `make bootstrap` from a fresh clone with no submodule auto-inits the submodule
- `make check` from a fresh clone without bootstrap gives a clear error with remediation
- CI behavior unchanged (non-interactive, fails on missing submodule)

## Testing Strategy

- Manual test: fresh clone → `make bootstrap` → verify submodule initialized
- Manual test: fresh clone without bootstrap → `make check` → verify clear error
- Existing CI checks pass
- 95%+ test coverage maintained
