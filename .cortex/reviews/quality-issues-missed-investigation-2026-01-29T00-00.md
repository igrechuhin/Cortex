# Investigation: Why Quality Issues Were Missed in Commit Session

**Date**: 2026-01-29  
**Context**: User reported that a commit session (transcript `138c59d6-adff-4b7a-8894-d200070dfa30`) "was going to succeed" but the IDE later showed five issues that had not been caught:

1. **session-optimization-2026-01-28T12-00.md**: MD009 (trailing spaces ×2), MD012 (multiple blank lines)
2. **tests/tools/test_rules_operations.py**: basedpyright `reportRedeclaration` (variable `all_rules` shadowed)
3. **src/cortex/core/mcp_stability.py**: Ruff UP034 (extraneous parentheses)

This document explains why each was missed and recommends fixes.

---

## 1. Markdown lint (session-optimization-2026-01-28T12-00.md)

### What the commit workflow did (markdown)

- The transcript shows `fix_markdown_lint(check_all_files=True, include_untracked_markdown=True)` at Step 1.5 (6 files fixed, 0 errors) and again at Step 12.0 (2 files fixed, 0 errors).
- The MCP tool correctly includes `.cortex/reviews/` (only `.cortex/plans/archive/` and a few other paths are excluded in `_collect_markdown_files_sync`).
- Untracked files are included when `check_all_files=True` and `include_untracked_markdown=True` (the list comes from `_get_all_markdown_files`, not git).

### Why markdown issues were missed

- **Most plausible**: The session review file **was created or overwritten after the last `fix_markdown_lint` run** in that session.
- Session optimization reports (e.g. `session-optimization-2026-01-28T12-00.md`) are often written by the session-optimization analyzer or by the same session that is running the commit. If that file is written (or saved) **after** Step 12.0, it is never passed through markdown lint in that run.
- So the pipeline did what it was supposed to (lint all markdown files at two points), but the file either did not exist yet or had different content at those times.

### Recommendations (markdown)

- In the commit prompt / session-optimization flow: **run markdown lint again after any step that writes or updates session review files** (e.g. after generating or saving `session-optimization-*.md`), or explicitly include "reviews just written" in the Step 12.6 scope.
- Alternatively: document that session review files created in the same session must be saved **before** the final markdown lint step so they are included in the same run.

---

## 2. test_rules_operations.py – reportRedeclaration (all_rules shadowed)

### What the commit workflow did (type check)

- The agent ran `check_types.py` (Step 12.2); it failed with **5** type errors, all in `test_commit_workflow_model.py` and `test_roadmap_sync.py`.
- After fixing those, the agent re-ran `check_types.py`; it passed (0 errors).
- So at that moment, **no** type errors were reported in `test_rules_operations.py`.

### Why reportRedeclaration was missed (test_rules_operations)

- **Pyright vs basedpyright**: The commit script runs **pyright** (`.venv/bin/pyright` or `uv run pyright`). The user’s IDE uses **basedpyright**.
- `pyrightconfig.json` does **not** set `reportRedeclaration`; it only lists many other rules explicitly. So:
  - **basedpyright** may treat `reportRedeclaration` as an **error** by default (or via the extension).
  - **pyright** may treat it as a warning or not report it with the same severity.
- So the **pipeline passed** (pyright did not fail on that rule) while the **IDE failed** (basedpyright reported it as an error). The redeclaration was always there; the difference is tool/severity.

### Recommendation (reportRedeclaration)

- Add **`"reportRedeclaration": "error"`** to `pyrightconfig.json` so both CLI (pyright/basedpyright) and IDE fail consistently on variable shadowing. Then the commit pipeline will catch this class of issue.

---

## 3. mcp_stability.py – Ruff UP034 (extraneous parentheses)

### What the commit workflow did (linting)

- The agent ran `check_linting.py` (Step 12.3), which runs:  
  `ruff check --select F,E,W src/ tests/`
- That step passed.

### Why UP034 was missed (mcp_stability)

- **Ruff rule set mismatch**: In the repo:
  - **pyproject.toml** sets `tool.ruff.lint.select = ["E", "F", "I", "B", "UP"]`, so **UP** (pyupgrade) and thus **UP034** are part of the intended project rule set.
  - **CI** (`.github/workflows/quality.yml`) and **check_linting.py** (`.cortex/synapse/scripts/python/check_linting.py`) **override** that with:  
    `ruff check --select F,E,W src/ tests/`
- So the pipeline only runs **F** (pyflakes), **E** (pycodestyle errors), **W** (pycodestyle warnings). It does **not** run **UP** (pyupgrade), so **UP034 is never checked** in CI or in `execute_pre_commit_checks`.
- The **IDE** (Ruff extension) typically uses the full config from `pyproject.toml`, so it reports UP034. The issue was missed because **the pipeline explicitly limits Ruff to F,E,W**, not the full config.

### Recommendation (Ruff UP034)

- **Option A**: Change CI and `check_linting.py` to use the **same** rule set as `pyproject.toml` (e.g. run `ruff check` **without** `--select F,E,W` so Ruff uses `pyproject.toml`), or explicitly add the same select list including UP (and I, B if desired).
- **Option B**: If the intent is to keep CI minimal (F,E,W only), document that UP (and similar) are **IDE-only** and accept that UP034-style issues can slip through until CI is aligned with pyproject.toml.

---

## Summary

| Issue | Root cause | Fix |
|-------|------------|-----|
| Markdown MD009/MD012 in session review | File likely created/updated **after** last `fix_markdown_lint` run | Lint again after writing session reviews, or ensure those files exist before final markdown lint |
| reportRedeclaration in test_rules_operations | **basedpyright** reports it; **pyright** (CLI) did not fail | Add `reportRedeclaration: error` to `pyrightconfig.json` |
| Ruff UP034 in mcp_stability | Pipeline runs `ruff --select F,E,W`; **UP** not included | Align CI/check_linting with pyproject.toml (include UP) or document the gap |

All three causes are **process/tooling alignment** (when files are linted, which type checker and rule set run in the pipeline vs IDE), not a single bug in one tool.
