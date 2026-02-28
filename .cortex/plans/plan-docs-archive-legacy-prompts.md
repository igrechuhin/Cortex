# Archive Legacy Prompt Docs

**Status**: PENDING
**Priority**: HIGH
**Created**: 2026-02-28
**Type**: Cleanup (DRY)
**Effort**: Small (15 min)

## Goal

Archive 7 legacy prompt documentation files in `docs/prompts/` that have been superseded by 3 unified prompts, eliminating DRY violation and user confusion.

## Context

`docs/prompts/README.md` states prompts were "simplified from 7 prompts to 3 unified prompts" but all 7 legacy files still exist alongside the 3 new ones:

**Legacy (to archive)**: `check-migration-status.md`, `initialize-memory-bank.md`, `migrate-memory-bank.md`, `migrate-project-structure.md`, `setup-cursor-integration.md`, `setup-project-structure.md`, `setup-shared-rules.md`

**Current (keep)**: `initialize.md`, `migrate.md`, `setup-synapse.md`

## Approach

Move legacy files to `docs/prompts/archive/`, add deprecation notice, update README.

## Implementation Steps

1. **Create archive directory**: `mkdir -p docs/prompts/archive`
2. **Move 7 legacy files** to `docs/prompts/archive/`
3. **Add deprecation header** to each archived file:

   ```markdown
   > **DEPRECATED**: This prompt has been unified. See [initialize.md](../initialize.md), [migrate.md](../migrate.md), or [setup-synapse.md](../setup-synapse.md).
   ```

4. **Update `docs/prompts/README.md`**: Remove references to legacy prompts, note archive location
5. **Check for broken links**: `grep -rn "check-migration-status\|initialize-memory-bank\|migrate-memory-bank\|migrate-project-structure\|setup-cursor-integration\|setup-project-structure\|setup-shared-rules" docs/`
6. **Fix any broken links** to point to archive location or unified replacements

## Dependencies

None.

## Success Criteria

- `docs/prompts/` contains only: `README.md`, `initialize.md`, `migrate.md`, `setup-synapse.md`, `archive/`
- All archived files have deprecation notice
- No broken links in docs

## Testing Strategy

- **Coverage Target**: N/A (docs-only change)
- **Verification**: Link validation via grep; visual inspection of docs/prompts/ listing
- **Regression**: No code changes

## Risks & Mitigation

- **Risk**: External links to old docs break → **Mitigation**: Files still exist in archive subdirectory

## Timeline

Single session (15 min).
