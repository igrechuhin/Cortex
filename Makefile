VENV_PY := ./.venv/bin/python
TIMEOUT := $(shell command -v gtimeout >/dev/null 2>&1 && echo "gtimeout -k 5" || echo "timeout -k 5")

.PHONY: help test test-full typecheck format lint compile check bootstrap env-check

help:
	@echo "Common targets:"
	@echo "  make test       - run fast test suite (timeout)"
	@echo "  make test-full  - run full test suite (timeout)"
	@echo "  make typecheck  - run pyright"
	@echo "  make format     - run black + ruff import sort"
	@echo "  make lint       - run ruff"
	@echo "  make compile    - run compileall for src/"
	@echo "  make check      - run format + lint + typecheck + test"

bootstrap:
	bash scripts/bootstrap.sh

env-check:
	@if [ ! -x "$(VENV_PY)" ]; then \
		echo "Python virtual environment not found at $(VENV_PY)."; \
		echo "Run 'bash scripts/bootstrap.sh' to create it."; \
		exit 1; \
	fi
	@version="$$($(VENV_PY) -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")')"; \
	if [ "$$version" != "3.13" ]; then \
		echo "Expected Python 3.13.x in $(VENV_PY), but found $$version."; \
		echo "Run 'bash scripts/bootstrap.sh' to recreate the environment with Python 3.13.x."; \
		exit 1; \
	fi

test: env-check
	$(TIMEOUT) 300 $(VENV_PY) -m pytest -q

test-full: env-check
	$(TIMEOUT) 600 $(VENV_PY) -m pytest

typecheck: env-check
	./.venv/bin/pyright src/ tests/

format:
	./.venv/bin/black .
	./.venv/bin/ruff check --select I --fix .

lint:
	./.venv/bin/ruff check src/ tests/

compile:
	$(VENV_PY) -m compileall -q src

check: env-check format lint typecheck test
