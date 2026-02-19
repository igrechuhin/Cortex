# Testing guide

Quick reference for testing and coverage in Cortex. For the full guide, see [Cortex Testing Guide](../development/testing.md).

## Coverage threshold policy

- **90%+** required for CI and release; commit pipeline blocks below 90%.
- **89.5%+** is accepted by the pre-commit tests check with a **warning** (so you can pass the gate while close to 90%); aim for 90%+ before merge.

## Coverage gap analysis

To identify files with the most uncovered lines (for prioritization):

1. Generate a coverage JSON report:

   ```bash
   uv run python -m pytest tests/ --cov=src/cortex --cov-report=json:coverage.json
   ```

2. Run the gap analysis script (from project root):

   ```bash
   uv run python .cortex/synapse/scripts/python/analyze_coverage_gaps.py
   ```

3. Optional: use `--top N`, `--directory SUBSTRING`, or `--module SUBSTRING` to limit or filter output.

The script prints the top 10 files by uncovered line count (and sample line numbers). It can be run as an optional step after tests in the commit pipeline to guide where to add tests.

## Integration tests vs unit tests (consolidated tools)

For consolidated tools that use **handler dispatch** (e.g. `query_memory_bank`, `query_usage`), see the **Coverage Expectations for Consolidated Tools** section in [testing-standards.mdc](../../.cortex/synapse/rules/general/testing-standards.mdc).

- **Unit tests with mocks**: Typically achieve 80–90% coverage. Handler imports and dispatch branches may not run when handlers are mocked. Use when you need fast, isolated tests and 90%+ is acceptable.
- **Integration tests**: Call the real tool so all handlers and imports run. Use when you need 95%+ coverage or must validate handler dispatch and error paths end-to-end.
- **Coverage expectations**: 90%+ is acceptable for consolidated tools; 95%+ is ideal and usually requires integration tests. Plan both unit and integration tests when implementing new consolidated tools (see the implement prompt Test Coverage Planning Checklist).
