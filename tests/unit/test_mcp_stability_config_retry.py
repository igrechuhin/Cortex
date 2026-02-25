"""Unit tests for connection retry overrides and response token flow in mcp_stability_config.

Blocker: MCP disconnects during commit - server-side retry with
exponential backoff for fix_markdown_lint.

Phase 62: Token-efficiency tracking - response_tokens passed through run_execute_and_finalize.
"""

import pytest

from cortex.core.mcp_stability_config import (
    get_connection_retry_attempts,
    get_connection_retry_delay,
    run_execute_and_finalize,
)


class TestConnectionRetryOverrides:
    """Tests for per-tool connection retry attempts and delays."""

    def test_fix_markdown_lint_gets_four_attempts(self) -> None:
        """fix_markdown_lint has 4 attempts (1 initial + 3 retries)."""
        assert get_connection_retry_attempts("fix_markdown_lint") == 4

    def test_fix_markdown_lint_exponential_backoff_delays(self) -> None:
        """fix_markdown_lint uses 1s, 2s, 4s delays before retries 2, 3, 4."""
        assert get_connection_retry_delay("fix_markdown_lint", 1) == 1.0
        assert get_connection_retry_delay("fix_markdown_lint", 2) == 2.0
        assert get_connection_retry_delay("fix_markdown_lint", 3) == 4.0

    def test_unknown_tool_uses_default_attempts(self) -> None:
        """Tools not in overrides use MCP_CONNECTION_RETRY_ATTEMPTS (2)."""
        assert get_connection_retry_attempts("other_tool") == 2

    def test_unknown_tool_uses_linear_delay(self) -> None:
        """Tools not in overrides use MCP_CONNECTION_RETRY_DELAY_SECONDS * attempt."""
        # Default MCP_CONNECTION_RETRY_DELAY_SECONDS is 0.5
        assert get_connection_retry_delay("other_tool", 1) == 0.5
        assert get_connection_retry_delay("other_tool", 2) == 1.0


class TestRunExecuteAndFinalizeResponseTokens:
    """Tests for response_tokens flow in run_execute_and_finalize (Phase 62)."""

    @pytest.mark.asyncio
    async def test_success_path_passes_response_tokens_to_finalize(self) -> None:
        """When execute succeeds, finalize_fn receives response_tokens."""
        from cortex.core.models import HandlerKind

        received: dict[str, object] = {}

        async def execute_fn() -> (
            tuple[str, bool, str | None, bool, int | None, str | None]
        ):
            return ("result", True, None, False, 0, None)

        async def finalize_fn(
            _progress_task: object,
            _ctx: object,
            _func_name: str,
            _start_ns: int,
            _was_cancelled: bool,
            success: bool,
            _error_type: str | None,
            _kind: object,
            *,
            retry_count: int | None = None,
            param_validation_failure: str | None = None,
            response_tokens: int | None = None,
        ) -> None:
            received["success"] = success
            received["response_tokens"] = response_tokens

        result = await run_execute_and_finalize(
            finalize_fn,
            execute_fn,
            None,
            None,
            "test_tool",
            0,
            HandlerKind.TOOL,
        )
        assert result == "result"
        assert received["success"] is True
        assert "response_tokens" in received
