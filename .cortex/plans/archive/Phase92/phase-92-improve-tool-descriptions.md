# Phase 92: Improve MCP Tool Descriptions and Usage Guidance

Status: DONE

Completed (2026-03-06): Standardized Tier 1 MCP tool descriptions with a consistent USE WHEN / DO NOT / EXAMPLES template, added governance coverage so tools steer agents toward canonical entrypoints, and verified quality gate + full tests.

## Goal

Make MCP tool descriptions, examples, and usage docs strong enough that agents naturally choose the correct, structured entrypoints (e.g. `manage_file`, `update_memory_bank`, `execute_pre_commit_checks`) and avoid anti-patterns like raw file edits to the memory bank or ad-hoc test commands.

## Context

- Some tools are powerful but underspecified, which leads agents to misuse them (for example, treating `manage_file` as a generic file API instead of a memory-bank-only helper, or calling `execute_pre_commit_checks` without required parameters).
- There are overlapping tool surfaces (e.g. direct memory-bank edits vs higher-level helpers like `update_memory_bank`) where the intended “happy path” is not obvious from the description alone.
- Governance tests (such as tool analyzer and categories tests) ensure registration and budget, but they do not yet enforce that descriptions clearly encode when/why/how to use each tool.

## Approach

- Inventory current MCP tool descriptions, arguments, and examples, focusing on high-impact tools (memory bank, pre-commit, analyze/session, structure, query_usage/query_memory_bank).
- Define a concise, standardized template for tool descriptions that encodes:
  - **USE WHEN** (primary scenarios),
  - **DO NOT** (common anti-patterns),
  - **EXAMPLES** (canonical calls),
  - and any **Safety/constraints** (e.g. “memory bank only”, “read-only”, “no project_root arg”).
- Update the most important tools first (phased rollout), then extend the pattern across the rest of the surface.
- Add or extend governance tests to ensure new/updated tools follow the template and include clear guidance on expected vs discouraged usage.

## Implementation Steps

1. **Tool inventory and prioritization**
   - Use existing health-check / tool-analyzer helpers to list all registered MCP tools and identify:
     - High-frequency tools (usage stats where available),
     - High-risk tools (memory bank, commit/quality, analyze, structure, query_usage/query_memory_bank),
     - Deprecated or internalized tools that should not be promoted.
   - Produce a short ranked list of “Tier 1” tools whose descriptions must be improved in this phase.

2. **Design a description template and rubric**
   - Draft a small, language-agnostic template for tool descriptions that includes:
     - `USE WHEN:` 1–3 bullet points,
     - `DO NOT:` 1–3 concrete anti-patterns,
     - `EXAMPLES:` 2–3 representative calls (including parameters),
     - Optional **Notes** for constraints (e.g., no `project_root` param).
   - Align the template with existing documentation (AGENTS, commit/implement prompts, memory-bank workflow, tools-optimization docs) so guidance is consistent.
   - Capture the rubric in Synapse rules for tools so future additions must meet the standard.

3. **Apply the template to Tier 1 tools**
   - Update descriptions for:
     - `manage_file` (emphasize memory-bank-only usage, required parameters, and common mistakes),
     - `update_memory_bank` (clearly position as the preferred way to mutate roadmap/progress/activeContext),
     - `execute_pre_commit_checks` (document phase vs checks usage and required arguments),
     - `check_mcp_connection_health` / structure tools (`get_structure_info`, `check_structure_health`),
     - `query_memory_bank`, `query_usage`, and composite tools that wrap multiple operations.
   - Ensure each description explicitly steers agents toward expected usage (e.g., “Do not call this for generic file I/O; use standard editor tools instead”).

4. **Extend improvements to remaining tools**
   - Sweep the rest of the MCP tool surface, applying the same template.
   - Normalize terminology (e.g., “memory bank”, “plans directory”, “roadmap entry”) and cross-reference canonical docs where helpful.
   - Mark internal-only or legacy tools explicitly and, where appropriate, discourage direct use in favor of consolidated replacements.

5. **Governance and tests**
   - Extend or add tests (e.g., in tool analyzer / governance modules) to verify:
     - Every registered tool has a non-empty description that mentions **USE WHEN** and, when applicable, **DO NOT** or “Preferred over …”.
     - High-risk tools include at least one explicit anti-pattern callout.
     - Any deprecated or internal tools are labeled as such in their description.
   - Wire these checks into the existing quality gate so description regressions are caught before merge.

6. **Documentation and examples**
   - Update developer-facing docs (tools reference, getting-started, commit/implement prompts where appropriate) to:
     - Highlight the canonical tools and their intended usage,
     - Provide end-to-end examples that show the correct sequence (e.g., `manage_file` + `update_memory_bank` for roadmap edits, `execute_pre_commit_checks` for tests).
   - Ensure docs and tool descriptions stay in sync via a brief “How to add a new tool” checklist.

## Verification Checklist

- [ ] Search for common anti-pattern phrases (e.g. “generic file I/O”, “project_root parameter”) in tool descriptions and confirm they have been replaced or clarified with the new template.
- [ ] Confirm that Tier 1 tools (`manage_file`, `update_memory_bank`, `execute_pre_commit_checks`, structure and query tools) all include:
  - A clear **USE WHEN** section,
  - At least one explicit **DO NOT** / anti-pattern,
  - At least two concrete usage examples.
- [ ] Run tool governance/tests to verify all registered tools meet the updated description rubric, with zero violations.
- [ ] Manually review a small sample of recent agent sessions (where available) to confirm that the updated descriptions are steering usage toward the preferred patterns.

## Testing Strategy

- Add or extend unit/integration tests around:
  - Tool analyzer / governance logic that inspects registered tools and validates description fields against the new template.
  - Any helper functions used to build or render tool descriptions.
- Ensure the existing pre-commit pipeline (format, type_check, quality, tests, markdown lint) passes with:
  - 100% test pass rate,
  - Global coverage ≥ 90%,
  - No new file-size/function-length violations in updated modules.
- Where tools are demonstrated in documentation examples, add or update tests that exercise the same patterns (e.g., a test that verifies `update_memory_bank` is used to add a roadmap entry, not raw `manage_file` writes).

## Risks & Mitigations

- **Risk**: Overly verbose descriptions could increase cognitive load.
  - **Mitigation**: Keep descriptions concise, prioritize USE WHEN/DO NOT, and push longer narratives into docs.
- **Risk**: Inconsistent updates could confuse agents (mixed old/new patterns).
  - **Mitigation**: Start with Tier 1 tools, then sweep the full surface in a single follow-up pass; enforce via governance tests.
- **Risk**: Tests may become brittle if tied too tightly to exact wording.
  - **Mitigation**: Validate presence of required sections and key phrases rather than exact full strings.

## Timeline

- **Day 1–2**: Inventory tools, design description template, and align with existing docs/prompts.
- **Day 3–4**: Apply template to Tier 1 tools and wire governance tests.
- **Day 5+**: Sweep remaining tools, refine docs/examples, and adjust based on early usage feedback.
