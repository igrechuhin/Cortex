#!/usr/bin/env bash
# Creates .venv via uv (pyproject [build-system] uses uv_build). For index
# connectivity before sync, run: make preflight or bash scripts/preflight.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=_synapse_lib.sh
source "${SCRIPT_DIR}/_synapse_lib.sh"

if ! _synapse_scripts_ready; then
  cat <<'EOF'
[Synapse] Cortex Synapse scripts are missing or the scripts directory is empty.
Initializing submodules (equivalent to):

  git submodule update --init --recursive

EOF
  git -C "${REPO_ROOT}" submodule update --init --recursive
fi

uv python install 3.13
uv sync --group dev --extra dev
