"""Inline pre-commit execution: language adapters and in-process check runs.

Extracted from pre_commit_tools to keep that module within file-size limits.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from cortex.core.context_logging import MCPContext, log_client
from cortex.core.models import ModelDict
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
from cortex.tools.execution.pre_commit_helpers import (
    determine_checks_to_perform,
    unsupported_language_result_dict,
)
from cortex.tools.execution.pre_commit_helpers_language import detect_or_use_language
from cortex.tools.execution.pre_commit_submodule_guard import precommit_block_response
from cortex.tools.execution.pre_commit_tools_run_helpers import (
    build_pre_commit_response,
    run_checks_with_connection_monitoring,
)

logger = logging.getLogger(__name__)

# Adapter registry: language -> factory(project_root) -> FrameworkAdapter.
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
# Public alias for pre_commit_worker subprocess (avoids reportPrivateUsage).
ADAPTER_REGISTRY = _ADAPTER_REGISTRY


def get_adapter(
    language_info: LanguageInfo, project_root: str | None
) -> FrameworkAdapter | None:
    """Get framework adapter for detected language."""
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
    adapter = get_adapter(language_info, root_to_use)
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


async def _submodule_hygiene_gate(
    root: Path, ctx: MCPContext | None
) -> ModelDict | None:
    blocked = await asyncio.to_thread(precommit_block_response, root)
    if blocked is None:
        return None
    await log_client(
        ctx,
        "warning",
        "execute_pre_commit_checks: blocked — submodule hygiene check failed",
        logger_name=__name__,
    )
    return blocked


async def _execute_inline_checks_after_hygiene(
    root: Path,
    language: str | None,
    checks: Sequence[str] | None,
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    ctx: MCPContext | None,
) -> ModelDict:
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


async def run_inline_pre_commit_checks(
    root: Path,
    language: str | None,
    checks: Sequence[str] | None,
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run pre-commit checks in-process (non-detached)."""
    blocked = await _submodule_hygiene_gate(root, ctx)
    if blocked is not None:
        return blocked
    return await _execute_inline_checks_after_hygiene(
        root,
        language,
        checks,
        strict_mode,
        timeout,
        coverage_threshold,
        ctx,
    )


__all__ = [
    "ADAPTER_REGISTRY",
    "SUPPORTED_LANGUAGES",
    "get_adapter",
    "run_inline_pre_commit_checks",
    "_execute_inline_checks_after_hygiene",
    "_resolve_language_and_adapter",
    "_submodule_hygiene_gate",
]
