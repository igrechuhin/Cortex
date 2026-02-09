"""Unit tests for cortex.transport_config."""

import os

import pytest

from cortex.transport_config import (
    DEFAULT_SSE_MOUNT_PATH,
    TRANSPORT_SSE,
    TRANSPORT_STDIO,
    TRANSPORT_STREAMABLE_HTTP,
    VALID_TRANSPORTS,
    apply_cortex_env_to_fastmcp,
    get_effective_transport,
    get_host,
    get_mount_path,
    get_port,
)


class TestGetPort:
    """Tests for get_port()."""

    def test_returns_none_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CORTEX_MCP_PORT", raising=False)
        assert get_port() is None

    def test_returns_int_when_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORTEX_MCP_PORT", "9000")
        assert get_port() == 9000

    def test_returns_none_when_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORTEX_MCP_PORT", "not-a-number")
        assert get_port() is None


class TestGetHost:
    """Tests for get_host()."""

    def test_returns_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CORTEX_MCP_HOST", raising=False)
        assert get_host() == "127.0.0.1"

    def test_returns_env_value_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORTEX_MCP_HOST", "0.0.0.0")
        assert get_host() == "0.0.0.0"


class TestGetEffectiveTransport:
    """Tests for get_effective_transport()."""

    def test_returns_stdio_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CORTEX_MCP_TRANSPORT", raising=False)
        assert get_effective_transport() == TRANSPORT_STDIO

    def test_returns_stdio_when_set_stdio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CORTEX_MCP_TRANSPORT", "stdio")
        assert get_effective_transport() == TRANSPORT_STDIO

    def test_returns_sse_when_set_sse(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORTEX_MCP_TRANSPORT", "sse")
        assert get_effective_transport() == TRANSPORT_SSE

    def test_returns_streamable_http_when_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CORTEX_MCP_TRANSPORT", "streamable-http")
        assert get_effective_transport() == TRANSPORT_STREAMABLE_HTTP

    def test_returns_stdio_when_invalid_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CORTEX_MCP_TRANSPORT", "invalid")
        assert get_effective_transport() == TRANSPORT_STDIO

    def test_ignores_case(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORTEX_MCP_TRANSPORT", "SSE")
        assert get_effective_transport() == TRANSPORT_SSE

    def test_returns_sse_when_port_set_and_transport_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Option C: when port set, default transport is sse."""
        monkeypatch.delenv("CORTEX_MCP_TRANSPORT", raising=False)
        monkeypatch.setenv("CORTEX_MCP_PORT", "8000")
        assert get_effective_transport() == TRANSPORT_SSE

    def test_returns_stdio_when_port_set_but_transport_explicitly_stdio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Option C: explicit CORTEX_MCP_TRANSPORT=stdio overrides port-based default."""
        monkeypatch.setenv("CORTEX_MCP_TRANSPORT", "stdio")
        monkeypatch.setenv("CORTEX_MCP_PORT", "8000")
        assert get_effective_transport() == TRANSPORT_STDIO


class TestGetMountPath:
    """Tests for get_mount_path()."""

    def test_returns_sse_path_for_sse(self) -> None:
        assert get_mount_path(TRANSPORT_SSE) == DEFAULT_SSE_MOUNT_PATH

    def test_returns_mcp_path_for_streamable_http(self) -> None:
        assert get_mount_path(TRANSPORT_STREAMABLE_HTTP) == "/mcp"

    def test_returns_mcp_path_for_stdio(self) -> None:
        assert get_mount_path(TRANSPORT_STDIO) == "/mcp"


class TestApplyCortexEnvToFastmcp:
    """Tests for apply_cortex_env_to_fastmcp()."""

    def test_does_not_set_fastmcp_when_cortex_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When CORTEX_MCP_PORT and CORTEX_MCP_HOST are unset, FASTMCP_* are unchanged."""
        monkeypatch.delenv("CORTEX_MCP_PORT", raising=False)
        monkeypatch.delenv("CORTEX_MCP_HOST", raising=False)
        monkeypatch.delenv("FASTMCP_PORT", raising=False)
        monkeypatch.delenv("FASTMCP_HOST", raising=False)
        apply_cortex_env_to_fastmcp()
        assert os.environ.get("FASTMCP_PORT") is None
        assert os.environ.get("FASTMCP_HOST") is None

    def test_sets_fastmcp_port_when_cortex_port_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FASTMCP_PORT", raising=False)
        monkeypatch.setenv("CORTEX_MCP_PORT", "8001")
        apply_cortex_env_to_fastmcp()
        assert os.environ.get("FASTMCP_PORT") == "8001"

    def test_sets_fastmcp_host_when_cortex_host_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FASTMCP_HOST", raising=False)
        monkeypatch.setenv("CORTEX_MCP_HOST", "0.0.0.0")
        apply_cortex_env_to_fastmcp()
        assert os.environ.get("FASTMCP_HOST") == "0.0.0.0"

    def test_does_not_overwrite_existing_fastmcp_port(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FASTMCP_PORT", "9999")
        monkeypatch.setenv("CORTEX_MCP_PORT", "8001")
        apply_cortex_env_to_fastmcp()
        assert os.environ.get("FASTMCP_PORT") == "9999"

    def test_does_not_overwrite_existing_fastmcp_host(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FASTMCP_HOST", "10.0.0.1")
        monkeypatch.setenv("CORTEX_MCP_HOST", "0.0.0.0")
        apply_cortex_env_to_fastmcp()
        assert os.environ.get("FASTMCP_HOST") == "10.0.0.1"


class TestConstants:
    """Tests for module constants."""

    def test_valid_transports_contains_expected(self) -> None:
        assert TRANSPORT_STDIO in VALID_TRANSPORTS
        assert TRANSPORT_SSE in VALID_TRANSPORTS
        assert TRANSPORT_STREAMABLE_HTTP in VALID_TRANSPORTS
        assert len(VALID_TRANSPORTS) == 3
