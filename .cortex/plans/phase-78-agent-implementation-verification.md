# Phase 78: Agent Implementation Verification Protocol

## Status

PENDING

## Goal

Establish mandatory verification steps in the implementation workflow to prevent agents from declaring work "done" when it hasn't been properly completed, committed, or verified against the full plan scope.

## Context

An audit of a Cursor agent session (2026-03-04) revealed systemic verification failures:

1. **Superficial completion checks**: The agent marked Phase 72 as "Done" because `isinstance()` checks existed, without verifying the plan's core requirement (eliminating string matching) was met. Phase 76 was marked "Done" because no `# type: ignore` comments were found, without checking the plan's deeper scope (converting `dict[str,Any]` patterns).

2. **No post-implementation source verification**: After claiming to implement Phase 70 (exec removal), Phase 72 (error classifier), and Phase 73 (async subprocess), the agent never re-read the modified files to confirm changes were actually applied. The implementations were reported as complete but never committed to the repository.

3. **Partial codebase searches**: The agent searched only `cortex/` for `exec()` instead of the full repository tree. It only checked one of three `is_connection_error` implementations.

4. **Validation tooling gaps**: A date typo (`2025` vs `2026`) passed through the agent's "docs validation" step, suggesting the validation tools don't catch date-format errors.

These failures have a common root cause: the implementation workflow lacks **mandatory verification gates** that agents cannot skip.

### New Input (2026-03-04): Commit Pipeline Agent Discipline Issues

Analysis of the 2026-03-04 commit pipeline discussion revealed additional agent discipline failures in the commit workflow itself:

1. **Generic commit messages**: The agent produced the commit message "Run full Cortex commit pipeline and update memory bank for Phase A preflight" — this describes the *process* (ran a pipeline), not the *changes* (added Phase 70-78 plan files, two review files, updated activeContext). Commit messages should describe what changed and why, not what the agent did. The commit prompt Step 13 says "generate comprehensive commit message" but provides no format, examples, or anti-patterns.

2. **`git add -A` used for staging**: The agent used `git add -A` (stage everything) despite AGENTS.md stating "stage only related changes." The commit prompt Step 13 says "Stage all changes" which directly contradicts the safety guidance. This risks staging sensitive files (.env, credentials) or unrelated work.

3. **Invalid analyze target guessed**: The agent called `analyze(target="session")` which is not a valid target (valid: `usage_patterns`, `structure`, `insights`, `context*`, `health`). The agent recovered by guessing `usage_patterns`, but the commit prompt Step 15 only says "execute the Analyze prompt" without specifying which targets to call, leaving agents to guess.

## Approach

Add verification requirements to the Synapse `implement` prompt and plan templates so that every implementation step includes a verification sub-step. Additionally, improve validation tooling to catch date errors. Extend to the `commit` prompt to enforce commit message quality, selective staging, and correct analyze target usage.

## Implementation Steps

### Step 1: Audit the current implement prompt for verification gaps

- Read `src/cortex/synapse/prompts/implement.md` (or equivalent) to understand the current workflow
- Identify where verification is expected but not enforced
- Document which steps currently have verification and which don't

### Step 2: Add mandatory verification gates to the implement workflow

Add the following requirements to the implement prompt:

**Post-edit verification (per file)**:

- After editing a file, the agent MUST re-read the file to confirm the edit was applied
- The re-read MUST be a separate tool call (not cached from the edit result)

**Post-step verification (per plan step)**:

- After completing a plan step, the agent MUST verify by searching the codebase for the pattern that should have been eliminated (e.g., search for `exec(` after removing exec)
- The search MUST cover the **full repository** (not a subdirectory)

**Plan-scope verification (end of implementation)**:

- Before declaring a plan complete, the agent MUST re-read the plan's success criteria
- For each criterion, the agent MUST provide evidence (file path + line, search result, test output)
- If any criterion cannot be verified, the plan MUST NOT be marked complete

**Commit verification**:

- After git commit, verify the commit includes all expected file changes via `git show --stat`

### Step 3: Add a "Verification Checklist" section to the plan template

Update the plan template (in `create-plan.md` or equivalent) to include a new mandatory section:

```markdown
## Verification Checklist

For each implementation step, define:
- **What to search for**: Pattern that should be eliminated (e.g., `exec(`)
- **Search scope**: Full repo, specific directory, or specific files
- **Expected result**: Zero matches, specific count, etc.
- **Files to re-read**: Which files must be re-read after editing
```

### Step 4: Improve date validation in pre-commit checks

- Check if the validation tools (`execute_pre_commit_checks`, `validate`) catch date format errors
- If not, add a date format validator that checks:
  - Dates in plan files match `YYYY-MM-DD` format
  - Year is within reasonable range (current year ± 1)
  - Dates in roadmap entries are consistent
- This catches the `2025-03-04` vs `2026-03-04` class of typos

### Step 5: Add "duplicate definition" detection to implementation workflow

- When fixing a function (like `is_connection_error`), the agent MUST search the full codebase for other definitions of the same function name
- Add this as a standard step in the implement prompt: "Before modifying a function, search for all definitions of that function name in the codebase"
- This prevents fixing one copy while leaving duplicates unpatched

### Step 6: Add tests

- Test that the verification checklist template renders correctly in new plans
- Test the date validator catches year typos
- Test the duplicate-definition search finds all copies

### Step 7: Enforce commit message quality in the commit prompt (Step 13)

Update the commit prompt's Step 13 to include:

**Commit message format requirements**:

- The commit message MUST describe **what changed** (files added/modified/removed, features/fixes), not **what the agent did** (ran pipeline, executed checks)
- Anti-pattern: "Run full Cortex commit pipeline and update memory bank" (describes process)
- Good pattern: "Add Phase 70-78 security and performance plans, update activeContext" (describes changes)
- Format guidance: Use conventional commit style (`feat:`, `fix:`, `docs:`, `chore:`) when applicable
- The message MUST reference the actual content of the diff, not the commit pipeline steps

### Step 8: Replace `git add -A` with selective staging in the commit prompt (Step 13)

Update the commit prompt's Step 13 to:

- Replace "Stage all changes" with "Stage related changes selectively"
- Add: "Use `git add <specific-files>` instead of `git add -A`. List files from `git status` and stage only files that are part of the current work."
- Add safety check: "Before staging, review `git status` output. Do NOT stage files matching `.env*`, `credentials*`, `*.key`, `*.pem`, or other sensitive patterns."
- Reconcile with AGENTS.md which already says "stage only related changes"

### Step 9: Fix commit prompt Step 15 analyze target specification

Update the commit prompt's Step 15 to specify exact tool calls instead of just "execute the Analyze prompt":

- Replace vague "execute the Analyze prompt" with specific targets: `analyze(target="context")` for context effectiveness, then `analyze(target="usage_patterns")` for session patterns
- Add: "Valid analyze targets are: `usage_patterns`, `structure`, `insights`, `context`, `context_stats`, `context_all_sessions`, `health`. Do NOT use `session` as a target."
- Consider whether Step 15 should read and execute `analyze.md` OR call specific analyze targets directly (the current phrasing is ambiguous)

## Dependencies

None — this is a process/tooling improvement, not a code feature.

## Success Criteria

- Implement prompt contains mandatory post-edit re-read requirement
- Implement prompt contains mandatory full-codebase search after elimination steps
- Implement prompt contains plan-scope verification before marking complete
- Plan template includes "Verification Checklist" section
- Date validator catches year typos in plan/roadmap files
- Duplicate-definition search is part of the standard implement workflow
- Commit prompt Step 13 specifies commit message format (content-descriptive, not process-descriptive)
- Commit prompt Step 13 uses selective `git add` instead of `git add -A`
- Commit prompt Step 15 specifies exact `analyze()` targets with valid target list

## Testing Strategy

- **Unit Tests**: Date validator, template rendering, commit message format validation
- **Process Tests**: Create a mock plan, run implementation workflow, verify all verification gates fire
- **Edge Cases**: Plans with no elimination steps, plans with multiple files, date edge cases (Dec 31 -> Jan 1)
- **Commit Message Tests**: Verify anti-patterns are rejected (process-descriptive messages), good patterns accepted
- **Staging Tests**: Verify selective staging excludes sensitive file patterns
- **Coverage Target**: 95%+ for new validation code

## Risks & Mitigation

- **Risk**: Verification steps add overhead to the implementation workflow
- **Mitigation**: Keep verification lightweight (single re-read, single search) — the cost of missing a verification is much higher than the overhead
- **Risk**: Agents find workarounds to skip verification
- **Mitigation**: Make verification gates produce artifacts (search results) that are visible in the plan output, not just assertions the agent can fabricate
- **Risk**: Selective staging may miss files that should be committed
- **Mitigation**: After staging, run `git diff --cached --stat` and compare against expected file list from the session's work

## Timeline

Medium-High effort (8-14h) — prompt engineering for implement and commit prompts + date validator + staging safety
