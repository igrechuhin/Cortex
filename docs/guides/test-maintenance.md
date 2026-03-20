# Test Maintenance Guide

This guide covers maintaining tests when production code changes, especially when converting code to async.

## Async method and test updates

When you change a method or function from sync to async (or introduce new async APIs), **all call sites in tests must be updated to await the coroutine**. The type checker often does not report unawaited coroutines in test files, so tests can appear to pass until the test suite actually runs (or the async check runs).

### Checklist

- When making a method or function async, search tests for call sites and add `await`.
- Verify no test calls an async function without `await` (or without being in an async test).
- Run the async test validation check via Phase A (`run_quality_gate()` includes `check_async_tests`) or rely on Step 12 of the commit pipeline, which includes `check_async_tests`.

### Correct async test usage (pytest)

```python
import pytest

# Async test function: use await for async code under test
@pytest.mark.asyncio
async def test_async_method_awaited():
    handler = MCPToolFailureHandler()
    result = await handler.detect_failure(some_input)  # await required
    assert result is not None

# Sync test calling async code: must run the coroutine (e.g. via asyncio.run or pytest-asyncio)
@pytest.mark.asyncio
async def test_another_async_call():
    service = MyService()
    value = await service.fetch_async()  # await required
    assert value == expected
```

### What to avoid

- Calling an async function without `await` in a test (e.g. `handler.detect_failure(x)` instead of `await handler.detect_failure(x)`). This creates an unawaited coroutine and can cause test failures or silent skips.
- Relying only on the type checker for test files; run `check_async_tests` when you change async behavior.

### Automated check

The commit pipeline (Step 12) and pre-commit checks include **check_async_tests**, which scans test files for unawaited coroutines and reports file/line. Use it after refactors that introduce or change async APIs.

## References

- [Commit pipeline phases](../design/commit-pipeline-phases.md) – Step 12 includes `check_async_tests`
- [Implement prompt](../../.cortex/synapse/prompts/implement-next-roadmap-step.md) – Step 4.3.1 (async method and test updates)
- [Python testing standards](../../.cortex/synapse/rules/python/python-testing-standards.mdc) – project testing rules
