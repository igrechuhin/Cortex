VENV_PY := ./.venv/bin/python
TIMEOUT := $(shell command -v gtimeout >/dev/null 2>&1 && echo "gtimeout -k 5" || echo "timeout -k 5")

.PHONY: help test test-full typecheck format format-check lint compile check check-ci-parity check-dep-parity fix bootstrap preflight env-check synapse-check commit-check

help:
	@echo "Common targets:"
	@echo "  make test               - run fast test suite (timeout)"
	@echo "  make test-full          - run full test suite (timeout)"
	@echo "  make typecheck          - run pyright on src/ and tests/"
	@echo "  make format-check       - verify Black formatting (no writes; src/ + tests/)"
	@echo "  make format             - apply Black + Ruff import sort (mutates files)"
	@echo "  make fix                - format + Ruff auto-fixes on src/ and tests/"
	@echo "  make lint               - run ruff"
	@echo "  make compile            - run compileall for src/"
	@echo "  make check              - non-mutating: format-check + lint + typecheck + test"
	@echo "  make check-dep-parity   - verify pyproject.toml [project.dependencies] matches requirements.txt"
	@echo "  make check-ci-parity    - broader CI-equivalent checks via uv run (see README)"
	@echo "  make commit-check       - same as make check before /cortex/commit in Cursor"
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

check-dep-parity:
	uv run python scripts/check_dep_parity.py

test: env-check synapse-check
	$(TIMEOUT) 300 $(VENV_PY) -m pytest -q

test-full: env-check
	$(TIMEOUT) 600 $(VENV_PY) -m pytest

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
	uv run python scripts/check_dep_parity.py
	uv run black --check src/ tests/
	uv run ruff check src/ tests/
	uv run python .cortex/synapse/scripts/python/check_formatting.py
	uv run python .cortex/synapse/scripts/python/check_linting.py
	uv run pyright src/
	uv run python .cortex/synapse/scripts/python/check_types.py
	uv run python .cortex/synapse/scripts/python/check_file_sizes.py
	uv run python .cortex/synapse/scripts/python/check_function_lengths.py
	@MD_FILES=$$(find . \( -name "*.md" -o -name "*.mdc" \) \
		-not -path "*/node_modules/*" \
		-not -path "*/.venv/*" \
		-not -path "*/venv/*" \
		-not -path "*/__pycache__/*" \
		-not -path "*/.git/*" \
		-not -path "./.cortex/plans/archive/*" \
		-not -path "./.cortex/history/*" \
		-not -path "./.cortex/.cache/*" 2>/dev/null | head -500); \
		if [ -n "$$MD_FILES" ]; then echo "$$MD_FILES" | xargs uv run rumdl check; else echo "No markdown files matched rumdl scope; skipping rumdl."; fi
	uv run python -m pytest tests/ -m "not slow" -n auto -v --cov=src/cortex --cov-report=xml --cov-report=term --cov-fail-under=90

commit-check: check
