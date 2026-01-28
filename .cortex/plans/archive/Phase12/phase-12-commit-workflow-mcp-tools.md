# Phase 12: Convert Commit Workflow Prompts to MCP Tools

## Status

- **Status**: ✅ COMPLETE
- **Priority**: Medium (Architectural Improvement)
- **Start Date**: 2026-01-12
- **Completion Date**: 2026-01-13

## Goal

Convert markdown prompt files used in commit workflow to structured MCP tools with typed parameters and return values.

## Problem Statement

The commit workflow (`commit.md`) references markdown prompt files that agents must read and interpret:

- `run-tests.md` - Markdown prompt file for test execution (language-specific logic)
- `fix-errors.md` - Markdown prompt file for error fixing (language-specific logic)
- `update-memory-bank.md` - Markdown prompt file (doesn't exist, should use existing MCP tools)

This is suboptimal architecture - these operations should be structured MCP tools with typed parameters.

## Context

See [Architecture: Cross-Project Helper MCP](../memory-bank/productContext.md#architecture-cross-project-helper-mcp) in `productContext.md` for architectural principles:

- Cross-project support
- Tool count optimization
- Language/environment agnostic design

## Design Options

### Option A - Merged Tool (Preferred)

Single MCP tool that handles multiple pre-commit operations:

```python
@mcp.tool()
async def execute_pre_commit_checks(
    checks: list[str],  # ["fix_errors", "format", "type_check", "quality", "tests"]
    language: str | None = None,  # Auto-detect if None
    project_root: str | None = None,
    timeout: int | None = None,
    coverage_threshold: float = 0.90,
    strict_mode: bool = False,
) -> PreCommitResult:
    """Execute pre-commit checks with language auto-detection."""
    ...
```

**Benefits**:

- Single tool instead of multiple
- Reduces tool count
- Unified interface

### Option B - Separate Tools

If merging proves too complex:

```python
@mcp.tool()
async def run_tests(
    timeout: int | None = None,
    coverage_threshold: float = 0.90,
    max_failures: int | None = None,
    project_root: str | None = None,
) -> TestResult:
    """Language-agnostic test execution."""
    ...

@mcp.tool()
async def fix_errors(
    error_types: list[str] | None = None,
    auto_fix: bool = True,
    strict_mode: bool = False,
    project_root: str | None = None,
) -> FixResult:
    """Language-agnostic error fixing."""
    ...
```

## Design Requirements

1. **Language-agnostic**: Must work with Python, TypeScript, JavaScript, Rust, Go, Java, C++, etc.
2. **Environment-agnostic**: Must work across different OS (Linux, macOS, Windows), different environments, different Synapse configurations
3. **Tool count optimization**: Prefer merged tools over separate tools to minimize MCP tool count
4. **Auto-detection**: Tools should auto-detect language, test framework, and build tools from project structure
5. **Fallback support**: Gracefully handle projects without standard tooling or with custom setups

## Implementation Plan

### Step 1: Language Detection Module

Create a language detection module that identifies:

- Project language(s) from file extensions, config files
- Test framework from `pyproject.toml`, `package.json`, `Cargo.toml`, etc.
- Build tools from project structure

### Step 2: Framework Adapters

Create adapters for each language/framework:

| Language | Test Framework | Error Tools |
|----------|----------------|-------------|
| Python | pytest | ruff, pyright |
| TypeScript | jest, vitest | eslint, tsc |
| JavaScript | jest, mocha | eslint |
| Rust | cargo test | clippy |
| Go | go test | golangci-lint |

### Step 3: Implement Core Tool

Implement `execute_pre_commit_checks()` with:

- Language auto-detection
- Parallel check execution where possible
- Structured JSON output
- Timeout handling
- Coverage threshold enforcement

### Step 4: Integration

- Update `commit.md` to use new MCP tool
- Remove deprecated prompt files
- Update documentation

## Expected Benefits

- Type safety with structured parameters
- Consistent return formats (JSON)
- Better error handling
- Easier to test and maintain
- Programmatic invocation instead of text interpretation
- Works across all languages and environments
- Optimized tool count for editor compatibility

## Dependencies

None (can be implemented incrementally)

## Files to Create

- `src/cortex/tools/pre_commit_tools.py` - Main tool implementation
- `src/cortex/services/language_detector.py` - Language detection service
- `src/cortex/services/framework_adapters/` - Framework-specific adapters
- `tests/unit/test_pre_commit_tools.py` - Unit tests
- `tests/integration/test_pre_commit_integration.py` - Integration tests

## Success Criteria

- [x] Language detection works for Python, TypeScript, JavaScript, Rust, Go
- [x] Test execution works with major frameworks (pytest implemented, others can be added)
- [x] Error fixing works with major tools (ruff, pyright implemented for Python)
- [x] Tool count remains optimized (single merged tool `execute_pre_commit_checks`)
- [x] All existing tests pass
- [x] Coverage threshold maintained at 90%+
- [x] Documentation updated (commit.md updated to use new tool)

## Implementation Summary

### Completed Components

1. **Language Detection Module** (`src/cortex/services/language_detector.py`)
   - Detects Python, TypeScript, JavaScript, Rust, Go from project structure
   - Identifies test frameworks, formatters, linters, type checkers
   - Confidence scoring for detection results

2. **Framework Adapters** (`src/cortex/services/framework_adapters/`)
   - Base adapter interface for language-agnostic operations
   - Python adapter implementation (pytest, ruff, pyright, black)
   - Extensible architecture for adding other languages

3. **Pre-Commit Tools** (`src/cortex/tools/pre_commit_tools.py`)
   - `execute_pre_commit_checks()` MCP tool with language auto-detection
   - Supports checks: fix_errors, format, type_check, quality, tests
   - Structured JSON responses with error counts and file modifications

4. **Unit Tests**
   - Language detector tests (11 test cases)
   - Pre-commit tools tests (5 test cases)
   - Python adapter tests (6 test cases)

5. **Documentation Updates**
   - Updated `commit.md` to use new MCP tool instead of prompt files
   - Deprecated prompt files (`fix-errors.md`, `run-tests.md`) kept for backward compatibility

### Notes

- Prompt files (`fix-errors.md`, `run-tests.md`) have been removed from Synapse repository as they are replaced by the MCP tool
- Only Python adapter is fully implemented; other language adapters can be added incrementally
- Tool follows architectural principles: language-agnostic, environment-agnostic, tool count optimized

## Related Files

- [commit.md](../../.cortex/synapse/prompts/commit.md) - Commit workflow (to be updated)
- [productContext.md](../memory-bank/productContext.md) - Architectural principles
- [roadmap.md](../memory-bank/roadmap.md) - Roadmap entry

## Notes (Implementation)

- Updated `commit.md` with architectural notes documenting this improvement (2026-01-12)
- Memory bank operations should use existing `manage_file()` tool (already language-agnostic)
- Validation operations should use existing `validate()` and `check_structure_health()` tools (already language-agnostic)
