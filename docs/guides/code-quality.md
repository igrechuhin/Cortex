# Code quality guide

Standards and tooling for code quality in Cortex (file size, formatting, linting, types).

## File size limits

- **Hard limit**: 400 logical lines per file (blank lines, comments, and docstrings excluded).
- **Warning**: Files between 350 and 400 lines trigger a **warning** in the file size check; the check still passes.
- **Error**: Files over 400 lines fail the quality gate and block commit/CI.

The quality gate runs the file size check via `execute_pre_commit_checks(checks=["quality"])` or the script:

```bash
uv run python .cortex/synapse/scripts/python/check_file_sizes.py
```

Environment variables (optional):

- `MAX_FILE_LINES`: hard limit (default 400)
- `FILE_SIZE_WARN_LINES`: warn above this (default 350)
- `SRC_DIR`: source directory (default auto-detected)

## IDE integration

- **Cursor / VS Code**: Use the project’s quality checks before commit; no extra settings required. For inline feedback, consider a line-count or “files over N lines” extension if desired.
- **Pre-commit**: File size is enforced as part of the Cortex quality gate (Step 12.6 in the commit pipeline). The check runs before the quality gate; warnings appear for files between 350–400 lines, and the run fails if any file exceeds 400 lines.

## Related

- [Testing guide](testing.md) – coverage and tests
- [Commit pipeline](../../design/commit-pipeline-phases.md) – Phase A and Step 12.6
