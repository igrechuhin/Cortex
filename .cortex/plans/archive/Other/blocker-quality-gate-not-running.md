# Blocker: GitHub Actions Quality Gate Not Running

Status: PENDING

## Goal

Restore the GitHub Actions "Code Quality" workflow so that the Cortex repository runs its full quality gate (format, type_check, quality, tests, markdown lint, coverage) on every relevant branch/PR again.

## Context

- The GitHub Actions page for `igrechuhin/Cortex` shows many recent successful runs of the "Code Quality" workflow, but the user reports that the **quality gate "doesn't run anymore"**.
- Recent work has significantly evolved the commit pipeline and MCP tools (e.g., `execute_pre_commit_checks`, `check_mcp_connection_health`, `plan`, `manage_file`), and there have been multiple phases tuning connection stability and CI parity.
- It is possible that quality gate behavior diverged between local MCP-driven checks and the GitHub Actions workflow (for example, workflow disabled, filtered to specific branches/paths, or failing early without visible status).
- This plan treats the situation as a **blocker**: CI must reliably enforce the same gates as `/cortex/commit`.

## Approach

1. **Confirm current GitHub Actions configuration and behavior**
2. **Diff workflow and scripts against expected commit pipeline behavior**
3. **Align quality gate steps with MCP-based pre-commit checks**
4. **Add targeted diagnostics and guardrails to prevent silent skipping**
5. **Verify end-to-end via synthetic changes and document expectations**

## Implementation Steps

1. **Inventory GitHub Actions workflows and history for Quality gate**
   - Open `.github/workflows/` and identify the workflow(s) responsible for the Code Quality gate (e.g., `code-quality.yml`, `ci.yml`, or split workflows).
   - From the GitHub Actions UI, verify:
     - Whether the Quality workflow is still enabled.
     - Which events trigger it (push, pull_request, workflow_dispatch, schedules) and what branches/paths are included or excluded.
     - Whether there are recent runs on `main` and on feature branches; note any gaps relative to expected activity.
   - Capture the current workflow name, file, and triggers as baseline.

2. **Analyze when and why the Quality gate might skip**
   - Review the workflow YAML for conditional execution (`if:` clauses, `paths`, `paths-ignore`, `branches`, `branches-ignore`).
   - Identify any conditions that could cause the job to **not run** or to exit early without a clear failure (e.g., early matrix conditions, `continue-on-error`, or only-on-label filters).
   - Compare these conditions with recent commit patterns (branches, PR types) to hypothesize why the user perceives "doesn't run anymore" (e.g., only runs on `main`, but work is currently on a long-lived feature branch).
   - Document all discovered conditions and suspected causes in a short internal note or review file.

3. **Align workflow steps with `/cortex/commit` quality gate expectations**
   - Cross-check the workflow steps against the documented commit pipeline (Phase A + Step 12), especially:
     - `uv sync --extra dev` or equivalent environment setup.
     - `execute_pre_commit_checks(phase="A")` usage (if any) vs. direct language-specific tools.
     - Formatting (Black), linting (Ruff/markdownlint-cli2), type checking (Pyright), tests with coverage (pytest/coverage), and quality/file-size/function-length checks.
   - Identify any drift: missing checks, incorrect thresholds (e.g., coverage < 90%), or outdated scripts.
   - Propose a minimal, CI-safe set of steps that mirrors the MCP-based pipeline (e.g., a single script that shells out to `uv run cortex` with a `run_composite_workflow` or `execute_pre_commit_checks` wrapper if available).

4. **Diagnose and fix specific reasons the Quality gate is not running**
   - Based on Steps 1–3, categorize the root cause into one or more of:
     - **Trigger misconfiguration** (e.g., events/branches/paths filters too narrow).
     - **Workflow disabled or required checks misaligned** (e.g., branch protection expects a different check name).
     - **Hidden or early-exit failures** (e.g., dependency installation failure, misconfigured Python/uv, or MCP startup failure that stops later steps).
   - Update the workflow YAML and/or repository settings to ensure:
     - The Code Quality workflow runs on all relevant branches (at least `main` and active feature branches/PRs).
     - Required checks in branch protection match the actual job name(s).
     - Early failures are visible (no inappropriate `continue-on-error`).
   - Where changes are risky, stage them as a separate PR and document the behavior change in the PR description.

5. **Harden the CI environment parity with local MCP pipeline**
   - Verify that CI uses the same Python/uv versions and dependencies as the documented local workflow (see `AGENTS.md`, `CLAUDE.md`, and the bootstrap script).
   - Ensure the Synapse submodule is initialized or that the CI path uses the same submodule-guard behavior as `/cortex/commit`.
   - Confirm that environment variables, secrets, and caching (e.g., pip/uv caches) do not interfere with running the MCP-based checks.
   - Add explicit logging around MCP connection and pre-commit tool invocations so that CI logs clearly show whether checks ran or were skipped.

6. **Add targeted safety rails against silent quality gate regression**
   - Where practical, introduce a small guard script or `execute_pre_commit_checks`-based step that:
     - Fails if the quality step is skipped or if critical checks (format, type_check, quality, tests, markdown lint) are not executed.
     - Optionally records a summary of which checks ran and their result into a CI artifact for future debugging.
   - Add or update tests that validate the CI configuration, for example:
     - A test that inspects `.github/workflows/` to ensure the expected quality job names and steps exist.
     - A doc or governance check that keeps workflow and commit-pipeline docs in sync.

7. **Verify end-to-end and document the restored behavior**
   - Create a small synthetic change that should obviously trigger the Quality gate (e.g., trivial doc change and/or a controlled formatting violation) on a test branch.
   - Open a PR or push directly (depending on workflow) and confirm that:
     - The Code Quality workflow runs as expected.
     - Failures are visible and block merges when quality thresholds are not met.
     - Successful runs show all expected checks.
   - Update relevant docs (e.g., `docs/guides/git-operations.md`, CI section in README, or commit/implement prompts) to describe:
     - When the quality gate runs.
     - Which checks it enforces.
     - How it relates to the `/cortex/commit` pipeline.

## Testing Strategy

- Add or update tests to ensure CI and `/cortex/commit` stay aligned:
  - **Workflow config tests**: A test that loads `.github/workflows/*` and asserts that the Code Quality job exists, is enabled for `main` and PRs, and contains the expected key steps (environment setup, quality gate script or `execute_pre_commit_checks`).
  - **Governance tests**: Extend existing governance or tool-analyzer tests to ensure that CI configuration is kept in sync with documented commit pipeline requirements (e.g., coverage threshold \\u2265 90%, zero-errors tolerance for lint/type/quality).
  - **MCP/CI parity tests**: Where possible, add an integration test that exercises the same `execute_pre_commit_checks` configuration used in CI, verifying that all checks can run successfully in a controlled environment.
- Ensure that after changes:
  - The full pre-commit suite passes locally (format, type_check, quality, tests, markdown lint, coverage \\u2265 90%).
  - GitHub Actions runs the Code Quality workflow on representative branches/PRs and reports status correctly.

## Risks & Mitigations

- **Risk**: Changing workflow triggers could accidentally reduce coverage (e.g., only running on `main`).
  - **Mitigation**: Start with additive triggers (include both `push` and `pull_request` on relevant branches) and validate on test branches before merging.
- **Risk**: CI environment differences (Python/uv versions, missing Synapse submodule) could cause new failures.
  - **Mitigation**: Align CI bootstrap with the documented local bootstrap script and Synapse guard; handle failures explicitly in logs.
- **Risk**: Overly strict checks might slow down feedback or cause frequent false positives.
  - **Mitigation**: Keep the workflow focused on the existing zero-errors policy and 90% coverage threshold already enforced locally; avoid adding unrelated checks in this plan.

## Timeline

- **Day 1**: Inventory workflows, triggers, and recent runs; analyze skipping conditions; draft proposed changes.
- **Day 2**: Implement workflow updates and parity alignment, add diagnostics and safety rails.
- **Day 3**: Verify end-to-end on test branches/PRs, refine based on results, and land documentation updates.
