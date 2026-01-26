# Phase 54: Clarify MCP Tool Error Handling Classification

## Status

- **Status**: Planning
- **Priority**: Medium
- **Start Date**: 2026-01-26
- **Type**: Rules Improvement, Documentation Enhancement

## Problem Statement

During Phase 28 implementation, the `load_context()` MCP tool failed with a validation error (`FileMetadataForScoring` validation issues), but the implementation continued successfully using alternative information sources (direct file reads, other MCP tools). This highlighted an ambiguity in the MCP Tool Error Handling rules.

**Current Issue**:

1. **Overly Strict Rules**: The current MCP Tool Error Handling rules (`.cortex/synapse/rules/general/agent-workflow.mdc` lines 265-305) state "STOP IMMEDIATELY" for any unexpected behavior, requiring investigation plans for all errors
2. **No Error Classification**: Rules don't distinguish between:
   - **Critical errors** (crashes, disconnects, protocol errors) that block work
   - **Non-critical errors** (validation errors, data model issues) where alternative approaches exist
3. **Missing Guidance**: No guidance on when it's acceptable to use alternative approaches (direct file reads, other MCP tools) vs. when investigation is mandatory
4. **Tool Reliability**: `load_context()` fails completely for minor validation issues, reducing tool reliability

**Impact**:

- Agents may create unnecessary investigation plans for non-critical validation errors (~10-20% of investigation plans)
- Uncertainty about when to continue with alternative approaches
- Reduced tool reliability when validation errors occur
- Potential workflow disruption for non-blocking errors

## Goals

1. **Clarify Error Classification**: Add clear distinction between critical blocking errors and non-critical errors where workarounds exist
2. **Provide Alternative Approach Guidance**: Document when alternative approaches are acceptable for non-critical errors
3. **Enhance Tool Error Handling**: Improve `load_context()` to handle validation errors more gracefully (optional, lower priority)
4. **Maintain Safety**: Ensure critical errors still trigger immediate investigation while allowing flexibility for non-critical issues

## Context

### Current State

- ✅ MCP Tool Error Handling rules exist in `.cortex/synapse/rules/general/agent-workflow.mdc` (lines 265-305)
- ✅ Rules require "STOP IMMEDIATELY" for any unexpected behavior
- ✅ Rules require investigation plans for all MCP tool errors
- ❌ No error classification (critical vs. non-critical)
- ❌ No guidance on alternative approaches
- ❌ `load_context()` fails completely for validation errors

### Session Findings (Phase 28)

**Error Encountered**:

- `load_context()` returned: `"9 validation errors for FileMetadataForScoring\nsections.0\n  Input should be a valid string [type=string_type, input_value={'title': '## Current Sta...3, 'content_hash': None}, input_type=dict]"`

**Agent Response**:

- Continued with alternative approaches (direct file reads, other MCP tools)
- Successfully completed Phase 28 implementation
- Created session optimization review identifying the ambiguity

**Review Recommendations**:

1. **Clarify MCP Tool Error Classification** (Medium Priority)
   - Add error classification to distinguish critical vs. non-critical errors
   - Expected impact: Prevents ~10-20% of unnecessary investigation plans

2. **Add Guidance on Alternative Approaches** (Low Priority)
   - Document when alternative approaches are acceptable
   - Expected impact: Provides clarity on acceptable workarounds

3. **Enhance load_context Error Handling** (Low Priority)
   - Improve handling of validation errors in the tool itself
   - Expected impact: Prevents complete tool failure for minor validation issues

## Approach

### High-Level Strategy

1. **Update Rules**: Add error classification and alternative approach guidance to MCP Tool Error Handling section
2. **Enhance Tool** (Optional): Improve `load_context()` validation error handling
3. **Documentation**: Ensure changes are clearly documented with examples
4. **Testing**: Verify rules changes don't break existing workflows

### Implementation Strategy

#### Phase 1: Rules Enhancement (Primary Focus)

- Add error classification subsection to agent-workflow.mdc
- Add alternative approaches guidance
- Update MCP Tool Error Handling section to reference classification
- Add examples of critical vs. non-critical errors

#### Phase 2: Tool Enhancement (Optional, Lower Priority)

- Enhance `load_context()` to handle validation errors gracefully
- Add fallback behavior for invalid sections
- Return partial results with error information
- Add tests for validation error handling

## Implementation Steps

### Step 1: Add Error Classification to Rules

**File**: `.cortex/synapse/rules/general/agent-workflow.mdc`

**Location**: After line 267 (after "MANDATORY" line, before "1. STOP IMMEDIATELY")

**Changes**:

1. Add new subsection "### Error Classification" with:
   - **CRITICAL ERRORS** (must investigate immediately):
     - Tool crashes or disconnects
     - Protocol errors (-32000, connection closed)
     - Tool returns completely unexpected response format
     - Tool blocks required workflow
   - **NON-CRITICAL ERRORS** (may continue with alternatives):
     - Validation errors in tool's data models (e.g., FileMetadataForScoring validation)
     - Data format issues where alternative information sources exist
     - Tool returns error but alternative approach is available
     - Error doesn't block core workflow
   - **Decision Criteria**:
     - If error blocks required workflow → CRITICAL (investigate immediately)
     - If alternative approach exists and error is non-blocking → NON-CRITICAL (may continue, but document)
     - When in doubt → Treat as CRITICAL (investigate)

2. Update "1. STOP IMMEDIATELY" section to reference error classification:
   - Only stop immediately for CRITICAL errors
   - For NON-CRITICAL errors, may continue with alternative approaches (see Alternative Approaches section)

**Acceptance Criteria**:

- Error classification clearly distinguishes critical vs. non-critical errors
- Decision criteria provide clear guidance
- Examples included for each error type
- Rules maintain safety for critical issues

### Step 2: Add Alternative Approaches Guidance

**File**: `.cortex/synapse/rules/general/agent-workflow.mdc`

**Location**: After error classification subsection

**Changes**:

1. Add new subsection "### Alternative Approaches for Non-Critical Errors" with:
   - When encountering NON-CRITICAL errors, you may:
     - Use alternative MCP tools that provide similar information
     - Use standard file tools (Read, Write) if MCP tool is for convenience only
     - Continue with available information if error doesn't block workflow
   - **Requirements**:
     - Document the error and alternative approach used
     - Verify alternative approach provides equivalent information
     - If alternative approach is insufficient, treat as CRITICAL error

2. Add examples of acceptable alternative approaches:
   - If `load_context()` fails with validation error → use `manage_file()` to read specific files
   - If `get_relevance_scores()` fails → use `load_context()` with explicit file list
   - If tool fails but standard file tools work → use standard tools and document

**Acceptance Criteria**:

- Clear guidance on when alternative approaches are acceptable
- Requirements for using alternative approaches documented
- Examples provided for common scenarios
- Safety maintained (insufficient alternatives → treat as critical)

### Step 3: Update MCP Tool Error Handling Section

**File**: `.cortex/synapse/rules/general/agent-workflow.mdc`

**Location**: Update existing section (lines 265-305)

**Changes**:

1. Update section header to reference error classification:
   - "## MCP Tool Error Handling (CRITICAL)"
   - Add note: "See Error Classification below for critical vs. non-critical errors"

2. Update "1. STOP IMMEDIATELY" step:
   - Add condition: "For CRITICAL errors only"
   - Add reference to Alternative Approaches section for non-critical errors
   - Maintain strict requirements for critical errors

3. Update "2. Create investigation plan" step:
   - Add condition: "For CRITICAL errors, create investigation plan"
   - Add note: "For NON-CRITICAL errors, document error and alternative approach used"

4. Update "5. Provide summary to user" step:
   - Add condition: "For CRITICAL errors, provide summary"
   - Add note: "For NON-CRITICAL errors, document in session notes"

**Acceptance Criteria**:

- Section updated to reference error classification
- Critical errors still require immediate investigation
- Non-critical errors have clear alternative path
- Safety maintained for critical issues

### Step 4: Enhance load_context Error Handling (Optional)

**File**: `src/cortex/tools/context_analysis_operations.py`

**Location**: `load_context()` function implementation

**Changes**:

1. Add try-catch for Pydantic validation errors:
   - Catch `ValidationError` for `FileMetadataForScoring` model
   - Log validation errors for debugging
   - Continue with fallback behavior

2. Implement fallback behavior:
   - Skip problematic sections that fail validation
   - Use default values for missing required fields
   - Continue processing other valid sections

3. Return partial results with error information:
   - Include error information in response
   - Indicate which sections were skipped
   - Return successfully processed sections

4. Add tests for validation error handling:
   - Test with invalid section data
   - Test fallback behavior
   - Test partial results return
   - Test error information in response

**Acceptance Criteria**:

- Tool handles validation errors gracefully
- Fallback behavior prevents complete failure
- Partial results returned with error information
- Tests verify error handling works correctly
- Tool reliability improved

### Step 5: Documentation and Examples

**Files**:

- `.cortex/synapse/rules/general/agent-workflow.mdc`
- Update any related documentation

**Changes**:

1. Add examples to error classification:
   - Example of critical error: Tool crash, disconnect
   - Example of non-critical error: Validation error with alternative available

2. Add examples to alternative approaches:
   - Example: `load_context()` validation error → use `manage_file()`
   - Example: Tool timeout → use alternative tool or standard file tools

3. Document decision process:
   - Flowchart or decision tree for error classification
   - Common scenarios and recommended actions

**Acceptance Criteria**:

- Examples clearly illustrate error classification
- Alternative approaches documented with examples
- Decision process clear and actionable

### Step 6: Testing and Validation

**Files**:

- Test rules changes don't break existing workflows
- Test tool enhancements (if Step 4 implemented)

**Changes**:

1. Review existing investigation plans:
   - Identify which would be classified as non-critical
   - Verify classification is correct

2. Test rules changes:
   - Verify critical errors still trigger investigation
   - Verify non-critical errors allow alternative approaches
   - Test decision criteria with various scenarios

3. Test tool enhancements (if implemented):
   - Run tests for validation error handling
   - Verify fallback behavior works
   - Verify partial results are useful

**Acceptance Criteria**:

- Rules changes validated with existing scenarios
- Tool enhancements tested and working
- No regressions in existing workflows

## Dependencies

- **None**: This is a standalone rules and documentation improvement
- **Optional**: Step 4 (tool enhancement) depends on understanding `load_context()` implementation

## Success Criteria

1. ✅ Error classification clearly distinguishes critical vs. non-critical errors
2. ✅ Alternative approaches guidance provides clear direction for non-critical errors
3. ✅ Rules maintain safety for critical errors (still require immediate investigation)
4. ✅ Rules allow flexibility for non-critical errors (may continue with alternatives)
5. ✅ Documentation includes examples and decision criteria
6. ✅ No regressions in existing workflows
7. ✅ Tool enhancements (if implemented) handle validation errors gracefully

## Testing Strategy

### Coverage Target

- **Minimum 95% code coverage** for ALL new functionality (MANDATORY)
- **100% coverage** for error classification logic
- **100% coverage** for alternative approach validation logic
- **95%+ coverage** for tool enhancements (if Step 4 implemented)

### Test Types

**Unit Tests** (MANDATORY):

1. **Error Classification Tests**:
   - Test critical error detection (crashes, disconnects, protocol errors)
   - Test non-critical error detection (validation errors, data format issues)
   - Test decision criteria logic
   - Test edge cases (ambiguous errors)

2. **Alternative Approach Tests** (if logic implemented):
   - Test alternative approach validation
   - Test equivalent information verification
   - Test insufficient alternative detection

3. **Tool Enhancement Tests** (if Step 4 implemented):
   - Test Pydantic validation error handling
   - Test fallback behavior (skip problematic sections)
   - Test partial results return
   - Test error information in response
   - Test default values for missing fields

**Integration Tests** (MANDATORY):

1. **Rules Integration Tests**:
   - Test rules changes with actual MCP tool errors
   - Test critical error triggers investigation plan
   - Test non-critical error allows alternative approach
   - Test decision criteria in real scenarios

2. **Tool Integration Tests** (if Step 4 implemented):
   - Test `load_context()` with invalid metadata
   - Test fallback behavior in real scenarios
   - Test partial results usability

**Edge Case Tests** (MANDATORY):

1. **Ambiguous Errors**:
   - Test errors that could be classified either way
   - Test decision criteria for ambiguous cases
   - Verify "when in doubt → treat as CRITICAL" rule

2. **Multiple Errors**:
   - Test multiple errors of same type
   - Test mix of critical and non-critical errors
   - Test error cascades

3. **Alternative Approach Edge Cases**:
   - Test alternative approach provides partial information
   - Test alternative approach fails
   - Test multiple alternative approaches available

**Regression Tests** (MANDATORY):

1. **Existing Workflow Tests**:
   - Verify critical errors still trigger investigation
   - Verify existing investigation plans still work
   - Verify no regressions in error handling

2. **Tool Regression Tests** (if Step 4 implemented):
   - Verify `load_context()` still works for valid data
   - Verify no performance regressions
   - Verify no behavior changes for valid inputs

### Test Documentation

- All tests MUST follow AAA pattern (Arrange-Act-Assert)
- All tests MUST have clear docstrings explaining purpose
- All tests MUST have descriptive names: `test_<functionality>_when_<condition>`
- All edge cases MUST be documented with test rationale

### Test Execution

- Run full test suite: `gtimeout -k 5 300 ./.venv/bin/python -m pytest -q`
- Run specific test file: `./.venv/bin/python -m pytest tests/unit/test_<module>.py -v`
- Verify coverage: `./.venv/bin/python -m pytest --cov=src --cov-report=term-missing`
- All tests MUST pass before considering implementation complete

## Technical Design

### Rules Structure

**Error Classification**:

- Clear categories: CRITICAL vs. NON-CRITICAL
- Decision criteria with examples
- "When in doubt" rule for safety

**Alternative Approaches**:

- When alternatives are acceptable
- Requirements for using alternatives
- Examples of common scenarios

**Updated Error Handling Flow**:

1. Encounter MCP tool error
2. Classify error (CRITICAL vs. NON-CRITICAL)
3. If CRITICAL → STOP IMMEDIATELY, create investigation plan
4. If NON-CRITICAL → Evaluate alternative approaches
5. If alternative available → Continue with alternative, document
6. If alternative insufficient → Treat as CRITICAL

### Tool Enhancement Design (Optional)

**Validation Error Handling**:

- Catch `ValidationError` from Pydantic models
- Log errors for debugging
- Skip problematic sections
- Use default values for missing fields

**Partial Results**:

- Return successfully processed sections
- Include error information
- Indicate which sections were skipped
- Maintain tool usability

## Risks & Mitigation

### Risk 1: Over-Relaxation of Error Handling

**Description**: Rules changes might cause agents to ignore critical errors

**Mitigation**:

- Maintain strict requirements for CRITICAL errors
- "When in doubt → treat as CRITICAL" rule
- Clear decision criteria
- Examples of critical errors

**Probability**: Low  
**Impact**: High  
**Severity**: Medium

### Risk 2: Inconsistent Error Classification

**Description**: Different agents might classify same error differently

**Mitigation**:

- Clear decision criteria with examples
- Document common scenarios
- "When in doubt → treat as CRITICAL" rule
- Review and refine classification over time

**Probability**: Medium  
**Impact**: Medium  
**Severity**: Medium

### Risk 3: Tool Enhancement Regressions

**Description**: Tool enhancements might break existing functionality

**Mitigation**:

- Comprehensive test coverage (95%+)
- Regression tests for existing workflows
- Careful fallback behavior implementation
- Gradual rollout with monitoring

**Probability**: Low  
**Impact**: Medium  
**Severity**: Low

### Risk 4: Alternative Approaches Insufficient

**Description**: Alternative approaches might not provide equivalent information

**Mitigation**:

- Requirement to verify alternative provides equivalent information
- If insufficient → treat as CRITICAL error
- Document alternative approaches used
- Review alternative approaches for effectiveness

**Probability**: Medium  
**Impact**: Low  
**Severity**: Low

## Timeline

### Phase 1: Rules Enhancement (Primary)

- **Step 1**: Add Error Classification (1-2 hours)
- **Step 2**: Add Alternative Approaches Guidance (1-2 hours)
- **Step 3**: Update MCP Tool Error Handling Section (1-2 hours)
- **Step 5**: Documentation and Examples (1-2 hours)
- **Step 6**: Testing and Validation (2-3 hours)

**Total Phase 1**: 6-11 hours

### Phase 2: Tool Enhancement (Optional)

- **Step 4**: Enhance load_context Error Handling (4-6 hours)
- **Additional Testing**: Tool-specific tests (2-3 hours)

**Total Phase 2**: 6-9 hours (optional)

### Overall Timeline

- **Minimum** (Rules only): 6-11 hours
- **Full Implementation** (Rules + Tool): 12-20 hours
- **Recommended**: Start with Phase 1 (Rules), evaluate Phase 2 (Tool) based on priority

## Notes

### Implementation Priority

1. **High Priority**: Steps 1-3 (Rules Enhancement) - Addresses main issue
2. **Medium Priority**: Step 5 (Documentation) - Improves clarity
3. **Low Priority**: Step 4 (Tool Enhancement) - Nice to have, not critical
4. **Mandatory**: Step 6 (Testing) - Required for all changes

### Decision Points

- **Step 4 (Tool Enhancement)**: Evaluate based on:
  - Frequency of `load_context()` validation errors
  - Impact of tool failures on workflows
  - Development capacity
  - User feedback

### Future Enhancements

- Monitor error classification effectiveness
- Refine classification based on real-world usage
- Add more examples as patterns emerge
- Consider automated error classification (future)

### Related Work

- **Phase 28**: Enforced MCP tool usage, identified this issue
- **Phase 36**: Enforce MCP Tool Failure Protocol (related error handling)
- **Session Optimization Review**: Identified this optimization opportunity

## References

- Session Optimization Review: `.cortex/reviews/session-optimization-2026-01-26T16:37.md`
- Current Rules: `.cortex/synapse/rules/general/agent-workflow.mdc` (lines 265-305)
- Phase 28 Plan: `.cortex/plans/phase-28-enforce-mcp-tools-for-cortex-operations.md`
- load_context Implementation: `src/cortex/tools/context_analysis_operations.py`
