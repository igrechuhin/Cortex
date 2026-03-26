---
title: "Per-Project Post-Edit Quality Hook — Language-Agnostic Pattern"
component: ci
work_type: improvement
status: IN_PROGRESS
priority: high
created: 2026-03-26
depends_on: [migrate-language-rules-scripts-scaffolding]
---

## Per-Project Post-Edit Quality Hook — Language-Agnostic Pattern

## Goal

Define a language-agnostic pattern for per-project Claude Code hooks that auto-run the
project's quality checks after edits, and make Cortex surface this pattern automatically
during project setup/migration so every Cortex-enabled project gets it — not just the
Cortex repo itself.

## Context

Usage analytics showed 11 buggy-code incidents (circular imports, corrupted code,
TYPE_CHECKING violations) that a post-edit hook would have caught immediately. The
initial plan proposed hardcoding pytest + pyright into `.claude/settings.json` inside the
Cortex repo — but that only protects Cortex. Every Cortex-enabled project (TradeWing,
future projects) has the same problem with its own toolchain.

The correct approach: during `migrate` / `initialize`, detect the project language and
emit the appropriate hook command into the project's own `.claude/settings.json`.

Hook commands by language:

- **Python**: `python -m pytest tests/ --timeout=30 -x -q 2>&1 | tail -20`
- **Swift**: `swift build 2>&1 | tail -20`
- **TypeScript/JavaScript**: `npm test --if-present 2>&1 | tail -20`
- **Rust**: `cargo test 2>&1 | tail -20`
- **Go**: `go test ./... 2>&1 | tail -20`
- **Java**: `./mvnw test -q 2>&1 | tail -20` (or Gradle equivalent)
- **Fallback**: no hook emitted; migration warns the user to configure one manually

The hook is placed in the **project's** `.claude/settings.json`, not in Cortex's.

## Implementation Steps

### Step 1: Hook template library in Cortex

Create `src/cortex/setup/hook_templates.py` with a `HookTemplates` class:

- `get_post_edit_hook(language: str) -> str | None` — returns the shell command for the
  language, or `None` if unknown
- Covers: `python`, `swift`, `typescript`, `javascript`, `rust`, `go`, `java`
- One public method, under 30 lines, no `Any`, full type hints

### Step 2: Emit hook during migration / initialize

In the migration flow, after language detection (Step 1 of
`migrate-language-rules-scripts-scaffolding`):

1. Call `HookTemplates.get_post_edit_hook(detected_language)`
2. If a command is returned, write/merge into the project's `.claude/settings.json`:

   ```json
   {
     "hooks": {
       "PostToolUse": [
         {
           "matcher": "Edit",
           "hooks": [{"type": "command", "command": "<language-specific command>"}]
         }
       ]
     }
   }
   ```

3. If `.claude/settings.json` already exists, merge rather than overwrite (read → merge
   hooks array → write back)
4. If no template available, emit a migration warning:
   `"No post-edit hook template for <lang>. Add one to .claude/settings.json manually."`

### Step 3: Document the pattern in the migration prompt

Update `docs/prompts/migrate.md` to add a "Post-edit hook" sub-section under Step 2b
(language scaffolding):

- Explain what the hook does and why
- Show the emitted JSON for the detected language
- Explain how to customize the command

### Step 4: Apply to the Cortex repo itself

As a concrete first use of the new infrastructure, configure the hook in
`/Users/i.grechukhin/Repo/Cortex/.claude/settings.json` using the Python template.
This validates the implementation and closes the original Cortex-specific gap.

### Step 5: Tests

1. Unit test `HookTemplates.get_post_edit_hook` for all supported languages and the
   unknown-language fallback
2. Unit test the merge logic: existing `.claude/settings.json` with unrelated keys is
   preserved; duplicate hook entries are not added
3. Integration test: run migration on a temp Swift project dir, assert
   `.claude/settings.json` contains the `swift build` command
4. Integration test: run migration on a temp Python project dir, assert pytest command
   is present

Coverage target: 95%.

## Verification Checklist

| Check | What to search for | Scope |
|---|---|---|
| `HookTemplates` class exists | `class HookTemplates` | `src/cortex/setup/hook_templates.py` |
| Migration emits hook | `get_post_edit_hook` called in migration path | `src/cortex/setup/` |
| Merge logic present | read-merge-write pattern | same |
| `migrate.md` documents hook | "Post-edit hook" section | `docs/prompts/migrate.md` |
| Cortex repo hook configured | `PostToolUse` key | `.claude/settings.json` |
| Tests cover all languages | parametrized test over language list | `tests/` |

## Dependencies

- `migrate-language-rules-scripts-scaffolding` — language detection must run before hook
  emission; shares the same migration step
- `.claude/settings.json` schema must be stable (Claude Code hooks API)

## Success Criteria

1. Running `migrate` on any supported-language project creates a working post-edit hook in
   that project's `.claude/settings.json` — no manual configuration required.
2. Running `migrate` on an unsupported language emits a clear warning instead of silently
   skipping.
3. The Cortex repo itself has the hook configured and validated.
4. Merge logic never corrupts an existing `.claude/settings.json`.
5. All new code passes `run_quality_gate()`.

## Testing Strategy

- AAA pattern; 95%+ coverage on new code
- `HookTemplates` tested with parametrize over all language keys
- Merge logic tested with pre-populated and empty `.claude/settings.json` fixtures
- Integration tests use `tmp_path` (pytest) — no side effects on real project files

## Status (2026-03-26)

Done:

- Added `HookTemplates.get_post_edit_hook()` hook template library
- Added safe `.claude/settings.json` PostToolUse(Edit) merge/write utility + tests
- Wired hook emission step into `MIGRATE_PROMPT` (Step 2b) and `INITIALIZE_PROMPT` (Step 5b) in `prompts.py` with full language->command table and merge instructions
- Updated `docs/prompts/migrate.md` Step 2a to document auto-emitted hook with language table and merge behavior
- Added 14 integration tests in `tests/unit/test_post_edit_hook_integration.py` covering Python, Swift, all other languages, idempotency, and key preservation
- Cortex repo `.claude/settings.json` already had the Python hook configured
- Added programmatic hook-language detection helper (`detect_post_edit_hook_language`) and Java project detection (Maven/Gradle)

Remaining:

- Wire `migrate` / `initialize` runtime execution paths to call `detect_post_edit_hook_language(project_root)` and apply the post-edit hook automatically (not just prompt-instructed)
- Integrate with language detection from `migrate-language-rules-scripts-scaffolding` so detection is fully automated (future: call `LanguageQualityRouter` programmatically)
