#!/usr/bin/env bash
set -euo pipefail

uv python install 3.13
uv sync --group dev --extra dev

# Install Node dev dependencies (markdownlint-cli2 for fix_markdown_lint and pre-commit)
if [ -f package.json ]; then
  if command -v npm &>/dev/null; then
    if [ -f package-lock.json ]; then
      npm ci
    else
      npm install
    fi
  fi
fi

