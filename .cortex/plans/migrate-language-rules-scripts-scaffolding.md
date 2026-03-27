---
title: "Migration Prompt: Language-Agnostic Rules and Scripts Scaffolding"
component: migration
work_type: enhancement
status: IN_PROGRESS
priority: high
created: 2026-03-26
depends_on: []
---

## Migration Prompt: Language-Agnostic Rules and Scripts Scaffolding

## Goal

Extend the `migrate` prompt (and the underlying migration flow) so that when a project is
migrated into `.cortex/`, it automatically detects the project's primary language(s) and
scaffolds the correct Synapse **rules** (`.cortex/synapse/rules/<lang>/`) and **scripts**
(`.cortex/synapse/scripts/<lang>/`) for that language — without manual copy-paste.

The current migration flow handles memory bank, plans, symlinks, and legacy path rewrites.
It does NOT scaffold language-specific content. For TradeWing (Swift), 8 rule files and
a scripts directory had to be created manually after migration. For any new non-Python
project this problem will recur.

## Context

### What was done manually for TradeWing

1. **Rules**: 8 `.mdc` files created under `.cortex/synapse/rules/swift/`:
   `swift-coding-standards`, `swift-style`, `swift-concurrency`, `swift-reliability`,
   `swift-observability`, `swift-testing`, `swift-performance`, `swift-protobuf`.
2. **Scripts**: Only Python scripts exist under `.cortex/synapse/scripts/python/` (copied
   from Cortex synapse). No Swift-native scripts exist yet — the Python analysis scripts
   don't apply to Swift source.

### Cortex infrastructure already available

- `LanguageDetector` + `LanguageInfo` in `src/cortex/services/language_detector.py` —
  detects language from file extensions and project markers.
- `SwiftAdapter`, `JavaScriptAdapter`, `JavaAdapter` in
  `src/cortex/services/framework_adapters/` — language-specific quality gate runners.
- `cortex://rules` resource reads from `.cortex/synapse/rules/` and merges `general/` +
  `<detected-lang>/` subfolders.
- Synapse submodule at `.cortex/synapse/` is the source of truth for rules/scripts;
  `.cortex/synapse/rules/general/` contains language-agnostic rules shared by all projects.

### The gap

The Synapse submodule ships only `general/` and `python/` rules and scripts out of the
box (because Cortex itself is a Python project). Language-specific content for Swift,
JavaScript, TypeScript, Java, Rust, Go etc. must be scaffolded into the **project's own**
`.cortex/synapse/rules/<lang>/` tree — these are project-local overrides, not part of the
shared submodule.

The migration prompt (`docs/prompts/migrate.md`) describes 7 migration steps but says
nothing about language detection or rules/scripts scaffolding.

## Implementation Steps

### Step 1: Language detection during migration

In the migration flow (prompt and/or `setup/` Python code), after Step 2
(initialize `.cortex/` structure), call `LanguageDetector` on the project root to
determine primary language(s).

Detection priority:

1. `Package.swift` → `swift`
2. `package.json` / `tsconfig.json` → `javascript` / `typescript`
3. `pom.xml` / `build.gradle` → `java`
4. `Cargo.toml` → `rust`
5. `go.mod` → `go`
6. `*.py` files dominant → `python` (already handled)
7. Multiple detected → scaffold all detected languages

The result must be stored as `detected_languages: list[str]` and surfaced to the user for
confirmation before scaffolding.

### Step 2: Language rule template library in Synapse

Create a template library at `.cortex/synapse/rules/_templates/<lang>/` inside the Synapse
submodule (i.e. in the `Cortex` repo under `.cortex/synapse/rules/_templates/`).

Each `<lang>/` folder contains starter `.mdc` rule files with:

- Standard structure (frontmatter with `alwaysApply: true`, title, enforcement note)
- Language-specific sections drawn from known best practices
- Placeholder TODOs for project-specific overrides

**Languages to add templates for** (based on adapter coverage):

- `swift/` — 8 files matching what was manually created for TradeWing
- `typescript/` — type safety, ESLint, async patterns, testing (Jest/Vitest)
- `javascript/` — same minus type rules
- `java/` — style (Google Java), Spring patterns, testing (JUnit)
- `rust/` — ownership, error handling, clippy standards, async (tokio)
- `go/` — effective Go, error wrapping, goroutine patterns

### Step 3: Scripts scaffolding per language

For each detected language, determine if language-native quality scripts are available.
Python scripts under `scripts/python/` do NOT apply to Swift, Rust, Go etc.

For languages without native scripts:

1. Create a stub `scripts/<lang>/README.md` explaining what scripts should be added
2. Create a stub `scripts/<lang>/run_quality_check.sh` that invokes the language's native
   toolchain (e.g. `swift build && swift test` for Swift, `cargo clippy && cargo test` for
   Rust)
3. Emit a migration warning: "No native quality scripts found for <lang>. Stub created at
   `.cortex/synapse/scripts/<lang>/run_quality_check.sh` — customize for your toolchain."

For Python projects: no change — scripts already exist and are fully functional.

### Step 4: Update `run_quality_gate` to route by language

`run_quality_gate()` currently runs Python quality scripts unconditionally. It should:

1. Call `detect_language_at_path(project_root)` to determine primary language
2. If `python`: run existing Python scripts (no change)
3. If `swift`: delegate to `SwiftAdapter` (already implemented; ensure it is wired into
   `run_quality_gate`)
4. If other language: run `scripts/<lang>/run_quality_check.sh` if present, else warn
5. Always run `general/` checks (markdown lint, memory bank validation) regardless of language

The routing logic lives in `src/cortex/tools/quality_gate.py` (or equivalent). Keep it
under 30 lines by delegating to `LanguageQualityRouter` (new class, one public method).

### Step 5: Update the `migrate` prompt

Update `docs/prompts/migrate.md` to document the new scaffolding step:

#### New Step 2b: Detect language and scaffold rules/scripts

```text
After `.cortex/` structure is initialized:
1. Detect primary language(s) from project markers
2. Confirm detected languages with user
3. Copy rule templates from `.cortex/synapse/rules/_templates/<lang>/` to
   `.cortex/synapse/rules/<lang>/`
4. Create scripts stub at `.cortex/synapse/scripts/<lang>/` if no native scripts exist
5. Report scaffolded files in migration output JSON
```

Add the scaffolding output to the migration JSON schema:

```json
"scaffolded_languages": ["swift"],
"rules_scaffolded": ["swift-coding-standards.mdc", "swift-style.mdc", ...],
"scripts_scaffolded": ["run_quality_check.sh"]
```

### Step 6: Backfill TradeWing

After the template library exists, verify TradeWing's manually-created Swift rules match
the templates. Apply any improvements from the templates back into TradeWing's rules.
This is a one-time reconciliation, not ongoing.

### Step 7: Tests

1. Unit test `LanguageQualityRouter` with mock adapters for each language branch
2. Integration test: create a temp directory with `Package.swift`, run migration flow,
   assert Swift rule files and script stub are created
3. Test that `run_quality_gate()` on a Swift project calls `SwiftAdapter` and not Python
   scripts
4. Test multi-language detection: project with both `Package.swift` and Python `setup.py`
   scaffolds both

Coverage target: 95%.

## Verification Checklist

| Check | What to search for | Scope |
|---|---|---|
| Language detection called in migration | `detect_language` in migration code path | `src/cortex/setup/` |
| Template library present | `_templates/swift/*.mdc` exists | `.cortex/synapse/rules/_templates/` |
| Quality gate routes by language | `LanguageQualityRouter` or equivalent | `src/cortex/tools/` |
| Migrate prompt documents Step 2b | "Detect language" section | `docs/prompts/migrate.md` |
| TradeWing rules match templates | diff between TradeWing rules and templates | manual review |
| Tests pass | `run_quality_gate()` on mock Swift project | `tests/` |

## Dependencies

- `src/cortex/services/language_detector.py` — must remain stable
- `src/cortex/services/framework_adapters/swift_adapter.py` — must be wired to quality gate
- Synapse submodule must accept the `_templates/` directory (no `.gitignore` exclusion)

## Progress Update (2026-03-27)

### Completed in this session

- Added `detect_languages_for_migration(project_root: Path) -> list[str]` in
  `src/cortex/setup/migration_language_detection.py`.
- Implemented deterministic multi-language detection order:
  `swift -> typescript/javascript -> java -> rust -> go -> python`.
- Added `tests/unit/test_migration_language_detection.py` with 5 tests covering
  no markers, multi-language ordering, and JS/TS precedence.

### Remaining

- Wire the new helper into migration flow and prompt output.
- Scaffold language rule/templates/scripts based on detected languages.
- Route `run_quality_gate` through language-aware dispatch for non-Python projects.

## Success Criteria

1. Running the `migrate` prompt on a Swift project automatically creates
   `.cortex/synapse/rules/swift/*.mdc` and `.cortex/synapse/scripts/swift/run_quality_check.sh`
   without any manual steps.
2. Running `run_quality_gate()` on a Swift project runs `swift build` + `swift test`
   (via `SwiftAdapter`) instead of Python scripts.
3. The same flow works generically for any language with a registered adapter or shell stub.
4. TradeWing's existing Swift rules are reconciled with the generated templates.
5. All new code passes `run_quality_gate()` (Python quality gate on the Cortex source).

## Testing Strategy

- AAA pattern throughout; 95%+ coverage on new code paths
- Mock `LanguageDetector` in migration unit tests (no real filesystem dependency)
- Integration test uses `tmp_path` fixture (pytest) with minimal project markers
- `SwiftAdapter` routing tested with a mock that asserts correct command invocation
