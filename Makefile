VENV_PY := ./.venv/bin/python
TIMEOUT := gtimeout -k 5

.PHONY: help test test-full typecheck format lint compile check

help:
	@echo "Common targets:"
	@echo "  make test       - run fast test suite (timeout)"
	@echo "  make test-full  - run full test suite (timeout)"
	@echo "  make typecheck  - run pyright"
	@echo "  make format     - run black + isort"
	@echo "  make lint       - run ruff"
	@echo "  make compile    - run compileall for src/"
	@echo "  make check      - run format + lint + typecheck + test"

test:
	$(TIMEOUT) 300 $(VENV_PY) -m pytest -q

test-full:
	$(TIMEOUT) 600 $(VENV_PY) -m pytest

typecheck:
	pyright src/ tests/

format:
	./.venv/bin/black .
	./.venv/bin/isort .

lint:
	./.venv/bin/ruff check src/ tests/

compile:
	$(VENV_PY) -m compileall -q src

check: format lint typecheck test
