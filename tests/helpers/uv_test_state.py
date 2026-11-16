"""Owned uv state for genuine repository and bundled-wheel protocol fixtures."""

# cspell:ignore SYSTEMROOT

import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TextIO

from pydantic import BaseModel, ConfigDict

from cortex.setup.uv_launch import UvLaunchDirectories

_INHERITED = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "SYSTEMROOT",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "all_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "UV_NATIVE_TLS",
    "UV_NO_SYNC",
)


class UvTestState(BaseModel):
    model_config = ConfigDict(frozen=True)
    base: Path
    cache: Path
    tools: Path
    home: Path

    def directories(self) -> UvLaunchDirectories:
        return UvLaunchDirectories(cache_dir=self.cache, tool_dir=self.tools)

    def environment(self) -> dict[str, str]:
        assert self.base.is_dir(), "Owned uv state has already been removed"
        inherited = {key: os.environ[key] for key in _INHERITED if key in os.environ}
        return {
            **inherited,
            **self.directories().environment(),
            **_home_environment(self),
            **_python_environment(self.base),
            "UV_NO_CONFIG": "1",
            "UV_KEYRING_PROVIDER": "disabled",
            "CORTEX_SKIP_SYNAPSE_UPDATE": "1",
            "CORTEX_USE_FALLBACK_ROOT": "0",
            "PYTHONPATH": "",
        }


def _home_environment(state: UvTestState) -> dict[str, str]:
    return {
        "HOME": str(state.home),
        "NETRC": str(state.home / ".netrc"),
        "XDG_CONFIG_HOME": str(state.home / "config"),
        "XDG_DATA_HOME": str(state.home / "data"),
        "XDG_CACHE_HOME": str(state.home / "cache"),
        "TMPDIR": str(state.base / "tmp"),
    }


def _python_environment(base: Path) -> dict[str, str]:
    return {
        "UV_PYTHON": str(Path(sys.executable).resolve()),
        "UV_PYTHON_PREFERENCE": "only-system",
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_PYTHON_INSTALL_DIR": str(base / "python"),
        "UV_TOOL_BIN_DIR": str(base / "bin"),
    }


@contextmanager
def owned_uv_state(root: Path) -> Iterator[UvTestState]:
    with TemporaryDirectory(
        prefix="cortex-uv-state-", dir=root.resolve().parent
    ) as directory:
        base = Path(directory).resolve(strict=True)
        state = UvTestState(
            base=base,
            cache=base / "cache ; $(touch UV_MUST_NOT_RUN)",
            tools=base / "tools & 'literal'",
            home=base / "home",
        )
        paths = [
            state.cache,
            state.tools,
            state.home,
            base / "tmp",
            base / "python",
            base / "bin",
        ]
        paths.extend(state.home / name for name in ("config", "data", "cache"))
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)
        _ = (state.home / ".netrc").write_text("", encoding="utf-8")
        yield state


def require_uv_state(root: Path, state: UvTestState | None) -> UvTestState:
    if state is None:
        raise ValueError("Packaged protocol requires explicit owned uv state")
    if state.base.resolve().is_relative_to(root.resolve()):
        raise ValueError("Owned uv state must be outside the project")
    assert state.cache.resolve(strict=True).is_relative_to(state.base)
    assert state.tools.resolve(strict=True).is_relative_to(state.base)
    return state


def verify_uv_state(
    state: UvTestState, environment: dict[str, str], stderr: TextIO
) -> str:
    assert environment["UV_CACHE_DIR"] == str(state.cache)
    assert environment["UV_TOOL_DIR"] == str(state.tools)
    for command, expected in (
        (["uv", "cache", "dir"], state.cache),
        (["uv", "tool", "dir"], state.tools),
    ):
        result = subprocess.run(
            command,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
            check=True,
            timeout=10,
        )
        assert len(result.stdout) < 4096
        assert Path(result.stdout.strip()).resolve() == expected
    version = _uv_version(environment, stderr)
    assert len(version) < 256 and version.startswith("uv ")
    _ = stderr.write(f"UV owned cache/tools verified; {version}\n")
    stderr.flush()
    return version


def _uv_version(environment: dict[str, str], stderr: TextIO) -> str:
    return subprocess.run(
        ["uv", "--version"],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=stderr,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()


def assert_uv_install_artifact(state: UvTestState) -> None:
    metadata = next(state.cache.rglob("cortex-*.dist-info/METADATA"), None)
    assert metadata is not None, "Real UV install produced no Cortex metadata"
    assert not metadata.is_symlink()
    assert metadata.resolve(strict=True).is_relative_to(
        state.cache.resolve(strict=True)
    )
    with metadata.open(encoding="utf-8") as stream:
        assert "Name: cortex\n" in stream.read(8192)
