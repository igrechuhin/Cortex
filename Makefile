VENV_PY := ./.venv/bin/python
TIMEOUT := $(shell command -v gtimeout >/dev/null 2>&1 && echo "gtimeout -k 5" || echo "timeout -k 5")
.PHONY: help test test-full typecheck format format-check lint compile check check-ci-parity fix bootstrap preflight env-check synapse-check commit-check dev

help:
	@echo "Common targets:"
	@echo "  make test               - run default suite: parallel, not slow, no coverage (timeout)"
	@echo "  make test-full          - run all tests (incl. slow): parallel, no coverage (timeout)"
	@echo "  make typecheck          - run pyright on src/ and tests/"
	@echo "  make format-check       - verify Black formatting (no writes; src/ + tests/)"
	@echo "  make format             - apply Black + Ruff import sort (mutates files)"
	@echo "  make fix                - format + Ruff auto-fixes on src/ and tests/"
	@echo "  make lint               - run ruff"
	@echo "  make compile            - run compileall for src/"
	@echo "  make check              - non-mutating: format-check + lint + typecheck + test"
	@echo "  make check-ci-parity    - broader CI-equivalent checks via uv run (see README)"
	@echo "  make commit-check       - same as make check before /cortex/commit"
	@echo "  make dev                - run FastMCP inspector with hot reload"
	@echo "  make preflight          - probe UV_INDEX_URL or PyPI (scripts/preflight.sh)"

bootstrap:
	bash scripts/bootstrap.sh

preflight:
	bash scripts/preflight.sh

env-check:
	@if [ ! -x "$(VENV_PY)" ]; then \
		echo "Python virtual environment not found at $(VENV_PY)."; \
		echo "Run 'bash scripts/bootstrap.sh' to create it."; \
		exit 1; \
	fi
	@version="$$($(VENV_PY) -c 'import sys; print("%d.%d" % (sys.version_info.major, sys.version_info.minor))')"; \
	if [ "$$version" != "3.13" ]; then \
		echo "Expected Python 3.13.x in $(VENV_PY), but found $$version."; \
		echo "Run 'bash scripts/bootstrap.sh' to recreate the environment with Python 3.13.x."; \
		exit 1; \
	fi

synapse-check:
	bash scripts/check_synapse.sh

# Match CI / PythonAdapter: pytest-xdist parallelizes; -m "not slow" skips ~20 long tests.
# Omit --cov here so local feedback stays minutes, not tens of minutes (coverage: make check-ci-parity).
test: env-check synapse-check
	$(TIMEOUT) 900 $(VENV_PY) -m pytest tests/ -m "not slow" -n auto -q

test-full: env-check
	$(TIMEOUT) 900 $(VENV_PY) -m pytest tests/ -n auto -q

typecheck: env-check
	./.venv/bin/pyright src/ tests/

format-check: env-check
	./.venv/bin/black --check src/ tests/

format: env-check
	./.venv/bin/black src/ tests/
	./.venv/bin/ruff check --select I --fix src/ tests/

fix: env-check
	$(MAKE) format
	./.venv/bin/ruff check --fix src/ tests/

lint:
	./.venv/bin/ruff check src/ tests/

compile:
	$(VENV_PY) -m compileall -q src

check: env-check synapse-check format-check lint typecheck test

# Subset of .github/workflows/quality.yml feasible locally (uv on PATH). Skips: cspell (npm in CI),
# eval suite, Codecov, health-check artifacts — see README and docs/guides/troubleshooting.md.
check-ci-parity: env-check synapse-check
	uv run black --check src/ tests/
	uv run ruff check src/ tests/
	uv run python .cortex/synapse/scripts/python/check_formatting.py
	uv run python .cortex/synapse/scripts/python/check_linting.py
	uv run pyright src/
	uv run python .cortex/synapse/scripts/python/check_types.py
	FILES="$$(uv run python -c 'from pathlib import Path; from cortex.tools.execution.file_language_router import collect_project_files; print("\n".join(map(str, collect_project_files(Path.cwd()))))')" && \
		export FILES && uv run python .cortex/synapse/scripts/python/check_file_sizes.py
	FILES="$$(uv run python -c 'from pathlib import Path; from cortex.tools.execution.file_language_router import collect_project_files; print("\n".join(map(str, collect_project_files(Path.cwd()))))')" && \
		export FILES && uv run python .cortex/synapse/scripts/python/check_function_lengths.py
	uv run python -m cortex.tools.files.markdown_lint_core
	uv run python -m pytest tests/ -m "not slow" -n auto -v --cov=src/cortex --cov-report=xml --cov-report=term --cov-fail-under=90

commit-check: check

dev:
	CORTEX_DEV=1 uv run cortex
