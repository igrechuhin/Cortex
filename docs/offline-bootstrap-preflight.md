# Offline bootstrap and preflight

## Overview

The registry **preflight** answers one question before you run `uv sync` or
`scripts/bootstrap.sh`: can this machine reach the **package index** that `uv` will use?
It does not validate the full dependency graph, credentials, or private package
permissions.

Typical entry points:

- `make preflight` (runs [`scripts/preflight.sh`](../scripts/preflight.sh), which
  invokes `python -m cortex.cli.preflight` with the repo `.venv` when present)
- `uv run python -m cortex.cli.preflight` after the environment exists

Use it when installs fail or hang in restricted networks, behind strict proxies, or in
air-gapped setups, so you can separate **network/index** problems from test or code
failures.

For broader offline bootstrap (wheelhouse, `make bootstrap-offline`), see
[Contributing — offline and restricted networks](development/contributing.md) and
[Troubleshooting — offline and network-restricted verification](guides/troubleshooting.md#offline-and-network-restricted-verification).

## Registry URL resolution

| Source | Value |
| ------ | ----- |
| Default index | `https://pypi.org/simple/` (`DEFAULT_REGISTRY_URL` in [`preflight.py`](../src/cortex/cli/preflight.py)) |
| Override | `UV_INDEX_URL` — same variable `uv sync` respects |
| Normalization | Leading and trailing whitespace on `UV_INDEX_URL` is stripped |

If `UV_INDEX_URL` is set to a non-empty string after stripping, that string is used;
otherwise the default applies.

### Scheme validation

Only URLs whose scheme prefix is `https://` or `http://` are accepted (tuple
`ALLOWED_SCHEMES` in [`preflight.py`](../src/cortex/cli/preflight.py)). Any other
scheme (for example `file://`, `ftp://`) causes `resolve_registry_url()` to raise
`ValueError`, which the CLI turns into a `[FAIL]` message and **exit code 2**. This
avoids passing unintended schemes to `urllib.request.urlopen`.

#### Why `http://` is allowed

Internal mirrors and some air-gapped lab setups still serve the Simple API over plain
HTTP. Rejecting `http://` in preflight would make Cortex unusable in those
environments even when operators deliberately point `UV_INDEX_URL` at an internal
endpoint. The **default** index when `UV_INDEX_URL` is unset remains
`https://pypi.org/simple/`, so stock installs never downgrade to HTTP unless the
operator opts in via the environment variable. Teams that must enforce HTTPS-only
index URLs can still do so outside this module (for example CI policy on
`UV_INDEX_URL`, egress rules, or private CA requirements).

## Probe strategy

### HEAD → GET fallback

PyPI and most index servers support `HEAD` for a cheap reachability check: you learn
whether the endpoint responds without downloading a full index page. That matches how
operators think about “is the registry up?” before a heavy `uv sync`.

Not every deployment honors `HEAD` the same way. Some private Simple API mirrors,
and some combinations of reverse proxies with registries such as Nexus, answer
`HEAD` with **HTTP 405 Method Not Allowed** while `GET` on the same URL still works.
The implementation in `_probe_with_method()` therefore tries `HEAD` first; on **405**
it retries once with `GET`. On that `GET` path it reads **one byte** from the body
so the connection and TLS stack are exercised without pulling the entire index.

### Step-by-step behavior

1. **Primary request:** `HEAD` against the resolved URL (lightweight; no response body
   required for success).
2. **Fallback:** If the server responds with **HTTP 405** (Method Not Allowed) on
   `HEAD`, the same URL is probed again with **GET**.
3. **GET success path:** On `GET`, the client reads **one byte** of the body so the
   connection is exercised without downloading the full index.
4. **Timeout:** Default **10.0** seconds (`DEFAULT_TIMEOUT_SEC`). Callers using
   `registry_reachable()` can pass a different `timeout`.

Success is reported when the HTTP status is in **[200, 400)** (2xx or 3xx). Other
status codes or connection errors yield failure with a short reason string.

## Exit codes

| Code | Meaning |
| ---- | ------- |
| 0 | Registry reachable |
| 2 | Registry unreachable, transport error, bad HTTP status, or invalid `UV_INDEX_URL` (scheme / resolution error) |

## Offline triage workflow

1. When `uv sync` or `scripts/bootstrap.sh` fails with timeouts or connection errors,
   run `make preflight` (or the shell script / module invocation above).
2. **Exit 0** — index is reachable from this environment; look elsewhere (proxy vars,
   SSL, corporate MITM, lockfile, etc.).
3. **Exit 2** — treat as index or network failure before blaming tests or application
   code.

`make preflight` is wired in the [`Makefile`](../Makefile) to `bash scripts/preflight.sh`.
Because `make` propagates subprocess exit codes, a failed preflight fails the Make
target.

### CI integration

- **[Bootstrap offline](../.github/workflows/bootstrap-offline.yml)** — After
  `make bootstrap-offline` inside a Docker container with `--network none`, the
  workflow runs `make preflight` and **expects exit code 2**, confirming the probe
  fails cleanly without network access.
- **Code Quality** (`.github/workflows/quality.yml`) — Installs dependencies via
  `scripts/bootstrap.sh`; it does not run the registry preflight as a separate step.
  Use local `make preflight` when triaging connectivity before bootstrap.

## Architecture (flow)

```text
Developer / CI
    |
    v
make preflight  -->  scripts/preflight.sh  -->  python -m cortex.cli.preflight
    |
    v
cortex.cli.preflight.main()
    |
    v
resolve_registry_url()    # UV_INDEX_URL or default; https/http only
    |
    v
registry_reachable(url)
    |
    +-- HEAD request
    |       |
    |       +-- 200 <= status < 400  -->  (True, "")
    |       +-- 405 Method Not Allowed  -->  retry with GET
    |       +-- other / error  -->  (False, reason)
    |
    +-- GET request (after 405 on HEAD)
            |
            +-- 200 <= status < 400  -->  (True, "")  [reads 1 byte]
            +-- other / error  -->  (False, reason)
    |
    v
stdout: [OK] Registry reachable  |  [FAIL] ...
exit 0  |  2
```

## Security notes

- `UV_INDEX_URL` is restricted to `http://` and `https://` before any `urlopen` call.
- The probe does not send credentials and does not log the full URL beyond standard
  error strings from the HTTP stack.
- For the wider threat model, see [Security best practices](security/best-practices.md).

## Related files

| File | Role |
| ---- | ---- |
| [`src/cortex/cli/preflight.py`](../src/cortex/cli/preflight.py) | Implementation |
| [`tests/test_preflight.py`](../tests/test_preflight.py) | Unit tests |
| [`scripts/preflight.sh`](../scripts/preflight.sh) | Make/CI-friendly wrapper |
| [`Makefile`](../Makefile) | `preflight` target |
| [`pyproject.toml`](../pyproject.toml) | `[project.scripts]` defines `cortex`; preflight is run as a module (`python -m cortex.cli.preflight`) |
| [`.github/workflows/bootstrap-offline.yml`](../.github/workflows/bootstrap-offline.yml) | Offline bootstrap + preflight exit assertion |
| [`docs/security/best-practices.md`](security/best-practices.md) | Threat model and network guidance |
