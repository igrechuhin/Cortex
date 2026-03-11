#!/usr/bin/env bash
set -euo pipefail

uv python install 3.13
uv sync --group dev --extra dev


