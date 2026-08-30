---
title: "Add narrative doc for preflight HEAD→GET fallback and http:// allowance"
component: cli
work_type: docs
status: PENDING
priority: Medium
created: 2026-03-22
depends_on: []
---

## Goal

Write a single narrative section in `docs/offline-bootstrap-preflight.md` that explains
two design decisions currently undocumented:

1. Why `registry_reachable()` tries HEAD first and falls back to GET on HTTP 405.
2. Why `ALLOWED_SCHEMES` includes `http://` alongside `https://` (internal mirrors).

This closes the Documentation plateau at 7/10 and is eligible to push it to 8/10.

## Context

All three 2026-03-22 reviews flag the same gap: `preflight.py` has solid inline
docstrings but no narrative explanation of its probe strategy or the deliberate
`http://` allowance. The third review (T20-28) even flagged the `http://` allowance
as a potential security concern — a narrative doc would preempt that objection by
documenting the intentional design.

The logic lives in `src/cortex/cli/preflight.py`:

- `_probe_with_method` at line 58: HEAD → on 405 recurses with GET.
- `ALLOWED_SCHEMES = ("https://", "http://")` at line 18: explicit tuple, not HTTPS-only.
- `docs/offline-bootstrap-preflight.md` already exists and is the right home.

## Implementation Steps

### Step 1: Read the existing doc and the source

**Verification checklist:**

- Read `docs/offline-bootstrap-preflight.md` end-to-end.
- Read `src/cortex/cli/preflight.py` lines 1–100.
- Identify where to insert the new section (after the existing "How it works" or
  "Usage" section, before any troubleshooting section).

### Step 2: Write the narrative section

Add a `## Probe strategy` (or `## Design notes`) section with two subsections:

#### HEAD → GET fallback

Explain: PyPI and most private registries support HEAD for lightweight reachability
checks without downloading content. Some registries (e.g. Nexus behind certain proxy
configurations) return HTTP 405 Method Not Allowed for HEAD. The fallback to GET with
`resp.read(1)` reads a single byte to confirm the connection is live without pulling
the full index page.

#### `http://` allowance

Explain: Internal/air-gapped package mirrors often serve over plain HTTP. Blocking
`http://` here would prevent Cortex from being used in those environments. The
`http://` path is operator-controlled via `UV_INDEX_URL`; the default is always
`https://pypi.org/simple/`. Environments that want to enforce HTTPS-only can validate
`UV_INDEX_URL` at a higher layer (CI policy, network egress rules).

**Verification checklist:**

- Section uses H2 heading with blank lines above and below (MD022).
- Fenced code blocks (if any) specify language (MD040).
- Lists have blank lines before and after (MD032).
- No trailing spaces (MD009).

### Step 3: Run markdown lint

Call `fix_quality_issues()` to auto-fix any markdown violations in the edited file.
Then call `run_docs_gate()` to verify the doc passes.

**Verification checklist:**

- `run_docs_gate()` returns `docs_phase_passed: true`.
- No MD022/MD031/MD032 violations in `docs/offline-bootstrap-preflight.md`.

## Dependencies

- None. Touches only `docs/offline-bootstrap-preflight.md`.

## Success Criteria

1. `docs/offline-bootstrap-preflight.md` contains a `## Probe strategy` or
   `## Design notes` section explaining HEAD→GET fallback and `http://` allowance.
2. `run_docs_gate()` passes.
3. No new markdown lint violations introduced.
4. Documentation metric eligible to advance from 7 → 8 in next review.

## Testing Strategy

No code changes — doc-only. Validation is via `run_docs_gate()` and `fix_quality_issues()`.
