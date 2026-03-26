# End-to-End Workflows

This guide documents common workflows as sequences of Cortex MCP tool calls, with example inputs/outputs, decision points, and error recovery.

## 1. New Project Setup Workflow

**Goal:** Initialize a project with Cortex, configure it, create the memory bank, and validate.

**Tool sequence:**

1. **session_start** (optional) – Get orientation and confirm MCP is healthy.

   ```json
   {"task_description": null}
   ```

   **Example output:** `mcp_healthy: true`, `current_focus`, `next_work_item`, `git_status`.

2. **initialize_memory_bank** – Create `.cortex/memory-bank/` and core files.

   **Parameters:** None (project root resolved internally).

   **Example output:** `status: "success"`, `files_created`, `total_files: 7`.

3. **configure** – Set validation, optimization, or other options if needed.

   **Parameters:** `updates` (object with config keys to merge).

4. **validate** – Check structure and content.

   **Parameters:** `check_type`: `"structure"` or `"schema"` or `"timestamps"` etc.

   **Example output:** `valid: true` or list of violations.

**Decision points:**

- If `session_start` returns `mcp_healthy: false`, stop and reconnect MCP.
- If `initialize_memory_bank` returns `already_initialized`, skip to configure/validate.
- If `validate` reports violations, fix via `manage_file` or config, then re-run validate.

**Error recovery:**

- Initialization failure: check path permissions and disk space; retry from project root.
- Validation failures: address reported files/sections, then re-validate.

---

## 2. Session Lifecycle Workflow

**Goal:** Start a session, load context, do work, optionally compact, and hand off.

**Tool sequence:**

1. **session_start** – Get brief and next work item.

   ```json
   {"task_description": "Implement feature X"}
   ```

   **Example output:** `next_work_item`, `next_work_plan_path`, `health`, `session_suggestions`.

2. **load_context** – Load memory bank content for the task.

   ```json
   {
     "task_description": "Implement feature X",
     "token_budget": 10000,
     "depth": "metadata_only"
   }
   ```

   **Example output:** `file_names`, `total_tokens`, optional section content. Then use **manage_file** with `sections=[...]` to drill into specific sections.

3. **Work** – Use **manage_file**, **rules**, **`run_quality_gate()`** (and related zero-arg quality tools), and other tools as needed.

4. **compact_session** (end of session) – Summarize progress and create handoff.

   **Parameters:** `summary` (optional). Writes handoff to `.cortex/.cache/session/last_handoff.json`.

5. Next session: **session_start** loads the handoff automatically for continuity.

**Decision points:**

- If `depth="metadata_only"`, follow with **manage_file**(`operation="read"`, `sections=[...]`) for full content where needed.
- If token budget is tight, use smaller `token_budget` or `strategy="progressive"`.

**Error recovery:**

- Connection closed during long **load_context**: retry once; reduce budget or scope if needed.
- Handoff missing: run **compact_session** again or proceed without handoff.

---

## 3. Code Quality Workflow

**Goal:** Run pre-commit checks, fix quality issues, validate, then commit.

**Tool sequence:**

1. **`run_quality_gate()`** – Zero-arg Phase A gate (fix_errors, format, type_check, quality, tests, markdown lint). Optional `test_timeout` / `coverage_threshold` come from the `pipeline_handoff` task file for `commit` / `checks`, not from JSON the client must forward.

   **Example output:** `preflight_passed`, `checks` with per-check success/failure.

2. If a check fails:
   - **`fix_quality_issues()`** for the bundled auto-fix pass, then re-run **`run_quality_gate()`**.
   - **fix_markdown_lint**(`include_untracked_markdown`: true) for markdown-only follow-ups.
   - Re-run **`run_quality_gate()`** until all pass.
   - Apply integrity NO-GO safeguards during fix loops:
     - never introduce duplicate function/class definitions
     - never use `TYPE_CHECKING` import workarounds
     - never introduce circular imports; extract shared code instead
     - never leave syntax-invalid Python in the tree
   - Post-fix validation before success:
     - run `python3 -m py_compile <module_path>` for each changed Python module
     - run `python3 -c "import <module_import_path>"` for each changed module
   - If a fix iteration introduces new failures, roll back that attempt and retry with a different approach (max 3 attempts).

3. **validate** – Optional: `check_type="timestamps"` or `"roadmap_sync"` for memory bank consistency.

4. Commit and push (outside Cortex; or use commit pipeline prompts that call these tools).

**Decision points:**

- If `preflight_passed` is false, inspect `checks` and fix the failing check before re-running.
- For coverage below threshold, add tests and re-run **`run_quality_gate()`** (Phase A includes tests).

**Error recovery:**

- Formatter/linter errors: run the corresponding fix check, then verify with the same check again.
- Test failures: fix code or tests, then re-run tests; do not skip.

---

## 4. Refactoring Workflow

**Goal:** Analyze patterns, get refactoring suggestions, execute safely, and validate.

**Tool sequence:**

1. **load_context** – Load relevant memory bank and code context.

2. **analyze_memory_bank** or **suggest_refactoring** – Get consolidation/splitting/reorganization suggestions.

   **Example:** **suggest_refactoring** with `refactoring_type`: `"consolidation"` or `"splitting"`.

   **Example output:** List of suggestions with file/function targets and confidence.

3. **apply_refactoring** – Execute one or more suggestions (with rollback support).

   **Parameters:** `suggestions` (from previous step), optional `dry_run`.

4. **`run_quality_gate()`** – Ensure no regressions (Phase A bundle includes type, quality, tests).

5. **validate** – Optional structure or roadmap sync check.

**Decision points:**

- If **suggest_refactoring** returns no suggestions, adjust scope or thresholds.
- If **apply_refactoring** reports partial failure, use rollback or fix manually and re-validate.

**Error recovery:**

- Rollback on failure: use **rollback_refactoring** or restore from version history if available.
- Type/quality regressions: fix and re-run checks before committing.

---

## 5. Plan Management Workflow

**Goal:** Create a plan, update progress, and archive completed plans.

**Tool sequence:**

1. **create_plan** (or use create-plan prompt) – Create a new plan file under `.cortex/plans/`.

   **Parameters:** Title, steps, optional priority. Plan file path returned.

2. **register_plan_in_roadmap** – Add the plan to the roadmap so implement/commit can pick it up.

   **Parameters:** `plan_path` or equivalent.

3. **Work** – Implement steps; use **manage_file** to update the plan file (mark steps done).

4. **complete_plan** – When the plan is done: remove from roadmap, append to progress and activeContext, and archive the plan file.

   **Parameters:** `plan_title`, `summary`, `completion_date`, `progress_entry`, `plan_file_name`.

   **Example output:** Roadmap entry removed, progress/activeContext updated, plan moved to archive.

5. **validate_links** – Ensure memory bank and roadmap links still point to the correct (archived) plan paths.

**Decision points:**

- If the plan is not yet complete, update the plan file with status and leave in `.cortex/plans/`.
- If **plan(operation="complete")** is unavailable, use **update_memory_bank(operation="roadmap_remove")**, **update_memory_bank(operation="progress_append")**, **update_memory_bank(operation="active_context_append")**, then run the plan-archiver steps manually.

**Error recovery:**

- Broken links after archive: run **validate_links** and fix links via **manage_file** to roadmap/activeContext.
- Duplicate plan in root: ensure plan-archiver moved the file; delete duplicate if present.
