#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SYNAPSE_SCRIPTS_DIR="${REPO_ROOT}/.cortex/synapse/scripts"

if [ ! -d "${SYNAPSE_SCRIPTS_DIR}" ]; then
  git -C "${REPO_ROOT}" submodule update --init --recursive
fi

uv python install 3.13
uv sync --group dev --extra dev
