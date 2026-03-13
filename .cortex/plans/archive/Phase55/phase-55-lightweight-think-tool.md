# Phase 55: Lightweight Think Tool Enhancement

**Status:** PENDING
**Created:** 2026-02-11
**Priority:** MEDIUM
**Estimated Effort:** 1 sprint
**Related:** Sequential Thinking (existing tool)

## Goal

Add a lightweight `think` tool alias alongside the existing `sequentialthinking` tool, following Anthropic's "Think Tool" pattern — a dead-simple scratchpad with just a `thought` string parameter, plus domain-specific thinking examples in system prompts for complex Cortex operations.

## Context

Anthropic's "The Think Tool" article shows that a minimal think tool (just a `thought` string) improved task accuracy by 54% on complex policy-heavy environments. The key insight: "Simply making the think tool available might improve performance somewhat, but pairing it with optimized prompting yielded dramatically better results."

Cortex already has `sequentialthinking` with many parameters (thought_number, total_thoughts, branch_from_thought, branch_id, revises_thought, is_revision, needs_more_thoughts). While powerful for formal reasoning, it's too heavyweight for quick deliberation moments where an agent just needs to pause and think.

Anthropic's recommended pattern:

```json
{
  "name": "think",
  "description": "Use the tool to think about something. It will not obtain new information or change the database, but just append the thought to the log.",
  "input_schema": {
    "properties": {
      "thought": {"type": "string", "description": "A thought to think about."}
    },
    "required": ["thought"]
  }
}
```

The article also shows that domain-specific thinking examples in prompts dramatically improve results.

**Reference:** <https://www.anthropic.com/engineering/claude-think-tool>

## Approach

1. Add a lightweight `think` tool that wraps sequentialthinking with minimal params
2. Add domain-specific thinking examples to key Cortex prompts
3. Measure impact on task accuracy

## Implementation Steps

### Step 1: Implement Lightweight think Tool

- [ ] Create `think(thought: str)` MCP tool:
  - Internally calls `SequentialThinkingCore.process_thought()` with auto-incrementing thought_number
  - Returns just `{"status": "thought_logged", "thought_number": N}`
  - No required parameters beyond `thought`
  - Description: "Use to think about something before taking action. Useful for analyzing tool outputs, checking policy compliance, planning multi-step operations, or reasoning about complex decisions."
- [ ] Keep `sequentialthinking` available for formal multi-step reasoning
- [ ] Register in tool discovery with appropriate USE WHEN guidance
- [ ] Unit tests for think tool (95%+ coverage)

### Step 2: Domain-Specific Thinking Examples for Prompts

- [ ] Add thinking examples to commit prompt for complex decisions:

  ```markdown
  ## Using the think tool

  Before taking action after receiving tool results, use think to:

  - List which pre-commit checks apply to the current changes
  - Verify all files are staged and no secrets included
  - Check if memory bank updates are needed

  Example:
  <think_example>
  Changes include: 3 Python files, 1 markdown file

  - Need: fix_errors, format, type_check, quality, tests
  - Markdown changed: need markdown lint
  - Memory bank: activeContext needs update for completed work
  - Check: no .env files staged, no hardcoded secrets
  </think_example>
  ```

- [ ] Add thinking examples to implement prompt for step analysis:

  ```markdown
  <think_example>
  Reading plan step: "Add response_format parameter to manage_file"

  - Dependencies: manage_file handler exists in file_operations.py
  - Need to: add parameter to schema, handler logic, tests
  - Risks: backward compatibility — default must be "detailed" for existing callers
  - Testing: unit test for both formats, integration test with real file
  </think_example>
  ```

- [ ] Add thinking examples to plan creation for scope analysis
- [ ] Add thinking examples to refactoring decisions

### Step 3: Prompt Integration

- [ ] Update commit.md with think tool examples for pre-commit reasoning
- [ ] Update implement-next-roadmap-step.md with think tool for step analysis
- [ ] Update create-plan.md with think tool for scope/dependency analysis
- [ ] Add general think tool guidance to AGENTS.md
- [ ] Reference think tool in CLAUDE.md

### Step 4: Testing and Validation

- [ ] Unit tests for think tool (95%+ coverage)
- [ ] Test that think tool correctly logs thoughts and increments counter
- [ ] Test that think tool is independent from sequentialthinking sessions
- [ ] Measure impact: compare task accuracy with/without think tool available
- [ ] Verify think tool doesn't interfere with existing sequentialthinking usage

## Dependencies

- `SequentialThinkingCore` (existing) — think wraps this
- Synapse prompts (existing) — need updates for thinking examples

## Success Criteria

1. `think` tool registered with single `thought` parameter
2. Domain-specific thinking examples added to 3+ prompts
3. think tool works independently from sequentialthinking sessions
4. 95%+ test coverage
5. No regression in existing sequentialthinking functionality

## Testing Strategy

- **Coverage Target:** 95%+
- **Unit Tests:** think tool registration, thought logging, auto-increment, independence from sequentialthinking
- **Integration Tests:** Think tool in agentic workflow (think → tool call → think → respond)
- **Edge Cases:** Very long thoughts, empty thoughts, rapid successive calls, unicode content
- **AAA Pattern:** All tests follow Arrange-Act-Assert

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Agents overuse think tool (wasting tokens) | Low | Clear description of when to use vs not |
| Think examples become stale | Low | Keep examples generic, review quarterly |
| Confusion between think and sequentialthinking | Low | Clear differentiation in descriptions |
