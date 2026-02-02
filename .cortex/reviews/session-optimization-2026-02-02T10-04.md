# Session Optimization Analysis

## Summary

Analysis of the current session focused on a **workflow-only** run: the `/cortex/commit` pipeline. No `load_context` calls occurred (`analyze_context_effectiveness` returned `status: "no_data"`), so primary signals were commit pipeline tool outputs, memory-bank updates, and MCP tool behavior. The commit completed successfully (Steps 0–14), with one MCP tool disconnect during Step 12.6 (markdown lint) and correct use of the documented fallback. No code defects or rule violations were introduced; the session exposed **process and tooling** improvement opportunities for Synapse prompts and rules.

## Mistake Patterns Identified

### Pattern 1: Rules Not Loaded When Rules Tool Is Disabled

- **Description**: The commit pre-action checklist requires loading rules before Step 0. When `rules(operation="get_relevant", ...)` returned `status: "disabled"`, the run proceeded with "Rules loaded via MCP: No; rules context from CLAUDE/AGENTS as fallback" and did not explicitly read rule files from the rules directory or Synapse rules directory.
- **Examples**: Pre-action used CLAUDE.md/AGENTS.md context only; no `Read` of `.cortex/synapse/rules/` or `structure_info.paths.rules` files.
- **Frequency**: Once in this session (rules tool was disabled).
- **Impact**: Medium. Commit and code-modifying steps can still align with project standards via CLAUDE/AGENTS, but the checklist item "Rules loaded: Yes/No" is only satisfied by MCP or by explicitly reading rule files; the prompt says to "read rules from the rules directory or the Synapse rules directory" when the tool is unavailable, and that read was not performed.

### Pattern 2: No Explicit Fallback Command for Markdown Lint in Step 12.6

- **Description**: When `fix_markdown_lint` MCP returned "Connection closed" and a retry failed with "Tool ... was not found", the agent correctly used the documented fallback ("Run markdown lint via shell with the same scope") but had to infer the exact command (e.g. `npx markdownlint-cli2 ...`).
- **Examples**: Fallback was executed successfully via an inline Python `subprocess.run(['npx', 'markdownlint-cli2', ...])`; the commit prompt does not specify the exact shell command or flags.
- **Frequency**: Once in this session (Step 12.6).
- **Impact**: Low. Fallback worked; adding an explicit example command would reduce ambiguity and speed future fallbacks.

### Pattern 3: Tool Unavailability After Connection Closed (Informational)

- **Description**: After "Connection closed", a retry of `fix_markdown_lint` failed with "Tool user-cortex-fix_markdown_lint was not found". This is likely client/MCP reconnection or tool-name resolution, not a Synapse prompt issue.
- **Examples**: Second MCP call to fix_markdown_lint after connection closed returned a "tool not found" style error.
- **Frequency**: Once in this session.
- **Impact**: Low for Synapse (handled by retry-then-fallback); may be worth documenting for MCP/client investigations.

## Root Cause Analysis

### Cause 1: Unclear "Read Rules" Requirement When Tool Is Disabled

- **Description**: The commit prompt states that if the rules tool is unavailable, the agent should "read rules from the rules directory ... or the Synapse rules directory". It does not explicitly say to use the `Read` tool with paths from `get_structure_info()` (e.g. `structure_info.paths.rules` or Synapse rules path) so that "Rules loaded: Yes" can be recorded.
- **Contributing factors**: Rules tool disabled in config; checklist allows "rules context from CLAUDE/AGENTS" as acceptable in practice, so agents may not treat file read as mandatory when disabled.
- **Prevention opportunity**: In the commit prompt (and optionally in the memory-bank-updater or agent-workflow rule), add an explicit step: "When `rules()` returns disabled, read at least [list key rule files] from `structure_info.paths.rules` or Synapse rules directory using the Read tool so that Rules loaded: Yes can be satisfied."

### Cause 2: Fallback Described by Scope, Not by Exact Command

- **Description**: Step 12.6 fallback is described as "Run markdown lint via shell with the same scope (e.g. same file set or equivalent of check_all_files)". Agents must infer the exact command (markdownlint-cli2, globs, exclusions).
- **Contributing factors**: Language-agnostic prompt avoids hardcoding tools; markdown lint is an exception where a single cross-platform tool (markdownlint-cli2) is standard.
- **Prevention opportunity**: In the commit prompt Failure Handling / Step 12.6, add an optional "Example fallback command" line (e.g. `npx markdownlint-cli2 '**/*.md' '**/*.mdc' !**/node_modules/** !**/.venv/** ... --fix` and without `--fix` for check) so agents do not need to infer.

### Cause 3: MCP Connection Closure and Tool Discovery (External)

- **Description**: Connection closed and subsequent "tool not found" are likely due to client/server reconnection or tool registration, not Synapse content.
- **Contributing factors**: Long-running or heavy tool (markdown lint over many files) may trigger timeouts or disconnects.
- **Prevention opportunity**: Keep "Retry Then Fallback" and document fallback clearly; no Synapse prompt change required for the "tool not found" case beyond ensuring fallback is unambiguous.

## Optimization Recommendations

### Recommendation 1: Require Explicit Rule File Read When Rules Tool Is Disabled

- **Priority**: Medium
- **Target**: Commit prompt (e.g. `.cortex/synapse/prompts/commit.md`) — Pre-Step "Load Rules" and Pre-Action Checklist.
- **Change**: Add an explicit step: "When `rules()` returns status `disabled`, resolve the rules or Synapse rules path via `get_structure_info()` (e.g. `structure_info.paths.rules` or Synapse rules directory), then use the Read tool to load at least [e.g. python-coding-standards.mdc, python-mcp-development.mdc, no-test-skipping.mdc] (or equivalent for the task). Record 'Rules loaded: Yes (via file read)' so the checklist is satisfied."
- **Expected impact**: Ensures "Rules loaded" is explicitly satisfied when MCP rules are disabled, aligning with the written requirement and improving consistency of rule application in commit runs.
- **Implementation**: Edit commit prompt Pre-Step and checklist; optionally add one sentence to the memory-bank-updater or agent-workflow rule about satisfying "Rules loaded" via file read when the tool is disabled.

### Recommendation 2: Add Example Fallback Command for Step 12.6 Markdown Lint

- **Priority**: Low
- **Target**: Commit prompt — Step 12.6 and "Connection Closed During Long Tool (Retry Then Fallback)" / fallbacks for `fix_markdown_lint`.
- **Change**: After the sentence "Run markdown lint via shell with the same scope", add: "Example (match CI scope): `npx markdownlint-cli2 '**/*.md' '**/*.mdc' !**/node_modules/** !**/.venv/** !**/venv/** !**/__pycache__/** !**/.git/**` with `--fix` to fix, or without `--fix` for check-only. Record 'MCP connection closed; fallback used' in the commit output."
- **Expected impact**: Reduces ambiguity and iteration when Step 12.6 fallback is used; avoids ad-hoc command construction.
- **Implementation**: Single edit in commit prompt Failure Handling and Step 12.6.

### Recommendation 3: Document Tool Unavailability After Connection Closed (Optional)

- **Priority**: Low
- **Target**: Docs (e.g. `docs/mcp-tool-timeouts.md`) or commit prompt Failure Handling.
- **Change**: Add a short note: "After a connection closed error, a retry may fail with 'tool not found' or similar; in that case proceed with the documented fallback for that step (e.g. markdown lint via shell) and do not block the pipeline."
- **Expected impact**: Clarifies that "tool not found" after disconnect is expected and should trigger fallback, not abort.
- **Implementation**: One paragraph in the relevant doc or commit prompt.

## Implementation Plan

1. **Recommendation 1** — Update commit prompt Pre-Step and checklist so that when the rules tool is disabled, agents explicitly read key rule files and record "Rules loaded: Yes (via file read)".
2. **Recommendation 2** — Add the example markdown lint fallback command to the commit prompt (Step 12.6 and Connection Closed fallback).
3. **Recommendation 3** — Optionally add a short note in docs or commit prompt about proceeding with fallback when retry returns "tool not found" after connection closed.

## Expected Impact

- **Recommendation 1**: Ensures every commit run satisfies "Rules loaded" either via MCP or via explicit file read, improving consistency and adherence to coding standards when the rules tool is disabled.
- **Recommendation 2**: Makes Step 12.6 fallback deterministic and quick to apply, with no need to infer markdown lint command or scope.
- **Recommendation 3**: Reduces confusion when MCP retry fails after a disconnect and keeps the pipeline moving to the documented fallback.

## Session Metadata

- **Session type**: Workflow-only (commit pipeline; no `load_context`).
- **Primary signals**: Commit pipeline tool outputs, memory-bank updates, MCP tool responses.
- **Context effectiveness**: `analyze_context_effectiveness(analyze_all_sessions=False)` returned `status: "no_data"` (expected).
- **Rules**: `rules(operation="get_relevant", ...)` returned `status: "disabled"`; context from CLAUDE/AGENTS used.
- **Report path**: `.cortex/reviews/session-optimization-2026-02-02T10-04.md` (timestamp from `date +%Y-%m-%dT%H-%M`).
