# Session Optimization: fix_markdown_lint Opaque Errors and Commit Fallback

Status: PENDING

## Goal

Improve the commit pipeline's ability to recover when `fix_markdown_lint` reports failures without parsed rule codes, and document the fallback so agents and users can unblock commits.

## Source

End-of-session analysis report: `.cortex/reviews/session-optimization-2026-02-16T20-41.md`

## Context

During a commit run, `fix_markdown_lint` returned `success: false` and `files_with_errors: 10` but each failing file had only `"error_message": "Markdown lint failed"` and `"errors": []`. Without rule codes (e.g. MD036, MD022), the agent could not target fixes. The batch failure path does not attach parsed markdownlint output to per-file results. In addition, the commit prompt does not describe what to do when the tool returns failures without rule codes (e.g. run markdown lint locally).

## Implementation Steps

### Step 1: Improve fix_markdown_lint error reporting when batch fails

- **Target**: `src/cortex/tools/markdown_operations.py` (and related batch/result building).
- **Change**: When a batch run fails (non-zero exit), either:
  - (a) Re-run markdownlint on each file in that batch individually, capture stderr, and parse rule codes into each FileResult, or
  - (b) Parse the batch stderr into per-file lines (markdownlint often outputs `file: line: rule`) and attach parsed rule codes to each FileResult.
- **Acceptance**: For any file reported with `error_message: "Markdown lint failed"`, the response includes a non-empty `errors` list with at least one rule code (e.g. MD036) when the markdownlint process produced it.

### Step 2: Document "Markdown lint failed" with no rule codes in commit and troubleshooting

- **Target**: Commit prompt (Step 1.5 and Step 12.5) and `docs/guides/troubleshooting.md` (or equivalent).
- **Change**: Add a short subsection: when `fix_markdown_lint` returns `files_with_errors` > 0 and `errors` is empty for those files, recommend running markdown lint locally (e.g. `npx --yes markdownlint-cli2 --fix '**/*.md' '**/*.mdc'` with project ignore patterns) to obtain rule codes and fix violations, then re-run commit.
- **Acceptance**: Commit prompt and troubleshooting doc both describe this fallback; agents can unblock without relying solely on the MCP tool.

### Step 3 (Optional): Single-file lint fallback in fix_markdown_lint

- **Target**: Markdown lint pipeline (e.g. after a batch fails).
- **Change**: For each file in a failed batch, optionally run markdownlint on that file only (same config), parse stdout/stderr, and merge rule codes into the result for that file.
- **Acceptance**: Failed files get populated `errors` when the subprocess produces parseable output; no requirement to run markdown lint locally for diagnostic.

## Dependencies

- Existing `fix_markdown_lint` MCP tool and `markdown_operations` module
- Commit prompt and docs layout (troubleshooting)

## Success Criteria

1. When a batch fails, at least one of: (a) per-file re-run, or (b) batch stderr parsing, is used so that FileResult.errors is non-empty when markdownlint emitted rule codes.
2. Commit prompt and troubleshooting document the fallback when the tool returns failures without rule codes.
3. Optional: single-file fallback implemented and tested; quality gate and tests pass.

## Risks and Mitigation

- **Per-file re-run may be slower**: Mitigate by doing it only when the batch failed and limiting concurrency.
- **Stderr format may vary**: Mitigate by using existing `_parse_markdownlint_errors` and testing with real markdownlint output.
