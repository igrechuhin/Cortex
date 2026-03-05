#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SYNAPSE_DIR="${REPO_ROOT}/.cortex/synapse"
SYNAPSE_SCRIPTS_DIR="${SYNAPSE_DIR}/scripts"

# If the Synapse scripts directory exists and is non-empty, we're good.
if [ -d "${SYNAPSE_SCRIPTS_DIR}" ] && [ "$(ls -A "${SYNAPSE_SCRIPTS_DIR}" 2>/dev/null | wc -l)" -gt 0 ]; then
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

exit 1

