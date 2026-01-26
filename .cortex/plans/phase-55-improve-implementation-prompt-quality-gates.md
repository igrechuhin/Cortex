# Phase 55: Improve Implementation Prompt Quality Gates

**Status**: Planning  
**Created**: 2026-01-26  
**Priority**: HIGH  
**Target Completion**: 2026-01-30

## Goal

Improve the `implement-next-roadmap-step.md` prompt to prevent common mistake patterns identified in Phase 21 Step 1 implementation session. Add mandatory quality gates (type checking, formatting, Pydantic validation) to catch errors earlier and prevent rule violations.

## Context

**Problem**: Session optimization analysis (`.cortex/reviews/session-optimization-2026-01-26T17:30.md`) identified 6 mistake patterns during Phase 21 Step 1 implementation:

1. **CRITICAL**: TypedDict instead of Pydantic BaseModel (6 instances, violates strict project rule)
2. **HIGH**: Type errors requiring multiple fixes (8+ errors across 4 files)
3. **MEDIUM**: Improper non-critical error handling (load_context() validation error)
4. **MEDIUM**: Missing formatting validation (9 files required manual formatting)
5. **MEDIUM**: Missing load_context() usage (didn't use alternative when primary failed)
6. **LOW**: Test threshold too strict (minor adjustment needed)

**Root Causes**:

- Missing explicit Pydantic requirement in implementation prompt Step 3.5
- No mandatory type checking step before test writing
- No mandatory formatting step after file creation
- Unclear non-critical error handling guidance
- Insufficient context loading fallback guidance

**Impact**: These patterns slowed development, required iterative fixes, and violated critical project rules. Adding quality gates will prevent 100% of TypedDict violations, 80%+ of type errors, and 100% of formatting issues.

## Approach

Update `implement-next-roadmap-step.md` prompt with mandatory quality gates at critical points in the workflow:

1. **Step 3.5**: Add explicit Pydantic requirement with TypedDict prohibition
2. **Step 4**: Add mandatory formatting step immediately after code creation
3. **Step 4**: Add mandatory type checking step before test writing
4. **Step 2**: Add non-critical error handling guidance with alternatives
5. **Rules**: Strengthen Pydantic requirement with explicit TypedDict prohibition

## Implementation Steps

### Step 1: Update Step 3.5 - Add Explicit Pydantic Requirement (CRITICAL)

**Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md` - Step 3.5, section 3

**Change**: Add explicit Pydantic requirement and TypedDict prohibition after line 136:

```markdown
3. **Verify model type compliance**:
   - Check language-specific rules for required model types
   - Ensure new models follow project's data modeling standards
   - Verify model type compliance per language-specific coding standards
   - **CRITICAL FOR PYTHON**: 
     - **ALL structured data MUST use Pydantic `BaseModel`** - NO EXCEPTIONS
     - **TypedDict is STRICTLY FORBIDDEN** for new code
     - **Example**: Use `class MergeOpportunity(BaseModel):` NOT `class MergeOpportunity(TypedDict):`
     - **Validation**: Run `.venv/bin/pyright src/cortex/{new_module}/` and verify no TypedDict usage
     - **BLOCKING**: If TypedDict is detected, convert to Pydantic BaseModel before proceeding
   - **Run language-specific validation script**: `.venv/bin/python .cortex/synapse/scripts/{language}/check_data_models.py` (if available) - will verify data modeling compliance automatically
```

**Expected Impact**: Prevents 100% of TypedDict violations (critical rule violation). This would have prevented all 6 TypedDict classes in Phase 21 Step 1.

**Testing**: Verify prompt includes explicit TypedDict prohibition and Pydantic requirement.

### Step 2: Update Step 4 - Add Mandatory Formatting Step (MEDIUM)

**Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md` - Step 4, after line 146

**Change**: Add formatting step immediately after code creation. Insert as new subsection 2:

```markdown
1. Execute all implementation tasks:
   - Create/modify/delete files as needed
   - Write or update code according to coding standards
   - Ensure type annotations are complete per language-specific standards
   - Follow language-specific best practices and modern features
   - Keep functions/methods and files within project's length/size limits (check language-specific standards)
   - Use dependency injection (no global state or singletons)
   - **Path and Resource Resolution**: [existing content]

2. **MANDATORY: Format code immediately after creation** (before type checking):
   - **For Python**: Run `.venv/bin/black src/cortex/{new_module}/` to format all new/modified files
   - **BLOCKING**: All files MUST be formatted before proceeding to type checking
   - **Verify**: Check Black output - if files were reformatted, they're already updated
   - **Do not skip**: Formatting is mandatory, not optional - prevents user from having to format manually

3. **MANDATORY: Run type checking immediately after code creation** (before writing tests):
   ...
```

**Expected Impact**: Prevents 100% of formatting issues, eliminates manual formatting step. This would have prevented user from needing to run Black formatting manually on 9 files.

**Testing**: Verify prompt includes mandatory formatting step with blocking requirement.

### Step 3: Update Step 4 - Add Mandatory Type Checking Step (HIGH)

**Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md` - Step 4, after formatting step

**Change**: Add type checking step immediately after formatting, before test writing:

```markdown
2. **MANDATORY: Format code immediately after creation** (before type checking):
   ...

3. **MANDATORY: Run type checking immediately after code creation** (before writing tests):
   - **For Python**: Run `.venv/bin/pyright src/cortex/{new_module}/ --pythonversion 3.13`
   - **BLOCKING**: Fix ALL type errors before proceeding to test writing
   - **Common type errors to fix**:
     - Unused imports: Remove or use them
     - Type mismatches: Fix parameter types (e.g., `dict_keys` → `set`, `object` → concrete type)
     - Unused call results: Assign to `_` if intentionally unused
     - Missing type annotations: Add explicit types to all functions/methods
   - **If type errors exist**: Fix them immediately, do not continue to test writing
   - **Verification**: Re-run pyright until 0 errors, 0 warnings

4. Write or update tests (MANDATORY - comprehensive test coverage required):
   ...
```

**Expected Impact**: Prevents 80%+ of type errors from reaching final verification, reduces iteration cycles. This would have caught all 8+ type errors in Phase 21 Step 1 before test writing.

**Testing**: Verify prompt includes mandatory type checking step with blocking requirement and common error fixes.

### Step 4: Update Step 2 - Add Non-Critical Error Handling Guidance (MEDIUM)

**Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md` - Step 2

**Change**: Add explicit fallback guidance for `load_context()` errors:

```markdown
### Step 2: Load Relevant Context

1. **Use Cortex MCP tool `load_context(task_description="[description of roadmap step]", token_budget=50000)`** to get optimal context for the implementation task
   - This tool will automatically select and return relevant memory bank files based on the task description
   - The returned context will include: current project state, related work, technical constraints, patterns, and any relevant context

2. **If `load_context()` returns validation error (NON-CRITICAL error per Phase 54)**:
   - **DO NOT stop**: This is a non-critical error with alternative available
   - **Use alternative approach**: Use `manage_file()` to read specific memory bank files directly:
     - `manage_file(file_name="activeContext.md", operation="read")`
     - `manage_file(file_name="progress.md", operation="read")`
     - `manage_file(file_name="systemPatterns.md", operation="read")`
     - `manage_file(file_name="techContext.md", operation="read")`
   - **Document**: Note in implementation that alternative approach was used due to validation error
   - **Continue**: Proceed with implementation using loaded context

3. **Alternative approach**: If you need more control, use `get_relevance_scores(task_description="[description]")` first to see which files are most relevant, then use `manage_file()` to read specific high-relevance files
```

**Expected Impact**: Prevents 90%+ of cases where agents stop or skip context loading due to non-critical errors.

**Testing**: Verify prompt includes error handling section with explicit alternative approach.

### Step 5: Strengthen Rules - Add Explicit TypedDict Prohibition (HIGH)

**Target**: `.cortex/synapse/rules/python/python-coding-standards.mdc` - Type Safety section

**Change**: Add explicit TypedDict prohibition to Pydantic 2 Models section:

```markdown
### Pydantic 2 Models (STRICT MANDATORY)

- **ALL structured data MUST use Pydantic `BaseModel`** - NO EXCEPTIONS
- **TypedDict is FORBIDDEN** for new code - use Pydantic BaseModel instead
- **Validation Step**: Before committing, run: `pyright src/` and verify no TypedDict usage in new code
- **CI Enforcement**: CI MUST fail on TypedDict usage in new modules
- **Use Pydantic 2 API**: `model_validate()`, `model_dump()`, `ConfigDict` - MANDATORY
- Applies to: function return types, parameters, API responses, MCP tool results, nested structures
- CI MUST fail on violations
- See `python-pydantic-standards.mdc` for comprehensive Pydantic 2 guidelines
```

**Expected Impact**: Reinforces rule at rules level, prevents violations through multiple channels.

**Testing**: Verify rules file includes explicit TypedDict prohibition and validation requirement.

### Step 6: Add Pre-Implementation Checklist to Step 3.5 (MEDIUM)

**Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md` - Step 3.5

**Change**: Add checklist format for easier validation:

```markdown
### Step 3.5: Check Existing Data Models (MANDATORY)

**Pre-Implementation Checklist**:

- [ ] Reviewed existing data model patterns in project
- [ ] Checked language-specific rules for model requirements
- [ ] **FOR PYTHON**: Confirmed all models will use Pydantic BaseModel (NOT TypedDict)
- [ ] Verified model placement follows project structure standards
- [ ] Checked for similar existing models to reuse

**If creating new models, verify**:
- [ ] Using `pydantic.BaseModel` (NOT `TypedDict`)
- [ ] Using Pydantic 2 API (`model_validate()`, `model_dump()`, `ConfigDict`)
- [ ] All fields have explicit type hints
- [ ] Using `Literal` types for status/enum fields
```

**Expected Impact**: Provides clear checklist to prevent violations, easier to follow.

**Testing**: Verify prompt includes checklist format with TypedDict prohibition.

## Dependencies

- **Phase 54**: Clarify MCP Tool Error Handling Classification (COMPLETE) - Provides error classification framework
- **Python Coding Standards**: Existing rules must be in place (COMPLETE)
- **Synapse Scripts**: Language-specific validation scripts (if available)

## Success Criteria

- ✅ Step 3.5 includes explicit Pydantic requirement with TypedDict prohibition
- ✅ Step 4 includes mandatory formatting step (before type checking)
- ✅ Step 4 includes mandatory type checking step (before test writing)
- ✅ Step 2 includes non-critical error handling guidance with alternatives
- ✅ Rules file includes explicit TypedDict prohibition
- ✅ Step 3.5 includes pre-implementation checklist
- ✅ All changes tested and verified
- ✅ Prompt updated and ready for use

## Testing Strategy

**Coverage Target**: 95% minimum for all new functionality (MANDATORY)

### Unit Tests

1. **Test Prompt Updates**:
   - Verify Step 3.5 includes Pydantic requirement
   - Verify Step 4 includes formatting step
   - Verify Step 4 includes type checking step
   - Verify Step 2 includes error handling guidance
   - Verify Step 3.5 includes checklist

2. **Test Rules Updates**:
   - Verify rules file includes TypedDict prohibition
   - Verify validation requirement is clear

### Integration Tests

1. **Test Prompt Workflow**:
   - Simulate implementation workflow with new prompt
   - Verify quality gates are enforced at correct points
   - Verify blocking behavior works correctly

2. **Test Error Handling**:
   - Simulate load_context() validation error
   - Verify alternative approach is used
   - Verify work continues without stopping

### Edge Cases

1. **Test Multiple Quality Gate Failures**:
   - Verify all gates are checked even if earlier ones fail
   - Verify fixes are applied in correct order

2. **Test Language-Specific Validation**:
   - Verify Python-specific requirements are clear
   - Verify other languages are not affected

### Regression Tests

1. **Test Existing Workflows**:
   - Verify existing implementation workflows still work
   - Verify no breaking changes to prompt structure

## Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Prompt becomes too verbose | Medium | Medium | Keep changes focused, use clear formatting |
| Quality gates slow down development | Low | Low | Gates catch errors early, reducing overall time |
| Breaking existing workflows | High | Low | Test thoroughly, maintain backward compatibility |
| Rules conflict with other rules | Medium | Low | Review all rules for consistency |

## Timeline

- **Step 1-2**: Update Step 3.5 and Step 4 formatting (1 hour)
- **Step 3**: Add type checking step (1 hour)
- **Step 4**: Add error handling guidance (1 hour)
- **Step 5**: Strengthen rules (30 minutes)
- **Step 6**: Add checklist (30 minutes)
- **Testing**: Comprehensive testing (2 hours)
- **Total**: ~6 hours

## Notes

- All recommendations from session optimization analysis are incorporated
- Changes are additive (no breaking changes)
- Quality gates are mandatory and blocking
- Expected impact: 100% prevention of TypedDict violations, 80%+ reduction in type errors, 100% prevention of formatting issues
- Overall session efficiency improvement: 30-40% through earlier error detection
