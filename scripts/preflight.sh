#!/usr/bin/env bash
# Check that the configured package index (UV_INDEX_URL or PyPI) is reachable
# before running bootstrap (scripts/bootstrap.sh / uv sync), or with --offline
# verify local wheels, lockfile, and toolchain for no-index workflows.
#
# Exit codes:
#   0 - registry reachable (--offline: offline readiness OK)
#   2 - registry unreachable or offline checks failed
#   1 - reserved for invalid CLI usage (none yet; python -m may use 1 internally)
#
# Implementation: thin wrapper; logic lives in cortex.cli.preflight (stdlib urllib).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  exec "${REPO_ROOT}/.venv/bin/python" -m cortex.cli.preflight "$@"
else
  exec python3 -m cortex.cli.preflight "$@"
fi
