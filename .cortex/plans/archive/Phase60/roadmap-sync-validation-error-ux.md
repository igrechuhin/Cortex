# Roadmap Sync & Validation Error UX Improvements

## Status

- Initial status: Planning

## Goal

Improve the developer experience around roadmap synchronization and Memory Bank validation by:

- Making `roadmap_sync` invalid reference diagnostics explicit and actionable
- Ensuring references to `.cortex/plans` files (Phase plans) resolve correctly without fragile workarounds
- Keeping commit pipeline behavior predictable and clearly documented

## Context

- Recent `/cortex/commit` runs surfaced confusing `roadmap_sync` results:
  - Phase plan links under `../plans/` were reported as invalid references even though the `.cortex/plans/*.md` files exist
  - The validator behavior around what counts as a “reference” vs. “TODO tracking” was not obvious from the raw JSON
- Roadmap and progress entries correctly track coverage and adapter work (e.g., `phase5_execution_helpers.py`, `python_adapter.py`), but:
  - Developers had to guess why certain links were considered invalid
  - The tool output did not clearly explain path resolution assumptions or how to fix problems
- Cortex already has:
  - Centralized path resolution via `get_structure_info()` and `CortexResourceType`
  - A strict commit pipeline that treats roadmap/Memory Bank validation as blocking
  - High coverage requirements and strong testing standards

This plan focuses on clarifying behavior and error messages, not changing high-level commit semantics.

## Approach

1. **Clarify semantics** of roadmap synchronization and references in docs and prompts
2. **Normalize and resolve paths** using the existing structure/path utilities instead of implicit project-root assumptions
3. **Enrich MCP responses** with human-readable explanations for invalid references and suggested fixes
4. **Add focused tests** that lock in the improved behavior and guard against regressions
5. **Update Memory Bank content** (where necessary) to align with the clarified rules while preserving useful context

## Implementation Steps

### 1. Requirements & Behavior Clarification

1.1 **Document current behavior**

- Summarize what `roadmap_sync` does today:
  - How TODOs are discovered from `src/` and `scripts/`
  - How file-like references are parsed from `roadmap.md`
  - How `valid`, `missing_roadmap_entries`, and `invalid_references` are computed
- Capture concrete examples from recent runs (including Phase plan references and coverage-related bullets).

1.2 **Clarify intended semantics**

- Decide and document:
  - How references to `.cortex/plans/*.md` should be represented in `roadmap.md`
  - Whether Phase plan links are considered “file references” or just documentation
  - What counts as a blocking `invalid_reference` vs. a non-blocking warning

### 2. Path Resolution Improvements for References

2.1 **Use structure-aware path resolution**

- Adjust roadmap reference validation to:
  - Resolve `plans/...` or `../plans/...` using the plans path from `get_structure_info()` / `CortexResourceType.PLANS`
  - Avoid hardcoding `.cortex/` or assuming everything lives under the project root

2.2 **Support safe aliases**

- Define a small, well-documented set of allowed reference patterns for Phase plans (e.g., ``../plans/phase-21-health-check-optimization.md``).
- Ensure those patterns resolve to actual files via structure-aware resolution.

2.3 **Keep TODO tracking behavior unchanged**

- Maintain existing semantics for:
  - TODO discovery in production code
  - Requirements that each production TODO is represented somewhere in `roadmap.md`

### 3. MCP Response Enrichment for `roadmap_sync`

3.1 **Expose detailed invalid reference information**

- Ensure the `roadmap_sync` MCP result includes, for each invalid reference:
  - Normalized `file_path`
  - Phase/section context
  - A short description of why it is invalid (missing file, out-of-range line, unresolved alias, etc.)

3.2 **Add human-readable summary hints**

- Extend the `summary` block with:
  - A small set of example messages like:
    - “Invalid reference `plans/phase-21-health-check-optimization.md` (no matching file under plans directory)”
    - “Reference `src/module.py:500` exceeds file length (320 lines)”
  - Clear guidance that agents can surface directly in commit reports.

3.3 **Document error interpretation**

- Update validation-related docs (and, if needed, Synapse agent prompts) to:
  - Explain how to read `missing_roadmap_entries` vs. `invalid_references`
  - Clarify that plan links may be checked via the new structure-aware resolution rules.

### 4. Tests & Validation

4.1 **Add unit tests for path resolution**

- Add focused tests for the roadmap sync utilities to cover:
  - `../plans/...` and `plans/...` references resolving correctly to `.cortex/plans/...`
  - Nonexistent plan files producing clear invalid reference entries
  - Mixed cases where some references are valid and others invalid.

4.2 **Add tests for enriched MCP responses**

- Extend tests for the `validate(check_type=\"roadmap_sync\")` tool handler to assert:
  - Presence of detailed `invalid_references` entries
  - Presence and shape of enriched `summary` information
  - Backwards compatibility of top-level fields (`status`, `check_type`, `valid`).

4.3 **Integration checks in commit pipeline**

- Add/extend tests that simulate a `/cortex/commit` run with:
  - Valid Phase plan references (ensuring the pipeline passes)
  - Intentionally broken references, verifying:
    - The commit is correctly blocked
    - The error messages are clear and actionable.

### 5. Memory Bank & Roadmap Alignment

5.1 **Review existing roadmap and progress entries**

- Audit `roadmap.md`, `activeContext.md`, and `progress.md` for:
  - References to plan files
  - Coverage- and adapter-related bullets mentioning specific files
  - Any remaining ambiguous paths that might confuse the validator.

5.2 **Adjust references where needed**

- Align Phase plan references with the new, structure-aware rules:
  - Ensure all Phase plan links use the supported patterns
  - Preserve useful context in bullet text while keeping file paths validator-friendly.

5.3 **Validate end-to-end**

- Run `validate(check_type=\"roadmap_sync\")` and confirm:
  - `valid` is `true` for the updated content (or that remaining issues are intentional and clearly described)
  - `invalid_references_count` is zero for well-formed Phase plan references.

## Dependencies

- Existing `validate` MCP tool and roadmap sync utility modules
- Path resolution utilities and structure info tooling
- Current commit pipeline and Synapse agents for validation and roadmap updates

## Testing Strategy (MANDATORY, ≥95% Coverage for New Code)

- **Coverage Target**: Achieve at least 95% coverage for all new or modified roadmap sync and validation-related code.
- **Unit Tests**:
  - Cover new path resolution helpers and alias handling for `plans/` and `../plans/`.
  - Cover enriched `roadmap_sync` response building, including edge cases (no invalid references, multiple invalid references).
  - Verify error summaries are stable and parseable for downstream tools.
- **Integration Tests**:
  - Simulate validation runs (`validate(check_type=\"roadmap_sync\")`) with realistic `roadmap.md` and plan layouts.
  - Ensure commit-oriented workflows see clear, actionable diagnostics.
- **Edge Cases**:
  - Missing plan files
  - Mixed valid/invalid references
  - Very large roadmaps with many references (performance sanity checks).
- **Regression Tests**:
  - Lock in current correct behaviors for TODO tracking and non-plan references.
  - Ensure no regressions in other validation types (`schema`, `timestamps`, `infrastructure`, etc.).

## Risks & Mitigations

- **Risk**: Changing path resolution could unexpectedly reclassify existing references.
  - **Mitigation**: Introduce changes behind well-tested helpers, add clear tests for legacy patterns, and validate against current Memory Bank content.
- **Risk**: Enriched error messages might be overlong or hard to parse.
  - **Mitigation**: Keep summaries concise and structured; validate with tests that assert JSON shape and length boundaries where needed.
- **Risk**: Confusion between plan links as documentation vs. hard requirements.
  - **Mitigation**: Clearly document which references are enforced and which are informational, and encode that distinction in tests and docs.

## Timeline (Rough)

- **Day 1**: Requirements clarification, behavior documentation, and design for path resolution changes.
- **Day 2**: Implement path resolution improvements and enriched `roadmap_sync` responses.
- **Day 3**: Add unit/integration tests, adjust Memory Bank references as needed, and validate end-to-end.

## Notes

- This plan is scoped specifically to roadmap synchronization and validation UX; broader Health-Check/Phase 21 work should reference this plan where applicable but will be tracked separately.
