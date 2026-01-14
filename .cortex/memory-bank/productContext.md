# Product Context: MCP Memory Bank

## Architecture: Cross-Project Helper MCP

**CRITICAL**: This MCP is a helper tool for OTHER projects, not a standalone application. Key architectural principles:

- **Language-Agnostic**: Must work with projects in ANY language (Python, TypeScript, JavaScript, Rust, Go, Java, C++, etc.)
- **Environment-Agnostic**: Must work across different OS (Linux, macOS, Windows), different environments, different build systems
- **Configuration-Agnostic**: Must work with different Synapse configurations, different project structures, different tooling
- **Tool Count Optimization**: Editors have limited MCP tool capacity - must optimize by merging related tools or reusing existing tools where possible
- **Auto-Detection**: Tools should auto-detect language, test framework, and build tools from project structure
- **Graceful Fallback**: Must handle projects without standard tooling or with custom setups

All MCP tools must be designed with these constraints in mind. Tools that are language-specific or environment-specific must use auto-detection and fallback mechanisms.

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

AI coding assistants (like Claude in Cursor) have no memory between sessions. Each conversation starts fresh, requiring developers to repeatedly explain project context, architecture, patterns, and decisions. This leads to:

- Inconsistent code quality across sessions
- Repeated explanations of project structure
- Loss of context about recent changes and decisions
- Difficulty maintaining coding standards across projects
- No systematic way to preserve and evolve project knowledge

The Memory Bank pattern addresses this by maintaining structured documentation that AI assistants can read at the start of each session, but existing implementations lack:

- Automated validation and quality checks
- DRY content management (linking/transclusion)
- Token optimization for large knowledge bases
- Self-evolution capabilities (pattern analysis, refactoring)
- Cross-project rule sharing
- Standardized structure across projects

## User Experience Goals

**For Developers:**

- Seamless integration with Cursor IDE via symlinks
- Automated setup and migration from legacy structures
- Clear, navigable project structure
- Automated housekeeping and health monitoring
- Minimal manual maintenance required

**For AI Assistants:**

- Fast, efficient context loading within token budgets
- Comprehensive project understanding from Memory Bank files
- Access to relevant rules based on task context
- Clear project structure and organization
- Rich metadata for intelligent decision-making

**For Teams:**

- Standardized structure across all projects
- Shared rules for consistency via git submodules
- Easy onboarding with migration tools
- Scalable from solo to large teams
- Version-controlled knowledge and rules

## Success Metrics

- **Quality Scores:** 9.5/10+ in all categories (Architecture, Test Coverage, Documentation, Code Style, Error Handling, Performance, Security, Maintainability, Rules Compliance)
- **Test Coverage:** 90%+ for all 47 modules
- **Code Quality:** All files ≤400 lines, all functions ≤30 lines
- **Performance:** Context loading <100ms for typical projects
- **Adoption:** Easy migration from legacy structures
- **Maintainability:** Automated housekeeping reduces manual work by 80%+
