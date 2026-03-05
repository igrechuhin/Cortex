"""Pre-Commit Tools

MCP tools for executing pre-commit checks with language auto-detection.

Total: 1 tool
- execute_pre_commit_checks: Execute pre-commit checks (fix errors,
  format, type check, quality, tests) or fix-quality mode (checks=["fix_quality"]).
"""

import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_VERY_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import external_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
    typed_mcp_tool,
)
from cortex.core.models import ModelDict
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.services.framework_adapters.base import FrameworkAdapter
from cortex.services.framework_adapters.go_adapter import GoAdapter
from cortex.services.framework_adapters.java_adapter import JavaAdapter
from cortex.services.framework_adapters.javascript_adapter import JavaScriptAdapter
from cortex.services.framework_adapters.kotlin_adapter import KotlinAdapter
from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.framework_adapters.rust_adapter import RustAdapter
from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.services.framework_adapters.typescript_adapter import TypeScriptAdapter
from cortex.services.language_detector import LanguageInfo
from cortex.tools.execution.pre_commit_fix_quality import (
    create_quality_error_response,
    fix_quality_issues_impl,
)
from cortex.tools.execution.pre_commit_helpers import (
    create_error_result_dict,
    determine_checks_to_perform,
    unsupported_language_result_dict,
)
from cortex.tools.execution.pre_commit_helpers_language import detect_or_use_language
from cortex.tools.execution.pre_commit_helpers_models import PreCommitCheck
from cortex.tools.execution.pre_commit_tools_run_helpers import (
    build_pre_commit_response,
    run_checks_with_connection_monitoring,
)

logger = logging.getLogger(__name__)

# Adapter registry: language -> factory(project_root) -> FrameworkAdapter.
# Python, TypeScript, JavaScript, Rust, Go, Java, Swift, and Kotlin have full implementations.
_ADAPTER_REGISTRY: dict[str, Callable[[str | None], FrameworkAdapter]] = {
    "python": lambda root: PythonAdapter(root),
    "typescript": lambda root: TypeScriptAdapter(root),
    "javascript": lambda root: JavaScriptAdapter(root),
    "rust": lambda root: RustAdapter(root),
    "go": lambda root: GoAdapter(root),
    "java": lambda root: JavaAdapter(root),
    "swift": lambda root: SwiftAdapter(root),
    "kotlin": lambda root: KotlinAdapter(root),
}
SUPPORTED_LANGUAGES: tuple[str, ...] = tuple(_ADAPTER_REGISTRY.keys())

# Type alias for check names (must match PreCommitCheck enum).
PreCommitCheckName = PreCommitCheck


def _get_adapter(
    language_info: LanguageInfo, project_root: str | None
) -> FrameworkAdapter | None:
    """Get framework adapter for detected language.

    Args:
        language_info: Detected language information.
        project_root: Project root directory.

    Returns:
        Framework adapter instance or None if language not in registry.
    """
    factory = _ADAPTER_REGISTRY.get(language_info.language)
    if factory is None:
        return None
    return factory(project_root)


async def _resolve_language_and_adapter(
    ctx: MCPContext | None,
    root_str: str,
    language: str | None,
) -> ModelDict | tuple[FrameworkAdapter, LanguageInfo]:
    """Resolve language and adapter; return error dict or (adapter, lang_info)."""
    result = detect_or_use_language(language, root_str)
    if isinstance(result, str):
        await log_client(
            ctx,
            "warning",
            "execute_pre_commit_checks: language detection failed",
            logger_name=__name__,
        )
        return cast(ModelDict, json.loads(result))
    language_info, root_to_use = result
    adapter = _get_adapter(language_info, root_to_use)
    if adapter is None:
        await log_client(
            ctx,
            "warning",
            "execute_pre_commit_checks: unsupported language",
            logger_name=__name__,
        )
        return unsupported_language_result_dict(
            language_info.language, SUPPORTED_LANGUAGES
        )
    return (adapter, language_info)


async def _execute_pre_commit_checks_impl(
    root: Path,
    language: str | None,
    checks: Sequence[str] | None,
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run pre-commit checks and return result dict (FastMCP serializes to JSON)."""
    root_str = str(root)
    resolved = await _resolve_language_and_adapter(ctx, root_str, language)
    if isinstance(resolved, dict):
        return resolved
    adapter, language_info = resolved
    checks_to_perform = determine_checks_to_perform(checks)

    results, stats = await run_checks_with_connection_monitoring(
        adapter,
        language_info,
        checks_to_perform,
        strict_mode,
        timeout,
        coverage_threshold,
        ctx,
    )

    out = build_pre_commit_response(results, stats, language_info.language)
    await log_client(
        ctx, "info", "execute_pre_commit_checks: completed", logger_name=__name__
    )
    return out


async def _dispatch_phase(
    phase: str,
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Dispatch to phase-based runner (A, B, or full)."""
    from cortex.tools.execution.pre_commit_phase_dispatch import (
        PreCommitPhase,
        run_execute_pre_commit_checks_by_phase,
    )

    return await run_execute_pre_commit_checks_by_phase(
        PreCommitPhase(phase),
        test_timeout,
        coverage_threshold,
        strict_mode,
        include_untracked_markdown,
        ctx,
    )


async def _run_fix_quality_and_return_dict(
    include_untracked_markdown: bool, ctx: MCPContext | None
) -> ModelDict:
    """Run fix_quality_issues_impl and return result as dict."""
    root = await get_or_resolve_project_root(ctx)
    json_str = await fix_quality_issues_impl(
        Path(root), include_untracked_markdown, ctx
    )
    result = json.loads(json_str)
    return cast(ModelDict, result)


async def _run_fix_quality_mode(
    include_untracked_markdown: bool, ctx: MCPContext | None
) -> ModelDict:
    """Run fix_quality path and return result dict."""
    await log_client(
        ctx,
        "info",
        "execute_pre_commit_checks: fix_quality mode (fix_errors, format, type_check, markdown)",
        logger_name=__name__,
    )
    try:
        return await _run_fix_quality_and_return_dict(include_untracked_markdown, ctx)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"execute_pre_commit_checks fix_quality: {e!s}",
            logger_name=__name__,
        )
        error_json = create_quality_error_response(str(e))
        return cast(ModelDict, json.loads(error_json))


async def _run_standard_checks_mode(
    checks: Sequence[PreCommitCheckName],
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run standard checks path and return result dict."""
    await log_client(
        ctx,
        "info",
        f"execute_pre_commit_checks: checks={list(checks)}, timeout={test_timeout}, cov={coverage_threshold}, strict={strict_mode}",
        logger_name=__name__,
    )
    try:
        root = await get_or_resolve_project_root(ctx)
        return await _execute_pre_commit_checks_impl(
            root, None, checks, strict_mode, test_timeout, coverage_threshold, ctx
        )
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"execute_pre_commit_checks: {e!s}",
            logger_name=__name__,
        )
        return create_error_result_dict(str(e), type(e).__name__)


async def _run_execute_pre_commit_checks(
    checks: Sequence[PreCommitCheckName],
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Resolve root, run impl, log and handle errors."""
    is_fix_quality_only = len(checks) == 1 and checks[0] == PreCommitCheck.FIX_QUALITY
    if is_fix_quality_only:
        return await _run_fix_quality_mode(include_untracked_markdown, ctx)
    return await _run_standard_checks_mode(
        checks, test_timeout, coverage_threshold, strict_mode, ctx
    )


@typed_mcp_tool(
    annotations=external_annotations(
        "Execute Pre-Commit Checks",
        read_only=False,
        destructive=False,
        idempotent=False,
    )
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)
async def execute_pre_commit_checks(
    phase: Literal["A", "B", "full"] | None = None,
    checks: Sequence[PreCommitCheckName] | None = None,
    test_timeout: int = 300,
    coverage_threshold: float = 0.9,
    strict_mode: bool = False,
    include_untracked_markdown: bool = True,
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Run pre-commit checks or a commit-pipeline phase (A, B, or full).

    USE WHEN: Running the quality gate before commit, validating format/type/quality/tests,
    or executing Phase A (preflight) or Phase B (docs/memory sync) of the commit pipeline.

    EXAMPLES: execute_pre_commit_checks(phase="A") for preflight;
    execute_pre_commit_checks(checks=["format", "type_check"]) for targeted checks;
    execute_pre_commit_checks(phase="B") for docs/memory validation after Step 5.

    DO NOT:
    - Run raw pytest/ruff/black commands in a shell for this project; use this MCP tool so
      results are structured and consistent with the commit pipeline.
    - Pass project_root or cwd-style parameters; the tool resolves the project root
      internally.
    - Mix phase and checks in the same call; use either a phase ("A", "B", "full") or an
      explicit checks list.

    RETURNS: JSON with status; for phase "A" or "full": preflight_passed, checks (per-check
    results); for phase "B" or "full": docs_phase_passed, timestamps, roadmap_sync; for
    explicit checks: results per check (format, type_check, quality, tests, etc.).

    Args:
        phase: "A", "B", or "full" for pipeline phases. Optional.
        checks: Required when phase is None. E.g. ["format"], ["type_check", "quality"].
        test_timeout, coverage_threshold, strict_mode: Check options.

    When phase is None, you must pass checks (e.g. ["format"], ["type_check", "quality"],
    ["fix_quality"] for auto-fix only, or ["tests"] with test_timeout and coverage_threshold).
    Language is auto-detected. checks=["fix_quality"] runs fix_errors, format, type_check,
    and markdown lint (no tests); returns fix-quality response shape.
    """
    if phase is not None:
        return await _dispatch_phase(
            phase,
            test_timeout,
            coverage_threshold,
            strict_mode,
            include_untracked_markdown,
            ctx,
        )
    if not checks:
        return create_error_result_dict(
            "checks required when phase is None; or use phase='A'/'B'/'full'",
            "ValidationError",
        )
    return await _run_execute_pre_commit_checks(
        checks,
        test_timeout,
        coverage_threshold,
        strict_mode,
        include_untracked_markdown,
        ctx,
    )
