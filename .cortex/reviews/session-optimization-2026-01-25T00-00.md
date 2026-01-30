# Session Optimization Analysis (2026-01-25)

## Summary

This session centered on running `/cortex/commit`. The pipeline stalled due to **process/tooling mismatches** (MCP invocation ergonomics, path assumptions like `.cursor/rules/`) and **quality-gate surprises** (markdownlint scanning scope; function-length gate surfacing a large backlog).

The highest-leverage Synapse improvements are: **(1) fail fast on quality gates before expensive steps**, **(2) avoid “check_all_files” markdownlint by default**, and **(3) standardize how MCP tool calls are invoked/validated in Cursor** (preventing “tool not found”/missing-args churn).

## Mistake Patterns Identified

### Pattern 1: “Wrong directory” assumptions (`.cursor/*` vs `.cortex/*`)

- **Description**: Commit flow expected `.cursor/rules/` and `.cursor/memory-bank/`; this repo’s canonical locations are `.cortex/synapse/rules/` and `.cortex/memory-bank/` (with `.cursor/` being optional/absent in this workspace).
- **Examples**:
  - `.cursor/rules/` does not exist in this workspace.
  - Memory bank is present at `.cortex/memory-bank/`.
- **Impact**: Causes early orchestration steps to fail or waste time “searching for rules”, and encourages agents to read/write the wrong files.

### Pattern 2: MCP tool-calling ergonomics drift (“tool not found” / missing args / inconsistent call shape)

- **Description**: The session encountered inconsistent MCP invocation behavior when calling tools multiple times, including failures like “Tool … was not found” after successful calls earlier.
- **Examples**:
  - Initial `manage_file` calls required explicitly providing `file_name`/`operation`.
  - Later calls failed with “Tool … was not found”, causing fallback to shell scripts.
- **Impact**: Interrupts automated workflows, breaks “MCP-first” rules, and increases risk of partial/unverified execution.

### Pattern 2.1: Memory bank metadata index staleness blocks `manage_file(write)`

- **Description**: `manage_file(write)` can become unusable for a memory bank file if `.cortex/index.json` metadata (hash/size/mtime) is stale relative to the on-disk file.
- **Examples**:
  - `manage_file(metadata)` reporting old `content_hash`/`size_bytes` while the on-disk `roadmap.md` differs.
  - `check_structure_health(... cleanup_actions=["update_index"] ...)` reporting success but not actually refreshing metadata.
- **Impact**: Breaks the “use MCP tools for memory bank ops” rule because the MCP write path is blocked until metadata is repaired.

### Pattern 3: Markdownlint scope too broad for commit pipeline

- **Description**: Running markdownlint with `check_all_files=True` surfaced a large number of MD024/MD036 issues in archived plans and docs. This is noisy and blocks the commit pipeline unless the workflow explicitly scopes or sets policy.
- **Examples**:
  - Many MD024 occurrences in `.cortex/plans/archive/**` and other documentation.
  - Fixes required manual edits (e.g., unique headings) even though they’re historical/archival content.
- **Impact**: Turns “commit” into a repo-wide doc cleanup; encourages risky mass edits or incorrect “mark step complete” behavior.

### Pattern 4: Quality-gate ordering and “fail-fast” missing

- **Description**: The workflow can spend time on formatting/markdownlint/type-check and only later discover **large, pre-existing** quality violations (e.g., function-length limit).
- **Examples**:
  - Function-length gate surfaced **dozens** of violations (backlog scale).
- **Impact**: Wastes time, increases churn, and encourages agents to “paper over” issues (e.g., trimming docstrings rather than structural refactors).

### Pattern 5: “Docstring size vs file-size gate” surprises

- **Description**: The file-size gate counts docstrings. MCP tool modules often carry very large docstrings (examples). This incentivizes destructive doc trimming to satisfy the 400-line cap.
- **Examples**:
  - `src/cortex/tools/configuration_operations.py` exceeded the 400-line limit; mitigation required reducing docstring payload.
  - `src/cortex/tools/phase5_execution.py` exceeded the 400-line limit; mitigation required extracting helpers and tightening module docs.
- **Impact**: Documentation quality can regress; the correct mitigation is often “move examples to docs” or split modules, not delete useful content.

## Root Cause Analysis

### Cause 1: Synapse prompt text assumes `.cursor/*` structure universally

- **Prevention opportunity**: Teach prompts to resolve “memory bank + rules” paths from `project_root` by probing `.cortex/` first, treating `.cursor/` as optional symlink.

### Cause 2: No “MCP call contract” section for Cursor execution environment

- **Prevention opportunity**: Add a short, explicit section (and examples) for MCP tool invocation: required args, typical failure modes, and the “verify with scripts if MCP call layer flakes” fallback.

### Cause 2.1: Missing/ineffective “update index” repair path for external edits

- **Prevention opportunity**: Ensure there is a documented and working repair mechanism (e.g., a cleanup action that refreshes `.cortex/index.json`) so `manage_file(write)` remains usable after out-of-band edits.

### Cause 3: Markdown policy mismatch (repo-wide vs commit-scoped)

- **Prevention opportunity**: Make markdownlint behavior explicit and scoped:
  - Default to git-modified markdown files
  - Treat `.cortex/memory-bank/**` and `.cortex/plans/**` as the *only blocking scopes*
  - Treat archived plans/docs as non-blocking unless explicitly requested

### Cause 4: Quality gates surfaced late

- **Prevention opportunity**: In commit orchestration, run a **fast quality preflight** immediately after “fix errors”:
  - file sizes
  - function lengths
  - lints/types quick checks

## Optimization Recommendations

### Recommendation 1: Update Synapse commit workflow to be `.cortex`-first, `.cursor`-optional

- **Priority**: Critical
- **Target**: `.cortex/synapse/prompts/commit.md` (and any referenced orchestration text)
- **Change**:
  - Resolve memory bank under `.cortex/memory-bank/` by default.
  - Resolve rules under `.cortex/synapse/rules/` by default.
  - Treat `.cursor/` locations as optional symlinks.
- **Expected impact**: Prevents early pipeline derailment in repos that don’t materialize `.cursor/` directories.

### Recommendation 2: Add “MCP invocation contract” + deterministic fallback

- **Priority**: High
- **Target**: `.cortex/synapse/rules/general/agent-workflow.mdc` (or a new “mcp-tooling.mdc”)
- **Change**:
  - Document the exact required parameters for core tools (`manage_file`, `execute_pre_commit_checks`, `validate`, `fix_markdown_lint`).
  - Add explicit guidance: if MCP call layer behaves inconsistently, immediately switch to the repo’s `.cortex/synapse/scripts/{language}/check_*.py` as fallback (still deterministic, still enforced).
- **Expected impact**: Reduces “tool not found / missing args” churn and keeps the pipeline moving safely.

### Recommendation 2.1: Add/repair an index refresh operation for memory bank files

- **Priority**: High
- **Target**: MCP structure/health tooling (e.g., `check_structure_health` cleanup `update_index`) + documentation
- **Change**:
  - Ensure “update index” actually refreshes `.cortex/index.json` to current disk state.
  - Add a test that reproduces stale metadata → repair → successful `manage_file(write)`.
- **Expected impact**: Prevents `manage_file(write)` from becoming permanently blocked after external edits.

### Recommendation 3: Change markdownlint defaults to “modified files”, not “all files”

- **Priority**: High
- **Target**: `.cortex/synapse/agents/markdown-linter.md` and commit workflow step 1.5
- **Change**:
  - Default: lint + fix only git-modified markdown files, optionally include untracked.
  - Blocking policy: fail only on critical errors inside `.cortex/memory-bank/**` and `.cortex/plans/**` (excluding archive by default).
- **Expected impact**: Prevents repo-wide markdown churn on commits; focuses on what CI typically enforces.

### Recommendation 4: Add “quality preflight” directly after Step 0

- **Priority**: High
- **Target**: `.cortex/synapse/prompts/commit.md` (step ordering)
- **Change**:
  - Run file size + function length checks *before* running expensive steps (tests, broad markdown operations).
  - If violations are large in count, stop and create/require a focused refactor plan instead of continuing.
- **Expected impact**: Avoids wasting time and prevents massive mid-commit refactors.

### Recommendation 5: Docstrings: move large examples out of tool modules

- **Priority**: Medium
- **Target**: `.cortex/synapse/rules/python/python-mcp-development.mdc` (or maintainability guidance)
- **Change**:
  - Encourage keeping MCP tool docstrings concise; move large examples to `docs/` and link.
- **Expected impact**: Prevents file-size violations without losing documentation fidelity.

## Implementation Plan (Suggested)

1. Implement Recommendation 1 (path resolution policy) and Recommendation 4 (fail-fast quality preflight).
2. Implement Recommendation 3 (markdownlint scoping + blocking policy).
3. Implement Recommendation 2 (MCP call contract + fallback).
4. Implement Recommendation 5 (docstring/external docs guidance).

## Notes / Evidence from This Session

- `analyze_context_effectiveness(analyze_all_sessions=False)` returned **no_data**: no `load_context` calls in current session, so context-usage optimization is N/A here.
- The repo-wide quality gates revealed a **large function-length backlog**, which should be treated as a dedicated refactor effort rather than a side-effect of “commit”.
