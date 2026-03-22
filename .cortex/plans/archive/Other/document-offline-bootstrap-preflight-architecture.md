---
title: "Document offline bootstrap and preflight CLI architecture"
component: docs
work_type: documentation
status: PENDING
priority: low
created: 2026-03-22
depends_on:
  - url-scheme-validation-preflight
covers:
  - Documentation gap (all 3 review reports, T18-16/T18-17/T18-27)
---

## Plan: Document Offline Bootstrap and Preflight CLI Architecture

### Goal

Create a narrative design document in `docs/` that explains the offline bootstrap
architecture, the `preflight.py` registry probe (including the HEAD→GET fallback
behavior), the `UV_INDEX_URL` resolution logic, and the interaction with the CI
`make preflight` target. This addresses the documentation gap flagged with a score of
7/10 across all three code review reports.

### Context

**Documentation gap — all 3 review reports (T18-16, T18-17, T18-27):**

The offline bootstrap workflow (`preflight.py`, `make preflight`, CI gate) is fully
implemented as of commit `5814f42` (feat: offline bootstrap preflight, Make targets,
and CI workflow), but no narrative design doc exists in `docs/`. Reviewers consistently
scored Documentation at 7/10, noting:

- No explanation of the HEAD→GET fallback logic and why it exists (some registries
  return HTTP 405 for HEAD; the probe retries with GET to avoid false negatives).
- No documentation of the `UV_INDEX_URL` env-var override and its relationship to
  `uv sync`'s index resolution.
- No explanation of the offline triage use-case (what `make preflight` is for and when
  to run it).
- No doc linking the `preflight.py` CLI entry point to the `pyproject.toml`
  `[project.scripts]` section.

The target document is `docs/offline-bootstrap-preflight.md`.

Note: This plan depends on Plan C (URL scheme validation, `url-scheme-validation-preflight`)
because the scheme validation logic should be documented once it is implemented.
If Plan C is not yet complete, proceed with documenting the intended behavior as
specified in that plan.

### Implementation Steps

#### Step 1 — Create `docs/offline-bootstrap-preflight.md`

**File:** `docs/offline-bootstrap-preflight.md` (new file)

The document should cover the following sections:

##### 1. Overview

- Purpose: detect connectivity issues before `uv sync` is run in CI or developer
  bootstraps.
- Entry point: `python -m cortex.cli.preflight` or `make preflight`.
- Scope: validates the package index, not the entire dependency graph.

##### 2. Registry URL Resolution

- Default: `https://pypi.org/simple/` (constant `DEFAULT_REGISTRY_URL`).
- Override: `UV_INDEX_URL` environment variable — same variable read by `uv sync`.
- Scheme validation: only `https://` and `http://` are accepted; other schemes raise
  `ValueError` / print `[FAIL]` and exit `2`.
- Strips whitespace from the env-var value.

##### 3. Probe Strategy: HEAD → GET Fallback

- Primary probe: `HEAD` request (lightweight, no body).
- Fallback trigger: HTTP 405 (Method Not Allowed) — some private registry
  implementations reject HEAD.
- Fallback behavior: retry the same URL with `GET`, reading one byte to confirm a live
  response.
- Timeout: `DEFAULT_TIMEOUT_SEC = 10.0` seconds, configurable via the
  `registry_reachable()` API.
- Success criterion: HTTP status in the range `[200, 400)`.

##### 4. Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Registry reachable |
| `2` | Registry unreachable or invalid URL |

##### 5. Offline Triage Workflow

- When to run: before `uv sync` in restricted networks, air-gapped environments, or
  when `uv sync` hangs.
- `make preflight` target: wraps `python -m cortex.cli.preflight`; non-zero exit
  causes `make` to fail.
- CI integration: the `preflight` job in `.github/workflows/` runs before the main
  install step; a failure annotates the PR.

##### 6. Architecture Diagram (ASCII)

```text
Developer / CI
    |
    v
make preflight
    |
    v
cortex.cli.preflight.main()
    |
    v
resolve_registry_url()         # reads UV_INDEX_URL or uses PyPI default
    |                          # validates https:// or http:// scheme
    v
registry_reachable(url)
    |
    +-- HEAD request
    |       |
    |       +-- 200-399 → (True, "")
    |       +-- 405     → retry with GET
    |       +-- other   → (False, reason)
    |
    +-- GET request (fallback)
            |
            +-- 200-399 → (True, "")
            +-- other   → (False, reason)
    |
    v
stdout: [OK] / [FAIL]
exit 0 / 2
```

##### 7. Security Notes

- `UV_INDEX_URL` is validated for scheme before use in `urlopen`.
- No credentials are stored or logged; the probe only checks reachability.
- See `docs/security/best-practices.md` for the full threat model.

##### 8. Related Files

| File | Role |
|------|------|
| `src/cortex/cli/preflight.py` | Implementation |
| `tests/test_preflight.py` | Unit tests |
| `Makefile` | `preflight` target |
| `.github/workflows/` | CI integration |
| `docs/security/best-practices.md` | Threat model |

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `docs/offline-bootstrap-preflight.md` exists | `Glob docs/*.md` | new file |
| All 8 sections present (Overview through Related Files) | new doc | same |
| Exit code table accurate vs. source | `preflight.py:73–85` | both files |
| HEAD→GET fallback description matches implementation | `preflight.py:48–63` | both files |
| URL scheme validation section updated after Plan C | `preflight.py:20–30` | both |

---

#### Step 2 — Cross-link from existing docs

**Files to update** (minor additions only — no rewrites):

1. `docs/security/best-practices.md` — add a "See also" reference to
   `offline-bootstrap-preflight.md` in the section that discusses network security or
   input validation.
2. `README.md` (if a bootstrap/installation section exists) — add a one-line mention of
   `make preflight` with a link to the new doc.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Link to `offline-bootstrap-preflight.md` in `best-practices.md` | `docs/security/best-practices.md` | same |
| `make preflight` mentioned with link in README (if applicable) | `README.md` | same |

---

#### Step 3 — Run docs gate

After writing the document, run `run_docs_gate()` to verify:

- No broken internal links.
- Document passes any doc linting rules in the project.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `run_docs_gate()` passes | MCP output | N/A |
| No broken links reported | same | N/A |

---

### Dependencies

- **Soft dependency on Plan C** (`url-scheme-validation-preflight`): the scheme
  validation section of the doc should reflect the implemented behavior. If Plan C is
  complete, document the `ValueError` / `ALLOWED_SCHEMES` logic. If Plan C is not yet
  complete, document the planned behavior and mark the section as "pending
  implementation of url-scheme-validation-preflight plan."
- No dependency on Plan A or Plan B.

### Success Criteria

1. `docs/offline-bootstrap-preflight.md` exists with all 8 sections.
2. All statements in the document are accurate relative to the current source code.
3. `run_docs_gate()` passes.
4. Cross-link added in `docs/security/best-practices.md`.
5. Documentation score target: 8/10 (up from 7/10 per review reports).

### Testing Strategy

- **No code tests.** Documentation quality is verified by `run_docs_gate()`.
- **Accuracy check:** Each technical claim in the document should be verified against
  the corresponding source lines before writing (use Read tool on `preflight.py`).
- **Link validation:** All internal links (relative paths to other docs and source files)
  must be verified to resolve correctly from the `docs/` directory.
