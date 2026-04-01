"""Public API for fix_markdown_lint: orchestration and MCP tool entry point."""

import asyncio
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MCP_TOOL_TIMEOUT_VERY_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.files.markdown_link_validation import find_broken_links
from cortex.tools.files.markdown_lint_cache import (
    MarkdownLintIndex,
    load_markdown_lint_index_safe,
)
from cortex.tools.files.markdown_lint_core import (
    filter_files_for_linting,
    get_all_markdown_files_for_lint,
    get_markdown_files_to_process,
    update_markdown_lint_cache_safe,
    validate_markdown_prerequisites,
)
from cortex.tools.files.markdown_lint_helpers import (
    FileResult,
    apply_validation_error_hint,
    calculate_statistics,
)
from cortex.tools.files.markdown_lint_responses import (
    create_empty_success_response,
    create_error_response,
)
from cortex.tools.files.markdown_lint_run import run_markdownlint_for_files

__all__ = [
    "FileResult",
    "FixMarkdownLintResult",
    "calculate_statistics",
    "fix_markdown_lint",
    "run_markdownlint_with_cache",
]


class FixMarkdownLintResult(BaseModel):
    """Result of markdown lint fixing operation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    success: bool = Field(description="Whether operation succeeded")
    files_processed: int = Field(ge=0, description="Number of files processed")
    files_fixed: int = Field(ge=0, description="Number of files fixed")
    files_unchanged: int = Field(ge=0, description="Number of files unchanged")
    files_with_errors: int = Field(ge=0, description="Number of files with errors")
    results: list[FileResult] = Field(
        default_factory=lambda: list[FileResult](), description="File results"
    )
    error_message: str | None = Field(default=None, description="Error message if any")


def _build_fix_response(results: list[FileResult]) -> str:
    """Build JSON response from file results."""
    files_fixed, files_with_errors, files_unchanged = calculate_statistics(results)
    script_result = FixMarkdownLintResult(
        success=files_with_errors == 0,
        files_processed=len(results),
        files_fixed=files_fixed,
        files_unchanged=files_unchanged,
        files_with_errors=files_with_errors,
        results=results,
        error_message=None,
    )
    return json.dumps(script_result.model_dump(), indent=2)


async def _fix_markdown_lint_impl(
    root_path: Path,
    include_untracked_markdown: bool,
    dry_run: bool,
    ctx: MCPContext | None = None,
) -> str:
    """Core implementation for fix_markdown_lint MCP tool.

    Always scopes to git-modified (+ optionally untracked) markdown files.
    Under the hood this now uses the rumdl CLI as the Markdown engine.
    """
    (
        validation_error,
        markdownlint_cmd,
        config_path,
    ) = await validate_markdown_prerequisites(root_path)
    if validation_error:
        return apply_validation_error_hint(validation_error)
    assert markdownlint_cmd is not None
    files = await get_markdown_files_to_process(root_path, include_untracked_markdown)
    if not files:
        return create_empty_success_response()
    return await run_markdownlint_with_cache(
        root_path, files, markdownlint_cmd, config_path, dry_run, ctx
    )


def _merge_internal_link_errors(
    results: list[FileResult], root_path: Path
) -> list[FileResult]:
    """Append markdown link validation errors to rumdl file results."""
    broken = find_broken_links(root_path)
    if not broken:
        return results
    by_file: dict[str, FileResult] = {r.file: r for r in results}
    for item in broken:
        msg = f"line {item.line}: broken link `{item.target}`"
        if item.source_file in by_file:
            cur = by_file[item.source_file]
            new_errs = list(cur.errors) + [msg]
            joined = "; ".join(new_errs[:5])
            by_file[item.source_file] = cur.model_copy(
                update={
                    "errors": new_errs,
                    "fixed": False,
                    "error_message": joined,
                }
            )
        else:
            by_file[item.source_file] = FileResult(
                file=item.source_file,
                fixed=False,
                errors=[msg],
                error_message=msg,
            )
    return sorted(by_file.values(), key=lambda r: r.file)


async def _lint_all_files_and_merge(
    root_path: Path,
    markdownlint_cmd: list[str],
    config_path: Path | None,
    ctx: MCPContext | None,
) -> str:
    """Run lint on all markdown files, merge link errors, and build response."""
    files = get_all_markdown_files_for_lint(root_path)
    if not files:
        return create_empty_success_response()
    results = await run_markdownlint_for_files(
        files,
        [],
        root_path,
        markdownlint_cmd,
        config_path,
        dry_run=True,
        ctx=ctx,
    )
    results = _merge_internal_link_errors(results, root_path)
    return _build_fix_response(results)


async def run_markdown_lint_all_files_check(
    root_path: Path | None = None, ctx: MCPContext | None = None
) -> str:
    """Run markdown lint on all repo markdown files (CI parity); check-only, no fix."""
    if root_path is None:
        root_path = await resolve_project_root_async(None, ctx)
    (
        validation_error,
        markdownlint_cmd,
        config_path,
    ) = await validate_markdown_prerequisites(root_path)
    if validation_error:
        return apply_validation_error_hint(validation_error)
    assert markdownlint_cmd is not None
    return await _lint_all_files_and_merge(
        root_path, markdownlint_cmd, config_path, ctx
    )


async def _run_lint_and_update_cache(
    root_path: Path,
    files_to_lint: list[Path],
    initial_results: list[FileResult],
    markdownlint_cmd: list[str],
    config_path: Path | None,
    dry_run: bool,
    ctx: MCPContext | None,
    index: MarkdownLintIndex,
    file_hashes: dict[str, str],
) -> list[FileResult]:
    """Run markdownlint for filtered files and update the cache."""
    results = await run_markdownlint_for_files(
        files_to_lint,
        initial_results,
        root_path,
        markdownlint_cmd,
        config_path,
        dry_run,
        ctx=ctx,
        index=index,
        file_hashes=file_hashes,
    )
    await update_markdown_lint_cache_safe(index, root_path, results, file_hashes, ctx)
    return results


async def run_markdownlint_with_cache(
    root_path: Path,
    files: list[Path],
    markdownlint_cmd: list[str],
    config_path: Path | None,
    dry_run: bool,
    ctx: MCPContext | None = None,
) -> str:
    """Run markdownlint with cache handling and build response JSON."""
    index = await load_markdown_lint_index_safe(root_path, ctx)
    files_to_lint, initial_results, file_hashes = await filter_files_for_linting(
        root_path, files, index, dry_run
    )
    results = await _run_lint_and_update_cache(
        root_path,
        files_to_lint,
        initial_results,
        markdownlint_cmd,
        config_path,
        dry_run,
        ctx,
        index,
        file_hashes,
    )
    return _build_fix_response(results)


async def _fix_markdown_lint_run_or_error(
    ctx: MCPContext | None,
    root_path: Path,
    include_untracked_markdown: bool,
    dry_run: bool,
) -> tuple[str, bool]:
    """Run fix_markdown_lint impl; return (result_json, success)."""
    try:
        result = await _fix_markdown_lint_impl(
            root_path,
            include_untracked_markdown,
            dry_run,
            ctx,
        )
        return (result, True)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        await log_client(
            ctx, "error", f"fix_markdown_lint: failed: {e}", logger_name=__name__
        )
        return (create_error_response(str(e)), False)
    except BaseException as e:  # pragma: no cover - defensive guardrail
        await log_client(
            ctx,
            "error",
            f"fix_markdown_lint: fatal: {e!r}",
            logger_name=__name__,
        )
        return (create_error_response(f"Fatal markdown lint error: {e!r}"), False)


async def _fix_markdown_lint_inner(
    include_untracked_markdown: bool,
    dry_run: bool,
    ctx: MCPContext | None,
) -> str:
    """Resolve root, run lint fix, and log completion."""
    await log_client(ctx, "info", "fix_markdown_lint: starting", logger_name=__name__)
    root_path = await resolve_project_root_async(None, ctx)
    result, ok = await _fix_markdown_lint_run_or_error(
        ctx,
        root_path,
        include_untracked_markdown,
        dry_run,
    )
    if ok:
        await log_client(
            ctx, "info", "fix_markdown_lint: completed", logger_name=__name__
        )
    return result


# MCP registration removed — autofix includes markdown auto-fix
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX, enable_progress=False)
async def fix_markdown_lint(
    include_untracked_markdown: bool = False,
    dry_run: bool = False,
    check_all_files: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """Fix markdown lint errors in markdown files.

    USE WHEN: User wants markdown fixes, user needs lint fixes, user
    requests markdown lint fix, user wants to fix markdown errors.

    RETURNS: JSON with fixes applied, files modified, and lint results.
    Scans git-modified markdown files, runs the rumdl CLI, and applies fixes.
    """
    _ = check_all_files
    return await _fix_markdown_lint_inner(include_untracked_markdown, dry_run, ctx)
