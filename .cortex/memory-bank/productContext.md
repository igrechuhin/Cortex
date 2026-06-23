# Product Context: MCP Memory Bank

## Architecture: Cross-Project Helper MCP

**CRITICAL**: This MCP is a helper tool for OTHER projects, not a standalone application. Key principles:

- **Language-Agnostic**: Works with ANY language (Python, TypeScript, JavaScript, Rust, Go, Java, C++, etc.)
- **Environment-Agnostic**: Works across OS (Linux, macOS, Windows), environments, build systems
- **Configuration-Agnostic**: Works with different Synapse configs, project structures, tooling
- **Tool Count Optimization**: Editors have limited MCP tool capacity — merge related tools, reuse where possible
- **Auto-Detection**: Tools auto-detect language, test framework, build tools from project structure
- **Graceful Fallback**: Handles projects without standard tooling or with custom setups

Language-specific/environment-specific tools must use auto-detection and fallback mechanisms.

### Language-Agnostic Implementation Requirements

**MANDATORY**: All procedures, prompts, and documentation MUST be language-agnostic:

1. **Use Scripts, Not Hardcoded Commands**:
   - ✅ **CORRECT**: Use `.cortex/synapse/scripts/{language}/check_linting.py` (language-agnostic script)
   - ❌ **WRONG**: Use `uv run ruff check src/ tests/` (hardcoded Python command)
   - Scripts auto-detect language, directories, and appropriate tools
   - Scripts handle different environments (.venv, uv, system tools)

2. **Pattern-Based References**:
   - ✅ **CORRECT**: "Execute language-specific script: `.cortex/synapse/scripts/{language}/check_formatting.py`"
   - ❌ **WRONG**: "Run `black --check src/ tests/` for Python"
   - Use `{language}` placeholder pattern for language-specific paths
   - Scripts handle language detection internally

3. **No Language-Specific Examples in Procedures**:
   - ✅ **CORRECT**: "Run formatter check script (auto-detects formatter for project language)"
   - ❌ **WRONG**: "Run `black --check` for Python, `prettier --check` for JavaScript"
   - Procedures should describe WHAT to do, not HOW (scripts handle HOW)

4. **Exception Handling**:
   - If a script doesn't exist, provide fallback guidance that's still language-agnostic
   - Example: "If script doesn't exist, run formatter in check-only mode manually (script will detect appropriate formatter)"

**CRITICAL**: When writing or updating procedures (like commit.md), prompts, or documentation:

- NEVER hardcode language-specific commands (e.g., `ruff`, `black`, `pyright`, `prettier`, `eslint`)
- ALWAYS reference scripts from `.cortex/synapse/scripts/{language}/` directory
- ALWAYS use `{language}` placeholder pattern
- ALWAYS assume scripts handle language detection and tool selection

## Problem Statement

AI coding assistants (like Claude in Cursor) have no memory between sessions — each conversation starts fresh, requiring repeated explanation of context, architecture, patterns, and decisions. This leads to inconsistent code quality, repeated structure explanations, loss of decision context, difficulty maintaining standards, and no systematic way to preserve project knowledge.

The Memory Bank pattern maintains structured documentation for AI assistants, but existing implementations lack: automated validation, DRY content management (linking/transclusion), token optimization, self-evolution capabilities, cross-project rule sharing, and standardized structure.

## User Experience Goals

**For Developers:** Seamless Cursor IDE integration via symlinks; automated setup and legacy migration; clear navigable structure; automated housekeeping and health monitoring; minimal manual maintenance.

**For AI Assistants:** Fast context loading within token budgets; comprehensive Memory Bank understanding; task-relevant rules access; clear structure and organization; rich metadata for decisions.

**For Teams:** Standardized structure across projects; shared rules via git submodules; easy onboarding with migration tools; scalable from solo to large teams; version-controlled knowledge.

## Success Metrics

- **Quality Scores:** 9.5/10+ in all categories (Architecture, Test Coverage, Documentation, Code Style, Error Handling, Performance, Security, Maintainability, Rules Compliance)
- **Test Coverage:** 90%+ for all 47 modules
- **Code Quality:** All files ≤400 lines, all functions ≤30 lines
- **Performance:** Context loading <100ms for typical projects (evidence and regression tests: [Performance baselines](../../docs/architecture/performance-baselines.md))
- **Adoption:** Easy migration from legacy structures
- **Maintainability:** Automated housekeeping reduces manual work by 80%+
