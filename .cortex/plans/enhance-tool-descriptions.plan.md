---
name: Enhance Tool Descriptions with USE WHEN and EXAMPLES
overview: Improve Cortex MCP tool descriptions by adding explicit "USE WHEN" triggers and "EXAMPLES" sections, following the pattern used in doc-mcp, taiga-ui-mcp, and react-mcp. This significantly improves tool discoverability for LLMs by making it clear when and how to use each tool.
todos:
  - id: analyze-current-descriptions
    content: Analyze current tool descriptions across all tool files and identify gaps
    status: pending
  - id: review-reference-patterns
    content: Review tool description patterns from doc-mcp, taiga-ui-mcp, and react-mcp
    status: pending
  - id: design-description-template
    content: Design standardized description template with USE WHEN, EXAMPLES, RETURNS sections
    status: pending
  - id: update-phase1-foundation-tools
    content: Enhance Phase 1 foundation tool descriptions (manage_file, get_memory_bank_stats, get_version_history, rollback_file_version, get_dependency_graph, cleanup_metadata_index)
    status: pending
  - id: update-phase2-linking-tools
    content: Enhance Phase 2 linking tool descriptions (parse_file_links, validate_links, resolve_transclusions, get_link_graph)
    status: pending
  - id: update-phase3-validation-tools
    content: Enhance Phase 3 validation tool descriptions (validate, get_validation_report)
    status: pending
  - id: update-phase4-optimization-tools
    content: Enhance Phase 4 optimization tool descriptions (load_context, load_progressive_context, summarize_content, get_relevance_scores)
    status: pending
  - id: update-phase5-analysis-tools
    content: Enhance Phase 5 analysis tool descriptions (analyze, analyze_context_effectiveness, get_context_usage_statistics)
    status: pending
  - id: update-phase5-refactoring-tools
    content: Enhance Phase 5 refactoring tool descriptions (suggest_refactoring, apply_refactoring, provide_feedback)
    status: pending
  - id: update-phase6-synapse-tools
    content: Enhance Phase 6 Synapse tool descriptions (sync_synapse, get_synapse_rules, get_synapse_prompts, update_synapse_rule, update_synapse_prompt)
    status: pending
  - id: update-phase8-structure-tools
    content: Enhance Phase 8 structure tool descriptions (check_structure_health, get_structure_info)
    status: pending
  - id: update-configuration-tools
    content: Enhance configuration tool descriptions (configure, get_config_status)
    status: pending
  - id: update-pre-commit-tools
    content: Enhance pre-commit tool descriptions (execute_pre_commit_checks, fix_quality_issues)
    status: pending
  - id: update-markdown-tools
    content: Enhance markdown tool descriptions (fix_markdown_lint, fix_roadmap_corruption)
    status: pending
  - id: update-rules-tools
    content: Enhance rules tool descriptions (rules operation)
    status: pending
  - id: update-connection-health-tools
    content: Enhance connection health tool descriptions (check_mcp_connection_health)
    status: pending
  - id: validate-discoverability
    content: Test tool discoverability with enhanced descriptions
    status: pending
isProject: false
---

# Enhance Tool Descriptions with USE WHEN and EXAMPLES

## Overview

Improve Cortex MCP tool descriptions by adding explicit "USE WHEN" triggers and "EXAMPLES" sections, following the pattern used in doc-mcp, taiga-ui-mcp, and react-mcp. This significantly improves tool discoverability for LLMs by making it clear when and how to use each tool.

**Reference Patterns:**

**doc-mcp (enhanced):**

```python
description=(
    "Search framework documentation using hybrid keyword + semantic search. "
    "USE WHEN: User asks about framework features, concepts, component behavior, "
    "or requests documentation ('explain X', 'how does Y work', 'what is Z', 'docs for W', 'link to X'). "
    "EXAMPLES: 'search for button components', 'find authentication docs', 'explain navigation patterns', "
    "'tui-button documentation'. "
    "RETURNS: Ranked sections with snippets and doc:// URIs."
)
```

**taiga-ui-mcp:**

```typescript
description: 'Return section-related content snippets (formerly examples) for specified documentation section name(s). The presence of id indicates a successful match.'
```

**react-mcp (enhanced):**

```typescript
description: 'Get a list of all components by platform'
```

## Current State

- **53+ tools** across 34+ files in `src/cortex/tools/` directory
- Some tools have detailed docstrings (e.g., `manage_file`, `validate`) but lack explicit "USE WHEN" and "EXAMPLES" sections
- Many tools have brief descriptions without usage guidance (e.g., `load_progressive_context`: "Load context progressively based on strategy.")
- Inconsistent format across tools - some have Args/Returns sections, others are minimal
- Missing explicit trigger patterns that help LLMs identify when to use each tool
- Tool descriptions are in docstrings, not in the `@mcp.tool()` decorator description parameter

## Benefits

1. **Better Discoverability**: LLMs can identify the right tool for a given task based on explicit trigger patterns
2. **Reduced Errors**: Clear usage guidance prevents tool misuse and parameter errors
3. **Consistency**: Standardized format across all 53+ tools
4. **Self-Documenting**: Descriptions serve as usage documentation for both LLMs and developers
5. **Improved Context**: Better tool selection reduces unnecessary tool calls and improves efficiency

## Implementation Plan

### Phase 1: Analysis and Design

1. **Analyze current descriptions**
   - Review all tool descriptions in `src/cortex/tools/` directory (34+ files)
   - Identify which tools already have detailed docstrings vs. minimal descriptions
   - Document gaps and inconsistencies
   - Categorize tools by phase/functionality for systematic updates

2. **Review reference patterns**
   - Study doc-mcp enhanced description format
   - Review taiga-ui-mcp and react-mcp patterns
   - Identify best practices for Cortex MCP context

3. **Design description template**

   ```python
   DESCRIPTION_TEMPLATE = """
   {Brief summary of what the tool does.}
   
   USE WHEN: {3+ specific trigger patterns}
         - User asks about {pattern 1}
         - User requests {pattern 2}
         - User needs {pattern 3}
   
   EXAMPLES: {3+ concrete query examples}
         - '{example 1}'
         - '{example 2}'
         - '{example 3}'
   
   RETURNS: {Clear description of output format}
   """
   ```

### Phase 2: Enhance Tool Descriptions by Category

Update each tool category systematically:

#### Phase 1 Foundation Tools

1. **manage_file**

   ```python
   description=(
       "Manage Memory Bank file operations: read, write, or get metadata. "
       "USE WHEN: User needs to read/write memory bank files, user requests file content, "
       "user needs file metadata, user wants to update project context files. "
       "EXAMPLES: 'read projectBrief.md', 'update activeContext.md', 'get metadata for roadmap.md', "
       "'write new content to systemPatterns.md'. "
       "RETURNS: JSON with file content (read), success status (write), or metadata object (metadata operation)."
   )
   ```

2. **get_memory_bank_stats**

   ```python
   description=(
       "Get comprehensive statistics about Memory Bank files and system status. "
       "USE WHEN: User asks about project status, user needs memory bank statistics, "
       "user wants to check file counts or token usage, user requests system overview. "
       "EXAMPLES: 'get memory bank stats', 'show project statistics', 'how many files in memory bank', "
       "'what is the token usage'. "
       "RETURNS: JSON with file counts, token usage, version history stats, and system health metrics."
   )
   ```

3. **get_version_history**

   ```python
   description=(
       "Get version history for a Memory Bank file showing all changes over time. "
       "USE WHEN: User asks about file history, user needs to see previous versions, "
       "user wants to track changes to a file, user requests version information. "
       "EXAMPLES: 'get version history for projectBrief.md', 'show changes to activeContext.md', "
       "'what versions exist for roadmap.md'. "
       "RETURNS: JSON array of version objects with timestamps, change descriptions, and version numbers."
   )
   ```

4. **rollback_file_version**

   ```python
   description=(
       "Rollback a Memory Bank file to a previous version, restoring earlier content. "
       "USE WHEN: User wants to undo changes, user needs to restore previous version, "
       "user requests rollback to specific version, user wants to revert file. "
       "EXAMPLES: 'rollback projectBrief.md to version 3', 'restore activeContext.md version 5', "
       "'revert roadmap.md to previous version'. "
       "RETURNS: JSON with success status, rolled back version number, and file content."
   )
   ```

5. **get_dependency_graph**

   ```python
   description=(
       "Get the Memory Bank dependency graph showing file relationships and transclusions. "
       "USE WHEN: User asks about file dependencies, user needs to understand file relationships, "
       "user wants to see transclusion tree, user requests dependency visualization. "
       "EXAMPLES: 'get dependency graph', 'show file dependencies', 'what files depend on projectBrief.md', "
       "'visualize transclusion tree'. "
       "RETURNS: JSON graph structure with nodes (files) and edges (dependencies/transclusions)."
   )
   ```

6. **cleanup_metadata_index**

   ```python
   description=(
       "Clean up stale entries from metadata index, removing orphaned or corrupted entries. "
       "USE WHEN: User reports index corruption, user needs to fix stale metadata, "
       "user wants to clean up index, user requests index maintenance. "
       "EXAMPLES: 'cleanup metadata index', 'fix stale index entries', 'repair corrupted index'. "
       "RETURNS: JSON with cleanup results: entries removed, entries kept, and dry-run preview if enabled."
   )
   ```

#### Phase 2 Linking Tools

1. **parse_file_links**

   ```python
   description=(
       "Parse and extract all markdown links and transclusion directives from a Memory Bank file. "
       "USE WHEN: User needs to find all links in a file, user wants to extract transclusions, "
       "user requests link parsing, user needs to analyze file references. "
       "EXAMPLES: 'parse links in projectBrief.md', 'extract transclusions from activeContext.md', "
       "'find all links in roadmap.md'. "
       "RETURNS: JSON with arrays of markdown links and transclusion directives found in the file."
   )
   ```

2. **validate_links**

   ```python
   description=(
       "Validate all markdown links and transclusion directives to ensure they point to existing targets. "
       "USE WHEN: User wants to check link integrity, user reports broken links, "
       "user needs to validate references, user requests link validation. "
       "EXAMPLES: 'validate links', 'check for broken links', 'validate transclusions in projectBrief.md'. "
       "RETURNS: JSON with validation results: valid links, broken links, and missing targets."
   )
   ```

3. **resolve_transclusions**

   ```python
   description=(
       "Resolve all {{include:}} transclusion directives in a file by replacing them with actual content. "
       "USE WHEN: User needs expanded file content, user wants to see transcluded content, "
       "user requests transclusion resolution, user needs full file content without transclusions. "
       "EXAMPLES: 'resolve transclusions in projectBrief.md', 'expand transclusions', "
       "'get full content with transclusions resolved'. "
       "RETURNS: JSON with resolved content where all {{include:}} directives are replaced with actual file content."
   )
   ```

4. **get_link_graph**

    ```python
    description=(
        "Get the link graph showing relationships between Memory Bank files via links and transclusions. "
        "USE WHEN: User asks about file relationships, user needs link visualization, "
        "user wants to see transclusion tree, user requests link graph. "
        "EXAMPLES: 'get link graph', 'show file link relationships', 'visualize transclusion tree'. "
        "RETURNS: JSON graph structure with nodes (files) and edges (links/transclusions)."
    )
    ```

#### Phase 3 Validation Tools

1. **validate**

    ```python
    description=(
        "Run validation checks on Memory Bank files for schema compliance, duplications, quality metrics, "
        "infrastructure consistency, timestamps, or roadmap synchronization. "
        "USE WHEN: User wants to validate memory bank, user needs quality check, "
        "user reports schema issues, user requests validation, user wants to check for duplicates. "
        "EXAMPLES: 'validate schema', 'check for duplications', 'validate quality metrics', "
        "'validate infrastructure consistency', 'check timestamp format', 'validate roadmap sync'. "
        "RETURNS: JSON with validation results, errors found, and suggested fixes."
    )
    ```

2. **get_validation_report**

    ```python
    description=(
        "Get comprehensive validation report with all check results and recommendations. "
        "USE WHEN: User needs full validation report, user wants validation summary, "
        "user requests validation details, user needs quality assessment. "
        "EXAMPLES: 'get validation report', 'show validation results', 'get quality report'. "
        "RETURNS: JSON with complete validation report including all check types and recommendations."
    )
    ```

#### Phase 4 Optimization Tools

1. **load_context**

    ```python
    description=(
        "Load relevant context for a task within token budget using dependency-aware or priority strategies. "
        "USE WHEN: User starts a task, user needs project context, user requests relevant files, "
        "user wants context for specific task, user needs memory bank content. "
        "EXAMPLES: 'load context for refactoring task', 'get relevant files for feature X', "
        "'load context with 5000 token budget', 'get context for bug fix'. "
        "RETURNS: JSON with selected files, their content, relevance scores, and token usage."
    )
    ```

2. **load_progressive_context**

    ```python
    description=(
        "Load context progressively based on relevance, loading files incrementally as needed. "
        "USE WHEN: User needs incremental context loading, user wants progressive file loading, "
        "user requests staged context, user needs context in batches. "
        "EXAMPLES: 'load progressive context for task', 'get context progressively', "
        "'load context in stages'. "
        "RETURNS: JSON with progressive context batches, each with files and relevance scores."
    )
    ```

3. **summarize_content**

    ```python
    description=(
        "Summarize Memory Bank content to reduce token usage while preserving key information. "
        "USE WHEN: User needs to reduce token count, user wants content summary, "
        "user requests token optimization, user needs condensed content. "
        "EXAMPLES: 'summarize projectBrief.md', 'reduce token usage for activeContext.md', "
        "'summarize content by 50%'. "
        "RETURNS: JSON with summarized content and token reduction metrics."
    )
    ```

4. **get_relevance_scores**

    ```python
    description=(
        "Get relevance scores for Memory Bank files based on task description. "
        "USE WHEN: User wants to know file relevance, user needs relevance ranking, "
        "user requests relevance scores, user wants to prioritize files. "
        "EXAMPLES: 'get relevance scores for refactoring task', 'score files for feature X', "
        "'rank files by relevance'. "
        "RETURNS: JSON with files ranked by relevance scores and detailed scoring breakdown."
    )
    ```

#### Phase 5 Analysis & Refactoring Tools

1. **analyze**

    ```python
    description=(
        "Analyze Memory Bank files for patterns, insights, and refactoring opportunities. "
        "USE WHEN: User wants pattern analysis, user needs insights, user requests analysis, "
        "user wants to find refactoring opportunities. "
        "EXAMPLES: 'analyze memory bank patterns', 'find refactoring opportunities', "
        "'analyze project structure', 'get insights about documentation'. "
        "RETURNS: JSON with analysis results, patterns found, and insights."
    )
    ```

2. **analyze_context_effectiveness**

    ```python
    description=(
        "Analyze load_context calls and update usage statistics for context optimization. "
        "USE WHEN: User wants to optimize context loading, user needs usage statistics, "
        "user requests context analysis, user wants to improve context selection. "
        "EXAMPLES: 'analyze context effectiveness', 'get context usage stats', "
        "'analyze context loading patterns'. "
        "RETURNS: JSON with context usage statistics and optimization recommendations."
    )
    ```

3. **get_context_usage_statistics**

    ```python
    description=(
        "Get current context usage statistics showing how context loading is being used. "
        "USE WHEN: User wants usage statistics, user needs context metrics, "
        "user requests usage data, user wants to monitor context usage. "
        "EXAMPLES: 'get context usage statistics', 'show context metrics', "
        "'get context usage data'. "
        "RETURNS: JSON with context usage statistics and metrics."
    )
    ```

4. **suggest_refactoring**

    ```python
    description=(
        "Suggest refactoring opportunities for consolidation, splits, or reorganization. "
        "USE WHEN: User wants refactoring suggestions, user needs consolidation ideas, "
        "user requests reorganization suggestions, user wants to improve structure. "
        "EXAMPLES: 'suggest refactoring for consolidation', 'find files to split', "
        "'suggest reorganization', 'get refactoring opportunities'. "
        "RETURNS: JSON with refactoring suggestions, similarity scores, and recommendations."
    )
    ```

5. **apply_refactoring**

    ```python
    description=(
        "Apply, approve, or rollback refactoring suggestions with safe execution. "
        "USE WHEN: User wants to apply refactoring, user needs to approve changes, "
        "user requests rollback, user wants to execute refactoring. "
        "EXAMPLES: 'apply refactoring suggestion X', 'approve refactoring Y', "
        "'rollback refactoring Z'. "
        "RETURNS: JSON with execution status, changes applied, and rollback information."
    )
    ```

6. **provide_feedback**

    ```python
    description=(
        "Provide feedback on refactoring suggestions to improve future recommendations. "
        "USE WHEN: User wants to give feedback, user needs to rate suggestions, "
        "user requests feedback submission, user wants to improve learning. "
        "EXAMPLES: 'provide feedback on suggestion X', 'rate refactoring Y', "
        "'submit feedback for improvement'. "
        "RETURNS: JSON with feedback submission status and learning updates."
    )
    ```

#### Phase 6 Synapse Tools

1. **sync_synapse**

    ```python
    description=(
        "Sync Synapse repository with remote using git operations (pull/push). "
        "USE WHEN: User wants to sync shared rules, user needs to update Synapse, "
        "user requests Synapse sync, user wants to pull/push changes. "
        "EXAMPLES: 'sync Synapse repository', 'pull Synapse updates', "
        "'push Synapse changes', 'sync shared rules'. "
        "RETURNS: JSON with sync status, changes pulled/pushed, and operation results."
    )
    ```

2. **get_synapse_rules**

    ```python
    description=(
        "Get relevant rules from Synapse repository based on task description. "
        "USE WHEN: User needs relevant rules, user wants Synapse rules, "
        "user requests rule retrieval, user needs coding standards. "
        "EXAMPLES: 'get Synapse rules for Python', 'get relevant rules for task', "
        "'get coding standards', 'get rules for refactoring'. "
        "RETURNS: JSON with relevant rules, relevance scores, and rule content."
    )
    ```

3. **get_synapse_prompts**

    ```python
    description=(
        "Get prompts from Synapse repository, optionally filtered by category. "
        "USE WHEN: User needs Synapse prompts, user wants prompt templates, "
        "user requests prompts, user needs workflow prompts. "
        "EXAMPLES: 'get Synapse prompts', 'get prompts for commit', "
        "'get prompts by category', 'get workflow prompts'. "
        "RETURNS: JSON with prompts, categories, and prompt content."
    )
    ```

4. **update_synapse_rule**

    ```python
    description=(
        "Update a Synapse rule file and push changes to all projects. "
        "USE WHEN: User wants to update shared rule, user needs to modify rule, "
        "user requests rule update, user wants to push rule changes. "
        "EXAMPLES: 'update Synapse rule python-security', 'modify shared rule', "
        "'update rule and push'. "
        "RETURNS: JSON with update status, changes made, and push results."
    )
    ```

5. **update_synapse_prompt**

    ```python
    description=(
        "Update a Synapse prompt file and push changes to all projects. "
        "USE WHEN: User wants to update shared prompt, user needs to modify prompt, "
        "user requests prompt update, user wants to push prompt changes. "
        "EXAMPLES: 'update Synapse prompt commit', 'modify shared prompt', "
        "'update prompt and push'. "
        "RETURNS: JSON with update status, changes made, and push results."
    )
    ```

#### Phase 8 Structure Tools

1. **check_structure_health**

    ```python
    description=(
        "Check project structure health and optionally perform cleanup actions. "
        "USE WHEN: User wants structure health check, user needs to fix structure issues, "
        "user requests structure validation, user wants cleanup actions. "
        "EXAMPLES: 'check structure health', 'fix structure issues', "
        "'validate project structure', 'perform structure cleanup'. "
        "RETURNS: JSON with health score, issues found, and cleanup results."
    )
    ```

2. **get_structure_info**

    ```python
    description=(
        "Get current project structure configuration, paths, and status information. "
        "USE WHEN: User needs structure paths, user wants structure configuration, "
        "user requests structure info, user needs path information. "
        "EXAMPLES: 'get structure info', 'show structure paths', "
        "'get structure configuration', 'get memory bank path'. "
        "RETURNS: JSON with structure version, paths, configuration, and health status."
    )
    ```

#### Configuration & Utility Tools

1. **configure**

    ```python
    description=(
        "Configure Cortex components (validation, optimization, refactoring) with custom settings. "
        "USE WHEN: User wants to configure settings, user needs to change configuration, "
        "user requests configuration update, user wants to customize behavior. "
        "EXAMPLES: 'configure validation settings', 'set optimization parameters', "
        "'update refactoring config', 'view current configuration'. "
        "RETURNS: JSON with configuration status and updated settings."
    )
    ```

2. **get_config_status**

    ```python
    description=(
        "Get current configuration status for all Cortex components. "
        "USE WHEN: User wants configuration status, user needs current settings, "
        "user requests config info, user wants to check configuration. "
        "EXAMPLES: 'get config status', 'show current configuration', "
        "'check config settings'. "
        "RETURNS: JSON with current configuration for all components."
    )
    ```

3. **execute_pre_commit_checks**

    ```python
    description=(
        "Execute pre-commit checks (formatting, linting, type checking, tests) before committing. "
        "USE WHEN: User wants pre-commit checks, user needs quality validation, "
        "user requests pre-commit validation, user wants to check before commit. "
        "EXAMPLES: 'execute pre-commit checks', 'run quality checks', "
        "'check formatting and linting', 'run pre-commit validation'. "
        "RETURNS: JSON with check results, errors found, and pass/fail status."
    )
    ```

4. **fix_quality_issues**

    ```python
    description=(
        "Automatically fix code quality issues (formatting, linting, type errors, markdown). "
        "USE WHEN: User wants auto-fix, user needs quality fixes, "
        "user requests automatic fixes, user wants to fix code quality. "
        "EXAMPLES: 'fix quality issues', 'auto-fix formatting', "
        "'fix linting errors', 'fix markdown issues'. "
        "RETURNS: JSON with fixes applied, files modified, and remaining issues."
    )
    ```

5. **fix_markdown_lint**

    ```python
    description=(
        "Fix markdown linting issues in Memory Bank files automatically. "
        "USE WHEN: User wants markdown fixes, user needs lint fixes, "
        "user requests markdown lint fix, user wants to fix markdown errors. "
        "EXAMPLES: 'fix markdown lint', 'fix markdown errors', "
        "'auto-fix markdown', 'fix markdown formatting'. "
        "RETURNS: JSON with fixes applied, files modified, and lint results."
    )
    ```

6. **fix_roadmap_corruption**

    ```python
    description=(
        "Fix text corruption in roadmap.md file, restoring proper formatting. "
        "USE WHEN: User reports roadmap corruption, user needs roadmap fix, "
        "user requests corruption repair, user wants to fix roadmap. "
        "EXAMPLES: 'fix roadmap corruption', 'repair roadmap.md', "
        "'fix corrupted roadmap', 'restore roadmap formatting'. "
        "RETURNS: JSON with fix status, changes made, and roadmap health."
    )
    ```

7. **rules**

    ```python
    description=(
        "Index or get relevant rules from project rules directory. "
        "USE WHEN: User wants to index rules, user needs relevant rules, "
        "user requests rule retrieval, user wants rule indexing. "
        "EXAMPLES: 'index rules', 'get relevant rules for task', "
        "'get rules for Python', 'index project rules'. "
        "RETURNS: JSON with indexed rules or relevant rules with scores."
    )
    ```

8. **check_mcp_connection_health**

    ```python
    description=(
        "Check MCP connection health and resource utilization. "
        "USE WHEN: User wants connection status, user needs health check, "
        "user requests connection health, user wants to monitor MCP server. "
        "EXAMPLES: 'check MCP connection health', 'get connection status', "
        "'check server health', 'monitor MCP connection'. "
        "RETURNS: JSON with connection status, resource metrics, and health indicators."
    )
    ```

### Phase 3: Validation

1. **Test discoverability**
   - Verify LLMs can identify correct tools from enhanced descriptions
   - Test with various query patterns matching USE WHEN triggers
   - Ensure examples are realistic and cover common use cases
   - Validate that RETURNS sections accurately describe output format

2. **Consistency check**
   - Verify all tools follow same format
   - Check for missing sections (USE WHEN, EXAMPLES, RETURNS)
   - Ensure examples are realistic and actionable
   - Validate that descriptions are concise but comprehensive

3. **Code quality validation**
   - Run pre-commit checks (formatting, linting, type checking)
   - Ensure all descriptions follow Python docstring conventions
   - Verify no syntax errors in description strings
   - Check that descriptions don't exceed reasonable length limits

## Example Enhanced Description

**Before:**

```python
@mcp.tool()
async def load_progressive_context(
    task_description: str,
    token_budget: int | None = None,
    loading_strategy: str = "by_relevance",
    project_root: str | None = None,
) -> str:
    """Load context progressively based on strategy."""
```

**After:**

```python
@mcp.tool()
async def load_progressive_context(
    task_description: str,
    token_budget: int | None = None,
    loading_strategy: str = "by_relevance",
    project_root: str | None = None,
) -> str:
    """Load context progressively based on relevance, loading files incrementally as needed.
    
    USE WHEN: User needs incremental context loading, user wants progressive file loading,
    user requests staged context, user needs context in batches.
    
    EXAMPLES: 'load progressive context for task', 'get context progressively',
    'load context in stages'.
    
    RETURNS: JSON with progressive context batches, each with files and relevance scores.
    """
```

## Testing Strategy

### Coverage Target

- **Minimum 95% code coverage** for all new description enhancements (MANDATORY)
- All tool description updates must be validated through comprehensive testing

### Unit Tests

- Test that all tools have enhanced descriptions with USE WHEN, EXAMPLES, and RETURNS sections
- Verify description format consistency across all tools
- Test description parsing and validation
- Validate that descriptions don't break existing tool functionality

### Integration Tests

- Test tool discoverability with enhanced descriptions using LLM simulation
- Verify that USE WHEN triggers correctly match user queries
- Test that examples are realistic and cover common use cases
- Validate that RETURNS sections accurately describe actual tool output

### Edge Cases

- Test tools with very long descriptions
- Test tools with minimal existing descriptions
- Test tools with complex parameter lists
- Test tools with multiple operation types (e.g., manage_file with read/write/metadata)

### Regression Tests

- Ensure existing tool functionality remains unaffected
- Verify that tool registration still works correctly
- Test that MCP protocol compliance is maintained
- Validate that tool calls work with enhanced descriptions

### Test Documentation

- Document test scenarios for description validation
- Document expected behaviors for USE WHEN triggers
- Document example validation criteria
- Document RETURNS format validation

### AAA Pattern

All tests MUST follow Arrange-Act-Assert pattern:

- **Arrange**: Set up tool description and test data
- **Act**: Validate description format and content
- **Assert**: Verify description meets requirements

### No Blanket Skips

- Every skip MUST have justification and linked ticket
- No temporary skips without removal conditions
- Prefer fixing flaky tests instead of skipping

## Success Criteria

- ✅ All 53+ tools have enhanced descriptions with USE WHEN section
- ✅ All tools have EXAMPLES section with 3+ examples
- ✅ All tools have RETURNS section describing output format
- ✅ Descriptions follow consistent format across all tools
- ✅ USE WHEN triggers are specific and actionable
- ✅ Examples are realistic and cover common use cases
- ✅ Tool discoverability is improved (validated through testing)
- ✅ All tests passing (2853+ tests)
- ✅ Code coverage maintained at 90%+ (target 95% for new code)
- ✅ No type errors or linting violations
- ✅ All descriptions validated for format consistency

## Risks & Mitigation

### Risk 1: Breaking Existing Tool Calls

- **Mitigation**: Descriptions are metadata only, don't affect tool behavior
- **Validation**: Run full test suite after updates

### Risk 2: Description Length Issues

- **Mitigation**: Keep descriptions concise but comprehensive
- **Validation**: Check description length during code review

### Risk 3: Inconsistent Format

- **Mitigation**: Use standardized template and review all descriptions
- **Validation**: Automated format checking in tests

### Risk 4: Examples Not Matching Actual Behavior

- **Mitigation**: Test examples against actual tool behavior
- **Validation**: Integration tests verify example accuracy

## Timeline

- **Phase 1 (Analysis & Design)**: 2-3 hours
- **Phase 2 (Enhance Descriptions)**: 8-10 hours (37 tools × ~15 minutes each)
- **Phase 3 (Validation)**: 2-3 hours
- **Total Estimated Effort**: 12-16 hours

## Dependencies

- No external dependencies
- Requires access to all tool files in `src/cortex/tools/`
- May benefit from Phase 45 (MCP Annotations) but not required

## Notes

- Follow existing pattern from doc-mcp enhanced descriptions
- Keep descriptions concise but comprehensive
- USE WHEN should have 3+ trigger patterns
- EXAMPLES should have 3+ concrete examples
- RETURNS should clearly describe output format
- Update descriptions as tools evolve
- Consider adding descriptions to `@mcp.tool()` decorator if FastMCP supports it
- Maintain backward compatibility - descriptions don't affect tool behavior
