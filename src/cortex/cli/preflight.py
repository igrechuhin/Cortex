"""Registry reachability check for bootstrap / offline triage.

Uses ``UV_INDEX_URL`` when set (same as uv), otherwise ``https://pypi.org/simple/``.
Build backend is ``uv_build`` (see ``pyproject.toml`` [build-system]); this probe
validates network access to the index ``uv sync`` would use.
"""

from __future__ import annotations

import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Default PyPI simple index; ``uv sync`` uses UV_INDEX_URL when configured.
DEFAULT_REGISTRY_URL = "https://pypi.org/simple/"
DEFAULT_TIMEOUT_SEC = 10.0
UV_INDEX_ENV = "UV_INDEX_URL"


def resolve_registry_url() -> str:
    """Return ``UV_INDEX_URL`` if set and non-empty after strip, else PyPI default."""
    raw = os.environ.get(UV_INDEX_ENV, "").strip()
    if raw:
        return raw
    return DEFAULT_REGISTRY_URL


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


def main() -> int:
    """Run preflight; print status to stdout. Returns exit code for shell."""
    url = resolve_registry_url()
    ok, reason = registry_reachable(url, timeout=DEFAULT_TIMEOUT_SEC)
    if ok:
        print("[OK] Registry reachable")
        return 0
    print(f"[FAIL] Cannot reach registry: {reason}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
