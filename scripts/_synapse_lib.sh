#!/usr/bin/env bash
# Shared Synapse submodule readiness helpers for shell entrypoints.
# Requires REPO_ROOT: absolute path to the repository root (set by the sourcing script).

_synapse_scripts_ready() {
  [ -n "${REPO_ROOT:-}" ] || return 1
  local synapse_scripts="${REPO_ROOT}/.cortex/synapse/scripts"
  [ -d "${synapse_scripts}" ] && [ "$(ls -A "${synapse_scripts}" 2>/dev/null | wc -l)" -gt 0 ]
}
