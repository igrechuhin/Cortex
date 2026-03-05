"""MCP connection stability and resource management.

This module provides connection stability features for MCP tool handlers:
- Timeout protection for long-running operations
- Resource limit enforcement (concurrent operations)
- Connection error handling and recovery
- Connection health monitoring
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar, cast

from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_SECONDS,
    PROGRESS_THRESHOLD_TIMEOUT_SECONDS,
)
from cortex.core.mcp_annotations import ToolAnnotations
from cortex.core.mcp_async_utils import cancel_and_drain_progress_task
from cortex.core.mcp_stability_config import (
    TrackedSemaphore,
    get_resource_semaphore,
    get_semaphore,
    long_running_tools_serialized,
    record_usage_finish,
    run_and_finalize_impl,
    to_timeout_value,
)
from cortex.core.mcp_stability_progress import (
    cancel_progress_and_report_done,
    create_progress_task_if_needed,
)
from cortex.core.mcp_stability_retry import (
    check_connection_health,
    execute_with_retry,
    reconnect,
)
from cortex.core.mcp_stability_usage import (
    ensure_usage_context,
    handle_tool_exception_if_failure,
)
from cortex.core.models import (
    HandlerKind,
    JsonValue,
    MCPToolArguments,
)
from cortex.core.protocols.mcp import SignatureAware

TToolFunc = TypeVar("TToolFunc", bound=Callable[..., Awaitable[object]])


# Re-export for backward compatibility
__all__ = [
    "ensure_usage_context",
    "with_mcp_stability",
    "mcp_tool_wrapper",
    "mcp_resource_wrapper",
    "execute_tool_with_stability",
    "check_connection_health",
    "reconnect",
    "CANCELLED_RESPONSE_JSON",
    "typed_mcp_tool",
]

# Returned to the client when the request was cancelled (e.g. client timeout).
CANCELLED_RESPONSE_JSON = '{"status":"error","error":"CancelledError","message":"Tool call was cancelled by client"}'


def typed_mcp_tool(
    *,
    annotations: ToolAnnotations | None,
) -> Callable[[TToolFunc], TToolFunc]:
    """Typed wrapper around mcp.tool to satisfy pyright.

    This keeps FastMCP as the single source of truth for tool registration
    while providing a typed decorator so tools don't need per-site suppressions.
    """
    from cortex.server import mcp as _mcp

    decorator = _mcp.tool(annotations=annotations)

    def _wrapper(func: TToolFunc) -> TToolFunc:
        return cast(TToolFunc, decorator(func))

    return _wrapper


def _stability_params(
    timeout: JsonValue | None,
    stability_timeout: JsonValue | None,
    kwargs: dict[str, JsonValue],
) -> tuple[float, MCPToolArguments, JsonValue | None]:
    """Compute effective timeout, validated kwargs, and ctx for with_mcp_stability."""
    st = to_timeout_value(stability_timeout)
    tv = to_timeout_value(timeout)
    effective = st or tv or float(MCP_TOOL_TIMEOUT_SECONDS)
    ctx = kwargs.get("ctx")
    func_kwargs = {
        k: v
        for k, v in kwargs.items()
        if k not in {"timeout", "stability_timeout", "kind", "ctx", "project_root"}
    }
    return effective, MCPToolArguments.model_validate(func_kwargs), ctx


def _prepare_execution_context(
    timeout: JsonValue | None,
    stability_timeout: JsonValue | None,
    kwargs: dict[str, JsonValue],
    kind: HandlerKind,
    enable_progress: bool,
    func_name: str,
) -> tuple[
    TrackedSemaphore,
    float,
    MCPToolArguments,
    JsonValue | None,
    asyncio.Task[None] | None,
    int,
]:
    """Prepare execution context for retry and record."""
    semaphore = (
        get_resource_semaphore() if kind == HandlerKind.RESOURCE else get_semaphore()
    )
    effective_timeout, kwargs_model, ctx = _stability_params(
        timeout, stability_timeout, kwargs
    )
    progress_task = create_progress_task_if_needed(
        enable_progress, ctx, effective_timeout, func_name
    )
    start_ns = time.perf_counter_ns()
    return semaphore, effective_timeout, kwargs_model, ctx, progress_task, start_ns


async def _finalize_execution(
    progress_task: asyncio.Task[None] | None,
    ctx: JsonValue | None,
    func_name: str,
    start_ns: int,
    was_cancelled: bool,
    success: bool,
    error_type: str | None,
    kind: HandlerKind,
    retry_count: int | None = None,
    param_validation_failure: str | None = None,
    response_tokens: int | None = None,
) -> None:
    """Finalize execution: cancel progress and record usage."""
    if not was_cancelled:
        await cancel_progress_and_report_done(progress_task, ctx, func_name)
    await record_usage_finish(
        func_name,
        start_ns,
        success,
        error_type,
        kind=kind,
        retry_count=retry_count,
        param_validation_failure=param_validation_failure,
        response_tokens=response_tokens,
    )


async def _handle_cancellation(
    progress_task: asyncio.Task[None] | None,
) -> tuple[bool, str, bool]:
    """Handle cancellation exception."""
    if progress_task is not None:
        await cancel_and_drain_progress_task(progress_task)
    return False, "CancelledError", True


async def _execute_with_error_handling[T](
    func: Callable[..., Awaitable[T]],
    semaphore: TrackedSemaphore,
    effective_timeout: float,
    args: tuple[JsonValue, ...],
    kwargs_model: MCPToolArguments,
    ctx: JsonValue | None,
    progress_task: asyncio.Task[None] | None,
) -> tuple[T, bool, str | None, bool, int | None, str | None]:
    """Execute function with retry and handle exceptions."""
    success, error_type, was_cancelled = True, None, False
    try:
        result, attempt = await execute_with_retry(
            func, semaphore, effective_timeout, args, kwargs_model, ctx
        )
        retry_count = attempt - 1 if attempt else 0
        return result, success, error_type, was_cancelled, retry_count, None
    except asyncio.CancelledError:
        success, error_type, was_cancelled = await _handle_cancellation(progress_task)
        return (
            cast(T, CANCELLED_RESPONSE_JSON),
            success,
            error_type,
            was_cancelled,
            None,
            None,
        )
    except Exception as e:
        success, error_type = False, type(e).__name__
        raise


async def _run_and_finalize[T](
    execute_fn: Callable[
        [], Awaitable[tuple[T, bool, str | None, bool, int | None, str | None]]
    ],
    progress_task: asyncio.Task[None] | None,
    ctx: JsonValue | None,
    func_name: str,
    start_ns: int,
    kind: HandlerKind,
    use_serial_semaphore: bool = False,
) -> T:
    """Run execute_fn and finalize (cancel progress, record usage)."""
    return await run_and_finalize_impl(
        _finalize_execution,
        execute_fn,
        progress_task,
        ctx,
        func_name,
        start_ns,
        kind,
        use_serial_semaphore,
    )


def _use_serial_semaphore(kind: HandlerKind, func_name: str) -> bool:
    """Return True if long-running tools should be serialized."""
    return kind == HandlerKind.TOOL and func_name in long_running_tools_serialized


async def _run_with_retry_and_record[T](
    func: Callable[..., Awaitable[T]],
    args: tuple[JsonValue, ...],
    timeout: JsonValue | None,
    stability_timeout: JsonValue | None,
    kwargs: dict[str, JsonValue],
    kind: HandlerKind = HandlerKind.TOOL,
    enable_progress: bool = False,
) -> T:
    """Run func with retry and record usage. Long-running tools are serialized."""
    semaphore, effective_timeout, kwargs_model, ctx, progress_task, start_ns = (
        _prepare_execution_context(
            timeout, stability_timeout, kwargs, kind, enable_progress, func.__name__
        )
    )

    async def _execute_and_finalize() -> (
        tuple[T, bool, str | None, bool, int | None, str | None]
    ):
        return await _execute_with_error_handling(
            func, semaphore, effective_timeout, args, kwargs_model, ctx, progress_task
        )

    return await _run_and_finalize(
        _execute_and_finalize,
        progress_task,
        ctx,
        func.__name__,
        start_ns,
        kind,
        use_serial_semaphore=_use_serial_semaphore(kind, func.__name__),
    )


async def with_mcp_stability[T](
    func: Callable[..., Awaitable[T]],
    *args: JsonValue,
    timeout: JsonValue | None = None,
    stability_timeout: JsonValue | None = None,
    kind: HandlerKind = HandlerKind.TOOL,
    enable_progress: bool = False,
    **kwargs: JsonValue,
) -> T:
    """Execute MCP tool or resource handler with stability protections."""
    health = await check_connection_health()
    if not health.healthy:
        raise ConnectionError("Connection not healthy before tool execution")
    return await _run_with_retry_and_record(
        func,
        args,
        timeout,
        stability_timeout,
        kwargs,
        kind=kind,
        enable_progress=enable_progress,
    )


def _make_tool_wrapper_func[T](
    func: Callable[..., Awaitable[T]],
    timeout: float,
    progress_enabled: bool,
) -> Callable[..., Awaitable[T]]:
    """Build wrapped async tool with stability and optional progress (Phase 46)."""
    import functools

    @functools.wraps(func)
    async def wrapper(
        *args: JsonValue,
        **kwargs: JsonValue,
    ) -> T:
        from cortex.core.context_logging import MCPContext

        kwargs_no_progress = {k: v for k, v in kwargs.items() if k != "enable_progress"}
        try:
            return await with_mcp_stability(
                func,
                *args,
                stability_timeout=timeout,
                kind=HandlerKind.TOOL,
                enable_progress=progress_enabled,
                **kwargs_no_progress,
            )
        except Exception as e:
            ctx_raw = kwargs.get("ctx")
            mcp_ctx = cast(MCPContext | None, ctx_raw)
            await handle_tool_exception_if_failure(e, func.__name__, mcp_ctx)
            raise

    return wrapper


def mcp_tool_wrapper[T](
    timeout: float = MCP_TOOL_TIMEOUT_SECONDS,
    enable_progress: bool | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for MCP tools to add stability protections."""
    import inspect

    progress_enabled = (
        enable_progress
        if enable_progress is not None
        else timeout >= PROGRESS_THRESHOLD_TIMEOUT_SECONDS
    )

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        wrapper = _make_tool_wrapper_func(func, timeout, progress_enabled)
        cast(SignatureAware, wrapper).__signature__ = inspect.signature(func)
        return wrapper

    return decorator


def mcp_resource_wrapper[T](
    timeout: float = MCP_TOOL_TIMEOUT_SECONDS,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for MCP resources to add stability protections (Phase 43)."""
    import functools
    import inspect

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(
            *args: JsonValue,
            **kwargs: JsonValue,
        ) -> T:
            kwargs_no_progress = {
                k: v for k, v in kwargs.items() if k != "enable_progress"
            }
            return await with_mcp_stability(
                func,
                *args,
                stability_timeout=timeout,
                kind=HandlerKind.RESOURCE,
                enable_progress=False,
                **kwargs_no_progress,
            )

        original_sig = inspect.signature(func)
        cast(SignatureAware, wrapper).__signature__ = original_sig
        return wrapper

    return decorator


async def execute_tool_with_stability[T](
    func: Callable[..., Awaitable[T]],
    *args: JsonValue,
    timeout: float = MCP_TOOL_TIMEOUT_SECONDS,
    **kwargs: JsonValue,
) -> T:
    """Execute MCP tool function with stability protections."""
    kwargs_clean = {
        k: v for k, v in kwargs.items() if k not in ("kind", "enable_progress")
    }
    return await with_mcp_stability(
        func,
        *args,
        stability_timeout=timeout,
        kind=HandlerKind.TOOL,
        enable_progress=False,
        **kwargs_clean,
    )
