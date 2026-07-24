# Naming Conventions for Tools, Resources, and Prompts

**Status**: Step 2 deliverable (plan: unify-simplify-tools-prompts-resources-naming)  
**Created**: 2026-02-27

## Purpose

Define a unified naming rubric for Cortex MCP **tools**, **`cortex://` resources**, and **Synapse prompts** so that names are consistent, predictable, and easy to discover.

## 1. Tools

### 1.1 Verb patterns

- **Imperative verbs for side effects**: `manage_file`, `apply_refactoring`, `configure`, `fix_markdown_lint`, `append_entry`
- **`query_*` for read-only consolidated dispatchers**: `query_memory_bank`, `query_usage` — when a tool aggregates multiple read operations, use `query_*`
- **`get_*`**: Reserved for read-only tools when no consolidated `query_*` alternative exists. Prefer `query_*` for new consolidated reads. Do **not** use `get_*` for mutating operations.

### 1.2 Naming rules

| Rule | Example |
|------|---------|
| snake_case | manage_file, query_memory_bank |
| Verb-first for actions | autofix, run_quality_gate |
| Noun for dispatchers (when established) | plan, roadmap, rules — acceptable for consolidated dispatchers with operation parameter |
| No get_* for writes | ❌ get_file (if it wrote); ✓ manage_file |

### 1.3 Tool description (altitude rubric)

All tool descriptions must conform to [tool-description-altitude-rubric.md](../guides/tool-description-altitude-rubric.md):

- **Score ≥ 4** (required): Purpose, USE WHEN, input expectations, RETURNS
- **Score 5** (target for 20+ tools): Add Examples or `input_examples`

## 2. Resources (`cortex://` URIs)

### 2.1 Structure

```text
cortex://{domain}/{path}
```

- **Domain**: Lowercase, hyphenated (e.g. `memory-bank`, `optimization`, `usage`)
- **Path**: Hyphenated segments; use nouns (e.g. `stats`, `load-context`, `version-history`)

### 2.2 Domain alignment

Domains align with tool categories and functionality:

| Domain | Purpose |
|--------|---------|
| memory-bank | File content, stats, version history, dependency graph |
| optimization | Context loading, relevance scores, summarization |
| usage | Usage stats, reports, recommendations, observations |
| links | Parse, validate, graph, transclusions |
| structure | Project structure info, health |
| project | Project root |
| analysis | Analyze targets, suggest refactoring |
| synapse | Rules, prompts |
| validation | Run validation by check type |
| health | Connection health, analysis |
| scripts | Script capture list, analyze, suggest improvements |
| config | Configuration components |

### 2.3 Path rules

- **Hyphenation**: Path segments use hyphens: `load-context`, `suggest-refactoring`, `optimization-recommendations`
- **Singular vs plural**: Use nouns that match the resource content; prefer singular for singleton resources (e.g. `stats`, `info`), plural where appropriate (e.g. `prompts`)
- **Parameters**: Use `{param}` in path for parameterized resources: `cortex://memory-bank/file/{file_name}`

## 3. Prompts

### 3.1 Filenames

- **Format**: `kebab-case.md` (e.g. `plan.md`, `fix-quality.md`)
- **Slug**: Filename without `.md`; used as the MCP client's command suffix

### 3.2 MCP client commands

- **Pattern**: `user-cortex/{slug}` (the convention several MCP-aware clients use to
  namespace a server's prompts as invokable commands)
- **Mapping**: Slug matches prompt filename (e.g. `commit.md` → `user-cortex/commit`)
- **Exception**: Long filenames may map to shorter slugs (e.g. `do.md` → `user-cortex/do`)

### 3.3 Verb-first

Action prompts use verb-first names: `commit`, `do`, `analyze`, `fix-tests`, `plan`, `docs-sync`

## 4. Examples

### Tools

| Pattern | Example |
|---------|---------|
| manage_* | manage_file |
| query_* | query_memory_bank, query_usage |
| fix_* | autofix, fix_markdown_lint |
| append_* | append_entry |
| execute_* | Legacy pre-commit helpers (prefer run_quality_gate zero-arg) |

### Resources

| URI | Purpose |
|-----|---------|
| cortex://memory-bank/stats | Memory bank statistics |
| cortex://optimization/load-context/{task} | Load context for task |
| cortex://usage/report | Usage report |
| cortex://structure/info | Project structure info |

### Prompts

| File | Command |
|------|---------|
| commit.md | user-cortex/commit |
| plan.md | user-cortex/plan |
| fix-quality.md | user-cortex/fix-quality |

## 5. Proposals (Steps 3–5)

### 5.1 Tool naming proposals

| Tool | Proposal | Rationale | Migration |
|------|----------|-----------|-----------|
| get_structure_info | **Keep** (or future: query_structure) | Widely used; no consolidated query_structure. Rename would be breaking. | Defer to future phase; document as exception. |
| get_relevance_scores | **Keep** (or future: fold into load_context resource) | Used in context workflow; resource cortex://optimization/relevance-scores exists. | Low priority; document as get_* exception. |
| sequentialthinking | Consider `sequential_thinking` | snake_case consistency. | Breaking; requires client updates. Defer. |
| think | **Keep** | Short, established. | — |

**Altitude rubric**: For each tool, ensure description includes Purpose, USE WHEN, input expectations, RETURNS. Add Examples for 20+ high-use tools (manage_file, load_context, query_memory_bank, rules, run_quality_gate, get_structure_info, session_start, plan, roadmap, etc.).

**Consolidation candidates** (from tool-optimization plans): No additional renames recommended this cycle. Plan/roadmap already consolidated.

### 5.2 Resource URI proposals

| Current | Proposal | Rationale |
|---------|----------|-----------|
| cortex://rules/relevant/{task} | **Deprecate** in favor of cortex://synapse/rules/{task} | Overlap with synapse/rules; consolidate to synapse domain. |
| cortex://synapse/rules/{task} | **Canonical** | Primary rules resource. |

**Backward compatibility**: If cortex://rules/relevant is deprecated, add redirect or document migration; clients should prefer cortex://synapse/rules.

### 5.3 Prompt naming proposals

| Current | Proposal | Rationale |
|---------|----------|-----------|
| do.md | **Keep** filename; document slug=do | Slug matches filename; mapping is intentional. |
| fix-quality vs fix_quality | Document mapping | An MCP client command may use fix_quality; prompt file is fix-quality.md. Ensure docs clarify. |

No prompt renames recommended; current mapping is acceptable.

## 6. References

- [Tool description altitude rubric](../guides/tool-description-altitude-rubric.md) — **MANDATORY** for tool descriptions
- [Naming inventory](naming-inventory-2026-02.md) — Current state and inconsistencies
- [Tools API](../api/tools.md) — Tools vs resources semantics
- [Tool optimization mapping](tool-optimization-mapping.md)
- Plan: [unify-simplify-tools-prompts-resources-naming](../../.cortex/plans/archive/Other/unify-simplify-tools-prompts-resources-naming.md)
