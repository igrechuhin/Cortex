# Progress Log

## 2026-04-02

- **Synapse prompt filenames (Do / Plan)** - COMPLETE. Renamed Synapse prompts to `do.md`/`plan.md` and updated prompts manifest plus all repo/test/docs references.

## 2026-04-01

- **Swift quality gate — multi-slice plans and roadmap** - COMPLETE. Historical PARTIAL ledger row resolved as closed documentation history; no remaining implementation backlog is required.
- **Structured Final Reports for Cortex Synapse Prompts** - COMPLETE. Historical PARTIAL ledger row resolved as closed documentation history; no remaining implementation backlog is required.
- **Phase: Investigate validate_impl MCP Tool Failure** - COMPLETE. Removed stale roadmap blocker entry for an already resolved plan and verified quality gate passes.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding (follow-up)** - PARTIAL. Added script-availability gating in file language dispatch so only languages with required Synapse size/function scripts are routed, plus regression tests for unsupported-language skip behavior.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding (follow-up)** - PARTIAL. Added migration-level scaffolding warnings for non-native language script stubs, extended MigrationReport with scaffolding_warnings, and added unit tests for warning behavior in scaffolding and structure migration flows.
- **Analyze Feedback Loop: Post-Prompt Self-Improvement** - PARTIAL. Auto-injected post-prompt hook guidance into prompt loading flow with recursion-safe exclusions (`analyze.md`, `post-prompt-hook.md`) and deduplication; added targeted tests and passed quality gate.
- **Analyze Feedback Loop: Post-Prompt Self-Improvement** - COMPLETE. Confirmed end-to-end hook coverage for caller prompts (Synapse + project), router presence in analyze flow, manifest registration, and recursion-safety guards via structural tests.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding (follow-up)** - COMPLETE. Added C# migration language-pack reconciliation (detection markers, csharp rule template source, docs marker list, and tests) and validated with passing quality/docs gates.

## 2026-03-31

- **Migration: Language-Agnostic Rules and Scripts Scaffolding (follow-up)** - PARTIAL. Added first-class `csharp` language-pack scaffolding hints (`dotnet build`/`dotnet test`) in `language_scripts_scaffolding` and expanded unit coverage; roadmap item remains open for additional language-pack/template reconciliation.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding (follow-up)** - PARTIAL. Extended extension-to-language routing map for scaffolded non-native languages (.java/.kt/.kts/.cs/.go/.rs/.ts/.tsx/.js/.jsx) and aligned router tests; quality gate fresh passed (5805/5805, 91.86% coverage).
- **Migration: Language-Agnostic Rules and Scripts Scaffolding (follow-up)** - PARTIAL. Implemented C# language detection path by integrating `CSharpAdapter` into framework detection and adding C# adapter/detection tests; quality gate remains blocked by pre-existing repository-wide quality/type/test failures outside this subtask.

## 2026-03-30

- **[QG-S1] Add EXTENSION_SCRIPT_MAP** - COMPLETE. Added EXTENSION_SCRIPT_MAP to constants.py with .py and .swift entries; quality gate passed.
- **[QG-S2] Create file_language_router module** - COMPLETE. New module with route_files, collect_project_files, run_quality_checks_for_all_languages, parsers, tests; quality gate passed.
- **[QG-S3] Wire router into execute_quality()** - COMPLETE. Quality check uses file_language_router for all languages; gate passed.
- **[QG-S4] Swift check_file_sizes FILES env** - COMPLETE. Added `FILES` env var dispatcher mode to check exactly provided Swift files; fallback now scans `Sources/` and (if present) `Tests/`; removed `Tests/` exclusion from generated-file filtering.
- **[QG-S5] Swift check_function_lengths FILES env** - COMPLETE. Support `FILES` env-var dispatcher mode for `check_function_lengths.py` and include `Tests/` in the fallback scan (removed path-based `Tests` exclusion); added unit tests for the FILES behavior.
- **[QG-S6] python synapse scripts FILES env** - COMPLETE. Added `FILES` dispatcher mode parity to Python size/length scripts with unit tests.
- **[QG-S7] Unit tests for file_language_router** - COMPLETE. Added a comprehensive unit test suite for `file_language_router` (routing, project file collection, violation parsing, mocked per-language script dispatch) plus an `execute_quality()` regression guard.
- **[QG-S8] Integration tests + validation** - COMPLETE. Added integration tests that invoke real Synapse scripts via FILES env (Swift/Python routing, mixed-language, unknown extension skip, clean pass, Swift function-length) and validated via cache-cleared quality gate run.
- **QG follow-up: incremental quality routing + full-scan fallback semantics** - COMPLETE. Updated `execute_quality()` to dispatch file/function checks over git-delta files when available, but fall back to full-project scans when git is unavailable or the tree is clean (avoids a false-green gate by skipping size/length checks). Updated router dispatch assertions to `files=None` in the no-git case.

## 2026-03-29

- **MCP startup: Synapse sync uses ff-only pull in submodule** - COMPLETE. Replaced superproject `git submodule update --init --recursive` with `git pull --ff-only origin main` inside `.cortex/synapse`; logging, lazy prompt registration comment, and unit tests updated; AGENTS/troubleshooting aligned.
- **project_root_resolver.py: handle roots/list_changed** - COMPLETE. Wired `notifications/roots/list_changed` to clear the cached MCP root (`handle_roots_list_changed`); registered on `mcp._mcp_server.notification_handlers`; tests in `test_project_root_resolver.py`.
- **Fix pipeline: submodule-only commit carve-out** - COMPLETE. Added explicit carve-out when submodule_hygiene blocks run_quality_gate: submodule commit allowed, superproject not; cross-references in Goals, routing, and failure handling.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. Extended `detect_languages_for_migration` with Gradle Kotlin DSL JVM markers (`build.gradle.kts`, `settings.gradle.kts`) so Java rule/script scaffolding runs for typical Kotlin/JVM Gradle roots; added unit tests; documented markers in `docs/prompts/migrate.md` Step 2b. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_jvm_migration_markers` now treats root `settings.gradle` (Groovy) as a JVM/Gradle marker so Java rule/script scaffolding runs without `build.gradle` at repo root; unit test and `docs/prompts/migrate.md` Step 2b marker list updated. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_jvm_migration_markers` now treats root `gradlew` and `gradlew.bat` as JVM/Gradle markers so Java rule/script scaffolding runs when only the wrapper is present; unit tests and `docs/prompts/migrate.md` Step 2b marker list updated. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_jvm_migration_markers` now treats root `mvnw` and `mvnw.cmd` as JVM/Maven markers so Java rule/script scaffolding runs when only the Maven wrapper is present; unit tests and `docs/prompts/migrate.md` Step 2b marker list updated. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_jvm_migration_markers` now treats root `.mvn/wrapper/maven-wrapper.properties` as a JVM/Maven marker; unit test and `docs/prompts/migrate.md` Step 2b marker list updated. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_jvm_migration_markers` now treats root `gradle/wrapper/gradle-wrapper.properties` as a JVM/Gradle marker; unit test and `docs/prompts/migrate.md` Step 2b updated. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_python_sources` now treats root `requirements.txt` and `Pipfile` as Python markers; module docstring and `docs/prompts/migrate.md` Step 2b updated; two unit tests. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_python_sources` now treats root `setup.cfg` as a Python/setuptools marker; module docstring and `docs/prompts/migrate.md` Step 2b updated; unit test added. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_python_sources` now treats root `tox.ini` as a Python marker; module docstring and `docs/prompts/migrate.md` Step 2b updated; unit test added. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_python_sources` now treats root `Pipfile.lock` and `poetry.lock` as Python markers; `docs/prompts/migrate.md` Step 2b and two unit tests updated. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_python_sources` now treats root `uv.lock` as a Python marker; module docstring and `docs/prompts/migrate.md` Step 2b updated; unit test added. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_python_sources` now treats root `environment.yml` and `environment.yaml` as Python (Conda) markers; module docstring, `docs/prompts/migrate.md` Step 2b, and two unit tests updated. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_python_sources` now treats root `conda-lock.yml` and `.python-version` as Python markers; module docstring, `docs/prompts/migrate.md` Step 2b, and two unit tests updated. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_python_sources` now treats root `MANIFEST.in` and `constraints.txt` as Python markers; module docstring, `docs/prompts/migrate.md` Step 2b, and two unit tests updated. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_python_sources` now treats root `runtime.txt` (Heroku) and `.flake8` as Python markers; module docstring, `docs/prompts/migrate.md` Step 2b, and two unit tests updated. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Phase: Investigate session_start MCP Tool Failure** - COMPLETE. Session brief payload capping, JSON validation on session_start, defensive quick_start parsing.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_python_sources` now treats root `pytest.ini` and `.coveragerc` as Python markers; module docstring, `docs/prompts/migrate.md` Step 2b, and two unit tests updated. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_python_sources` now treats root `pyrightconfig.json`, `mypy.ini`, `.mypy.ini`, `ruff.toml`, `.ruff.toml`, and `noxfile.py` as Python markers; module docstring, `docs/prompts/migrate.md` Step 2b, and parametrized unit tests (6 cases) updated. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. `_has_python_sources` now treats root `pdm.toml`, `pdm.lock`, and `pixi.toml` as Python markers; module docstring and `docs/prompts/migrate.md` Step 2b updated; three parametrized test cases added. Remaining: optional TradeWing template reconciliation and any further language packs.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - COMPLETE (2026-03-29). Extended `scaffold_language_scripts` to emit `README.md` + `run_quality_check.sh` stubs for all non-Python/Swift languages (java, go, rust, typescript, javascript) under `.cortex/synapse/scripts/<lang>/`. Added 29-test suite `tests/unit/test_language_scripts_scaffolding.py` covering all 5 languages, native-skip, idempotency, unknown-language fallback, executable bit, and return-value shape. All quality gates pass.
- **Fix pipeline: surface rules-resource disabled warning** - COMPLETE. fix.md: disabled vs failure branches; ⚠️ in Next; `rules.enabled` path.
- **Debug external integration prompt: stale index state** - COMPLETE. Split Step 4 stable vs dynamic sections; conditional index repair in Notes.
- **Synapse fix.md: NO-GO Cursor command stubs** - COMPLETE. NO-GO bullet and routing when `.cursor/commands` has no `*.md`; submodule commit with rules-disabled branching updates.
- **Swift quality gate — multi-slice plans and roadmap** - PARTIAL. Umbrella plan archived; QG-S1–QG-S8 slice plans added with markdown lint fixes; roadmap Blockers and index/history updated; Synapse gitlink staged. Remaining: implement slices per plans (start with QG-S1).

## 2026-03-28

- **Structured final-report types + Synapse prompts** - COMPLETE. Pipeline/Diagnostic/Artifact templates applied in Synapse; docs guide, integration test, and Claude implement-code agent updated; submodule commit and superproject gitlink in Cortex commit pipeline.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PARTIAL. Landed Synapse template stubs under rules/_templates for go/java/javascript/rust/typescript; generalized migration scaffolded_languages reporting and tests; committed via Cortex commit pipeline with updated submodule gitlink.
- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - COMPLETE. Migrate prompt Step 2b + JSON fields; quality gate routing documented and covered by resolve_adapter_worker tests.
- **Structured Final Reports for Cortex Synapse Prompts** - PARTIAL. Step 1 complete: prompt/command inventory table in docs/guides/REFACTORING_GUIDE.md appendix; plan Step 1 marked done. Remaining: Steps 2–5 (templates, Synapse apply, Cursor align, tests).

## What Works

Pre-commit pipeline (fix_errors, format, type_check, quality, tests); 3702 tests, 90.36% coverage; integration tests for projectBrief schema; Option C HTTP/SSE transport (Phase 1 and 2). Plan prompt and memory-bank-updater mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption.

## What's Left

See roadmap.md.
