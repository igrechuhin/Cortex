"""
Markdown Operations Tools

This module re-exports the fix_markdown_lint tool and related types.
Implementation is split across:
- markdown_lint: fix_markdown_lint, FixMarkdownLintResult, orchestration
- markdown_lint_run: batch run, heartbeat, run_markdownlint_for_files
- markdown_lint_core: git, command discovery, config, cache filtering

Consumers should import from this module for backward compatibility.
Tests that patch internals should patch the implementation modules
(cortex.tools.files.markdown_lint_core, cortex.tools.files.markdown_lint_run).
"""

# pyright: reportPrivateUsage=false

from cortex.tools.files.markdown_lint import (
    FileResult,
    FixMarkdownLintResult,
    calculate_statistics,
    fix_markdown_lint,
    run_markdownlint_with_cache,
)
from cortex.tools.files.markdown_lint_core import (
    _update_markdown_lint_cache_from_results,
    after_one_file,
    compute_file_hashes,
    filter_files_for_linting,
    find_markdownlint_command,
    get_markdown_files_to_process,
    get_modified_markdown_files,
    is_cached_clean_entry,
    parse_git_output,
    parse_untracked_files,
    run_command,
    update_markdown_lint_cache_safe,
    validate_markdown_prerequisites,
)
from cortex.tools.files.markdown_lint_helpers import (
    parse_markdownlint_errors,
    parse_markdownlint_output,
)
from cortex.tools.files.markdown_lint_run import (
    _process_markdown_files_sequential,
    run_markdownlint_batch,
    run_markdownlint_fix,
    run_markdownlint_for_files,
)

__all__ = [
    "FileResult",
    "FixMarkdownLintResult",
    "calculate_statistics",
    "after_one_file",
    "compute_file_hashes",
    "filter_files_for_linting",
    "find_markdownlint_command",
    "get_markdown_files_to_process",
    "get_modified_markdown_files",
    "is_cached_clean_entry",
    "parse_git_output",
    "parse_markdownlint_errors",
    "parse_markdownlint_output",
    "parse_untracked_files",
    "run_command",
    "run_markdownlint_with_cache",
    "_update_markdown_lint_cache_from_results",
    "update_markdown_lint_cache_safe",
    "validate_markdown_prerequisites",
    "_process_markdown_files_sequential",
    "run_markdownlint_batch",
    "run_markdownlint_fix",
    "run_markdownlint_for_files",
    "fix_markdown_lint",
]
