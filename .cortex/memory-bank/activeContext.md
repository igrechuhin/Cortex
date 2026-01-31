# Active Context: Cortex

## Current Focus (2026-01-31)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- ✅ **Commit: type fix (reportPrivateUsage)** - COMPLETE (2026-01-31)
  - Fixed 7 Pyright reportPrivateUsage errors by refactoring tests to use public API only. Markdown lint fixed 19 files (17 in Step 1.5, 2 in Step 12). Synapse submodule: markdown lint in prompts/rules. All 3134 tests passing; coverage 90.44%.

- ✅ **Session optimization (2026-01-31 review)** - COMPLETE (2026-01-31)
- ✅ **Sync plans with roadmap** - COMPLETE (2026-01-31)
- ✅ **Kotlin Pre-Commit Adapter** - COMPLETE (2026-01-31)
- ✅ **Swift Pre-Commit Adapter** - COMPLETE (2026-01-31)
- ✅ **Java Pre-Commit Adapter** - COMPLETE (2026-01-30)
- ✅ **Go Pre-Commit Adapter** - COMPLETE (2026-01-30)
- ✅ **Session hang: run pre-commit adapter work off event loop** - COMPLETE (2026-01-30)
- ✅ **Rust Pre-Commit Adapter** - COMPLETE (2026-01-30)
- ✅ **JavaScript Pre-Commit Adapter** - COMPLETE (2026-01-30)
- ✅ **Phases 64, 65, 66** - COMPLETE (2026-01-30)

### Recently Completed

- Commit: type fix (reportPrivateUsage) committed and pushed; Synapse submodule markdown lint committed and pushed.
- Implement run: no pending roadmap step; plan sync checked—no plans to archive.

## Project Health

- **Tests**: 3134+ passing; coverage ≥ 90%.
- **Linting/Types**: Pyright 0 errors, 0 warnings.
- **Pre-commit adapters**: Python, TypeScript, JavaScript, Rust, Go, Java, Kotlin, Swift full implementations.
- **Plans**: Plans directory in sync with roadmap.
- **Path resolution**: Use semantic names and Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) for memory bank and structure paths; do not hardcode paths.

## Next Focus

- No blockers. Add a new roadmap entry for next work, or run commit pipeline when ready.
