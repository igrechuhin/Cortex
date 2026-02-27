# Plan: Unify and Simplify Tools, Prompts, and Resources Naming

**Status**: PENDING  
**Priority**: P2 (medium)  
**Estimated Effort**: 12–18 hours

## Goal

Unify and simplify naming conventions across Cortex MCP **tools**, **prompts**, and **resources** so that names are consistent, predictable, and easy to discover. Reduce cognitive load for agents and documentation maintenance.

## Context

### Current State

- **Tools**: Mix of patterns—`manage_file`, `query_memory_bank`, `query_usage`, `add_roadmap_entry`, `create_plan`, `get_structure_info`. Phase 43 addressed tools vs resources and `get_*` read-only semantics; Phase 50 consolidated into `query_*`; tool-optimization mapping documents keep/deprecate decisions.
- **Resources**: `cortex://` URIs—`cortex://memory-bank/stats`, `cortex://optimization/load-context/{task}`, `cortex://usage/report`, `cortex://synapse/rules/{task}`, etc. Domains: memory-bank, optimization, usage, links, structure, health, analysis, config, scripts, synapse, validation, project. Paths use hyphen (load-context) or none (stats).
- **Prompts**: Synapse prompts `implement-next-roadmap-step.md`, `create-plan.md`, `analyze.md`, `commit.md`, `review.md`, `fix-tests.md`, `fix-quality.md`, `docs-sync.md`. Cursor commands map via `user-cortex/<slug>` (e.g. `user-cortex/commit` → commit.md).
- **Naming friction**: Inconsistent verb forms, singular vs plural in resource paths, mixed hyphenation, overlapping concepts (rules vs synapse/rules), and prompt slugs that don’t always match command intent.

### Business Value

- **Discoverability**: Predictable names make it easier for agents and users to find the right tool, resource, or prompt.
- **Documentation**: Single rubric reduces doc drift and clarifies when to use tools vs resources.
- **Maintainability**: Consistent patterns simplify onboarding and future consolidation (e.g. plan/roadmap tools).

### References

- [Tools vs Resources naming](docs/api/tools.md) — Phase 43 conventions
- [Tool optimization mapping](docs/architecture/tool-optimization-mapping.md)
- [Tool optimization baseline](docs/architecture/tool-optimization-baseline.md)
- [Phase 43 plan](.cortex/plans/archive/Phase43/phase-43-reconsider-tools-registration.md)
- [Tool description altitude rubric](docs/guides/tool-description-altitude-rubric.md) — **MANDATORY** for tool descriptions

## Approach

1. **Audit**: Catalog current names for tools, resource URIs, and prompts; identify inconsistencies.
2. **Define rubric**: Single naming rubric for tools, resources, and prompts with clear rules.
3. **Respect altitude rubric**: All tool descriptions (including new/renamed tools) must conform to [tool-description-altitude-rubric.md](docs/guides/tool-description-altitude-rubric.md): Purpose, When to use (USE WHEN), Input expectations, Output format (RETURNS), and optionally Examples for score 5. Target: ≥4 for all tools; 20+ tools at score 5.
4. **Simplify**: Propose renames or consolidation where patterns conflict; prioritize high-impact, low-risk changes.
5. **Document**: Update tools.md, Phase 43 follow-up, and a new naming-conventions guide.
6. **Implement incrementally**: Apply renames in small batches with backward compatibility where needed.

## Implementation Steps

**Implementation sequence**: Execute in order (Step 1 → 2 → … → 8).

### Step 1: Audit current naming

- **Tools**: List all registered tools; categorize by pattern (verb_noun, query_*, manage_*, etc.). Note overlap with resources. For each tool, audit description against [tool-description-altitude-rubric.md](docs/guides/tool-description-altitude-rubric.md) (Purpose, USE WHEN, input/output expectations; flag tools below score 4).
- **Resources**: List all `cortex://` URIs; extract domain + path patterns. Check hyphenation and singular/plural.
- **Prompts**: List Synapse prompts and Cursor command slugs; map prompt filename → command slug.
- **Deliverable**: Markdown inventory (`docs/architecture/naming-inventory-YYYY-MM.md`) with tables, inconsistencies, and altitude-rubric gaps flagged.

### Step 2: Define naming rubric

- **Tools**:
  - Imperative verbs for side effects: `manage_file`, `apply_refactoring`, `configure`
  - `query_*` for read-only consolidated dispatchers: `query_memory_bank`, `query_usage`
  - No `get_*` for mutating operations; `get_*` only for read-only when no consolidated alternative
  - Cross-reference [tool-description-altitude-rubric.md](docs/guides/tool-description-altitude-rubric.md) for description quality (Purpose, USE WHEN, input/output, Examples)
- **Resources**:
  - `cortex://{domain}/{path}` — domain lowercase, hyphenated; path segments hyphenated; use nouns (stats, report, load-context)
  - Align domain with tool category (memory-bank, optimization, usage, links, structure, health, analysis, config, scripts, synapse, validation, project)
- **Prompts**:
  - Filename: `kebab-case.md`; slug = filename without .md
  - Command: `user-cortex/{slug}`; slug matches prompt filename
  - Verb-first for action prompts (commit, implement, analyze, fix-tests)
- **Deliverable**: `docs/architecture/naming-conventions.md` with rubric, examples, and link to the altitude rubric.

### Step 3: Propose tool naming changes

- Apply rubric to tools; list recommended renames (e.g. any remaining `get_*` that should become `query_*` or resource-only).
- Flag tools that duplicate resource functionality; recommend deprecation path.
- Consider consolidation candidates from tool-optimization plans (plan, roadmap) — naming should support merged tools.
- Include altitude-rubric improvements: for each proposed rename, specify description updates (Purpose, USE WHEN, RETURNS, Examples) so score ≥4.
- **Deliverable**: Section in naming-conventions.md or plan addendum with tool rename proposals, description updates, and migration notes.

### Step 4: Propose resource URI changes

- Apply rubric to resource URIs; list recommended path changes (e.g. singular vs plural, hyphenation).
- Resolve overlaps (e.g. `cortex://rules/relevant/{task}` vs `cortex://synapse/rules/{task}`).
- Document backward compatibility: old URIs deprecated vs breaking.
- **Deliverable**: Resource URI proposal table with old → new mapping.

### Step 5: Propose prompt naming changes

- Apply rubric to prompts; ensure slug matches intent and Cursor command.
- Resolve any duplicates (e.g. archive/analyze-session-optimization vs analyze.md).
- **Deliverable**: Prompt rename proposal table if any changes; update create-plan/implement prompts if command-to-file mapping changes.

### Step 6: Update documentation

- Update `docs/api/tools.md` with references to naming-conventions.md.
- Update AGENTS.md, CLAUDE.md, memory-bank-workflow.mdc with naming guidance where relevant.
- Add naming-conventions.md to docs index.
- **Deliverable**: Docs updated; links valid.

### Step 7: Implement high-impact, low-risk renames

- Implement only renames that (a) don’t break existing clients, or (b) have a clear deprecation path.
- Prefer documentation-first: publish rubric and proposals before code changes.
- If tool/resource renames require code: add aliases for old names where feasible; update tool_categories, MCP registration.
- **Altitude rubric compliance**: For any new or renamed tool, ensure its description meets [tool-description-altitude-rubric.md](docs/guides/tool-description-altitude-rubric.md) (score ≥4): Purpose, USE WHEN, input expectations, RETURNS; add Examples where feasible for score 5.
- **Deliverable**: Renames applied; descriptions compliant; tests updated; tool-optimization and Phase 43 docs refreshed.

### Step 8: Validate and record

- Run `execute_pre_commit_checks(phase="A")`; run `validate(check_type="roadmap_sync")` if roadmap references change.
- Update activeContext, progress, roadmap.
- **Deliverable**: Regression passed; memory bank updated.

## Testing Strategy

- **Coverage target**: 95% for any new validation logic or rename helpers.
- **Regression**: Full pre-commit suite; verify tool discovery, resource resolution, and prompt resolution.
- **Documentation**: Verify all links in naming-conventions.md and tools.md.
- **Backward compatibility**: If aliases added, test both old and new names resolve correctly.

## Success Criteria

- **Naming rubric**: Single source of truth in `docs/architecture/naming-conventions.md`.
- **Altitude rubric respected**: Tool descriptions (new/renamed) conform to [tool-description-altitude-rubric.md](docs/guides/tool-description-altitude-rubric.md): score ≥4; 20+ tools with examples (score 5) where feasible.
- **Inventory**: Current state documented with inconsistencies and altitude gaps flagged.
- **Proposals**: Clear rename/consolidation proposals for tools, resources, prompts.
- **Low-risk renames**: Applied where safe; higher-risk changes documented for future phases.
- **Docs updated**: tools.md, AGENTS.md, and related docs reference both rubrics.

## Risks & Mitigation

- **Breaking changes**: Renaming tools/resources can break clients. Mitigation: prefer deprecation + alias; document migration path.
- **Scope creep**: Full rename of all URIs may be large. Mitigation: phase high-impact changes first; defer cosmetic fixes.
- **Prompt mapping**: Cursor command → file mapping may be fixed by client. Mitigation: document current mapping; propose changes only if Cortex controls it.
