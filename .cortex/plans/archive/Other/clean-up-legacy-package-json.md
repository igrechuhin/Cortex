---
title: "Clean up legacy package.json and clarify Node dependency"
component: build
work_type: refactor
status: DONE
priority: Low
created: 2026-03-21
depends_on: []
---

## Progress (2026-03-22)

- Removed `package.json` — had no `devDependencies` and was not used by `bootstrap.sh` or CI.
- Updated `docs/development/contributing.md`: corrected bootstrap comment and paragraph (removed incorrect npm/Node claim); added a note that Node is only needed in CI for `cspell` via `npm install -g cspell@8.6.1`.
- Quality gate passes.

## Goal

Remove or formalize the legacy `package.json` to reduce contributor confusion about the project's toolchain, and document the exact remaining Node.js responsibility (CI spelling checks).

## Context

- **Codex review finding #6**: `package.json` declares legacy metadata with no `devDependencies`. CI still installs Node for spelling checks. Contributors may assume Node workflows are current.
- The file already contains a description noting it's legacy, but its continued presence is ambiguous.

## Implementation Steps

### Step 1: Audit Node.js usage in CI

Determine exactly which CI steps require Node.js. Check `quality.yml` and any other workflow files.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `node` or `npm` or `npx` in CI | `.github/workflows/` | All workflow files |
| `cspell` or spelling tool refs | `.github/workflows/` | `quality.yml` |

### Step 2: Decide: remove or document

- **If Node is only used for `cspell`**: Document this in one place (e.g., `CONTRIBUTING.md` or a comment in `quality.yml`) and either keep a minimal `package.json` with that documented purpose or remove it if cspell runs without it.
- **If Node is not needed at all**: Remove `package.json` entirely.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `package.json` references | All config files, scripts, docs | `package.json` |

### Step 3: Implement decision and update docs

Execute the chosen approach. Update contributor docs to clarify the toolchain is Python-first with the specific Node exception (if any).

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Toolchain documentation | `CONTRIBUTING.md`, `README.md` | Relevant sections |

## Dependencies

- None.

## Success Criteria

- `package.json` is either removed or has a clear, documented purpose.
- CI still passes (spelling checks work).
- Contributor docs accurately describe the toolchain.
- Quality gate passes.

## Testing Strategy

- CI workflow verification (spelling checks still run).
- No code-level tests needed (build/config change).
- Target: 95% coverage maintained.
