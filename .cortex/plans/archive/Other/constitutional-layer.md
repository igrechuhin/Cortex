---
title: "Constitutional Layer for Projects"
component: planning
work_type: feature
status: PENDING
priority: high
created: 2026-04-06
depends_on: []
---

## Goal

Add a `constitution.md` to the Cortex memory bank at project initialization. This document captures immutable architectural principles (e.g., "no `Any` types", "functions ≤30 lines", tech stack constraints). The `plan` tool checks new plans against it and flags violations with an explicit audit trail in the plan file rather than silently accepting them.

## Context

Inspired by GitHub Spec Kit's `constitution.md` concept. Currently, Cortex encodes coding standards only in `cortex://rules` (which agents read on demand). There is no persistent, per-project governance document that survives rule-set updates and is embedded directly into planning artifacts. Teams often violate architectural decisions implicitly because there is no enforcement point between ideation and implementation.

## Implementation Steps

### Step 1: Define constitution schema

- Add `ConstitutionDoc` Pydantic model in `src/cortex/core/models.py` with fields: `principles: list[str]`, `tech_stack: list[str]`, `hard_limits: list[str]`, `compliance_requirements: list[str]`, `created: date`, `last_updated: date`.
- Define the memory-bank file path as `.cortex/memory-bank/constitution.md`.

**Verification**: Model is importable, fields are typed, no `Any`.

### Step 2: Add constitution template

- Create `.cortex/synapse/templates/constitution.md` — a starter template with placeholder sections for principles, tech stack, hard limits.
- Template should include inline comments explaining each section.

**Verification**: Template file exists, renders correctly as markdown.

### Step 3: Add `init_constitution` operation to `manage_file`

- In `src/cortex/tools/manage_file.py`, add `operation="init_constitution"` that:
  1. Checks if `.cortex/memory-bank/constitution.md` already exists (skip if so).
  2. Copies template to the memory bank path.
  3. Returns path + instructions for the user to fill it in.

**Verification**: `manage_file(operation="init_constitution")` creates the file; second call is a no-op.

### Step 4: Add constitutional compliance check to plan creation

- In `src/cortex/tools/plan.py`, when `operation="create"` or `operation="enrich"`:
  1. Read `constitution.md` from memory bank (non-blocking if missing).
  2. For each hard limit or principle, scan the plan content for potential violations.
  3. If violations detected, append a `## Constitutional Compliance` section to the plan with each violation listed as `[VIOLATION: <principle>] <explanation>`.
  4. Log a warning; do NOT block plan creation.

**Verification**: Creating a plan that violates a constitutional principle adds the compliance section; plans with no violations have no section added.

### Step 5: Surface constitution in `cortex://context` resource

- In `src/cortex/resources/context.py`, include constitution content in the context payload (after memory bank sections, before rules).
- Mark the section clearly so agents know it is immutable governance.

**Verification**: `cortex://context` response includes constitution content when the file exists.

### Step 6: Add `session()` constitution check

- In `session()` startup, check if `constitution.md` exists. If missing, include a one-line prompt: "No constitution.md found. Run `manage_file(operation='init_constitution')` to create one."

**Verification**: Session output includes the prompt when constitution is absent; no prompt when present.

### Step 7: Tests

- Unit test: `ConstitutionDoc` model validation.
- Unit test: `init_constitution` creates file, is idempotent.
- Unit test: Plan creation with violation inserts `## Constitutional Compliance` section.
- Unit test: Plan creation without violation has no compliance section.
- Integration test: Full flow — init constitution → create violating plan → verify section present.

**Verification**: All tests pass, coverage ≥ 95% for new code.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `ConstitutionDoc` class | `src/cortex/core/` | `models.py` |
| 2 | Template file | `.cortex/synapse/templates/` | `constitution.md` |
| 3 | `init_constitution` branch | `src/cortex/tools/manage_file.py` | full file |
| 4 | `Constitutional Compliance` section | `src/cortex/tools/plan.py` | full file |
| 5 | Constitution in context resource | `src/cortex/resources/context.py` | full file |
| 6 | Constitution check in session | `src/cortex/tools/session.py` | full file |
| 7 | Test files | `tests/` | new test files |

## Dependencies

- Existing `manage_file` tool infrastructure
- Existing `plan` tool
- `cortex://context` resource
- `session()` tool

## Success Criteria

- `constitution.md` can be initialized per project via a single MCP tool call.
- New plans automatically include a `## Constitutional Compliance` section when violations are detected.
- The constitution is visible to agents via `cortex://context`.
- All new code has ≥ 95% test coverage; no `Any` types; functions ≤ 30 lines.

## Testing Strategy

Target: 95% coverage on all new code paths.

- **Unit**: Model validation, file operations (mock filesystem), compliance scanner (parametrized: violating / non-violating plans).
- **Integration**: End-to-end flow using a real temp directory; no mocks for file I/O.
- **Edge cases**: Missing constitution (non-blocking), malformed constitution (graceful degradation), plan with multiple violations (all listed).

## Partial Progress Log

- 2026-04-06: Implement Step 1 foundation: add ConstitutionDoc schema and canonical constitution path primitives — files: src/cortex/core/models/_governance.py, src/cortex/core/models/**init**.py, src/cortex/core/constants.py, src/cortex/core/path_resolver.py, tests/unit/test_constitution_models.py, tests/unit/test_path_resolver.py
