# Active Context: Cortex

## Current Focus (2026-02-01)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- **Phase 21: Health-Check and Optimization Analysis** - IN PROGRESS (2026-02-01) - Step 5 complete: MCP tool `analyze_health_check` in src/cortex/tools/health_check_operations.py. Remaining: Steps 2–4 (similarity/dependency/quality enhancements), 6–9 (CLI script, CI/CD, tests, docs). Plan: .cortex/plans/phase-21-health-check-optimization.md.

- **Phase 20: Code Review Fixes** - IN PROGRESS (2026-01-31) - Steps 1, 2, 4, 5 complete; Step 3.10 complete (phase5_execution split). Remaining files >400 lines: rollback_manager, template_manager, initialization, structure_analyzer, optimization_strategies, phase8_structure. Plan: .cortex/plans/phase-20-code-review-fixes.md.

- ✅ **Phase 21 Step 5 (analyze_health_check MCP tool)** - COMPLETE (2026-02-01)
- ✅ **Phase 20 Step 3.10 (phase5_execution split)** - COMPLETE (2026-01-31)
- ✅ **Ensure proper logging (FastMCP context)** - COMPLETE (2026-01-31)
- ✅ **Conditional prompt registration** - COMPLETE (2026-01-31)

### Recently Completed

- Commit (2026-02-01): Pre-commit pipeline passed; memory bank and markdown lint updates. Tests 3194, coverage 90.5%. Phase 21 Step 5 (analyze_health_check) and health_check_operations in place.

## Project Health

- **Tests**: 3194 passing; coverage ≥ 90%.
- **Linting/Types**: Pyright 0 errors, 0 warnings.
- **Quality**: File size and function length gates passing.
- **Pre-commit adapters**: Python, TypeScript, JavaScript, Rust, Go, Java, Kotlin, Swift full implementations.
- **Plans**: Plans directory in sync with roadmap.
- **Path resolution**: Use Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) for memory bank and structure paths.

## Next Focus

- Continue Phase 21 (Steps 2–4, 6–9) or Phase 20 (remaining file splits); or pick next roadmap step. Run commit pipeline when ready.
