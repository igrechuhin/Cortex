# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-03-29)

- **MCP startup: Synapse sync uses ff-only pull in submodule** - COMPLETE (2026-03-29) - `synapse_submodule_startup` runs `git pull --ff-only origin main` inside `.cortex/synapse` instead of `git submodule update --init --recursive` from the superproject; stash/pop behavior unchanged when the submodule has local changes; unit tests and log messages updated; AGENTS and troubleshooting docs aligned.

- ✅ **project_root_resolver.py: handle roots/list_changed** - COMPLETE (2026-03-29) - Registered low-level MCP notification handler for RootsListChangedNotification; added handle_roots_list_changed() to clear cached root; unit tests for clear, noop, and re-resolve.

- ✅ **Fix pipeline: submodule-only commit carve-out** - COMPLETE (2026-03-29) - Documented submodule-only commit exception in Synapse fix.md (Goals, Submodule-First authority, Failure Handling for submodule_hygiene); verified with fix_quality_issues, run_docs_gate, and run_quality_gate.

- ✅ **Migration scaffolding — Gradle Kotlin DSL markers** - COMPLETE (2026-03-29) - JVM migration detection now treats `build.gradle.kts` and `settings.gradle.kts` like other Gradle/Maven markers so `_templates/java/` scaffolding applies without a Groovy `build.gradle` at the root.

- ✅ **Migration scaffolding — Groovy settings.gradle JVM marker (PARTIAL)** - COMPLETE (2026-03-29) - detect_languages_for_migration includes root `settings.gradle` for JVM scaffolding; migrate.md documents `settings.gradle` / `settings.gradle.kts`; new unit test. Roadmap migration item remains until optional TradeWing reconciliation or broader language-pack work.

- ✅ **Migration scaffolding (PARTIAL)** - COMPLETE (2026-03-29) - Gradle wrapper files at repo root (`gradlew`, `gradlew.bat`) are JVM migration markers; migrate.md Step 2b documents them.

- ✅ **Migration scaffolding — Maven wrapper JVM markers (PARTIAL)** - COMPLETE (2026-03-29) - Java migration detection includes `mvnw` / `mvnw.cmd` at repo root; tests and migrate.md Step 2b updated. Roadmap item kept until optional TradeWing/further packs work is done or reconciled.

- ✅ **Migration scaffolding — Maven wrapper properties JVM marker (PARTIAL)** - COMPLETE (2026-03-29) - Java migration detection includes `.mvn/wrapper/maven-wrapper.properties`; test and migrate.md Step 2b updated. Roadmap item unchanged until optional TradeWing/further packs work is reconciled.

- ✅ **Migration scaffolding — Gradle wrapper properties JVM marker (PARTIAL)** - COMPLETE (2026-03-29) - Java migration detection includes `gradle/wrapper/gradle-wrapper.properties`; test and migrate.md Step 2b updated. Roadmap migration bullet unchanged.

- ✅ **Migration scaffolding — requirements.txt / Pipfile Python markers (PARTIAL)** - COMPLETE (2026-03-29) - `detect_languages_for_migration` detects Python from `requirements.txt` or `Pipfile` at repo root; docs and tests updated. Roadmap migration bullet unchanged.

- ✅ **Migration scaffolding — setup.cfg Python marker (PARTIAL)** - COMPLETE (2026-03-29) - `detect_languages_for_migration` detects Python from `setup.cfg` at repo root; docs and test updated. Roadmap migration bullet unchanged.

- ✅ **Migration scaffolding — tox.ini Python marker (PARTIAL)** - COMPLETE (2026-03-29) - `detect_languages_for_migration` detects Python from `tox.ini` at repo root; docs and test updated. Roadmap migration bullet unchanged.

- ✅ **Migration scaffolding — Pipfile.lock / poetry.lock Python markers (PARTIAL)** - COMPLETE (2026-03-29) - `detect_languages_for_migration` includes root `Pipfile.lock` and `poetry.lock`; migrate.md Step 2b and unit tests updated. Roadmap migration bullet unchanged until optional TradeWing/further packs work.

- ✅ **Migration scaffolding — uv.lock Python marker (PARTIAL)** - COMPLETE (2026-03-29) - `detect_languages_for_migration` detects Python from root `uv.lock`; migrate.md Step 2b and `test_migration_language_detection` updated. Roadmap migration bullet unchanged until optional TradeWing/further packs work.

- ✅ **Migration scaffolding — conda-lock / pyenv markers** - COMPLETE (2026-03-29) - `detect_languages_for_migration` recognizes `conda-lock.yml` and `.python-version` at repo root for Python rule/script scaffolding.

- ✅ **Migration scaffolding — MANIFEST.in / constraints.txt** - COMPLETE (2026-03-29) - `detect_languages_for_migration` treats setuptools `MANIFEST.in` and pip `constraints.txt` at repo root as Python signals for rule/script scaffolding.

- ✅ **Migration scaffolding — Heroku runtime / flake8** - COMPLETE (2026-03-29) - Migration language detection treats root `runtime.txt` and `.flake8` as Python markers; tests and migrate prompt updated.

- ✅ **Phase: Investigate session_start MCP Tool Failure** - COMPLETE (2026-03-29) - Capped long strings in session brief (concurrent task, focus, etc.); JSON round-trip validation on session_start return; quick_start handles invalid session/load_context JSON with error_response; tests added.

- ✅ **Migration scaffolding — pytest / coverage markers** - COMPLETE (2026-03-29) - `detect_languages_for_migration` recognizes root `pytest.ini` and `.coveragerc` for Python rule/script scaffolding.

- ✅ **Migration scaffolding — Python tooling markers (PARTIAL)** - COMPLETE (2026-03-29) - Migration language detection now recognizes Pyright, mypy, Ruff, and Nox root files for Python scaffolding; docs and tests aligned.

- ✅ **Migration scaffolding — PDM/Pixi markers (PARTIAL)** - COMPLETE (2026-03-29) - Migration language detection recognizes PDM and Pixi root manifests for Python scaffolding.

- ✅ **Migration: Language-Agnostic Rules and Scripts Scaffolding** - COMPLETE (2026-03-29) - `scaffold_language_scripts` now creates `README.md` + `run_quality_check.sh` stubs for java, go, rust, typescript, and javascript under `.cortex/synapse/scripts/<lang>/`. Python and Swift skipped (have native scripts). Unknown languages get a generic TODO stub. Stubs are idempotent. 29 tests in `tests/unit/test_language_scripts_scaffolding.py`. Roadmap PENDING item resolved.

- ✅ **Fix pipeline: surface rules-resource disabled warning** - COMPLETE (2026-03-29) - Updated `.cortex/synapse/prompts/fix.md`: Pre-Action Checklist distinguishes `cortex://rules` status `disabled` vs connection failure; agents record a ⚠️ warning for the final report Next section with accurate `rules.enabled` knob in `.cortex/config/optimization.json`. Final report Rules reference the Next placement.

- ✅ **Debug external integration prompt: stale index state** - COMPLETE (2026-03-29) - Step 4 splits stable structural facts from dynamic index state; Glob-driven presence checks for index.corrupted and index.json; Notes index repair is conditional on Glob output.

- ✅ **Synapse fix.md: NO-GO Cursor command stubs** - COMPLETE (2026-03-29) - Documented policy against adding tracked `.cursor/commands/*.md` to satisfy tests or the gate; routes final-report alignment failures to test/prompt fixes; submodule commit `docs: clarify fix prompt for rules-disabled and cursor command stubs`.

- ✅ **Swift quality gate — plans and roadmap (QG-S1–S8)** - COMPLETE (2026-03-29) - Archived umbrella plan `swift-quality-gate-support.v1` to `.cortex/plans/archive/`; added eight slice plans (`swift-qg-s1` … `swift-qg-s8`) under `.cortex/plans/` with rumdl-clean markdown; registered Blockers in roadmap with plan links; updated `.cortex/index.json` and history snapshots; staged superproject Synapse gitlink to match checked-out submodule.

## Completed Work (2026-03-28)

- **Summary (2026-03-28)** - 1 entries archived.

## Completed Work (2026-03-27)

- **Summary (2026-03-27)** - 1 entries archived.

## Completed Work (2026-03-26)

- **Summary (2026-03-26)** - 1 entries archived.

## Completed Work (2026-03-25)

- **Summary (2026-03-25)** - 1 entries archived.

## Completed Work (2026-03-24)

- **Summary (2026-03-24)** - 1 entries archived.

## Completed Work (2026-03-23)

- **Summary (2026-03-23)** - 1 entries archived.

## Completed Work (2026-03-22)

- **Summary (2026-03-22)** - 1 entries archived.

## Completed Work (2026-03-21)

- **Summary (2026-03-21)** - 1 entries archived.

## Completed Work (2026-03-20)

- **Summary (2026-03-20)** - 1 entries archived.

## Completed Work (2026-03-16)

- **Summary (2026-03-16)** - 1 entries archived.

## Completed Work (2026-03-14)

- **Summary (2026-03-14)** - 1 entries archived.

## Completed Work (2026-03-13)

- **Summary (2026-03-13)** - 1 entries archived.

## Completed Work (2026-03-12)

- **Summary (2026-03-12)** - 1 entries archived.

## Completed Work (2026-03-11)

- **Summary (2026-03-11)** - 1 entries archived.

## Completed Work (2026-03-10)

- **Summary (2026-03-10)** - 1 entries archived.

## Completed Work (2026-03-09)

- **Summary (2026-03-09)** - 1 entries archived.

## Completed Work (2026-03-08)

- **Summary (2026-03-08)** - 1 entries archived.

## Completed Work (2026-03-07)

- **Summary (2026-03-07)** - 1 entries archived.

## Completed Work (2026-03-06)

- **Summary (2026-03-06)** - 1 entries archived.

## Completed Work (2026-03-05)

- **Summary (2026-03-05)** - 1 entries archived.

## Completed Work (2026-03-04)

- **Summary (2026-03-04)** - 1 entries archived.

## Completed Work (2026-03-03)

- **Summary (2026-03-03)** - 1 entries archived.

## Completed Work (2026-03-02)

- **Summary (2026-03-02)** - 1 entries archived.

## Completed Work (2026-03-01)

- **Summary (2026-03-01)** - 1 entries archived.

## Completed Work (2026-02-28)

- **Summary (2026-02-28)** - 1 entries archived.

## Completed Work (2026-02-27)

- **Summary (2026-02-27)** - 1 entries archived.

## Completed Work (2026-02-26)

- **Summary (2026-02-26)** - 1 entries archived.

## Completed Work (2026-02-25)

- **Summary (2026-02-25)** - 1 entries archived.

## Completed Work (2026-02-24)

- **Summary (2026-02-24)** - 1 entries archived.

## Completed Work (2026-02-23)

- **Summary (2026-02-23)** - 1 entries archived.

## Completed Work (2026-02-22)

- **Summary (2026-02-22)** - 1 entries archived.

## Completed Work (2026-02-21)

- **Summary (2026-02-21)** - 1 entries archived.

## Completed Work (2026-02-20)

- **Summary (2026-02-20)** - 1 entries archived.

## Completed Work (2026-02-19)

- **Summary (2026-02-19)** - 1 entries archived.

## Completed Work (2026-02-18)

- **Summary (2026-02-18)** - 1 entries archived.

## Completed Work (2026-02-17)

- **Summary (2026-02-17)** - 1 entries archived.

## Completed Work (2026-02-16)

- **Summary (2026-02-16)** - 1 entries archived.

## Completed Work (2026-02-13)

- **Summary (2026-02-13)** - 1 entries archived.

## Completed Work (2026-01-14)

- **Summary (2026-01-14)** - 1 entries archived.

## Completed Work (2026-02-12)

- **Summary (2026-02-12)** - 1 entries archived.

## Completed Work (2026-02-11)

- **Summary (2026-02-11)** - 1 entries archived.

## Completed Work (2026-02-10)

- **Summary (2026-02-10)** - 1 entries archived.

## Completed Work (2026-02-09)

- **Summary (2026-02-09)** - 1 entries archived.

## Completed Work (2026-02-07)

- **Summary (2026-02-07)** - 1 entries archived.

## Current Focus

Next implementation slice: **[QG-S1] Add EXTENSION_SCRIPT_MAP** per [roadmap.md](roadmap.md) Blockers and `.cortex/plans/swift-qg-s1-add-extension-script-map.plan.md`.

## Recent Changes

Synapse sync timing (2026-03-28): submodule update runs when lazy prompts first register, after `resolve_project_root_async`, aligning sync with MCP roots (not only process CWD).

MCP startup Synapse sync (2026-03-29): dirty submodule worktrees are stashed around `git pull --ff-only origin main` inside `.cortex/synapse` (replacing superproject `git submodule update --init --recursive`); structured outcomes cover stash/push/pop edge cases; see AGENTS.md and `docs/guides/troubleshooting.md` MCP preflight.

Submodule hygiene for commits (2026-03-20): `pre_commit_submodule_guard` blocks Phase A when a submodule worktree is dirty or the gitlink is out of sync; covered by `test_pre_commit_submodule_guard.py` and pre-commit tool fixture patches.

Blocker (2026-02-09): create-plan and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
