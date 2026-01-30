# Active Context: Cortex

## Current Focus (2026-01-30)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- ✅ **Session hang: run pre-commit adapter work off event loop** - COMPLETE (2026-01-30)
  - Per `.cortex/reviews/session-hang-investigation-2026-01-30T15-00.md`: `execute_pre_commit_checks` now runs `_execute_all_checks` via `asyncio.to_thread()` so format, fix_errors, type_check, quality, and tests run off the event loop. Event loop stays responsive; MCP tool timeout still applies. Unit test `test_runs_adapter_checks_off_event_loop_via_to_thread` verifies to_thread usage.

- ✅ **Rust Pre-Commit Adapter** - COMPLETE (2026-01-30)
  - RustAdapter in src/cortex/services/framework_adapters/rust_adapter.py (cargo fmt, cargo clippy, cargo check, cargo test, cargo fix). Registered in pre_commit_tools; rust uses RustAdapter. StubAdapterLanguage no longer includes RUST. Unit tests in test_rust_adapter.py; test_get_adapter_returns_rust_adapter_for_rust. All 3000 tests passing.

- ✅ **JavaScript Pre-Commit Adapter** - COMPLETE (2026-01-30)
- ✅ **Phase 64: Promote fixed string sets to enums** - COMPLETE (2026-01-30)
- ✅ **Phase 66: Plan Creation Workflow Compliance** - COMPLETE (2026-01-30)
- ✅ **Phase 65: Commit Workflow — Cortex Tools Only** - COMPLETE (2026-01-30)

### Recently Completed

- ✅ Session hang fix: pre-commit adapter work (format, fix_errors, type_check, quality, tests) now runs via `asyncio.to_thread(_execute_all_checks, ...)` so the event loop stays responsive during long runs.
- ✅ Rust Pre-Commit Adapter (RustAdapter, tests, registry; StubAdapter RUST removed).
- ✅ JavaScript Pre-Commit Adapter (JavaScriptAdapter, tests, registry).
- ✅ Phase 64 plan archived to .cortex/plans/archive/Phase64/.

## Project Health

- **Tests**: 3000 passing; coverage meets project threshold when running full suite.
- **Linting/Types**: Pyright 0 errors, 0 warnings.
- **Pre-commit adapters**: SUPPORTED_LANGUAGES = (python, typescript, javascript, rust, go, java); Python, TypeScript, JavaScript, and Rust have full implementations; Go, Java use StubAdapter.
- **Pre-commit event loop**: Adapter work runs off the event loop via `asyncio.to_thread()` to avoid session-hang perception during format/fix_errors.

## Next Focus

- No blockers. Next pending roadmap item: tracked pre-commit adapters (Go, Java) as needed, or other Future Enhancements.
