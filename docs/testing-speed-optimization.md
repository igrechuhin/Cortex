# Testing Speed Optimization

Ways to speed up the test suite (4800+ tests, `-m "not slow"`).

## Already in place

- **Parallel runs**: `pytest-xdist` with `-n auto` is used by default when available (Python adapter and commit pipeline). CI also uses `-n auto`. Set `CORTEX_PYTEST_PARALLEL=0` to disable (e.g. for debugging).
- **Slow tests excluded**: `-m "not slow"` in CI and commit pipeline; two long integration tests are skipped.
- **Per-test timeout**: 5–10s in `pytest.ini` so slow tests fail fast.
- **Usage context bypass**: Tool tests that call decorated handlers patch `get_current_managers` so `ensure_usage_context` does not run `resolve_project_root_async` / `get_managers()` (avoids multi-second stalls).
- **Progress heartbeat**: When `execute_pre_commit_checks` runs tests with progress (e.g. 300/4800+), a heartbeat thread reports progress every 20s even when pytest emits no output (e.g. one long test). The UI no longer appears stuck during those gaps.

## Finding slow tests that cause long progress gaps

If progress stalls at a given count (e.g. 300/4800+) for minutes, one or more tests in that range are slow. To find them:

- Run with durations: `pytest tests/ -m "not slow" -v --durations=20` (or `--durations=0` for all). The slowest tests are listed at the end.
- Run without xdist to get deterministic order: `CORTEX_PYTEST_PARALLEL=0 pytest tests/ -m "not slow" -v --durations=20`. Then correlate the slowest tests with the approximate position (e.g. test #300) to find the culprit.
- Consider marking very slow tests with `@pytest.mark.slow` so they are excluded from the default commit run (`-m "not slow"`).

## Decomposing slow or complex tests

When a test is slow or does too much, split it into smaller, faster tests:

1. **One behavior per test** – Each test should assert one outcome (one code path, one error type, one success case). If a test has multiple "given X, when Y, then Z" blocks, split into separate tests. Smaller tests run faster and fail with a clearer signal.

2. **Extract shared setup into fixtures** – If several tests build the same mocks (e.g. `LazyManager`, `get_managers` patches), move that into a fixture in the same file or in `conftest.py`. Reusing fixtures reduces duplication and can reduce per-test cost (e.g. session- or module-scoped fixtures where safe).

3. **Use per-test timeouts instead of class-level** – Prefer `@pytest.mark.timeout(15)` on each test over `@pytest.mark.timeout(60)` on the class. That way a single slow test fails at 15s instead of holding the whole class. Reserve 60s only for tests that genuinely need it (e.g. real I/O or many cases).

4. **Parametrize only when it shortens tests** – Use `@pytest.mark.parametrize` when you have the same test logic over different inputs (e.g. invalid file names). Avoid one huge parametrized test that runs 50 cases; prefer a few parametrized tests with small, focused sets.

5. **Test helpers and pure functions in isolation** – If a handler test is slow because it runs through many layers, add a unit test for the underlying helper with minimal mocks. Keep the integration-style test for the main path only.

6. **Mark integration-style tests** – Tests that hit the real filesystem, subprocess, or many managers are good candidates for `@pytest.mark.slow` so the default `-m "not slow"` run stays fast.

**Example**: In `tests/tools/test_consolidated.py`, `TestSuggestRefactoring` has three tests that each build `LazyManager` instances and the same `get_managers` / `get_project_root` patches. A shared fixture (e.g. `refactoring_mock_managers`) that returns the common manager dict, with per-test overrides for detector return values, would shorten each test and make adding new refactoring tests easier.

### Why some tool tests are slow in the commit pipeline

Tools that call **`resolve_project_root_async(None, ctx)`** (e.g. `suggest_refactoring`, `analyze_context_effectiveness`, `configure`) run the real resolver when that call is not patched. The resolver either requests roots from the MCP client (slow round-trip) or falls back to **`get_project_root(None)`** (filesystem/cwd resolution). In tests, **patch where the function is used** (e.g. `cortex.tools.refactoring_operations.resolve_project_root_async`) with `new_callable=AsyncMock, return_value=Path("/tmp/test")` so no real I/O runs. Without that patch, those tests stay slow (tens of seconds each) in the pipeline.

## Recommended improvements

### 1. Coverage only when needed (high impact)

**Current**: `pytest.ini` `addopts` always enable `--cov=src/cortex` and reports. Coverage adds noticeable overhead (instrumentation + report generation).

**Options**:

- **A** – Make coverage opt-in for local runs: remove `--cov*` from `addopts`; CI and commit pipeline explicitly pass `--cov=src/cortex --cov-report=xml ...` so coverage is only run where required.
- **B** – Keep default coverage but add a “fast” profile: e.g. `pytest -p no:cov` or an env var that skips coverage for quick local runs (document in CLAUDE.md / AGENTS.md).

**Trade-off**: Local “no coverage” runs are faster; developers must remember to run with coverage before pushing or rely on CI.

### 2. Run only unit tests for quick feedback (medium impact)

**Current**: Full suite is unit + integration + tools; all run together unless you pass paths or markers.

**Option**: Use a marker so “fast” runs can be one command:

- Ensure all fast tests are marked `@pytest.mark.unit` (or a new `@pytest.mark.fast`).
- Document: “Quick check: `pytest -m unit`” (or `-m fast`).
- CI / commit pipeline keep running the full suite with `-m "not slow"`.

**Trade-off**: Need to keep the marker applied as new tests are added; “unit” run must stay fast.

### 3. Centralize usage-context bypass for tool tests (low effort, consistency)

**Current**: `test_connection_health`, `test_configuration_operations`, and `test_analysis_operations` each patch `get_current_managers` (per-file fixture or helper).

**Option**: In `tests/conftest.py`, add an autouse fixture that applies only inside `tests/tools/` (e.g. via a `conftest.py` under `tests/tools/` that patches `cortex.core.mcp_stability_usage.get_current_managers` to return `{}`). Then any new tool test that calls a decorated handler gets the bypass by default and avoids accidental slow runs.

### 4. CI: cache and test step tuning (medium impact)

- **Cache**:
  - `uv` / pip cache (e.g. `actions/cache` for `~/.cache/uv` or the directory used by `uv sync`).
  - Optional: cache `.venv` keyed by lockfile so installs are faster when only code changed.
- **Test step**:
  - Already using `-n auto`; ensure the job has enough CPUs (e.g. no unnecessary `runs-on` constraint that limits parallelism).
  - Keep a single test step with `-m "not slow"` and coverage; avoid splitting into many small jobs unless needed (splits add overhead and duplicate setup).

### 5. Session timeout and collection (low impact)

- **Session timeout**: `pytest.ini` has `session_timeout = 600`. If the full suite (with coverage) often approaches this, consider raising it slightly or reducing work per run (e.g. coverage only in CI).
- **Collection**: Avoid heavy imports or work at collection time in `conftest.py` and test modules; keep session-scoped fixtures (e.g. tiktoken mock, Pydantic shim) cheap.

### 6. Optional: test selection (advanced)

- **pytest-testmon** or **pytest-picked**: run only tests affected by changed files. Useful for very large suites; adds a dependency and some workflow complexity.
- **Custom script**: “run tests under `tests/unit` and `tests/tools` unless `--full`” to get a default “fast” subset without markers.

## Summary

| Action                         | Impact   | Effort | Recommendation        |
|--------------------------------|----------|--------|------------------------|
| Coverage opt-in / fast profile| High     | Low    | Do (1A or 1B)          |
| Unit/fast marker + doc         | Medium   | Medium | Optional (2)           |
| Centralize usage-context patch | Low      | Low    | Do (3)                 |
| CI cache + test tuning         | Medium   | Low    | Do (4)                 |
| Session timeout / collection  | Low      | Low    | As needed (5)          |
| testmon / custom selection    | Medium   | Higher | Optional (6)           |

Implementing (1), (3), and (4) gives the best speed-up for the least ongoing cost.
