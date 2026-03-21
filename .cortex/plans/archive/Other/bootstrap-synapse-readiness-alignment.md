---
title: "Align bootstrap.sh Synapse readiness check with check_synapse.sh"
component: scripts
work_type: fix
status: PENDING
priority: high
created: 2026-03-21
depends_on: []
---

## Goal

Eliminate the silent-skip failure mode where `bootstrap.sh` treats an empty `.cortex/synapse/scripts` directory as initialized, while `check_synapse.sh` correctly requires the directory to contain files. After this fix, bootstrap will always initialize submodules when the scripts directory is empty.

## Context

- **Codex review finding #1** and **Cortex review (submodule resilience)**: `scripts/bootstrap.sh` only checks `[ ! -d "${SYNAPSE_SCRIPTS_DIR}" ]`, so a partial checkout with an empty directory silently skips submodule init.
- `scripts/check_synapse.sh` already has the correct check: directory exists **and** `ls -A` returns files.
- This creates a confusing first-run failure mode for new contributors.

## Implementation Steps

### Step 1: Extract shared readiness function

Create a small shared shell function (or align the bootstrap check inline) so both scripts use the same semantics.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `_synapse_scripts_ready` or equivalent | `scripts/` | `check_synapse.sh`, `bootstrap.sh` |
| Empty-dir guard logic | `scripts/bootstrap.sh` | `bootstrap.sh` |

**Changes:**

- `scripts/bootstrap.sh`: Replace `[ ! -d "${SYNAPSE_SCRIPTS_DIR}" ]` with a check that also verifies the directory is non-empty (matching `check_synapse.sh` semantics).
- Optionally extract `_synapse_scripts_ready()` into a shared `scripts/_synapse_lib.sh` sourced by both scripts.

### Step 2: Add regression test for empty-directory case

Add a test that verifies bootstrap triggers submodule init when `.cortex/synapse/scripts` exists but is empty.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Test for empty synapse dir | `tests/` | New test file |
| Bootstrap behavior with empty dir | `scripts/bootstrap.sh` | `bootstrap.sh` |

**Changes:**

- Add a shell or pytest test that creates an empty scripts directory, runs bootstrap logic, and asserts submodule init was triggered.

### Step 3: Add actionable error message

When Synapse is missing or empty, emit a clear remediation message: `git submodule update --init --recursive`.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Remediation message text | `scripts/bootstrap.sh` | `bootstrap.sh` |

## Dependencies

- None (self-contained shell script fix).

## Success Criteria

- `bootstrap.sh` triggers submodule init when scripts directory exists but is empty.
- `check_synapse.sh` and `bootstrap.sh` use equivalent readiness semantics.
- Regression test covers the empty-directory case.
- Quality gate passes.

## Testing Strategy

- Shell-level test (or pytest subprocess test) for the empty-directory scenario.
- Manual verification: `mkdir -p .cortex/synapse/scripts && ./scripts/bootstrap.sh` triggers init.
- Target: 95% coverage maintained.
