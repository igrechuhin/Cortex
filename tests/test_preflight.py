"""Tests for cortex.cli.preflight registry probe."""

from __future__ import annotations

import os
import time
from email.message import Message
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from cortex.cli import preflight


def _http_hdrs() -> Message[str, str]:
    return Message()


def _mock_urlopen_factory(
    *,
    head_status: int | None = 200,
    head_error: Exception | None = None,
    get_status: int | None = None,
) -> MagicMock:
    """Build a urlopen mock: optional HEAD failure, then success or GET path."""
    get_status = head_status if get_status is None else get_status

    def fake_urlopen(req: object, timeout: float = 0) -> object:
        assert isinstance(req, Request)
        method = req.get_method()
        if method == "HEAD":
            if head_error is not None:
                raise head_error
            resp = MagicMock()
            resp.status = head_status
            resp.getcode.return_value = head_status
            resp.__enter__.return_value = resp
            resp.__exit__.return_value = None
            return resp
        if method == "GET":
            resp = MagicMock()
            resp.status = get_status
            resp.getcode.return_value = get_status
            resp.read.return_value = b"x"
            resp.__enter__.return_value = resp
            resp.__exit__.return_value = None
            return resp
        raise AssertionError(f"unexpected method {method}")

    return MagicMock(side_effect=fake_urlopen)


def test_resolve_registry_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(preflight.UV_INDEX_ENV, raising=False)
    assert preflight.resolve_registry_url() == preflight.DEFAULT_REGISTRY_URL


def test_resolve_registry_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(preflight.UV_INDEX_ENV, "  https://example.com/simple/  ")
    assert preflight.resolve_registry_url() == "https://example.com/simple/"


def test_resolve_registry_url_empty_env_uses_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(preflight.UV_INDEX_ENV, "   ")
    assert preflight.resolve_registry_url() == preflight.DEFAULT_REGISTRY_URL


def test_resolve_registry_url_rejects_file_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(preflight.UV_INDEX_ENV, "file:///etc/passwd")
    with pytest.raises(ValueError, match="must start with"):
        _ = preflight.resolve_registry_url()


def test_resolve_registry_url_rejects_ftp_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(preflight.UV_INDEX_ENV, "ftp://internal/")
    with pytest.raises(ValueError, match="must start with"):
        _ = preflight.resolve_registry_url()


def test_resolve_registry_url_accepts_https(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://my.registry/simple/"
    monkeypatch.setenv(preflight.UV_INDEX_ENV, url)
    assert preflight.resolve_registry_url() == url


def test_resolve_registry_url_accepts_http(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "http://internal.registry/"
    monkeypatch.setenv(preflight.UV_INDEX_ENV, url)
    assert preflight.resolve_registry_url() == url


def test_main_invalid_url_scheme(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(preflight.UV_INDEX_ENV, "file:///tmp/")
    code = preflight.main()
    assert code == 2
    out = capsys.readouterr().out
    assert "[FAIL]" in out


def test_registry_reachable_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        preflight,
        "urlopen",
        _mock_urlopen_factory(head_status=200),
    )
    ok, reason = preflight.registry_reachable("https://pypi.org/simple/")
    assert ok is True
    assert reason == ""


def test_registry_reachable_connection_error_exit_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        preflight,
        "urlopen",
        MagicMock(side_effect=URLError("timed out")),
    )
    ok, reason = preflight.registry_reachable("https://pypi.org/simple/")
    assert ok is False
    assert "timed out" in reason


def test_registry_reachable_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    err = HTTPError(
        "https://pypi.org/simple/",
        503,
        "Service Unavailable",
        hdrs=_http_hdrs(),
        fp=BytesIO(),
    )
    monkeypatch.setattr(preflight, "urlopen", MagicMock(side_effect=err))
    ok, reason = preflight.registry_reachable("https://pypi.org/simple/")
    assert ok is False
    assert "503" in reason


def test_registry_reachable_head_405_falls_back_to_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    not_allowed = HTTPError(
        "https://pypi.org/simple/",
        405,
        "Method Not Allowed",
        hdrs=_http_hdrs(),
        fp=BytesIO(),
    )
    monkeypatch.setattr(
        preflight,
        "urlopen",
        _mock_urlopen_factory(head_error=not_allowed, get_status=200),
    )
    ok, reason = preflight.registry_reachable("https://pypi.org/simple/")
    assert ok is True
    assert reason == ""


def test_main_ok(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(preflight.UV_INDEX_ENV, raising=False)
    monkeypatch.setattr(
        preflight,
        "urlopen",
        _mock_urlopen_factory(head_status=200),
    )
    code = preflight.main()
    assert code == 0
    out = capsys.readouterr().out
    assert "[OK] Registry reachable" in out


def test_main_fail_network(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(preflight.UV_INDEX_ENV, raising=False)
    monkeypatch.setattr(
        preflight,
        "urlopen",
        MagicMock(side_effect=OSError("Network is down")),
    )
    code = preflight.main()
    assert code == 2
    out = capsys.readouterr().out
    assert "[FAIL] Cannot reach registry:" in out
    assert "Network is down" in out


def test_probe_bad_http_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        preflight,
        "urlopen",
        _mock_urlopen_factory(head_status=500),
    )
    ok, reason = preflight.registry_reachable("https://pypi.org/simple/")
    assert ok is False
    assert "HTTP 500" in reason


def test_response_status_unknown_code_falls_back_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RespWeird:
        status = "nope"

        def getcode(self) -> str:
            return "nope"

        def __enter__(self) -> RespWeird:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(req: object, timeout: float = 0) -> object:
        return RespWeird()

    monkeypatch.setattr(preflight, "urlopen", fake_urlopen)
    ok, reason = preflight.registry_reachable("https://example.com/")
    assert ok is False
    assert "HTTP 0" in reason


def test_response_status_uses_getcode(monkeypatch: pytest.MonkeyPatch) -> None:
    class RespNoStatus:
        def getcode(self) -> int:
            return 204

        def __enter__(self) -> RespNoStatus:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(req: object, timeout: float = 0) -> object:
        return RespNoStatus()

    monkeypatch.setattr(preflight, "urlopen", fake_urlopen)
    ok, reason = preflight.registry_reachable("https://example.com/")
    assert ok is True
    assert reason == ""


def test_main_offline_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def _offline_ok(_root: Path) -> tuple[bool, list[str]]:
        return True, []

    monkeypatch.setattr(preflight, "offline_readiness", _offline_ok)
    assert preflight.main(["--offline"]) == 0


def test_main_offline_failures(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _offline_fail(_root: Path) -> tuple[bool, list[str]]:
        return False, ["[FAIL] missing widget"]

    monkeypatch.setattr(preflight, "offline_readiness", _offline_fail)
    assert preflight.main(["--offline"]) == 2
    assert "[FAIL] missing widget" in capsys.readouterr().out


def _fake_which(_cmd: str) -> str | None:
    return "/fake/bin"


def _fake_run_cmd(
    _args: list[str], *, timeout_sec: float = 30.0
) -> tuple[int, str, str]:
    _ = timeout_sec
    return 0, "uv 0.5.0", ""


def _uv_build_always(_repo: Path, _cache: Path | None) -> bool:
    _ = (_repo, _cache)
    return True


def test_offline_readiness_missing_uv_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path
    monkeypatch.setattr("cortex.cli.preflight.shutil.which", _fake_which)
    monkeypatch.setattr(preflight, "_run_cmd", _fake_run_cmd)
    monkeypatch.setattr(preflight, "_uv_build_available", _uv_build_always)
    ok, failures = preflight.offline_readiness(root)
    assert ok is False
    joined = "\n".join(failures)
    assert "uv.lock is missing" in joined


def test_offline_lockfile_warns_when_pyproject_newer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path
    lock = root / "uv.lock"
    pyproject = root / "pyproject.toml"
    _ = lock.write_text("lock", encoding="utf-8")
    _ = pyproject.write_text("[project]\nname=x\n", encoding="utf-8")
    old = time.time() - 7200.0
    _ = os.utime(lock, (old, old))
    new = time.time()
    _ = os.utime(pyproject, (new, new))
    monkeypatch.setattr("cortex.cli.preflight.shutil.which", _fake_which)
    monkeypatch.setattr(preflight, "_run_cmd", _fake_run_cmd)
    monkeypatch.setattr(preflight, "_uv_build_available", _uv_build_always)
    ok, failures = preflight.offline_readiness(root)
    assert ok is True
    assert failures == []
    err = capsys.readouterr().err
    assert "[WARN]" in err and "uv.lock" in err
