# Active Context: Cortex

## Current Focus (2026-01-11)

### Phase 10.4: Test Coverage Improvement ✅

- Current Status: Complete (100%)
- Coverage: 88.52% → 90.20% (+1.68%)
- All 2270 tests passing (3 skipped)
- **Impact**: CI quality gate now passing, improved code quality assurance

### Phase 11.1: Fix Rules Tool AttributeError ✅ COMPLETE

- Current Status: ✅ COMPLETE (2026-01-12)
- Issue: `AttributeError: 'LazyManager' object has no attribute 'is_rules_enabled'`
- Root Cause: Using `cast()` instead of `get_manager()` to unwrap LazyManager
- Fix: Replaced `cast()` with `await get_manager()` in `rules_operations.py`
- Impact: Tool now functional, Phase 4 verification can proceed to 100%
- Result: All 34 tests passing, fix verified in code
- Plan: `.cortex/plans/phase-11.1-fix-rules-tool-error.md`

### Phase 3 Extension: Infrastructure Validation ✅ COMPLETE

- Current Status: ✅ COMPLETE (2026-01-12)
- Goal: Extend Phase 3 validation tools to check project infrastructure consistency
- Implementation:
  - Added `infrastructure_validator.py` module with CI vs commit prompt alignment checking
  - Extended `validate` tool with `check_type="infrastructure"` support
  - Validates CI workflow vs commit prompt alignment, code quality consistency, documentation, and configuration
- Impact: Proactive detection of infrastructure inconsistencies before CI failures
- Plan: `.cortex/plans/phase-3-infrastructure-validation.md`

### Phase 11: Comprehensive MCP Tool Verification

- Current Status: 🔄 IN PROGRESS (17/29 tools verified - 59%)
- Goal: Verify all 29 Cortex MCP tools work correctly in the actual Cortex project
- Plan: `.cortex/plans/phase-11-tool-verification.md`
- Progress:
  - ✅ Phase 1: Foundation Tools - 4/5 verified (80%)
  - ✅ Phase 2: Link Management - 4/4 verified (100%) ✅ COMPLETE
  - ✅ Phase 3: Validation & Quality - 2/2 verified (100%) ✅ COMPLETE (now includes infrastructure validation)
  - ✅ Phase 4: Token Optimization - 6/6 verified (100%) ✅ COMPLETE
  - ✅ **FIXED**: MCP connection instability issues resolved (2026-01-12)
    - Applied stability wrapper to critical tools (rollback_file_version, resolve_transclusions)
    - Improved server error handling for connection errors
    - Enhanced retry logic to catch connection-related exceptions
    - Added graceful shutdown for client disconnections
  - ✅ **FIXED**: `rules` tool AttributeError resolved - Phase 11.1 complete

### MCP Connection Stability and Health Monitoring

- Current Status: Complete (100%)
- Added MCP connection stability module (`mcp_stability.py`) with timeout protection, resource limits, and retry logic
- Added connection health monitoring tool (`connection_health.py`) for observability
- Updated constants with MCP stability configuration
- Improved error handling in main.py for better reliability
- **Impact**: Prevents hanging operations, enforces resource limits, enables health monitoring

### Synapse Path Refactoring

- Current Status: Path Refactoring Complete (100%)
- Renamed `.cortex/rules/shared/` to `.cortex/synapse/` to better reflect content
- Synapse contains rules, prompts, and other configuration files
- Updated all code references, configuration, and documentation
- Updated symlinks: `.cursor/synapse` → `../.cortex/synapse`

### MCP Prompts and Token Counter Improvements

- Current Status: MCP Prompts Feature Complete (100%)
- Added 7 MCP prompt templates for setup and migration operations
- Improved token counter with timeout handling for tiktoken loading
- Updated README with comprehensive prompts documentation

### Phase 9.3: Performance Optimization

- Current Status: Phase 9.3.3 Complete (100%)
- Performance Score: 9.0/10
- Next: Phase 9.3.4 - Medium-Severity Optimizations

## Recent Work

### 2026-01-11: MCP Connection Stability and Health Monitoring ✅

Added comprehensive MCP connection stability features and health monitoring:

1. **Connection Stability Module** (`mcp_stability.py`)
   - Timeout protection (configurable, default 300s)
   - Resource limit enforcement via semaphore (max 5 concurrent operations)
   - Automatic retry for transient failures (3 attempts with exponential backoff)
   - Connection error handling and recovery

2. **Health Monitoring Tool** (`connection_health.py`)
   - MCP tool for monitoring connection health
   - Reports concurrent operations, utilization, and available resources
   - Enables observability of MCP connection state

3. **Configuration Constants**
   - Centralized MCP stability constants in `constants.py`
   - Configurable timeouts, retry attempts, and resource limits

4. **Improved Error Handling**
   - Better error handling in `main.py` for connection errors
   - Explicit handling for `BrokenPipeError` and `ConnectionError`
   - Improved logging and error messages

### 2026-01-11: Shared Rules Repository Migration ✅

Migrated all project rules to shared repository structure for centralized management:

1. **Synapse Path Refactoring** - Renamed path to better reflect content
   - Synapse repository now located at `.cortex/synapse/` (was `.cortex/rules/shared/`)
   - Contains rules, prompts, and other configuration files
   - Updated all references throughout codebase and documentation
   - Updated symlinks for IDE compatibility

2. **Rule Categories**:
   - **general/**: coding-standards.mdc, maintainability.mdc, no-test-skipping.mdc, testing-standards.mdc
   - **markdown/**: markdown-formatting.mdc
   - **python/**: python-async-patterns.mdc, python-coding-standards.mdc, python-mcp-development.mdc, python-package-structure.mdc, python-performance.mdc, python-security.mdc, python-testing-standards.mdc

3. **Impact**: Enables cross-project rule sharing and centralized rule management

### 2026-01-10: MCP Prompts and Token Counter Improvements ✅

Added MCP prompt templates for one-time setup operations and improved token counter reliability:

1. **prompts.py** - New module with 7 MCP prompt templates
   - Setup prompts: initialize_memory_bank, setup_project_structure, setup_cursor_integration, setup_shared_rules
   - Migration prompts: check_migration_status, migrate_memory_bank, migrate_project_structure
   - Better UX for one-time operations compared to tools

2. **token_counter.py** - Timeout handling for tiktoken loading
   - Added `_load_tiktoken_with_timeout()` method with 5-second timeout
   - Prevents hangs during initialization
   - Graceful fallback to word-based estimation

3. **README.md** - Comprehensive prompts documentation
   - Usage guide and prompt descriptions
   - When to use prompts vs tools

### Phase 9.3.3: Final High-Severity Optimizations ✅

Completed optimization of remaining high-severity performance bottlenecks:

1. **file_system.py** - Lock acquisition optimization
   - Reduced file I/O by ~50% during lock polling
   - Cached existence check before loop entry

2. **token_counter.py** - Markdown parsing optimization
   - Eliminated nested loop for counting '#' characters
   - O(n×m) → O(n) complexity improvement

3. **duplication_detector.py** - Pairwise comparison optimization
   - Replaced nested loops with `itertools.combinations`
   - Cleaner, more Pythonic O(n²) implementation

### Test Results

- All 2185 tests passing (2 skipped) in 28.15s
- Zero linter errors after Black and Ruff formatting
- Code quality maintained at high standards
- 90.28% test coverage (exceeds 90% threshold)

## Active Files

### Modified in Phase 9.3.3

- `src/cortex/core/file_system.py` (line 191)
- `src/cortex/core/token_counter.py` (line 238)
- `src/cortex/validation/duplication_detector.py` (lines 108, 115, 170-171, 245-249)

### Documentation

- `.plan/phase-9.3.3-performance-optimization-summary.md` (created)
- `.plan/README.md` (updated)
- `.cursor/memory-bank/progress.md` (updated)

## Known Issues

### Remaining Performance Opportunities

From `scripts/analyze_performance.py`:

**High-Severity (6 remaining):**

1. `core/file_system.py:202` - File I/O in loop (inherent to polling lock mechanism)
2. `core/dependency_graph.py:305` - Nested loop in `to_dict()`
3. `core/dependency_graph.py:352` - Nested loop in `to_mermaid()`
4. `core/dependency_graph.py:409` - Nested loop in `build_from_links()`
5. `core/dependency_graph.py:417` - Nested loop in `build_from_links()`
6. `analysis/structure_analyzer.py:273` - Nested loop in `_detect_similar_filenames()`

**Medium-Severity (37 remaining):**

- Multiple list append in loop opportunities
- String operations in loops
- See `scripts/analyze_performance.py` output for full list

## Next Actions

### Immediate (Phase 11)

1. Begin systematic verification of all 29 MCP tools
   - Start with Phase 1: Foundation Tools (5 tools)
   - Test each tool with real Cortex project data
   - Document results, issues, and discrepancies
   - Verify JSON response formats match documentation
2. Complete verification across all 8 phases
3. Generate comprehensive verification report
4. Document and prioritize any issues found

### Short-Term (Phase 9.3.4)

1. Review remaining high-severity issues in `dependency_graph.py`
   - Note: Some were marked as complete in Phase 9.3.2 but still flagged by static analysis
   - Verify if these are false positives or require further optimization
2. Address medium-severity issues with high impact
3. Run performance benchmarks to measure real-world impact

### Short-Term (Phase 9.4+)

1. Documentation improvements
2. Additional test coverage for edge cases
3. Performance profiling with real-world workloads

## Context for AI Assistants

### Performance Optimization Strategy

- Using static analysis tool: `scripts/analyze_performance.py`
- Targeting algorithmic improvements (O(n²) → O(n))
- Applying Pythonic optimizations (list comprehensions, itertools)
- Maintaining test coverage and code quality throughout

### Code Quality Standards

- Maximum file length: 400 lines
- Maximum function length: 30 logical lines
- Type hints: 100% coverage required
- Testing: AAA pattern, 90%+ coverage target
- Formatting: Black + Ruff (import sorting)

### Testing Approach

- Run targeted tests after each optimization: `pytest tests/unit/test_<module>.py`
- Full test suite before completion: `pytest --session-timeout=300`
- Verify performance improvements with `analyze_performance.py`

## Project Structure

```text
cortex/
├── .cursor/memory-bank/        # Memory bank files (this directory)
├── .plan/                      # Project plans and phase summaries
├── src/cortex/                 # Main source code
│   ├── core/                   # Core functionality
│   ├── analysis/               # Pattern and structure analysis
│   ├── validation/             # Quality and duplication detection
│   ├── optimization/           # Context optimization
│   ├── refactoring/            # Safe refactoring tools
│   └── tools/                  # MCP tool implementations
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   └── integration/            # Integration tests
└── scripts/                    # Development and analysis scripts
```

## Performance Score History

| Date | Phase | Score | Change | Notes |
|------|-------|-------|--------|-------|
| 2026-01-03 | 9.3.3 | 9.0/10 | +0.1 | Final high-severity optimizations |
| 2026-01-02 | 9.3.2 | 8.9/10 | +0.2 | Dependency graph optimization |
| 2026-01-01 | 9.3.1 | 8.7/10 | +0.5 | Initial performance optimization |

Target: 9.5/10+ by end of Phase 9.3
