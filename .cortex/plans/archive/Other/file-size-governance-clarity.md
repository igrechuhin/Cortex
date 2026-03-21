---
title: "Clarify file/function size governance: document logical-line counting"
component: documentation
work_type: fix
status: PENDING
priority: high
created: 2026-03-21
depends_on: []
---

## Goal

Eliminate confusion between total line counts and logical line counts in file/function size governance. Document that enforcement uses logical lines (excluding blanks, comments, docstrings) and publish the current state clearly.

## Context

- CI enforces `MAX_FILE_LINES = 400` and `MAX_FUNCTION_LINES = 30` via `.cortex/synapse/scripts/python/check_file_sizes.py` and `check_function_lengths.py`.
- These checks count **logical lines** (blanks, comments, docstrings excluded), not total lines.
- 33 files under `src/` exceed 400 **total** lines but all pass CI because their **logical** line count is under 400.
- Example: `pre_commit_tools.py` has 730 total lines but only ~301 logical lines (58.8% is documentation).
- The comprehensive review flagged this as "governance vs reality out of sync" — the gap is actually a documentation/communication issue, not an enforcement failure.
- `FILE_SIZE_EXCLUDED_FILENAMES = ("models.py",)` excludes Pydantic model definitions by filename.
- Function length check has its own exclusion list: `plan.py`, `plan_dispatcher.py`, `roadmap_dispatcher.py`, `sequential_thinking.py`, `pre_commit_pipeline.py`.

## Implementation Steps

### Step 1: Document counting method in developer docs

- **File**: `docs/development/contributing.md` (or new `docs/development/code-standards.md`)
- Add section "File and function size limits" explaining:
  - MAX_FILE_LINES = 400 logical lines (blanks, comments, docstrings excluded)
  - MAX_FUNCTION_LINES = 30 logical lines
  - Exclusions: `models.py` files (Pydantic schema-heavy), specific dispatcher files for function length
  - How to check locally: `uv run python .cortex/synapse/scripts/python/check_file_sizes.py`
  - Reference: `src/cortex/core/constants.py` for limit values

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| "logical lines" in docs | `docs/development/` | Contributing or code-standards doc |
| MAX_FILE_LINES reference | docs | `src/cortex/core/constants.py` |

### Step 2: Update CI workflow log messages

- **File**: `.github/workflows/quality.yml` (file-size and function-length steps)
- Change step names from "Check file sizes (max 400 lines)" to "Check file sizes (max 400 logical lines)"
- Similarly for function lengths: "max 30 logical lines"
- Add brief inline comment in workflow explaining what logical lines means

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Step names mentioning "lines" | `.github/workflows/quality.yml` | quality.yml |
| "logical" qualifier | quality.yml | quality.yml |

### Step 3: Add inline documentation to constants

- **File**: `src/cortex/core/constants.py`
- Expand comment on `MAX_FILE_LINES` to clarify: "400 logical lines (blanks, comments, docstrings excluded per check_file_sizes.py)"
- Same for `MAX_FUNCTION_LINES`

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| MAX_FILE_LINES comment | `src/cortex/core/constants.py` | constants.py |

### Step 4: Add a "heavy files" dashboard to quality gate output

- **Files**: `src/cortex/tools/execution/pre_commit_helpers_quality.py` or check scripts
- When a file passes but is within 80% of the limit (>320 logical lines), emit an informational note in quality gate output
- This gives early warning before files hit the limit

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Warning threshold for file size | Quality helper files | `pre_commit_helpers_quality.py` |

## Dependencies

None.

## Success Criteria

- Developer docs clearly state "logical lines" counting method
- CI step names include "logical lines" qualifier
- Constants have inline documentation matching the enforcement behavior
- No source code changes to limits or enforcement logic (this is a docs-only plan)

## Testing Strategy

- Existing CI quality checks continue to pass
- Markdown lint passes on new/updated docs
- 95%+ test coverage maintained (no new source logic unless Step 4 is implemented)
