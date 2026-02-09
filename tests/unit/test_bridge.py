"""Unit tests for cortex.bridge."""

import asyncio
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.bridge import (
    BRIDGE_PORT_DEFAULT,
    CORTEX_BRIDGE_PORT_ENV,
    CORTEX_BRIDGE_URL_ENV,
    DEFAULT_BRIDGE_URL,
    WAIT_TIMEOUT_SECONDS,
    _cortex_repo_root,  # type: ignore[reportPrivateUsage]
    _get_bridge_port,  # type: ignore[reportPrivateUsage]
    _get_bridge_url,  # type: ignore[reportPrivateUsage]
    _read_subprocess_stderr,  # type: ignore[reportPrivateUsage]
    _require_server_deps,  # type: ignore[reportPrivateUsage]
    _tcp_connect,  # type: ignore[reportPrivateUsage]
    _url_to_host_port,  # type: ignore[reportPrivateUsage]
    _wait_for_url,  # type: ignore[reportPrivateUsage]
)


class TestGetBridgeUrl:
    """Tests for _get_bridge_url()."""

    def test_returns_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(CORTEX_BRIDGE_URL_ENV, raising=False)
        assert _get_bridge_url() == DEFAULT_BRIDGE_URL

    def test_returns_env_value_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(CORTEX_BRIDGE_URL_ENV, "http://localhost:9000/mcp")
        assert _get_bridge_url() == "http://localhost:9000/mcp"

    def test_strips_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(CORTEX_BRIDGE_URL_ENV, "  http://x:8000/mcp  ")
        assert _get_bridge_url() == "http://x:8000/mcp"

    def test_returns_default_when_empty_after_strip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(CORTEX_BRIDGE_URL_ENV, "   ")
        assert _get_bridge_url() == DEFAULT_BRIDGE_URL


class TestGetBridgePort:
    """Tests for _get_bridge_port()."""

    def test_returns_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(CORTEX_BRIDGE_PORT_ENV, raising=False)
        assert _get_bridge_port() == BRIDGE_PORT_DEFAULT

    def test_returns_int_when_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(CORTEX_BRIDGE_PORT_ENV, "9000")
        assert _get_bridge_port() == 9000

    def test_returns_default_when_invalid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(CORTEX_BRIDGE_PORT_ENV, "not-a-number")
        assert _get_bridge_port() == BRIDGE_PORT_DEFAULT

    def test_strips_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(CORTEX_BRIDGE_PORT_ENV, "  8001  ")
        assert _get_bridge_port() == 8001


class TestCortexRepoRoot:
    """Tests for _cortex_repo_root()."""

    def test_returns_path_three_levels_above_bridge(self) -> None:
        root = _cortex_repo_root()
        assert isinstance(root, Path)
        assert root.is_dir()
        # bridge.py is at src/cortex/bridge.py -> root is repo root
        assert (root / "src" / "cortex" / "bridge.py").exists()


class TestRequireServerDeps:
    """Tests for _require_server_deps()."""

    def test_raises_system_exit_when_import_error(self) -> None:
        """When optional deps are missing, _require_server_deps raises SystemExit(1)."""
        import builtins

        real_import = builtins.__import__

        def fail_httpx(
            name: str,
            globals: Mapping[str, object] | None = None,
            locals: Mapping[str, object] | None = None,
            fromlist: Sequence[str] | None = (),
            level: int = 0,
        ) -> object:
            if name == "httpx":
                raise ImportError("No module named 'httpx'")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fail_httpx):
            with pytest.raises(SystemExit, match="1"):
                _require_server_deps()


class TestReadSubprocessStderr:
    """Tests for _read_subprocess_stderr()."""

    def test_returns_empty_when_stderr_is_none(self) -> None:
        proc = MagicMock(spec=subprocess.Popen)
        proc.stderr = None
        assert _read_subprocess_stderr(proc) == ""

    def test_returns_decoded_stderr_when_read_succeeds(self) -> None:
        proc = MagicMock()
        proc.stderr = MagicMock()
        proc.stderr.flush.return_value = None
        proc.stderr.read.return_value = b"some error"
        result = _read_subprocess_stderr(proc)
        assert result == "some error"

    def test_returns_empty_on_exception(self) -> None:
        proc = MagicMock()
        proc.stderr = MagicMock()
        proc.stderr.flush.side_effect = OSError("read failed")
        assert _read_subprocess_stderr(proc) == ""


class TestUrlToHostPort:
    """Tests for _url_to_host_port()."""

    def test_parses_host_and_port(self) -> None:
        assert _url_to_host_port("http://127.0.0.1:8000/mcp") == ("127.0.0.1", 8000)

    def test_default_port_when_omitted(self) -> None:
        # hostname is preserved when present; port defaults to 8000
        assert _url_to_host_port("http://localhost/path") == ("localhost", 8000)

    def test_default_host_when_empty(self) -> None:
        host, port = _url_to_host_port("http://:9000/")
        assert host == "127.0.0.1"
        assert port == 9000


class TestTcpConnect:
    """Tests for _tcp_connect()."""

    def test_returns_true_when_connection_succeeds(self) -> None:
        with patch("socket.create_connection") as mock_create:
            mock_sock = MagicMock()
            mock_create.return_value = mock_sock
            assert _tcp_connect("127.0.0.1", 8000) is True
            mock_sock.close.assert_called_once()

    def test_returns_false_on_os_error(self) -> None:
        with patch(
            "socket.create_connection", side_effect=OSError("Connection refused")
        ):
            assert _tcp_connect("127.0.0.1", 8000) is False


@pytest.mark.asyncio
class TestWaitForUrl:
    """Tests for _wait_for_url()."""

    async def test_raises_runtime_error_when_proc_exits_before_ready(self) -> None:
        proc = MagicMock()
        proc.poll.return_value = 1
        proc.returncode = 1
        proc.stderr = MagicMock()
        proc.stderr.flush.return_value = None
        proc.stderr.read.return_value = b"error"
        with pytest.raises(RuntimeError, match="Cortex subprocess exited"):
            await _wait_for_url("http://127.0.0.1:8000/mcp", proc)

    async def test_returns_when_tcp_connect_succeeds(self) -> None:
        proc = MagicMock()
        proc.poll.return_value = None
        fut: asyncio.Future[bool] = asyncio.Future()
        fut.set_result(True)
        with patch(
            "cortex.bridge.asyncio.get_event_loop",
            return_value=MagicMock(run_in_executor=MagicMock(return_value=fut)),
        ):
            with patch("cortex.bridge.time.monotonic", return_value=1.0):
                await _wait_for_url("http://127.0.0.1:8000/mcp", proc)

    async def test_raises_runtime_error_when_server_not_ready_in_time(self) -> None:
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stderr = MagicMock()
        proc.stderr.flush.return_value = None
        proc.stderr.read.return_value = b"cortex stderr output"
        fut: asyncio.Future[bool] = asyncio.Future()
        fut.set_result(False)
        call_count = 0

        def monotonic_side_effect() -> float:
            nonlocal call_count
            call_count += 1
            return 0.0 if call_count == 1 else 0.5 + WAIT_TIMEOUT_SECONDS

        with patch(
            "cortex.bridge.asyncio.get_event_loop",
            return_value=MagicMock(run_in_executor=MagicMock(return_value=fut)),
        ):
            with patch(
                "cortex.bridge.time.monotonic",
                side_effect=monotonic_side_effect,
            ):
                with pytest.raises(RuntimeError, match="did not become ready in time"):
                    await _wait_for_url("http://127.0.0.1:8000/mcp", proc)

    async def test_timeout_error_includes_stderr_when_proc_exited(self) -> None:
        proc = MagicMock()
        proc.poll.side_effect = [None, 1]
        stderr_mock = MagicMock()
        stderr_mock.flush.return_value = None
        stderr_mock.read.return_value = b"subprocess error"
        proc.stderr = stderr_mock
        fut: asyncio.Future[bool] = asyncio.Future()
        fut.set_result(False)
        call_count = 0

        def monotonic_side_effect() -> float:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 0.0
            return 0.5 + WAIT_TIMEOUT_SECONDS

        with patch(
            "cortex.bridge.asyncio.get_event_loop",
            return_value=MagicMock(run_in_executor=MagicMock(return_value=fut)),
        ):
            with patch(
                "cortex.bridge.time.monotonic",
                side_effect=monotonic_side_effect,
            ):
                with pytest.raises(RuntimeError, match="did not become ready in time"):
                    await _wait_for_url("http://127.0.0.1:8000/mcp", proc)
