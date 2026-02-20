"""Unit tests for connection retry overrides in mcp_stability_config.

Blocker: MCP disconnects during commit - server-side retry with
exponential backoff for fix_markdown_lint.
"""

from cortex.core.mcp_stability_config import (
    get_connection_retry_attempts,
    get_connection_retry_delay,
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
