"""Unit tests for MCP tool timeout behavior.

Tests verify that:
- Timeout wrappers enforce timeouts correctly
- Tools complete successfully within timeout limits
- Timeout errors are clear and actionable
- Different timeout categories work correctly
- All MCP tools have timeout wrapper (Phase 34 verification)
- Long-running semaphore wait allows second call to succeed after first completes
"""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core import mcp_stability_retry
from cortex.core.constants import (
    MCP_MAX_CONCURRENT_RESOURCES,
    MCP_TOOL_TIMEOUT_COMPLEX,
    MCP_TOOL_TIMEOUT_EXTERNAL,
    MCP_TOOL_TIMEOUT_FAST,
    MCP_TOOL_TIMEOUT_MEDIUM,
    MCP_TOOL_TIMEOUT_VERY_COMPLEX,
    PROGRESS_THRESHOLD_TIMEOUT_SECONDS,
)
from cortex.core.mcp_async_utils import cancel_and_drain_progress_task
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
    with_mcp_stability,
)
from cortex.core.models import HandlerKind
from cortex.core.usage_context import set_current_managers
from cortex.managers.initialization import get_project_root


@pytest.fixture(autouse=True)
def _reset_connection_state() -> None:
    """Ensure MCP connection state is healthy before each timeout test."""
    mcp_stability_retry._connection_state = None  # type: ignore[attr-defined]
    _ = mcp_stability_retry._get_connection_state()


async def _block_forever() -> str:
    """Block until timeout (no real sleep). Used for timeout tests."""
    _ = await asyncio.Event().wait()
    return "never"


async def fast_operation() -> str:
    """Fast operation that completes quickly."""
    await asyncio.sleep(0.1)
    return "success"


async def slow_operation(delay: float) -> str:
    """Slow operation that takes specified delay."""
    await asyncio.sleep(delay)
    return "success"


class TestTimeoutEnforcement:
    """Test that timeout wrappers enforce timeouts correctly."""

    @pytest.mark.asyncio
    async def test_fast_operation_completes_within_timeout(self) -> None:
        """Test that fast operations complete successfully within timeout."""
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await with_mcp_stability(
                fast_operation, timeout=MCP_TOOL_TIMEOUT_FAST
            )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_slow_operation_times_out(self) -> None:
        """Test that slow operations timeout correctly."""
        timeout = 0.5
        with pytest.raises(TimeoutError, match="exceeded timeout"):
            _ = await with_mcp_stability(_block_forever, timeout=timeout)

    @pytest.mark.asyncio
    async def test_operation_completes_just_before_timeout(self) -> None:
        """Test that operations completing just before timeout succeed."""
        timeout = 1.0
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await with_mcp_stability(
                slow_operation, timeout=timeout, delay=timeout - 0.1
            )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_timeout_error_message_is_clear(self) -> None:
        """Test that timeout error messages are clear and actionable."""
        timeout = 0.5
        with pytest.raises(TimeoutError) as exc_info:
            _ = await with_mcp_stability(_block_forever, timeout=timeout)
        assert "exceeded timeout" in str(exc_info.value)
        assert str(timeout) in str(exc_info.value)


class TestTimeoutDecorator:
    """Test that @mcp_tool_wrapper decorator works correctly."""

    @pytest.mark.asyncio
    async def test_decorator_applies_timeout(self) -> None:
        """Test that decorator applies timeout protection."""

        @mcp_tool_wrapper(timeout=0.5)
        async def decorated_function() -> str:
            await asyncio.sleep(0.1)
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await decorated_function()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_enforces_timeout(self) -> None:
        """Test that decorator enforces timeout."""

        @mcp_tool_wrapper(timeout=0.5)
        async def decorated_function() -> str:
            _ = await asyncio.Event().wait()
            return "success"

        with pytest.raises(TimeoutError):
            _ = await decorated_function()

    @pytest.mark.asyncio
    async def test_decorator_preserves_signature(self) -> None:
        """Test that decorator preserves function signature for FastMCP."""
        import inspect

        @mcp_tool_wrapper(timeout=1.0)
        async def decorated_function(
            arg1: str, arg2: int = 42, *, kwarg: bool = True
        ) -> str:
            return f"{arg1}-{arg2}-{kwarg}"

        sig = inspect.signature(decorated_function)
        params = list(sig.parameters.keys())
        assert "arg1" in params
        assert "arg2" in params
        assert "kwarg" in params
        assert sig.return_annotation is str

    @pytest.mark.asyncio
    async def test_decorator_with_enable_progress_false_completes(self) -> None:
        """Decorator with enable_progress=False completes without progress task."""

        @mcp_tool_wrapper(
            timeout=PROGRESS_THRESHOLD_TIMEOUT_SECONDS + 10,
            enable_progress=False,
        )
        async def long_timeout_tool() -> str:
            await asyncio.sleep(0.1)
            return "ok"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await long_timeout_tool()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_decorator_with_timeout_above_threshold_completes(self) -> None:
        """Decorator with timeout >= threshold completes (progress only when ctx present)."""

        @mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
        async def complex_tool() -> str:
            await asyncio.sleep(0.1)
            return "ok"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await complex_tool()
        assert result == "ok"


class TestTimeoutCategories:
    """Test that different timeout categories work correctly."""

    @pytest.mark.asyncio
    async def test_fast_timeout_category(self) -> None:
        """Test fast timeout category (60s)."""
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await with_mcp_stability(
                fast_operation, timeout=MCP_TOOL_TIMEOUT_FAST
            )
        assert result == "success"
        assert MCP_TOOL_TIMEOUT_FAST == 60

    @pytest.mark.asyncio
    async def test_medium_timeout_category(self) -> None:
        """Test medium timeout category (120s)."""
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await with_mcp_stability(
                fast_operation, timeout=MCP_TOOL_TIMEOUT_MEDIUM
            )
        assert result == "success"
        assert MCP_TOOL_TIMEOUT_MEDIUM == 120

    @pytest.mark.asyncio
    async def test_complex_timeout_category(self) -> None:
        """Test complex timeout category (300s)."""
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await with_mcp_stability(
                fast_operation, timeout=MCP_TOOL_TIMEOUT_COMPLEX
            )
        assert result == "success"
        assert MCP_TOOL_TIMEOUT_COMPLEX == 300

    @pytest.mark.asyncio
    async def test_very_complex_timeout_category(self) -> None:
        """Test very complex timeout category (960s for full test run)."""
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await with_mcp_stability(
                fast_operation, timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX
            )
        assert result == "success"
        assert MCP_TOOL_TIMEOUT_VERY_COMPLEX == 960.0

    @pytest.mark.asyncio
    async def test_external_timeout_category(self) -> None:
        """Test external timeout category (120s)."""
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await with_mcp_stability(
                fast_operation, timeout=MCP_TOOL_TIMEOUT_EXTERNAL
            )
        assert result == "success"
        assert MCP_TOOL_TIMEOUT_EXTERNAL == 120


class TestTimeoutEdgeCases:
    """Test edge cases for timeout behavior."""

    @pytest.mark.asyncio
    async def test_very_fast_operation_does_not_timeout_prematurely(
        self,
    ) -> None:
        """Test that very fast operations don't timeout prematurely."""

        async def very_fast() -> str:
            return "instant"

        result = await with_mcp_stability(very_fast, timeout=MCP_TOOL_TIMEOUT_FAST)
        assert result == "instant"

    @pytest.mark.asyncio
    async def test_operation_exceeding_timeout_raises_error(self) -> None:
        """Test that operations exceeding timeout raise TimeoutError."""
        timeout = 0.1
        with pytest.raises(TimeoutError):
            _ = await with_mcp_stability(
                slow_operation, timeout=timeout, delay=timeout * 2
            )


class TestJsonValueTimeoutNormalization:
    """Test JsonValue timeout normalization behavior."""

    @pytest.mark.asyncio
    async def test_timeout_accepts_numeric_string(self) -> None:
        """Test that numeric string timeouts are accepted and enforced."""
        # Arrange
        timeout_str = "0.2"
        delay = float(timeout_str) + 0.2

        # Act & Assert
        with pytest.raises(TimeoutError):
            _ = await with_mcp_stability(
                slow_operation,
                timeout=timeout_str,
                delay=delay,
            )

    @pytest.mark.asyncio
    async def test_timeout_invalid_string_falls_back_to_default(self) -> None:
        """Test that invalid timeout strings fall back to default timeout."""

        # Arrange
        async def very_fast() -> str:
            return "instant"

        # Act
        result = await with_mcp_stability(very_fast, timeout="not-a-number")

        # Assert
        assert result == "instant"


class TestProgressHelpers:
    """Tests for progress-related helper utilities."""

    @pytest.mark.asyncio
    async def test_cancel_and_drain_progress_task_cancels_task(self) -> None:
        """cancel_and_drain_progress_task should cancel and drain the task."""

        async def never_finishes() -> None:
            _ = await asyncio.Event().wait()

        task = asyncio.create_task(never_finishes())
        await cancel_and_drain_progress_task(task)
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_timeout_with_exception_handling(self) -> None:
        """Test that timeout errors are properly handled."""
        timeout = 0.1

        async def operation_that_raises() -> str:
            _ = await asyncio.Event().wait()
            raise ValueError("Should not reach here")

        with pytest.raises(TimeoutError):
            _ = await with_mcp_stability(operation_that_raises, timeout=timeout)

    @pytest.mark.asyncio
    async def test_progress_task_cancelled_on_tool_error(self) -> None:
        """Progress task must be cancelled when tool raises, preventing orphaned notifications.

        Reproduces the bug where execute_pre_commit_checks returned early with an
        error but the progress loop kept sending notifications for a resolved
        progressToken, causing "unknown token" errors that killed the connection.
        """
        progress_loop_running = asyncio.Event()

        async def fake_progress_loop() -> None:
            progress_loop_running.set()
            while True:
                await asyncio.sleep(0)  # Yield only; no real delay

        async def tool_that_fails() -> str:
            raise RuntimeError("Tool failed early")

        from cortex.core.mcp_stability import _run_and_finalize
        from cortex.core.mcp_stability_config import get_semaphore

        progress_task = asyncio.create_task(fake_progress_loop())
        _ = await progress_loop_running.wait()
        assert not progress_task.done(), "Progress task should be running"

        semaphore = get_semaphore()

        async def execute_fn() -> (
            tuple[str, bool, str | None, bool, int | None, str | None]
        ):
            async with semaphore:
                result = await tool_that_fails()
            return result, True, None, False, None, None

        with pytest.raises(RuntimeError, match="Tool failed early"):
            _ = await _run_and_finalize(
                execute_fn,
                progress_task,
                None,
                "test_tool",
                0,
                HandlerKind.TOOL,
            )

        assert progress_task.done(), "Progress task must be cancelled after tool error"


class TestLongRunningSemaphoreWait:
    """Tests for long-running tool serialization with configurable wait."""

    def test_long_running_wait_at_least_default_test_timeout(self) -> None:
        """Wait must be >= execute_pre_commit_checks default test_timeout so sequential calls succeed."""
        from cortex.core.mcp_stability_config import LONG_RUNNING_SEMAPHORE_WAIT_SECONDS

        # execute_pre_commit_checks default test_timeout is 300s; second call must wait that long.
        assert LONG_RUNNING_SEMAPHORE_WAIT_SECONDS >= 300.0, (
            "LONG_RUNNING_SEMAPHORE_WAIT_SECONDS must be >= 300 so a second long-running tool "
            "can wait for execute_pre_commit_checks (with default test_timeout) to finish."
        )

    @pytest.mark.asyncio
    async def test_second_long_running_waits_then_succeeds(self) -> None:
        """Second long-running call waits for first to finish then runs (reduces commit blocking)."""
        import cortex.core.mcp_stability_semaphores as semaphores_mod
        from cortex.core.mcp_stability import _run_and_finalize
        from cortex.core.mcp_stability_config import get_long_running_semaphore

        semaphores_mod._long_running_tools_semaphore = None
        _ = get_long_running_semaphore()
        first_done: asyncio.Event = asyncio.Event()
        first_acquired: asyncio.Event = asyncio.Event()

        async def first_execute() -> (
            tuple[str, bool, str | None, bool, int | None, str | None]
        ):
            _ = first_acquired.set()
            _ = await first_done.wait()
            return "first", True, None, False, None, None

        async def second_execute() -> (
            tuple[str, bool, str | None, bool, int | None, str | None]
        ):
            return "second", True, None, False, None, None

        with patch(
            "cortex.core.mcp_stability_semaphores.LONG_RUNNING_SEMAPHORE_WAIT_SECONDS",
            1.0,
        ):
            # Start first (holds semaphore), then second (waits then runs)
            first_task: asyncio.Task[str] = asyncio.create_task(
                _run_and_finalize(
                    first_execute,
                    None,
                    None,
                    "first_tool",
                    0,
                    HandlerKind.TOOL,
                    use_serial_semaphore=True,
                )
            )
            _ = await first_acquired.wait()
            second_task: asyncio.Task[str] = asyncio.create_task(
                _run_and_finalize(
                    second_execute,
                    None,
                    None,
                    "second_tool",
                    0,
                    HandlerKind.TOOL,
                    use_serial_semaphore=True,
                )
            )
            first_done.set()
            first_result: str = await first_task
            second_result: str = await second_task
        assert first_result == "first"
        assert second_result == "second"

    @pytest.mark.asyncio
    async def test_second_long_running_fails_after_wait_timeout(self) -> None:
        """Second long-running call raises RuntimeError if first runs longer than wait."""
        import cortex.core.mcp_stability_semaphores as semaphores_mod
        from cortex.core.mcp_stability import _run_and_finalize
        from cortex.core.mcp_stability_config import get_long_running_semaphore

        semaphores_mod._long_running_tools_semaphore = None
        sem = get_long_running_semaphore()
        await sem.acquire()
        try:

            async def fast_execute() -> (
                tuple[str, bool, str | None, bool, int | None, str | None]
            ):
                return "fast", True, None, False, None, None

            with patch(
                "cortex.core.mcp_stability_semaphores.LONG_RUNNING_SEMAPHORE_WAIT_SECONDS",
                0.15,
            ):
                with pytest.raises(RuntimeError, match="Another long-running tool"):
                    _ = await _run_and_finalize(
                        fast_execute,
                        None,
                        None,
                        "second_tool",
                        0,
                        HandlerKind.TOOL,
                        use_serial_semaphore=True,
                    )
        finally:
            sem.release()


def _tools_dir() -> Path:
    """Return src/cortex/tools path relative to repo root."""
    return get_project_root() / "src" / "cortex" / "tools"


def _file_has_mcp_tool_missing_required_wrappers(content: str) -> list[int]:
    """Return line numbers where @mcp.tool() lacks required decorator stack.

    Required stack (in order): @mcp.tool(), @ensure_usage_context, @mcp_tool_wrapper(...).
    """
    lines = content.splitlines()
    bad: list[int] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == "@mcp.tool()":
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines):
                bad.append(i + 1)
                break
            first = lines[j].strip()
            if first != "@ensure_usage_context":
                bad.append(i + 1)
                i = j
                i += 1
                continue
            j += 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines):
                bad.append(i + 1)
                break
            second = lines[j].strip()
            if not second.startswith("@mcp_tool_wrapper("):
                bad.append(i + 1)
            i = j
        i += 1
    return bad


def _functions_with_both_tool_and_resource(content: str) -> list[tuple[int, int]]:
    """Return (decorator_start_1based, async_def_line_1based) for double-registrations.

    Phase 56 Step 7: No function must be registered as both @mcp.tool() and
    @mcp.resource(); resources must be resource-only so they do not count toward
    the tool limit.
    """
    lines = content.splitlines()
    result: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("async def "):
            # Collect decorator block (lines above this def that are decorators)
            block_start = i
            j = i - 1
            while j >= 0 and (lines[j].strip().startswith("@") or not lines[j].strip()):
                if lines[j].strip().startswith("@"):
                    block_start = j
                j -= 1
            block = " ".join(lines[k].strip() for k in range(block_start, i))
            if "@mcp.tool(" in block and "@mcp.resource(" in block:
                result.append((block_start + 1, i + 1))
        i += 1
    return result


def _file_has_mcp_resource_missing_required_wrappers(content: str) -> list[int]:
    """Return line numbers where @mcp.resource(uri=...) lacks required stack.

    Required stack (Phase 43): @mcp.resource(uri=...), @ensure_usage_context,
    @mcp_resource_wrapper(timeout=...).
    """
    lines = content.splitlines()
    bad: list[int] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if "@mcp.resource(" in stripped and "uri=" in stripped:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines):
                bad.append(i + 1)
                i = j
                continue
            first = lines[j].strip()
            if first != "@ensure_usage_context":
                bad.append(i + 1)
                i = j
                i += 1
                continue
            j += 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines):
                bad.append(i + 1)
                break
            second = lines[j].strip()
            if not second.startswith("@mcp_resource_wrapper("):
                bad.append(i + 1)
            i = j
        i += 1
    return bad


class TestAllToolsHaveTimeoutWrapper:
    """Phase 34: Every @mcp.tool() must have @ensure_usage_context and @mcp_tool_wrapper."""

    def test_every_mcp_tool_has_required_wrappers(self) -> None:
        """Every @mcp.tool() must have @ensure_usage_context then @mcp_tool_wrapper(timeout=...)."""
        tools_dir = _tools_dir()
        assert tools_dir.is_dir(), f"Tools dir not found: {tools_dir}"
        violations: list[tuple[str, list[int]]] = []
        for path in sorted(tools_dir.glob("*.py")):
            if path.name.startswith("__"):
                continue
            text = path.read_text()
            bad_lines = _file_has_mcp_tool_missing_required_wrappers(text)
            if bad_lines:
                violations.append((path.name, bad_lines))
        assert not violations, (
            "MCP tools missing required decorator stack (@mcp.tool() -> @ensure_usage_context -> @mcp_tool_wrapper): "
            + ", ".join(f"{f}: lines {lns}" for f, lns in violations)
        )


class TestProjectRootStrippedFromToolKwargs:
    """project_root is stripped before calling tools; tools resolve root internally."""

    @pytest.mark.asyncio
    async def test_with_mcp_stability_strips_project_root_from_kwargs(self) -> None:
        """When project_root is passed to with_mcp_stability, it is stripped.

        Tools resolve root internally and must not accept project_root
        as a parameter.
        """
        from unittest.mock import AsyncMock, patch

        from cortex.core.models import ConnectionHealth

        received_kwargs: list[dict[str, object]] = []

        async def tool_with_kwargs(**kwargs: object) -> str:
            received_kwargs.append(dict(kwargs))
            return "ok"

        with patch(
            "cortex.core.mcp_stability.check_connection_health",
            new_callable=AsyncMock,
            return_value=ConnectionHealth(
                healthy=True,
                concurrent_operations=0,
                max_concurrent=5,
                semaphore_available=5,
                utilization_percent=0.0,
            ),
        ):
            result = await with_mcp_stability(
                tool_with_kwargs,
                timeout=MCP_TOOL_TIMEOUT_FAST,
                project_root="/some/path",
            )

        assert result == "ok"
        assert len(received_kwargs) == 1
        # project_root must be stripped; tools resolve root internally
        first_kw: dict[str, object] = received_kwargs[0]
        assert "project_root" not in first_kw


class TestResourceReadsUseSeparateSemaphore:
    """Phase 69: Resource reads use a dedicated semaphore so they do not queue behind tools."""

    @pytest.mark.asyncio
    async def test_resource_reads_use_resource_semaphore_not_tool_semaphore(
        self,
    ) -> None:
        """When kind='resource', tool semaphore is not used (resource semaphore is used)."""
        from unittest.mock import AsyncMock, patch

        from cortex.core.models import ConnectionHealth

        async def dummy_resource() -> str:
            return "ok"

        health = ConnectionHealth(
            healthy=True,
            concurrent_operations=0,
            max_concurrent=5,
            semaphore_available=5,
            utilization_percent=0.0,
        )

        with patch(
            "cortex.core.mcp_stability.check_connection_health",
            new_callable=AsyncMock,
            return_value=health,
        ):
            # If resource path used tool semaphore, patching get_semaphore to raise would fail.
            with patch(
                "cortex.core.mcp_stability.get_semaphore",
                side_effect=RuntimeError(
                    "tool semaphore must not be used for resources"
                ),
            ):
                result = await with_mcp_stability(
                    dummy_resource,
                    stability_timeout=10.0,
                    kind=HandlerKind.RESOURCE,
                )
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_parallel_resource_reads_all_succeed(self) -> None:
        """Multiple resource reads in parallel all complete successfully."""
        from unittest.mock import AsyncMock, patch

        from cortex.core.models import ConnectionHealth

        num_calls = 8
        health = ConnectionHealth(
            healthy=True,
            concurrent_operations=0,
            max_concurrent=5,
            semaphore_available=5,
            utilization_percent=0.0,
        )

        async def fast_resource() -> str:
            return "ok"

        with patch(
            "cortex.core.mcp_stability.check_connection_health",
            new_callable=AsyncMock,
            return_value=health,
        ):
            results = await asyncio.gather(
                *[
                    with_mcp_stability(
                        fast_resource,
                        stability_timeout=5.0,
                        kind=HandlerKind.RESOURCE,
                    )
                    for _ in range(num_calls)
                ]
            )

        assert list(results) == ["ok"] * num_calls

    def test_resource_concurrency_constant_at_least_six(self) -> None:
        """MCP_MAX_CONCURRENT_RESOURCES allows at least 6 parallel resource reads."""
        assert MCP_MAX_CONCURRENT_RESOURCES >= 6


class TestAllResourcesHaveRequiredWrappers:
    """Phase 43: Every @mcp.resource(uri=...) must have ensure_usage_context and mcp_resource_wrapper."""

    def test_every_mcp_resource_has_required_wrappers(self) -> None:
        """Every @mcp.resource(uri=...) must have @ensure_usage_context then @mcp_resource_wrapper(timeout=...)."""
        tools_dir = _tools_dir()
        assert tools_dir.is_dir(), f"Tools dir not found: {tools_dir}"
        violations: list[tuple[str, list[int]]] = []
        for path in sorted(tools_dir.glob("*.py")):
            if path.name.startswith("__"):
                continue
            text = path.read_text()
            bad_lines = _file_has_mcp_resource_missing_required_wrappers(text)
            if bad_lines:
                violations.append((path.name, bad_lines))
        assert not violations, (
            "MCP resources missing required decorator stack (@mcp.resource(uri=...) -> @ensure_usage_context -> @mcp_resource_wrapper): "
            + ", ".join(f"{f}: lines {lns}" for f, lns in violations)
        )


class TestNoResourceDoubleRegisteredAsTool:
    """Phase 56 Step 7: Resources must be resource-only (no @mcp.tool on same function)."""

    def test_no_function_has_both_mcp_tool_and_mcp_resource(self) -> None:
        """No async def may have both @mcp.tool() and @mcp.resource() in its decorators."""
        tools_dir = _tools_dir()
        core_dir = tools_dir.parent / "core"
        violations: list[tuple[str, list[tuple[int, int]]]] = []
        for directory in (tools_dir, core_dir):
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.py")):
                if path.name.startswith("__"):
                    continue
                text = path.read_text()
                pairs = _functions_with_both_tool_and_resource(text)
                if pairs:
                    violations.append((path.name, pairs))
        assert not violations, (
            "Functions must not be registered as both tool and resource (Step 7): "
            + ", ".join(f"{f}: decorator+def at {pairs}" for f, pairs in violations)
        )


class TestUsageContextInitLockTimeout:
    """Test that usage context init lock has timeout to prevent indefinite hangs."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)  # Allow up to 30s for this test (timeout + overhead)
    async def test_usage_context_init_lock_timeout(self) -> None:
        """Test that usage context init lock times out after configured duration."""
        from unittest.mock import AsyncMock, patch

        # Clear current managers to force lock acquisition
        set_current_managers(None)

        @ensure_usage_context
        async def test_tool() -> str:
            return "success"

        # Create a lock that will be held indefinitely by simulating a stuck initialization
        from cortex.core.mcp_stability_config import get_usage_context_init_lock

        lock = get_usage_context_init_lock()

        # Hold the lock in a background task to simulate a stuck initialization
        lock_acquired: asyncio.Event = asyncio.Event()

        async def hold_lock_forever() -> None:
            async with lock:
                _ = lock_acquired.set()
                _ = await asyncio.Event().wait()

        # Start holding the lock
        hold_task = asyncio.create_task(hold_lock_forever())
        _ = await lock_acquired.wait()

        try:
            # Mock resolve_project_root_async and get_managers to avoid real file system operations
            with (
                patch(
                    "cortex.core.project_root_resolver.resolve_project_root_async",
                    new_callable=AsyncMock,
                    return_value=Path("/test"),
                ),
                patch(
                    "cortex.managers.initialization.get_managers",
                    new_callable=AsyncMock,
                    return_value={},
                ),
            ):
                # Attempt to call tool - should timeout trying to acquire lock
                with pytest.raises(
                    RuntimeError, match="Failed to acquire usage context init lock"
                ):
                    _ = await test_tool()
        finally:
            # Clean up: cancel the hold task and release lock
            _ = hold_task.cancel()
            try:
                _ = await hold_task
            except asyncio.CancelledError:
                pass
            # Reset managers for other tests
            set_current_managers(None)

    @pytest.mark.asyncio
    async def test_usage_context_init_lock_succeeds_when_not_held(self) -> None:
        """Test that usage context init succeeds when lock is not held."""
        from unittest.mock import AsyncMock, patch

        # Clear current managers to force lock acquisition
        set_current_managers(None)

        @ensure_usage_context
        async def test_tool() -> str:
            return "success"

        # Mock initialization to avoid real file system operations
        with (
            patch(
                "cortex.core.project_root_resolver.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/test"),
            ),
            patch(
                "cortex.managers.initialization.get_managers",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await test_tool()
            assert result == "success"
