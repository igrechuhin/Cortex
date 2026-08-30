---
title: "MCP docs, README, and CI — single source of truth for published tool surface"
component: documentation
work_type: infrastructure
status: PENDING
priority: Critical
created: 2026-03-21
depends_on: []
sources:
  - .cortex/reviews/code-review-report-2026-03-21T11-18.md
  - "Comprehensive Project Review — 2026-03-21 (audit)"
related_archived:
  - .cortex/plans/archive/Other/plan-docs-fix-stale-counts.md
---

## Goal

Eliminate drift between **marketing/README counts**, **`docs/api/tools.md` narrative**, and **code-enforced published inventory** (e.g. `TOOL_CATEGORIES`, `tests/tools/test_tool_categories.py`). Agents and humans must share one canonical, machine-verifiable definition of “published MCP tools/resources.”

## Context

- README advertises counts (e.g. tools / prompts / resources) that may not match the reduced consolidated surface and governance tests.
- `docs/api/tools.md` still mixes current and legacy catalog material.
- `tests/tools/test_tool_categories.py` encodes expectations (e.g. 10 categorized tools); docs should not contradict this without an intentional, versioned change.

## Implementation steps

1. **Inventory source of truth** — Identify the authoritative runtime/registry structures for: published tools, prompts, resources (e.g. server registration, category map, resource URIs). Document the chosen “canonical” module(s) in a short comment or `docs/api/tools.md` intro paragraph.
2. **Split `docs/api/tools.md`** — Add clearly labeled sections: **Current published** (maintained) vs **Historical / legacy** (frozen with last-reviewed date). Link legacy sections to replacements where applicable.
3. **README alignment** — Replace static counts with either: (a) counts generated at doc-build or release time, or (b) qualitative description + link to canonical doc section (prefer (a) if CI enforces parity).
4. **CI guardrail** — Add a check (pytest or small script invoked in CI) that fails when README-declared counts (or a dedicated generated snippet) diverge from code-derived counts. Prefer generating a small `docs/_generated/tool-inventory.json` or embedding a `<!-- cortex:tool-count: N -->` marker updated by script.
5. **Prompts / AGENTS cross-links** — Ensure Synapse/Cursor prompts that list tools point at the “current published” section only.

## Verification checklist (per step)

| Step | What to search for | Scope | Re-read |
|------|---------------------|--------|---------|
| 1 | `TOOL_CATEGORIES`, tool registration, resource registry | `src/cortex/` | `server.py`, tools `__init__`, resource modules |
| 2 | “Historical”, “legacy”, “current published” | `docs/api/tools.md` | Full file for heading balance / rumdl |
| 3 | tool count integers, “tools,” “resources” | `README.md` | README + link targets |
| 4 | new test or workflow step | `tests/`, `.github/workflows/` | quality workflow parity docs |
| 5 | deprecated tool names in prompts | `.cortex/synapse/prompts/` | grep tool names vs registry |

## Dependencies

- None blocking; coordinate with any in-flight tool consolidation PRs.

## Success criteria

- README and `docs/api/tools.md` **current** section match code-derived published inventory.
- CI fails on drift without updating the generated artifact or intentional registry change.
- No Synapse prompt references-only deprecated tools without an explicit “legacy” label.

## Testing strategy (95%+ coverage target for new code)

- New inventory script logic: unit tests with fixed fixture registries (happy path + edge: zero tools, renamed category).
- If only docs/markdown: add/extend a test that parses README markers or runs the drift script against the repo (fast, deterministic).
