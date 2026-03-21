---
title: "Add CI markdown link validation for non-archive docs"
component: ci
work_type: feature
status: PENDING
priority: medium
created: 2026-03-21
depends_on: []
---

## Goal

Add automated CI validation that checks internal markdown links in non-archive documentation resolve to existing files, preventing broken navigation from accumulating undetected.

## Context

- The comprehensive project review found a reference to `file.md` in `docs/index.md:39` — this is an example in documentation text (`[text](file.md#section)`) rather than a real broken link. However, no automated link validation exists in CI.
- Stale links can accumulate silently as files are renamed, moved, or deleted.
- `rumdl` handles markdown formatting rules (MD009, MD036, etc.) but does not validate link targets.
- CI already has markdown lint (`rumdl check`) in `quality.yml` — link validation should live alongside it.

## Implementation Steps

### Step 1: Create a link-checking script

- **File**: `.cortex/synapse/scripts/python/check_markdown_links.py` (new)
- Walk all `.md` files in `docs/`, `README.md`, `AGENTS.md`, `CLAUDE.md` (exclude `.cortex/plans/archive/`, `.cortex/history/`)
- Parse markdown for `[text](target)` links where target is a relative path (not `http://`, `https://`, `cortex://`, `#anchor-only`)
- Resolve each relative path from the file's directory
- Report broken links with file:line and the broken target
- Exit 0 if no broken links, exit 1 otherwise
- Keep under 400 logical lines, functions under 30 lines

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `check_markdown_links` | `.cortex/synapse/scripts/python/` | The new script |
| Import and path resolution logic | New script | `pathlib` usage patterns |

### Step 2: Add CI workflow step

- **File**: `.github/workflows/quality.yml`
- Add step after the existing markdown lint step (step id: `markdown_lint`)
- Step name: "Check markdown links"
- Command: `uv run python .cortex/synapse/scripts/python/check_markdown_links.py`
- Add result to quality check summary (non-blocking initially — set `continue-on-error: true` for first iteration, then promote to blocking)

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `check_markdown_links` in workflow | `.github/workflows/quality.yml` | quality.yml |
| Step ordering relative to markdown_lint | quality.yml | quality.yml |

### Step 3: Add unit tests for link checker

- **File**: `tests/unit/test_check_markdown_links.py` (new)
- Test cases: valid relative link, broken link, anchor-only link (skip), HTTP link (skip), link in archive (excluded), link with fragment (`file.md#section`)
- Use `tmp_path` fixture to create test markdown files

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `test_check_markdown_links` | `tests/unit/` | New test file |
| Test coverage of edge cases | Test file | Script implementation |

### Step 4: Integrate into local quality gate

- **File**: `src/cortex/tools/files/markdown_lint.py` or new helper
- Add link validation to `run_markdown_lint_all_files_check()` or as a separate check in Phase A
- Ensure `run_quality_gate()` catches broken links locally, not just in CI

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Link validation in quality gate | `src/cortex/tools/` | `pre_commit_phase_dispatch.py` |

## Dependencies

None.

## Success Criteria

- CI detects broken internal markdown links in non-archive docs
- Local quality gate (`run_quality_gate()`) also validates markdown links
- No false positives on example/template links (like `[text](file.md#section)` in code blocks)
- Zero broken links in current docs at time of merge

## Testing Strategy

- Unit tests for the link checker script with 95%+ coverage
- Integration: run checker on actual `docs/` and verify zero broken links
- Markdown lint continues to pass (`rumdl check`)
