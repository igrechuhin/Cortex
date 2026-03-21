#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=_synapse_lib.sh
source "${SCRIPT_DIR}/_synapse_lib.sh"

while true; do
  if _synapse_scripts_ready; then
    exit 0
  fi

  # Allow an explicit escape hatch for environments that want to run with
  # minimal checks but no Synapse (e.g., constrained local setups).
  if [ "${CORTEX_ALLOW_MISSING_SYNAPSE:-0}" != "0" ]; then
    cat <<'EOF'
[WARNING] Cortex Synapse submodule is not initialized, but CORTEX_ALLOW_MISSING_SYNAPSE is set.
Continuing without Synapse-specific quality checks (formatting, linting, type checks, eval).
Native checks (Black, Ruff, Pyright, pytest) will still run, but Synapse scripts are preferred.

To fully enable all quality checks, initialize the Synapse submodule:

  git submodule update --init --recursive
EOF
    exit 0
  fi

  cat <<'EOF'
[ERROR] Cortex Synapse submodule is not initialized.

This repository uses the .cortex/synapse submodule for shared quality checks and rules.
To initialize it, run:

  git submodule update --init --recursive

If you intentionally want to run without Synapse (for minimal local checks), set:

  export CORTEX_ALLOW_MISSING_SYNAPSE=1

and re-run the command. Synapse is still strongly recommended for full quality gates.
EOF

  if [ -t 0 ]; then
    read -r -p "Run 'git submodule update --init --recursive' now? [y/N] " reply || reply=""
    case "${reply}" in
      [yY] | [yY][eE][sS])
        git -C "${REPO_ROOT}" submodule update --init --recursive
        continue
        ;;
      *) ;;
    esac
  fi

  exit 1
done
