# Tech Context: Cortex

## Technologies Used

- **Python 3.13 - Modern Python with built-in types (list[str], dict[str, int], etc.)
- **FastMCP** - MCP server framework
- **aiofiles** - Async file I/O operations
- **tiktoken** - Token counting for OpenAI models
- **watchdog** - File system event monitoring
- **pytest** - Testing framework
- **pytest-timeout** - Test timeout management
- **Black** - Code formatting
- **Ruff** - Linting and import sorting
- **Pyright** - Type checking
- **coverage** - Test coverage tracking

## Development Setup

### Prerequisites

- Python 3.13+
- UV package manager (recommended) or pip
- Git

### Installation

```bash
# With UV (recommended)
uv sync --dev

# Or with pip
pip install -e ".dev]"
```

### Virtual Environment

- Default location: `.venv/`
- Python interpreter: `.venv/bin/python`
- All tools use `.venv/bin/` binaries

## Technical Constraints

- **File Size Limits**: Maximum400per file (production code)
- **Function Size Limits**: Maximum 30 logical lines per function
- **Type Coverage**: 100% type hints required (no `Any` type)
- **Test Coverage**: 90%+ target for all modules
- **Async Only**: All I/O operations must be async
- **No Global State**: All dependencies injected via constructors
- **One Public Type Per File**: Single public class/type per module

## Dependencies

### Core Dependencies

- `fastmcp` - MCP server framework
- `aiofiles` - Async file operations
- `tiktoken` - Token counting
- `watchdog` - File watching

### Development Dependencies

- `pytest` - Testing framework
- `pytest-timeout` - Test timeouts
- `pytest-cov` - Coverage tracking
- `black` - Code formatting
- `ruff` - Linting and import sorting
- `pyright` - Type checking

## Tool Usage Patterns

**NOTE**: These are examples for THIS project (Python). For language-agnostic procedures, use scripts from `.cortex/synapse/scripts/{language}/` instead.

### Code Formatting (This Project - Python)

```bash
./.venv/bin/black .
./.venv/bin/ruff check --fix .
```

### Type Checking (This Project - Python)

```bash
./.venv/bin/pyright src/ tests/
```

### Testing (This Project - Python)

```bash
# Run all tests
./.venv/bin/pytest --session-timeout=300Run specific test file
./.venv/bin/pytest tests/unit/test_file.py

# With coverage
./.venv/bin/pytest --cov=src --cov-report=html
```

### Language-Agnostic Pattern (For Procedures)

**CRITICAL**: When writing procedures or prompts, use language-agnostic scripts:

```bash
# ✅ CORRECT: Language-agnostic script
python .cortex/synapse/scripts/{language}/check_linting.py

# ❌ WRONG: Hardcoded Python command
ruff check src/ tests/
```

Scripts auto-detect:

- Project language (Python, TypeScript, Rust, etc.)
- Appropriate tools (ruff/black for Python, eslint/prettier for JS/TS, etc.)
- Source/test directories
- Build system (.venv, uv, system tools)

### MCP Server Execution

```bash
# Development mode
python -m cortex.main

# Or via UV
uv run cortex
```

## Project Structure

```
Cortex/
├── src/cortex/          # Main source code
│   ├── core/            # Core functionality (Phase 1)
│   ├── linking/         # DRY linking (Phase 2)
│   ├── validation/      # Validation (Phase 3
│   ├── optimization/    # Token optimization (Phase 4
│   ├── analysis/        # Pattern analysis (Phase5)
│   ├── refactoring/     # Refactoring tools (Phase 5)
│   ├── rules/           # Shared rules (Phase6)
│   ├── structure/       # Project structure (Phase 8─ tools/           # MCP tool implementations
│   └── managers/        # Manager initialization
├── tests/               # Test suite
│   ├── unit/            # Unit tests
│   └── integration/     # Integration tests
├── .cursor/             # Cursor IDE integration
│   ├── memory-bank/     # Memory bank files
│   ├── rules/           # Project rules
│   └── plans/           # Development plans
└── docs/                # Documentation
```

## Memory Bank Location

- **Primary Location**: `.cursor/memory-bank/` (for Cursor IDE)
- **Core Files**: projectBrief.md, productContext.md, activeContext.md, systemPatterns.md, techContext.md, progress.md, roadmap.md
- **Metadata**: `.memory-bank-index` (JSON index)
- **Version History**: `.memory-bank-history/` (snapshots)

## Code Quality Standards

- **Formatting**: Black (88 columns) + Ruff (import sorting)
- **Type Hints**:100verage, Python 3.13 built-ins only
- **Testing**: AAA pattern,90coverage
- **File Size**: ≤400s (excluding license/imports)
- **Function Size**: ≤30 logical lines
- **No Global State**: Dependency injection only
- **Async I/O**: All file operations must be async

## Performance Targets

- Context loading: <100ms for typical projects
- Token optimization: Efficient within budget constraints
- File operations: Async with locking for safety
- Test execution: <10s per test case, <300s total session
