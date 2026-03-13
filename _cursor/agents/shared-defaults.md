---
name: shared-defaults
description: Reference-only. Shared quality thresholds and conventions cited by Synapse cursor-agents. Projects using Cortex MCP can override these via their rules() configuration.
invocable: false
---

# Shared Defaults

These are the Synapse defaults. Projects override via their rules loaded by `rules()` at runtime.

## Quality Thresholds

- Max function length: **30 lines**
- Max file length: **400 lines**
- Coverage threshold (global): **0.90** (90%)
- Coverage threshold (new/modified code): **0.95** (95%)

## Fix Loop Limits

- Max iterations: **3**
- Convergence rule: if iteration 2 violation count >= iteration 1, abort — the loop is oscillating and will not converge

## Test Pattern

- **AAA** (Arrange / Act / Assert)

## Dependency Injection

- All external dependencies must be injected via initializers (not imported directly inside functions)

## Incremental Validation

- After each refactor: run type check and quality check before the next change — do not batch
