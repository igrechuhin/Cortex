# Session Optimization: load_context Budget and Test Type Narrowing

## Source

Created from end-of-session analysis report: `.cortex/reviews/session-optimization-2026-02-18T11-21.md`

## Goals

1. Ensure implement/fix workflows always use a non-zero `load_context` token budget for non-trivial tasks.
2. Document test typing for dict/JsonValue results (narrow before numeric comparison).

## Steps

### 1. Implement and fix prompts: load_context budget

- **Target**: Implement prompt and fix-path/fix-quality (or equivalent) prompt.
- **Change**: Add or reinforce that for non-trivial tasks (implement, fix, debug, refactor), `load_context` MUST be called with a non-zero token budget (e.g. 10k–15k for fix/debug, 20k–30k for implement). Zero-budget or zero-files for those tasks is a configuration error.
- **Rationale**: Historical context-effectiveness data shows zero-budget/zero-files calls for non-trivial tasks; documenting this in prompts reduces repeat violations.

### 2. Testing / type rules: JsonValue narrowing

- **Target**: Testing guide and/or Synapse rules (e.g. Python coding standards, testing).
- **Change**: Document that assertions on dict values from adapter/API responses (e.g. `_parse_test_output` or other JsonValue-returning APIs) must narrow type before numeric comparison: use `cast(float, result["key"])` after a not-None check, or `isinstance(v, (int, float))` then use `v`.
- **Rationale**: Avoids type-checker errors (e.g. operator "<" not supported for JsonValue and float) and sets a clear pattern for test authors.

## Success Criteria

- Implement (and relevant fix) prompts explicitly require non-zero `load_context` budget for non-trivial tasks.
- Testing or type rules document the JsonValue narrowing pattern for tests.
