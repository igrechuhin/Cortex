# Phase 76: Replace TypedDict with BaseModel and Remove Type-Checker Suppressions

## Status

PENDING

## Goal

Eliminate all TypedDict usage, TYPE_CHECKING imports, and type-checker suppression comments to comply with Python coding standards.

## Context

The code review (2026-03-04) identified three rules violations:

- **MEDIUM**: 8 TypedDict classes (rule: use Pydantic BaseModel instead)
- **MEDIUM**: 2 TYPE_CHECKING imports (rule: no TYPE_CHECKING imports)
- **MEDIUM**: ~17 type-checker suppression comments (`# type: ignore`, `# pyright: ignore`)

These violate the project's Python coding standards which mandate Pydantic v2, no TypedDict, no TYPE_CHECKING, and no suppression comments.

## Approach

Replace TypedDict with Pydantic BaseModel, resolve circular imports that TYPE_CHECKING was working around, and fix underlying type errors that suppressions were hiding.

## Implementation Steps

### Step 1: Replace TypedDict classes with Pydantic BaseModel

- Find all 8 TypedDict classes in the codebase
- Replace each with equivalent Pydantic BaseModel
- Update all usage sites (type annotations, instantiation, access patterns)
- Note: TypedDict uses bracket access (`d["key"]`), BaseModel uses attribute access (`d.key`)

### Step 2: Remove TYPE_CHECKING imports

- Find the 2 files using TYPE_CHECKING
- Resolve circular import dependencies that motivated TYPE_CHECKING
- Replace with direct imports (may require restructuring to break cycles)

### Step 3: Fix type errors and remove suppressions

- Find all ~17 type-checker suppression comments
- For each suppression, fix the underlying type error
- If the symbol is private but accessed cross-module, make it public (remove `_` prefix)
- Remove the suppression comment after fixing

### Step 4: Verify

- Run pyright — should report 0 errors
- Run ruff — should pass clean
- Run full test suite

## Dependencies

None.

## Success Criteria

- Zero TypedDict classes in codebase
- Zero TYPE_CHECKING imports
- Zero type-checker suppression comments
- Pyright passes with 0 errors
- All tests pass
- 95%+ test coverage for changed code

## Testing Strategy

- **Unit Tests**: Verify BaseModel replacements work identically to TypedDict
- **Edge Cases**: Serialization/deserialization, optional fields, nested models, default values
- **Regression**: Full test suite passes
- **Coverage Target**: 95%+ for modified modules

## Risks & Mitigation

- **Risk**: TypedDict-to-BaseModel migration changes access patterns
- **Mitigation**: Careful search-and-replace; run full test suite after each class migration
- **Risk**: Circular import resolution may require module restructuring
- **Mitigation**: Analyze import graph before changes; prefer extracting shared types to a common module

## Timeline

Medium effort (8-12h)
