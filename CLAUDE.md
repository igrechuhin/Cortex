# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cortex is an MCP (Model Context Protocol) server that helps build structured documentation systems based on [Cline's Memory Bank pattern](https://docs.cline.bot/improving-your-prompting-skills/cline-memory-bank) for context preservation in AI assistant environments.

Key capabilities:

- **Memory Bank Management**: Create, validate, and maintain structured memory bank files for AI assistants
- **DRY Linking**: Transclusion engine for including content across files without duplication
- **Validation & Quality**: Schema validation, duplication detection, and quality metrics
- **Token Optimization**: Context optimization within token budgets, progressive loading, and summarization
- **Refactoring Support**: Pattern analysis, refactoring suggestions, safe execution, and rollback capabilities
- **Shared Rules**: Git submodule integration for cross-project rule sharing
- **Project Structure**: Standardized project structure management with templates

## Common Development Commands

### Running & Testing

```bash
# Quick test run (requires gtimeout on macOS)
gtimeout -k 5 300 ./.venv/bin/python -m pytest -q

# Full test suite with timeout
gtimeout -k 5 600 ./.venv/bin/python -m pytest

# Run specific test file
./.venv/bin/python -m pytest tests/unit/test_file_system.py -v

# Run integration tests
./.venv/bin/python -m pytest tests/integration/ -v
```

### Virtualenv Discoverability (IMPORTANT)

- `.venv/` is usually **ignored** by git and may be **invisible** to IDE file tools/search in some environments.
- Do **not** infer “pytest is missing” based on file-tree tools; verify with the shell instead:

```bash
test -x ./.venv/bin/python && ./.venv/bin/python -V
test -x ./.venv/bin/pytest && ./.venv/bin/pytest --version
```

### Local Development

```bash
# Install dependencies
uv sync --dev

# Run server locally
uv run cortex

# Alternative: pip-based
pip install -r requirements.txt
python -m cortex.main
```

### Code Quality

```bash
# Format code (MANDATORY before commit)
./.venv/bin/black .
./.venv/bin/isort .

# The codebase uses Black formatter with 88-char line length
# and isort for import organization
```

### Building & Distribution

```bash
# Run from git (recommended deployment method)
uvx --from git+https://github.com/igrechuhin/Cortex.git cortex
```

## Architecture

### Core Services Stack

The server initializes services in this order:

1. **FileSystemManager** - File I/O, locking, hashing, conflict detection
2. **MetadataIndex** - JSON index for file metadata, corruption recovery
3. **TokenCounter** - tiktoken integration for token counting
4. **DependencyGraph** - Static and dynamic dependency tracking
5. **VersionManager** - Snapshots and version history
6. **MigrationManager** - Auto-migration between versions
7. **FileWatcher** - External change detection
8. **LinkParser** - Parse links and transclusions
9. **TransclusionEngine** - Resolve `{{include:}}` references
10. **LinkValidator** - Validate link integrity
11. **SchemaValidator** - File schema validation
12. **DuplicationDetector** - Find duplicate content
13. **QualityMetrics** - Calculate quality scores
14. **RelevanceScorer** - Score files by relevance
15. **ContextOptimizer** - Optimize context within budget
16. **ProgressiveLoader** - Load context incrementally
17. **SummarizationEngine** - Summarize content
18. **PatternAnalyzer** - Analyze code patterns
19. **StructureAnalyzer** - Analyze project structure
20. **InsightEngine** - Generate insights
21. **RefactoringEngine** - Generate refactoring suggestions
22. **RefactoringExecutor** - Execute refactorings safely
23. **RollbackManager** - Rollback capabilities
24. **LearningEngine** - Learn from feedback
25. **SynapseManager** - Manage shared rules repositories (replaces SharedRulesManager)
26. **StructureManager** - Manage project structure

### Key Design Patterns

**MCP Server Structure**:

- `cortex.server` contains the MCP server instance
- Handlers are registered as decorated functions using `@mcp.tool()`
- The server communicates over stdio using MCP protocol
- Main entry point is synchronous `main()` which calls `mcp.run(transport="stdio")`

**Async initialization**:

- Services are initialized via `get_managers()` function
- All file operations are async using `aiofiles`
- Dependency injection via constructor parameters

**Memory Bank Structure**:

- Core files: `projectBrief.md`, `productContext.md`, `activeContext.md`, `systemPatterns.md`, `techContext.md`, `progress.md`
- Location: `.cortex/memory-bank/` (primary), `.cursor/memory-bank/` (symlink for IDE compatibility)
- DRY linking via transclusion: `{{include:path/to/file.md}}`
- Validation via schema and duplication detection

**Refactoring Workflow**:

1. Pattern analysis identifies opportunities
2. Refactoring engine generates suggestions
3. Approval manager validates changes
4. Refactoring executor applies changes safely
5. Rollback manager provides safety net
6. Learning engine captures feedback

### Critical Guardrails

**Security** (from .cortex/rules/python-security.mdc):

- **Path traversal protection**: All file paths validated against base directories
- **Input validation**: Validate all external inputs
- **Secure file operations**: Use aiofiles for async file I/O
- **No secrets in code**: Never hardcode credentials

**Performance budgets**:

- File operations: <200ms for typical operations
- Token counting: Efficient tiktoken integration
- Context optimization: Within specified token budgets
- Progressive loading: Incremental context loading

**Code constraints** (from .cortex/rules/):

- Production files: <400 lines (MANDATORY) - excluding license headers & imports
- Functions: <30 lines (MANDATORY) - logical lines, excluding doc comments & blank lines
- One public type per file (MANDATORY) - private/fileprivate helpers may share the file
- Private constants: MUST be defined at file level, at bottom of file (MANDATORY)
- Private helper functions: Pure helpers at file level; state-dependent helpers inside type (MANDATORY)
- Dependency injection: All external dependencies MUST be injected via initializers (MANDATORY)
- No global state or singletons in production code (MANDATORY)
- Async paths: non-blocking (use TaskGroup, gather, or semaphores)
- Type hints: 100% coverage required; NEVER use `Any` type (use Protocols, TypedDict, or `object`)
- Concrete types: Use concrete types instead of `object` wherever possible - investigate actual return types and use them (MANDATORY)
- Type specificity: Make types MORE specific, not less - prefer `dict[str, str]` over `dict[str, object]`, `list[RefactoringSuggestion]` over `list[object]` (MANDATORY)
- Avoid abstractions: Don't use `Mapping` or other abstractions when `dict` works - use `dict` directly (MANDATORY)
- Python 3.13+ built-ins: Use `list[str]`, `dict[str, int]`, `tuple[str, int]`, `set[str]` instead of `typing.List[str]`, `typing.Dict[str, int]`, `typing.Tuple[str, int]`, `typing.Set[str]` (MANDATORY)
- Python 3.13+ types: Use `T | None` instead of `Optional[T]` or `Union[T, None]` (MANDATORY)
- Python 3.13+ async: Use `asyncio.timeout()` instead of `asyncio.wait_for()` (MANDATORY)
- Error handling: Never use bare `except:`; raise domain-specific errors

## Cursor / IDE Usage for MCP Development

- **Interpreter alignment**: Configure Cursor and other IDEs to use `.venv/bin/python` so type checking, completions, and MCP tool discovery match the runtime environment.
- **Typed MCP handlers**: Define all `@mcp.tool()` handlers with explicit parameter and return types, using Pydantic models / dataclasses for JSON payloads instead of untyped dicts.
- **Thin async orchestrators**: Keep handlers as thin async functions that orchestrate calls to small, pure helper functions that contain the main business logic.
- **JSON modeling**: Model known JSON shapes with Pydantic models / dataclasses; reserve JSON-boundary types (e.g. `JsonValue`) only where the domain is truly arbitrary JSON.
- **Refactor focus**: Prefer refactoring pure helpers (not handlers) when using automated refactor tools to avoid breaking protocol contracts or async behavior.

## Synapse Architecture (CRITICAL)

Synapse (`.cortex/synapse/`) is a git submodule providing shared resources with strict separation:

```text
.cortex/synapse/
├── prompts/           # Language-AGNOSTIC workflow definitions
├── rules/             # Coding standards (general + language-specific)
└── scripts/           # Language-SPECIFIC implementations
    └── {language}/    # e.g., python/, typescript/
```

**Prompts are Language-AGNOSTIC (MANDATORY)**:

- **DO NOT** hardcode language-specific commands (`ruff`, `black`, `prettier`, `eslint`) in prompts
- **DO** use script references: `.venv/bin/python .cortex/synapse/scripts/{language}/check_*.py`
- Scripts auto-detect project root, source directories, and appropriate tools

**Scripts are Language-SPECIFIC**:

- Each language has its own directory (`scripts/python/`, `scripts/typescript/`)
- Available Python scripts: `check_formatting.py`, `fix_formatting.py`, `check_linting.py`, `check_types.py`, `check_file_sizes.py`, `check_function_lengths.py`, `run_tests.py`
- To add a new language: Create `scripts/{language}/` with required scripts

## Configuration Essentials

All Cortex data is stored in `.cortex/` directory. For IDE compatibility, `.cursor/` contains symlinks:

**Directory Structure**:

```text
.cortex/                    # Primary Cortex data directory
├── memory-bank/           # Core memory bank files
├── rules/                 # Project rules
├── plans/                 # Development plans
├── synapse/               # Shared resources (git submodule)
│   ├── prompts/          # Language-agnostic workflows
│   ├── rules/            # Coding standards
│   └── scripts/          # Language-specific scripts
├── config/                # Configuration files
├── history/               # Version history
└── index.json             # Metadata index

.cursor/                    # IDE compatibility (symlinks)
├── memory-bank -> ../.cortex/memory-bank
├── rules -> ../.cortex/rules
└── plans -> ../.cortex/plans
```

**Core Memory Bank files**:

- `projectBrief.md` - Foundation document
- `productContext.md` - Product context and requirements
- `activeContext.md` - Current active development context
- `systemPatterns.md` - System architecture patterns
- `techContext.md` - Technical context and decisions
- `progress.md` - Development progress tracking
- `roadmap.md` - Development roadmap and milestones

## Testing Requirements

**Test structure**:

- `tests/unit/` - Unit tests for individual modules
- `tests/integration/` - Integration tests for cross-module workflows

**Test patterns** (from .cortex/rules/python-testing-standards.mdc):

- Use Arrange-Act-Assert (AAA) pattern (MANDATORY)
- Naming: `test_<functionality>_when_<condition>` or `test_<functionality>_<scenario>` (MANDATORY)
- Fixtures in `conftest.py` for shared test data
- Mock external services (filesystem, git operations)
- Use `pytest-asyncio` for async tests
- Unit tests for all critical business logic and every public API surface (MANDATORY)
- Test renaming: When updating tests, ALWAYS verify function name reflects new behavior (MANDATORY)

**Coverage requirements**:

- Aim for 100% coverage on new code
- Minimum 90% coverage for new code (MANDATORY)
- Use `pytest-cov` to track coverage

**Test skipping** (from .cortex/rules/no-test-skipping.mdc):

- No blanket skips (MANDATORY)
- Justify every skip with clear reason and linked ticket/issue
- Temporary only: Include removal/reenable condition
- No silent xfail: Must specify condition and reason
- Prefer fixing flaky/slow tests instead of skipping

## Common Pitfalls

1. **MCP Handler Registration**: Always use `@mcp.tool()` decorator
2. **Async File Operations**: Use `aiofiles` for all file I/O, never use synchronous `open()`
3. **Type Hints**: 100% coverage required; use Python 3.13+ built-ins (`list[str]`, `dict[str, int]`, `tuple[str, int]`, `set[str]`, `T | None`) instead of `typing` module types (MANDATORY); use concrete types instead of `object` wherever possible - investigate actual return types and use them (MANDATORY)
4. **Line Limits**: Production files must be <400 lines, functions <30 lines
5. **Import Organization**: Standard lib → third-party → local with blank lines between groups
6. **Memory Bank Location**: All memory bank files are in `.cortex/memory-bank/` directory (`.cursor/memory-bank/` is a symlink)
7. **Dependency Injection**: All external dependencies MUST be injected via initializers (MANDATORY)
8. **Concrete Types**: Use concrete types instead of `object` wherever possible - investigate actual return types (e.g., `list[RefactoringSuggestion]`, `RollbackResult`, `dict[str, str | None]`) and use them instead of generic `object` (MANDATORY)
9. **Type Specificity**: Make types MORE specific, not less - prefer `dict[str, str]` over `dict[str, object]`, don't replace concrete types with generic ones (MANDATORY)
10. **Avoid Abstractions**: Don't use `Mapping` or other abstractions when `dict` works - use `dict` directly (MANDATORY)
11. **Python 3.13+ Features**: Use modern built-ins - `asyncio.timeout()`, `itertools.batched()`, `contextlib.chdir()`, `@cache`, `except*`, `typing.Self`, `Required`/`NotRequired` (MANDATORY)
12. **DRY Linking**: Use transclusion `{{include:path/to/file.md}}` instead of duplicating content
13. **Avoid typing Module**: Do NOT use `typing.List`, `typing.Dict`, `typing.Tuple`, `typing.Set`, `typing.Optional`, `typing.Union` - use Python 3.13+ built-ins (`list`, `dict`, `tuple`, `set`, `T | None`) instead (MANDATORY)

## Development Workflow

1. **Make changes** to source files in `src/cortex/`
2. **Format code**: Run `black .` and `isort .` (MANDATORY)
3. **Write tests**: Add unit tests in `tests/unit/` or integration tests in `tests/integration/`
4. **Run tests**: Use `gtimeout -k 5 300 ./.venv/bin/python -m pytest -q` for quick validation
5. **Check line counts**: Ensure no file exceeds 400 lines, no function exceeds 30 lines
6. **Update memory bank**: After significant changes, update `.cortex/memory-bank/` files (MANDATORY)
7. **No auto-commit**: Never commit or push without explicit user request (MANDATORY)

## Memory Bank Workflow (MANDATORY)

**Location**: Memory bank files are in `.cortex/memory-bank/` directory (`.cursor/memory-bank/` is a symlink for IDE compatibility)

**Core files required**:

- `projectBrief.md` - Project overview and goals
- `productContext.md` - Product context and requirements
- `systemPatterns.md` - System architecture patterns
- `techContext.md` - Technical context and decisions
- `activeContext.md` - Current active development context
- `progress.md` - Development progress tracking
- `roadmap.md` - Development roadmap and milestones

**When to update** (MANDATORY):

- After significant code changes
- When adding new features
- After architectural decisions
- When adding TODO comments in code (must be tracked in roadmap.md)
- When user requests with **update memory bank** or **umb**

**How to update** (MANDATORY):

1. Review all memory bank files
2. Update relevant files based on changes made
3. Ensure consistency across all files
4. Focus on `activeContext.md` and `progress.md` for current state
5. All TODO comments in code MUST be tracked in `roadmap.md` with corresponding milestones

**Plan archival** (MANDATORY):

- Archive completed plans under `.cortex/plans/archive/PhaseX/MilestoneY/` matching the plan's Phase/Milestone
- Use `mkdir -p .cortex/plans/archive/PhaseX/MilestoneY` to create archive directory
- Move plans: `mv .cortex/plans/<plan-name>.plan.md .cortex/plans/archive/PhaseX/MilestoneY/`

## File Operations (MANDATORY)

**Standard tools preference**:

- **Default to standard tools** for all file operations: `Read`, `ApplyPatch`, `Write`, `LS`, `Glob`, `Grep`
- **MCP filesystem tools are optional fallbacks** - use only if explicitly requested or when standard tools unavailable
- **Prefer non-shell tools** for file edits/search/listing; shell is allowed for build/test/run commands
- **Use absolute paths** when using MCP filesystem tools as fallback

## Python 3.13+ Features (MANDATORY)

This project targets Python 3.13+ and MUST use modern built-ins instead of `typing` module types:

**Type Hints** (MANDATORY):

- ✅ Use `list[str]`, `dict[str, int]`, `tuple[str, int]`, `set[str]` instead of `typing.List[str]`, `typing.Dict[str, int]`, `typing.Tuple[str, int]`, `typing.Set[str]`
- ✅ Use `T | None` instead of `Optional[T]` or `Union[T, None]`
- ✅ Use `typing.Self` for methods returning instances of their class
- ✅ Use `typing.Required` and `typing.NotRequired` for TypedDict optional fields
- ❌ **PROHIBITED**: `typing.List`, `typing.Dict`, `typing.Tuple`, `typing.Set`, `typing.Optional`, `typing.Union` (use built-ins `list`, `dict`, `tuple`, `set`, `T | None` instead)

**Concrete Types** (MANDATORY):

- ✅ Use concrete types instead of `object` wherever possible
- ✅ Investigate actual return types and use them (e.g., `list[RefactoringSuggestion]`, `RollbackResult`, `dict[str, str | None]`)
- ✅ Make types MORE specific, not less - prefer `dict[str, str]` over `dict[str, object]`
- ❌ **PROHIBITED**: Using `object` when concrete types are available
- ❌ **PROHIBITED**: Replacing concrete types with `object`
- ❌ **PROHIBITED**: Using abstractions like `Mapping` when `dict` works

**Async** (MANDATORY):

- ✅ Use `asyncio.timeout()` instead of `asyncio.wait_for()`
- ✅ Use `asyncio.TaskGroup` for concurrent operations

**Itertools** (MANDATORY):

- ✅ Use `itertools.batched()` for chunking iterables
- ✅ Use `itertools.pairwise()` for pairwise iteration

**Contextlib** (MANDATORY):

- ✅ Use `contextlib.chdir()` for temporary directory changes

**Functools** (MANDATORY):

- ✅ Use `@cache` for unbounded caching instead of `@lru_cache`

**Exceptions** (MANDATORY):

- ✅ Use `except*` for ExceptionGroup handling

**Enforcement**: CI MUST fail on violations. All code MUST use Python 3.13+ built-ins when available.

## Git Workflow (MANDATORY)

**No auto-commit**:

- **Never create commits or push** without explicit user instruction (e.g., `/commit`)
- **Explicit trigger only**: Perform commit/push actions solely after clear user request
- **Follow commit procedure**: When requested, execute full documented commit workflow (format, test, memory bank + roadmap updates, plan archival/validation, sync checks, commit, push)
- **No implicit staging**: Do not stage or amend unrelated user changes
- **No auto-amend**: Do not amend existing commits unless user explicitly asks
- **Branch safety**: Do not rebase, reset, or force-push unless explicitly approved

## Tool Names and MCP Capabilities

**MCP Tools** (exposed via `list_tools` / `call_tool`):

- Phase 1 (Foundation): `initialize_memory_bank`, `check_migration_status`, `get_memory_bank_stats`, `validate_memory_bank`, `get_file_metadata`, `get_file_dependencies`, `get_file_version_history`, `create_snapshot`, `rollback_to_snapshot`, `detect_external_changes`
- Phase 2 (DRY Linking): `parse_links`, `validate_links`, `resolve_transclusion`, `get_transclusion_tree`
- Phase 3 (Validation): `validate_schema`, `detect_duplications`, `calculate_quality_metrics`, `get_validation_report`, `configure_validation`
- Phase 4 (Optimization): `load_context`, `score_relevance`, `load_progressively`, `summarize_content`, `get_optimization_config`
- Phase 5.1 (Pattern Analysis): `analyze_patterns`, `analyze_structure`, `get_insights`
- Phase 5.2 (Refactoring): `get_refactoring_suggestions`, `analyze_consolidation`, `analyze_splits`, `plan_reorganization`
- Phase 5.3-5.4 (Execution & Learning): `execute_refactoring`, `get_refactoring_status`, `rollback_refactoring`, `approve_refactoring`, `submit_feedback`, `get_learning_stats`
- Phase 6 (Shared Rules): `initialize_shared_rules`, `sync_shared_rules`, `get_shared_rules`, `merge_rules`
- Phase 8 (Structure): `setup_project_structure`, `validate_project_structure`, `get_structure_report`, `migrate_structure`, `get_structure_templates`, `analyze_structure_quality`

## Memory Bank File Structure

The Memory Bank consists of core files and optional context files, all in Markdown format:

### Core Files (Required)

1. `projectBrief.md` - Foundation document that shapes all other files
2. `productContext.md` - Explains why the project exists, problems being solved
3. `activeContext.md` - Current work focus, recent changes, next steps
4. `systemPatterns.md` - System architecture, technical decisions, design patterns
5. `techContext.md` - Technologies used, development setup, constraints
6. `progress.md` - What works, what's left to build
7. `roadmap.md` - Development roadmap and milestones

### DRY Linking

Use transclusion to include content from other files:

```markdown
{{include:path/to/file.md}}
```

This prevents duplication and ensures single source of truth.
