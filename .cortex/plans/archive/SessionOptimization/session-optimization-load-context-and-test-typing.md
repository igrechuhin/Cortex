# Session Optimization: load_context Budget and Test Type Narrowing

## Source

Created from end-of-session analysis report: `.cortex/reviews/session-optimization-2026-02-18T11-21.md`

Enriched from: `.cortex/reviews/session-optimization-2026-02-18T22-09.md` (cross-linking and task description guidance)

## Goals

1. Ensure implement/fix workflows always use a non-zero `load_context` token budget for non-trivial tasks.
2. Document test typing for dict/JsonValue results (narrow before numeric comparison).
3. Cross-link reference documentation from AGENTS.md/CLAUDE.md for discoverability.
4. Improve task description guidance in prompts to increase context loading effectiveness.

## Steps

### 1. Implement and fix prompts: load_context budget

- **Target**: Implement prompt and fix-path/fix-quality (or equivalent) prompt.
- **Change**: Add or reinforce that for non-trivial tasks (implement, fix, debug, refactor), `load_context` MUST be called with a non-zero token budget (e.g. 10k–15k for fix/debug, 20k–30k for implement). Zero-budget or zero-files for those tasks is a configuration error.
- **Rationale**: Historical context-effectiveness data shows zero-budget/zero-files calls for non-trivial tasks; documenting this in prompts reduces repeat violations.

### 2. Testing / type rules: JsonValue narrowing

- **Target**: Testing guide and/or Synapse rules (e.g. Python coding standards, testing).
- **Change**: Document that assertions on dict values from adapter/API responses (e.g. `_parse_test_output` or other JsonValue-returning APIs) must narrow type before numeric comparison: use `cast(float, result["key"])` after a not-None check, or `isinstance(v, (int, float))` then use `v`.
- **Rationale**: Avoids type-checker errors (e.g. operator "<" not supported for JsonValue and float) and sets a clear pattern for test authors.

### 3. Cross-link reference documentation

- **Target**: AGENTS.md and CLAUDE.md
- **Change**: Add links to reference documentation sections:
  - Commit pipeline context loading: Link to `docs/design/commit-pipeline-phases.md#context-loading-for-commit-pipeline`
  - Helper module extraction: Link to `docs/guides/code-quality.md#helper-module-extraction`
  - Consider adding a "Reference Documentation" section in AGENTS.md listing canonical docs
- **Rationale**: Reference docs added to design/guides directories are not discoverable from primary agent guidance files, reducing their effectiveness.

### 4. Improve task description guidance

- **Target**: Implement and analyze prompts
- **Change**: Document task description best practices:
  - Include keywords that match memory bank file content (e.g., "commit pipeline", "context loading", "helper module")
  - Avoid overly generic descriptions that result in low relevance scores (<0.3)
  - Provide examples of effective vs. ineffective task descriptions
- **Rationale**: Low relevance scores (0.221-0.25) in some sessions suggest task descriptions may be too generic, leading to zero-files selection or poor context matching.

## Success Criteria

- Implement (and relevant fix) prompts explicitly require non-zero `load_context` budget for non-trivial tasks.
- Testing or type rules document the JsonValue narrowing pattern for tests.
- AGENTS.md and/or CLAUDE.md include links to commit pipeline context loading and helper module extraction reference docs.
- Implement/analyze prompts include task description best practices with examples.
