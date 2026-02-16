# Phase 52: Consistent Helpful Error Responses

**Status:** PENDING
**Created:** 2026-02-11
**Priority:** MEDIUM
**Estimated Effort:** 1 sprint
**Related:** Phase 50 (Tool Consolidation)

## Goal

Standardize all Cortex MCP tool error responses to consistently include: (1) what went wrong, (2) what the agent should do differently, and (3) an example of correct usage — following Anthropic's guidance that "error responses should clearly communicate specific and actionable improvements, rather than opaque error codes or tracebacks."

## Context

From Anthropic's "Writing Effective Tools for Agents": tools should "prompt-engineer your error responses to clearly communicate specific and actionable improvements, rather than opaque error codes or tracebacks."

Current Cortex error handling is inconsistent:

- Some tools return helpful errors with `available_files` and `suggestion` fields (e.g., `manage_file` when file not found)
- Other tools return raw exception messages or generic "error" strings
- Stack traces sometimes leak into error responses
- No standard error response schema across tools

## Approach

1. Define a standard error response Pydantic model
2. Audit all tool error paths
3. Implement consistent error formatting
4. Add actionable suggestions and examples to all error responses

## Implementation Steps

### Step 1: Define Standard Error Response Schema

- [ ] Create `ToolErrorResponse` Pydantic model:

  ```python
  class ToolErrorResponse(BaseModel):
      status: Literal["error"] = "error"
      error: str  # Human-readable error message
      error_type: str  # Exception class name
      suggestion: str | None = None  # What to do differently
      example: dict | None = None  # Example of correct usage
      available_options: list[str] | None = None  # Valid values if applicable
  ```

- [ ] Create `format_tool_error()` helper function
- [ ] Create domain-specific error formatters (file errors, validation errors, config errors)
- [ ] Unit tests for error response formatting

### Step 2: Audit All Tool Error Paths

- [ ] Catalog every tool's error responses (53+ tools):
  - What errors can each tool produce?
  - What information is currently returned?
  - What additional context would be helpful?
- [ ] Categorize error types:
  - **File not found** → include available_files, did-you-mean suggestion
  - **Invalid parameter** → include valid options, example of correct usage
  - **Permission/lock error** → include who holds lock, retry guidance
  - **Validation failure** → include specific violations, fix suggestions
  - **Configuration error** → include current config, expected format
  - **External tool failure** → include troubleshooting steps
- [ ] Create error response templates for each category

### Step 3: Implement Consistent Error Formatting

- [ ] Update all tool handlers to use `format_tool_error()`:
  - Phase 1 (high-impact tools): manage_file, validate, load_context, execute_pre_commit_checks, fix_quality_issues
  - Phase 2 (medium-impact): suggest_refactoring, apply_refactoring, rules, configure
  - Phase 3 (low-impact): all remaining tools
- [ ] Replace raw exception messages with formatted responses
- [ ] Remove stack trace leakage from all error responses
- [ ] Add truncation hints to large error outputs: "Showing first 5 of 23 errors. Use validate(check_type='schema', file_name='specific_file.md') for detailed per-file results."

### Step 4: Add Actionable Suggestions

- [ ] Implement suggestion generators for common errors:
  - File not found: `"Did you mean 'activeContext.md'? Available files: [...]"`
  - Invalid check_type: `"Valid check_types: schema, duplications, quality, timestamps, roadmap_sync, infrastructure"`
  - Missing required param: `"The 'content' parameter is required for write operations. Example: manage_file(file_name='notes.md', operation='write', content='# Notes\n...')"`
  - Token budget exceeded: `"Content exceeds token budget (15000). Try: load_context(depth='metadata_only') or reduce token_budget"`
- [ ] Add fuzzy matching for file names and parameter values (Levenshtein distance)
- [ ] Include one-line example of correct usage in every error response

### Step 5: Testing and Validation

- [ ] Unit tests for all error formatters (95%+ coverage)
- [ ] Test every tool's error paths produce structured ToolErrorResponse
- [ ] Integration test: trigger each error category and verify response format
- [ ] Verify no stack traces leak in any error response
- [ ] Measure impact: count how many tool retries are needed before/after

## Dependencies

- None (standalone improvement)

## Success Criteria

1. All 53+ tools use standardized `ToolErrorResponse` format
2. Every error response includes `suggestion` field with actionable guidance
3. Zero stack trace leakage in tool error responses
4. 95%+ test coverage for error formatting
5. Fuzzy matching for file names and parameter values

## Testing Strategy

- **Coverage Target:** 95%+ for error formatting code
- **Unit Tests:** Test format_tool_error for each error category, fuzzy matching, suggestion generation
- **Integration Tests:** Trigger errors in each tool and verify response schema
- **Edge Cases:** Empty error messages, very long error messages, unicode in errors, nested exception chains
- **Regression Tests:** Existing error handling still works for tools not yet migrated
- **AAA Pattern:** All tests follow Arrange-Act-Assert
- **Pydantic v2:** Use ToolErrorResponse model for validation in all tests

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Suggestions become stale as tools evolve | Low | Generate suggestions dynamically from tool schemas |
| Fuzzy matching returns wrong suggestions | Low | Use minimum distance threshold, show top 3 |
| Error formatting overhead | Low | Negligible compared to tool execution time |
