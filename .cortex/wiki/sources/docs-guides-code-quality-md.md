# Code quality guide

Standards and tooling for code quality in Cortex (file size, formatting, linting, types).

## File size limits

- **Hard limit**: 400 logical lines per file (blank lines, comments, and docstrings excluded).
- **Warning**: Files between 350 and 400 lines trigger a **warning** in the file size check; the check still passes.
- **Error**: Files over 400 lines fail the quality gate and block commit/CI.

The quality gate runs the file size check via `run_quality_gate()` (Phase A includes quality) or the script:

```bash
uv run python .cortex/synapse/scripts/python/check_file_sizes.py
```

Environment variables (optional):

- `MAX_FILE_LINES`: hard limit (default 400)
- `FILE_SIZE_WARN_LINES`: warn above this (default 350)
- `SRC_DIR`: source directory (default auto-detected)

## IDE integration

- **VS Code-based editors**: Use the project’s quality checks before commit; no extra settings required. For inline feedback, consider a line-count or “files over N lines” extension if desired.
- **Pre-commit**: File size is enforced as part of the Cortex quality gate (Step 12.6 in the commit pipeline). The check runs before the quality gate; warnings appear for files between 350–400 lines, and the run fails if any file exceeds 400 lines.

## Function length limits

- **Hard limit**: 30 logical lines per function (blank lines, comments, and docstrings excluded).
- **Violation**: Functions over 30 lines fail the quality gate and block commit/CI.

When either the file size or function length limit is exceeded, use the **helper module extraction pattern** (see below).

## Helper module extraction

When the quality gate reports file size (>400 lines) or function length (>30 lines) violations, resolve them using the **helper module extraction pattern**:

1. **Identify cohesive function groups** in the oversized file (e.g. validation helpers, formatting helpers).
2. **Extract** those groups into a new module named `*_helpers.py` (e.g. `phase4_metadata_helpers.py`).
3. **Update** the original module: import from the helpers module and keep the public API unchanged.
4. **Update tests**: add or adjust tests for the new helpers; keep coverage and update imports.
5. **Run the quality gate** to confirm file size and function length are within limits.

Naming: use `*_helpers.py` for extracted modules. Full pattern and examples are in the maintainability rules (e.g. `maintainability.mdc` via the rules directory or the `cortex://rules` resource). The do prompt also documents this pattern as the standard refactoring approach for quality violations.

## Related

- [Testing guide](testing.md) – coverage and tests
- [Commit pipeline](../design/commit-pipeline-phases.md) – Phase A and Step 12.6
