"""Registry reachability check for bootstrap / offline triage.

Uses ``UV_INDEX_URL`` when set (same as uv), otherwise ``https://pypi.org/simple/``.
Build backend is ``uv_build`` (see ``pyproject.toml`` [build-system]); this probe
validates network access to the index ``uv sync`` would use.

``--offline`` skips the registry probe and checks local prerequisites for
air-gapped or restricted-network installs (see README and ``make preflight-offline``).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Default PyPI simple index; ``uv sync`` uses UV_INDEX_URL when configured.
DEFAULT_REGISTRY_URL = "https://pypi.org/simple/"
DEFAULT_TIMEOUT_SEC = 10.0
UV_INDEX_ENV = "UV_INDEX_URL"
ALLOWED_SCHEMES = ("https://", "http://")
UV_BUILD_WHEEL_GLOB = "*uv_build*.whl"
# AI: Cap rglob work — uv caches can be large; vendor/wheelhouse are small.
_MAX_UV_BUILD_SCAN_FILES = 8000


def _repo_root() -> Path:
    """Repository root (directory containing pyproject.toml for this package)."""
    # AI: ``CORTEX_REPO_ROOT`` is for subprocess tests that need an isolated tree without
    # mutating the real checkout (integration tests only; not a supported public contract).
    env_root = os.environ.get("CORTEX_REPO_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[3]


def resolve_registry_url() -> str:
    """Return ``UV_INDEX_URL`` if set and non-empty after strip, else PyPI default.

    Raises:
        ValueError: If ``UV_INDEX_URL`` is set but does not start with ``https://``
            or ``http://``.
    """
    raw = os.environ.get(UV_INDEX_ENV, "").strip()
    if not raw:
        return DEFAULT_REGISTRY_URL
    if not raw.startswith(ALLOWED_SCHEMES):
        raise ValueError(
            f"UV_INDEX_URL must start with 'https://' or 'http://'; got: {raw!r}"
        )
    return raw


def _failure_message(exc: BaseException) -> str:
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}: {exc.reason}"
    if isinstance(exc, URLError):
        return str(exc.reason)
    return str(exc)


def _response_status(resp: object) -> int:
    status = getattr(resp, "status", None)
    if isinstance(status, int):
        return status
    getcode = getattr(resp, "getcode", None)
    if callable(getcode):
        code = getcode()
        if isinstance(code, int):
            return code
    return 0


def _probe_with_method(url: str, method: str, *, timeout: float) -> tuple[bool, str]:
    req = Request(url, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            code = _response_status(resp)
            if 200 <= code < 400:
                if method == "GET":
                    resp.read(1)
                return True, ""
            return False, f"HTTP {code}"
    except HTTPError as exc:
        if exc.code == 405 and method == "HEAD":
            return _probe_with_method(url, "GET", timeout=timeout)
        return False, _failure_message(exc)
    except (URLError, TimeoutError, OSError) as exc:
        return False, _failure_message(exc)


def registry_reachable(
    url: str, *, timeout: float = DEFAULT_TIMEOUT_SEC
) -> tuple[bool, str]:
    """Probe registry with HEAD, falling back to GET if HEAD is not allowed."""
    return _probe_with_method(url, "HEAD", timeout=timeout)


def _run_cmd(args: list[str], *, timeout_sec: float = 30.0) -> tuple[int, str, str]:
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _find_uv_build_wheels_under(root: Path, *, max_files: int = 8000) -> bool:
    """Return True if a uv_build wheel file exists under root (bounded scan)."""
    count = 0
    try:
        for path in root.rglob(UV_BUILD_WHEEL_GLOB):
            count += 1
            if path.is_file():
                return True
            if count >= max_files:
                return False
    except OSError:
        return False
    return False


def _uv_build_in_project_venv(repo_root: Path) -> bool:
    """True when uv_build is present in the repo-local .venv (editable / dev installs)."""
    lib = repo_root / ".venv" / "lib"
    if not lib.is_dir():
        return False
    try:
        for site in lib.glob("python3.*/site-packages"):
            if not site.is_dir():
                continue
            for candidate in site.glob("uv_build*"):
                if candidate.is_dir() or candidate.suffix == ".dist-info":
                    return True
    except OSError:
        return False
    return False


def _uv_build_available(repo_root: Path, cache_dir: Path | None) -> bool:
    if _uv_build_in_project_venv(repo_root):
        return True
    for sub in (repo_root / "vendor", repo_root / "wheelhouse"):
        if sub.is_dir() and _find_uv_build_wheels_under(
            sub, max_files=_MAX_UV_BUILD_SCAN_FILES
        ):
            return True
    if cache_dir is not None and cache_dir.is_dir():
        return _find_uv_build_wheels_under(
            cache_dir, max_files=_MAX_UV_BUILD_SCAN_FILES
        )
    return False


def _offline_git_python_failures() -> list[str]:
    out: list[str] = []
    if shutil.which("git") is None:
        out.append("[FAIL] git is not on PATH (required for submodule workflows).")
    if shutil.which("python3") is None:
        out.append("[FAIL] python3 is not on PATH.")
    return out


def _offline_uv_failures(uv_bin: str) -> list[str]:
    code, stdout, stderr = _run_cmd([uv_bin, "--version"], timeout_sec=10.0)
    if code != 0 or not (stdout or stderr):
        return [
            f"[FAIL] uv --version failed (exit {code}). stderr: {stderr or '(empty)'}"
        ]
    line = (stdout or stderr).splitlines()[0].strip()
    if not any(ch.isdigit() for ch in line):
        return [f"[FAIL] uv --version output looks invalid: {line!r}"]
    return []


def _resolve_uv_cache_dir(uv_bin: str) -> Path | None:
    code, cout, _cerr = _run_cmd([uv_bin, "cache", "dir"], timeout_sec=10.0)
    if code == 0 and cout:
        return Path(cout)
    return None


def _offline_lockfile_failures(repo_root: Path) -> list[str]:
    lock_path = repo_root / "uv.lock"
    pyproject_path = repo_root / "pyproject.toml"
    if not lock_path.is_file():
        return [
            "[FAIL] uv.lock is missing. Run `uv lock` on a networked machine and commit uv.lock."
        ]
    if not pyproject_path.is_file():
        return []
    try:
        if pyproject_path.stat().st_mtime > lock_path.stat().st_mtime:
            # AI: Advisory only — developers often touch pyproject before re-running ``uv lock``.
            warn = "[WARN] uv.lock is older than pyproject.toml — run `uv lock` if you changed dependencies."
            print(warn, file=sys.stderr)
    except OSError as exc:
        return [f"[FAIL] Could not compare lockfile mtimes: {exc}"]
    return []


def offline_readiness(repo_root: Path) -> tuple[bool, list[str]]:
    """Check local prerequisites for offline / no-index workflows.

    Returns:
        (True, []) when all checks pass, else (False, human-readable failure lines).
    """
    failures = _offline_git_python_failures()
    uv_bin = shutil.which("uv")
    if uv_bin is None:
        failures.append(
            "[FAIL] uv is not on PATH. Install uv: "
            + "https://docs.astral.sh/uv/getting-started/installation/"
        )
    else:
        failures.extend(_offline_uv_failures(uv_bin))
    cache_dir = _resolve_uv_cache_dir(uv_bin) if uv_bin else None
    failures.extend(_offline_lockfile_failures(repo_root))
    if not _uv_build_available(repo_root, cache_dir):
        msg = (
            "[FAIL] No uv_build found in .venv, vendor/, wheelhouse/, or the uv cache. "
            + "Remediation (networked machine): "
            + "`uv pip download uv-build --dest vendor/ && uv pip install --no-index "
            + "--find-links vendor/ uv-build` "
            + "or add the wheel to wheelhouse/ used by `make bootstrap-offline`."
        )
        failures.append(msg)
    return (len(failures) == 0, failures)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cortex bootstrap / offline preflight."
    )
    _ = parser.add_argument(
        "--offline",
        action="store_true",
        help="Check local offline prerequisites instead of probing the package index.",
    )
    return parser.parse_known_args(argv)[0]


def main(argv: list[str] | None = None) -> int:
    """Run preflight; print status to stdout. Returns exit code for shell."""
    args = _parse_args(argv)
    if args.offline:
        ok, failures = offline_readiness(_repo_root())
        if ok:
            print("[OK] Offline readiness — all prerequisites satisfied.")
            return 0
        for line in failures:
            print(line)
        return 2

    try:
        url = resolve_registry_url()
    except ValueError as exc:
        print(f"[FAIL] Invalid registry URL: {exc}")
        return 2
    ok, reason = registry_reachable(url, timeout=DEFAULT_TIMEOUT_SEC)
    if ok:
        print("[OK] Registry reachable")
        return 0
    print(f"[FAIL] Cannot reach registry: {reason}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
