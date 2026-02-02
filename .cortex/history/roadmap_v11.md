# Roadmap: MCP Memory Bank

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

- **Fix commit workflow: re-run Step 12.3 after code fixes in Step 12** - PENDING - Prevent CI Ruff failure when type/lint fixes in Step 12 introduce new lint (e.g. E402). Commit prompt must require re-run of Step 12.3 (quality) after any code change in 12.2 or 12.3; add reminder that type/lint fixes can introduce new lint. Plan: .cortex/plans/fix-commit-workflow-rerun-12.3-after-fix.md.

- **Session optimization (2026-02-02): Commit rules load and Step 12.6 fallback** - COMPLETE (2026-02-02) - Implemented all recommendations from .cortex/reviews/session-optimization-2026-02-02T10-04.md: (1) Commit prompt Pre-Step and checklist require explicit rule file read when rules() returns disabled (get_structure_info + Read tool; record "Rules loaded: Yes (via file read)"). (2) Example markdown lint fallback command (npx markdownlint-cli2 ...) in Step 12.6 and Connection Closed fallback. (3) docs/mcp-tool-timeouts.md and commit prompt: tool unavailability after connection closed ("tool not found" → use documented fallback). Integration tests test_commit_prompt_requires_rules_file_read_when_rules_disabled, test_commit_prompt_contains_markdown_lint_fallback_example. Plan: .cortex/plans/archive/SessionOptimization/session-optimization-commit-rules-and-fallback-2026-02-02.md.

- **Session optimization (2026-02-01): Connection closed handling** - COMPLETE (2026-02-01) - Added "Connection Closed During Long Tool (Retry Then Fallback)" in commit prompt Failure Handling; exception in MCP Tool Failure for Connection closed/ClosedResourceError; fallback for fix_markdown_lint and optional Step 12.6 narrower scope. docs/mcp-tool-timeouts.md: "Client connection closed during long tools" subsection. Plan: .cortex/plans/archive/SessionOptimization/session-optimization-commit-connection-closed-handling.md.

- **Session optimization (2026-02-01): Require script-analysis when script run** - COMPLETE (2026-02-02) - Commit prompt: "Script use (MANDATORY)" step and "Script run without analysis" in COMMON ERRORS; agent-workflow (Synapse rule) script-use rule; integration tests test_commit_prompt_requires_script_tooling_when_script_run, test_commit_prompt_lists_script_run_without_analysis_common_error. Plan: .cortex/plans/archive/SessionOptimization/session-optimization-commit-require-script-analysis.md.

## Current Status (2026-02-02)

### Active Work

- ✅ **Conditional prompt registration** - COMPLETE (2026-01-31) - Implementation already present (src/cortex/tools/config_status.py, src/cortex/tools/prompts.py conditional registration). Documented conditional availability in README.md, docs/prompts/README.md, CLAUDE.md. All tests passing (3134); coverage 90.44%. Plan: .cortex/plans/conditional-prompt-registration.md.

(Content truncated for length - full roadmap preserved in memory bank)
