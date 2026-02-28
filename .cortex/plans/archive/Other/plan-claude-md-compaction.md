# Compact .claude/CLAUDE.md — Remove Synapse Rule Duplication

**Status**: PENDING
**Priority**: MEDIUM
**Created**: 2026-02-28
**Type**: Cleanup (DRY)
**Effort**: Medium (20 min)

## Goal

Reduce `.claude/CLAUDE.md` from 172 lines to ~120 lines by removing Python standards that duplicate Synapse rules, while keeping unique governance content.

## Context

`.claude/CLAUDE.md` contains ~80 lines of Python standards (lines 88-137) that duplicate content from Synapse rules:

| .claude/CLAUDE.md Section | Synapse Rule |
|--------------------------|--------------|
| Type Safety (90-96) | `python-coding-standards.mdc` |
| Pydantic 2 (98-103) | `python-pydantic-standards.mdc` |
| Async Patterns (105-110) | `python-async-patterns.mdc` |
| Code Organization (112-118) | `python-coding-standards.mdc` |
| Module Visibility (120-124) | `python-coding-standards.mdc` |
| Testing (126-131) | `python-testing-standards.mdc` |
| Formatting (133-137) | `python-coding-standards.mdc` |
| MCP Development (139-144) | `python-mcp-development.mdc` |

Root `CLAUDE.md` already says "do not duplicate — always fetch from Cortex MCP."

## Approach

Replace detailed sections with a compact summary + Synapse reference. Keep unique sections (Identity, Core Workflow, Execution Continuity, Quality Assessment, Violations).

## Implementation Steps

1. **Identify unique content** in `.claude/CLAUDE.md` that must be preserved:
   - Identity, Input Hierarchy, Core Workflow, Agent Operating Guidelines
   - Execution Continuity, Quality Assessment, MCP Tool Error Handling
   - Date & Time, Language, Violations
2. **Replace Python Standards section** (lines 88-137) with compact summary:

   ```markdown
   ## Python Standards

   Loaded from Synapse rules. Key constraints:
   - No `Any` type; 100% type hints; Pydantic 2 mandatory
   - Functions <=30 lines; files <=400 lines
   - AAA test pattern; 90%+ coverage
   - Black (88 cols); async-first I/O

   See `get_synapse_rules(task_description="python standards")` for full details.
   ```

3. **Replace MCP Development section** (lines 139-144) with compact summary
4. **Update Violations section** to reference Synapse rules for details
5. **Verify** file is under 120 lines and all unique governance content is preserved

## Dependencies

None.

## Success Criteria

- `.claude/CLAUDE.md` < 120 lines
- No content lost (all details available via Synapse rules)
- Violations section still lists all blocked behaviors
- Unique governance content preserved

## Testing Strategy

- **Coverage Target**: N/A (docs-only change)
- **Verification**: Line count check; review all violations still listed
- **Regression**: No code changes

## Risks & Mitigation

- **Risk**: Claude Code agents lose Python standards without Cortex MCP → **Mitigation**: Keep key constraints inline as brief summary

## Timeline

Single session (20 min).
