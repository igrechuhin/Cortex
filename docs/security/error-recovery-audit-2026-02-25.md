# Error Recovery Audit (2026-02-25)

Security & Resilience plan Step 3: Error Recovery Audit.

## Scope

Audit all `except Exception` and `except BaseException` handlers for:

1. Silent error swallowing
2. Resource release on exception
3. Meaningful error return to MCP client
4. `asyncio.CancelledError` never accidentally caught

## Findings

### CancelledError handling

- **context_logging.py**: `log_client` and `report_progress_safe` use `except BaseException`. Added explicit `if isinstance(e, asyncio.CancelledError): raise` before connection-error check for defense in depth. `_is_connection_error` does not include CancelledError, so it would re-raise; explicit check clarifies intent.
- **mcp_stability_config.py**: `run_and_finalize_impl` catches BaseException and calls `_release_serial_and_reraise` which releases semaphore and re-raises. CancelledError propagates correctly.
- **markdown_lint.py**: Explicit `except asyncio.CancelledError: raise` before Exception and BaseException handlers. Correct.

### Resource release

- **TrackedSemaphore**: Context manager `__aexit__` always calls `release()`; exception propagates (returns None). Verified in `test_resilience_concurrent_access` and `test_error_recovery_audit`.
- **run_and_finalize_impl**: On BaseException, calls `_release_serial_and_reraise` which releases serial semaphore and cancels progress before re-raising.

### Handler count

- **src/**: ~100+ `except Exception` or `except BaseException` handlers across tools, adapters, and core.
- **tests/**: Handlers are test-specific (catching expected errors). Not in scope for production audit.

### Recommendations

1. **Done**: Explicit CancelledError re-raise in context_logging BaseException handlers.
2. **Done**: Tests in `test_error_recovery_audit` verify CancelledError propagation and semaphore release.
3. **Future**: Replace generic `except Exception` with specific custom exceptions (e.g. `FileOperationError`, `ValidationError`) where handlers know the expected type. Low priority; current handlers log and re-raise or return structured errors.
4. **Future**: Add `# noqa: BLE001` or document rationale where broad Exception catch is intentional (e.g. framework adapters wrapping arbitrary tool code).

## Acceptance criteria

- [x] No silent error swallowing in BaseException handlers (context_logging, mcp_stability_config re-raise)
- [x] All resources released on error (semaphore, progress task in mcp_stability_config)
- [x] CancelledError never accidentally caught (explicit re-raise in context_logging; mcp_stability_config re-raises)
- [x] Tests added: `test_error_recovery_audit`
