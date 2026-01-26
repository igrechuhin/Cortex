# Agent Set Optimization Analysis

## Current Agent Set (20 agents)

### Pre-Commit Quality Agents (7)

1. `code-formatter` - Formats code
2. `type-checker` - Validates type safety
3. `quality-checker` - Validates file size/function length
4. `test-executor` - Runs tests and validates coverage
5. `markdown-linter` - Fixes markdown lint errors
6. `static-analyzer` - Runs linters and type checkers
7. **MISSING**: `error-fixer` - Fixes compiler errors, type errors, formatting issues, warnings (Step 0 in commit)

### Code Review Agents (8)

1. `bug-detector` - Finds potential bugs
2. `consistency-checker` - Verifies naming conventions
3. `rules-compliance-checker` - Verifies project rules
4. `completeness-verifier` - Identifies incomplete implementations
5. `test-coverage-reviewer` - Ensures test coverage
6. `security-assessor` - Finds security vulnerabilities
7. `performance-reviewer` - Identifies performance bottlenecks
8. `static-analyzer` - **OVERLAP** with type-checker (runs type checker)

### Memory Bank & Planning Agents (3)

1. `memory-bank-updater` - Updates memory bank files
2. `plan-archiver` - Archives completed plans
3. `plan-creator` - Creates development plans

### Roadmap Agents (1)

1. `roadmap-implementer` - Implements roadmap steps

### Analysis Agents (2)

1. `context-effectiveness-analyzer` - Analyzes context usage
2. `session-optimization-analyzer` - Analyzes session for optimization

## Issues Identified

### 1. Missing Critical Agents

#### Error Fixer (HIGH PRIORITY)

- **Missing**: Step 0 in commit workflow - "Fix errors and warnings"
- **Purpose**: Fixes compiler errors, type errors, formatting issues, warnings BEFORE other checks
- **Why needed**: This is a distinct step that runs BEFORE formatting/type-checking
- **Action**: Create `error-fixer.md`

#### Link Validator (MEDIUM PRIORITY)

- **Missing**: Used in plan-archiver but no dedicated agent
- **Purpose**: Validates link integrity after archiving
- **Why needed**: Could be reused in other contexts
- **Action**: Create `link-validator.md` OR merge into plan-archiver

#### Timestamp Validator (MEDIUM PRIORITY)

- **Missing**: Step 9 in commit workflow
- **Purpose**: Validates memory bank timestamps use YYYY-MM-DD format
- **Why needed**: Specific validation step in commit workflow
- **Action**: Create `timestamp-validator.md` OR merge into memory-bank-updater

#### Roadmap Sync Validator (MEDIUM PRIORITY)

- **Missing**: Step 10 in commit workflow
- **Purpose**: Validates roadmap.md is synchronized with codebase
- **Why needed**: Specific validation step in commit workflow
- **Action**: Create `roadmap-sync-validator.md` OR merge into roadmap-implementer

#### Submodule Handler (LOW PRIORITY)

- **Missing**: Step 11 in commit workflow
- **Purpose**: Commits and pushes `.cortex/synapse` submodule changes
- **Why needed**: Specific git operation in commit workflow
- **Action**: Create `submodule-handler.md` OR merge into commit orchestrator

#### Commit Message Generator (LOW PRIORITY)

- **Missing**: Step 13 in commit workflow
- **Purpose**: Generates comprehensive commit messages
- **Why needed**: Could be reused for other git operations
- **Action**: Create `commit-message-generator.md` OR merge into commit orchestrator

#### Git Pusher (LOW PRIORITY)

- **Missing**: Step 14 in commit workflow
- **Purpose**: Pushes committed changes to remote
- **Why needed**: Could be reused for other git operations
- **Action**: Create `git-pusher.md` OR merge into commit orchestrator

### 2. Overlap Issues

#### static-analyzer vs type-checker (HIGH PRIORITY)

- **Issue**: `static-analyzer` runs type checker, but `type-checker` is separate
- **Problem**: Redundant functionality, unclear when to use which
- **Solutions**:
  - **Option A**: Remove type checking from `static-analyzer`, keep it focused on linting only
  - **Option B**: Remove `type-checker` as separate agent, use `static-analyzer` for all static analysis
  - **Recommendation**: **Option A** - Keep them separate because:
    - Type checking is a distinct step in commit workflow (Step 2)
    - Static analysis (linting) is different from type checking
    - Type checking has specific validation requirements (zero errors AND zero warnings)

#### consistency-checker vs rules-compliance-checker (MEDIUM PRIORITY)

- **Issue**: Both check file organization, code style, patterns
- **Problem**: Overlap in functionality, unclear boundaries
- **Solutions**:
  - **Option A**: Merge into single `code-standards-checker`
  - **Option B**: Clarify boundaries:
    - `consistency-checker`: Cross-file consistency (naming patterns, style uniformity)
    - `rules-compliance-checker`: Project rule compliance (SOLID, DRY, file limits, DI patterns)
  - **Recommendation**: **Option B** - Keep separate but clarify boundaries

### 3. Granularity Issues

#### markdown-linter (LOW PRIORITY)

- **Issue**: Could be part of `code-formatter`
- **Current**: Separate agent (Step 1.5 in commit)
- **Recommendation**: Keep separate because:
  - Different tool (markdownlint-cli2 vs code formatter)
  - Different file types (markdown vs code)
  - Different validation requirements (critical errors in memory bank files)

### 4. Missing Orchestration Agent

#### Pre-Commit Orchestrator (HIGH PRIORITY)

- **Missing**: Agent that coordinates all pre-commit checks
- **Purpose**: Orchestrates error-fixer → formatter → markdown-linter → type-checker → quality-checker → test-executor
- **Why needed**: The commit workflow has a specific order and dependencies
- **Action**: Create `pre-commit-orchestrator.md` OR this is handled by the commit prompt itself

## Recommended Optimizations

### Priority 1: Add Missing Critical Agents

1. **Create `error-fixer.md`** (HIGH)
   - Fixes compiler errors, type errors, formatting issues, warnings
   - Runs BEFORE all other checks (Step 0)
   - Uses `execute_pre_commit_checks(checks=["fix_errors"])`

2. **Clarify static-analyzer vs type-checker** (HIGH)
   - Remove type checking from `static-analyzer`
   - Keep `static-analyzer` focused on linting only
   - Keep `type-checker` as separate agent

3. **Clarify consistency-checker vs rules-compliance-checker** (MEDIUM)
   - Update descriptions to clarify boundaries
   - `consistency-checker`: Cross-file consistency
   - `rules-compliance-checker`: Project rule compliance

### Priority 2: Add Missing Workflow Agents

1. **Create `timestamp-validator.md`** (MEDIUM)
   - Validates memory bank timestamps
   - Uses `validate(check_type="timestamps")` MCP tool
   - OR merge into `memory-bank-updater` if only used in one context

2. **Create `link-validator.md`** (MEDIUM)
   - Validates link integrity
   - Uses `validate_links()` MCP tool
   - OR merge into `plan-archiver` if only used there

3. **Create `roadmap-sync-validator.md`** (MEDIUM)
   - Validates roadmap-codebase synchronization
   - Uses `validate(check_type="roadmap_sync")` MCP tool
   - OR merge into `roadmap-implementer` if only used there

### Priority 3: Consider Consolidation

1. **Git Operations** (LOW)
   - Consider creating `git-operations.md` that handles:
     - Submodule handling
     - Commit message generation
     - Git push
   - OR keep in commit prompt if only used there

## Optimal Agent Set (Recommended: 22-25 agents)

### Pre-Commit Quality Agents (8)

1. `error-fixer` ⭐ **NEW** - Fixes errors before other checks
2. `code-formatter` - Formats code
3. `markdown-linter` - Fixes markdown lint errors
4. `type-checker` - Validates type safety
5. `quality-checker` - Validates file size/function length
6. `test-executor` - Runs tests and validates coverage
7. `static-analyzer` - **UPDATED** - Linting only (no type checking)
8. `timestamp-validator` ⭐ **NEW** - Validates memory bank timestamps

### Code Review Agents (8)

1. `bug-detector` - Finds potential bugs
2. `consistency-checker` - **UPDATED** - Cross-file consistency only
3. `rules-compliance-checker` - **UPDATED** - Project rule compliance
4. `completeness-verifier` - Identifies incomplete implementations
5. `test-coverage-reviewer` - Ensures test coverage
6. `security-assessor` - Finds security vulnerabilities
7. `performance-reviewer` - Identifies performance bottlenecks

### Memory Bank & Planning Agents (4)

1. `memory-bank-updater` - Updates memory bank files
2. `plan-archiver` - Archives completed plans
3. `plan-creator` - Creates development plans
4. `link-validator` ⭐ **NEW** - Validates link integrity

### Roadmap Agents (2)

1. `roadmap-implementer` - Implements roadmap steps
2. `roadmap-sync-validator` ⭐ **NEW** - Validates roadmap-codebase sync

### Analysis Agents (2)

1. `context-effectiveness-analyzer` - Analyzes context usage
2. `session-optimization-analyzer` - Analyzes session for optimization

### Optional: Git Operations Agent (1)

1. `git-operations` ⭐ **NEW** - Handles submodule, commit message, push (optional)

## Summary

**Current**: 20 agents
**Recommended**: 22-25 agents (add 2-5, update 3)

**Key Changes**:

- ✅ Add `error-fixer` (critical - Step 0 in commit)
- ✅ Update `static-analyzer` to remove type checking overlap
- ✅ Clarify boundaries between `consistency-checker` and `rules-compliance-checker`
- ✅ Add `timestamp-validator`, `link-validator`, `roadmap-sync-validator`
- ⚠️ Consider `git-operations` agent (optional)

**Impact**: Better separation of concerns, clearer agent responsibilities, no missing critical workflow steps.
