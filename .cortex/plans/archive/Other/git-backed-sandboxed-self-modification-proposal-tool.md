---
title: "Git-Backed Sandboxed Self-Modification Proposal Tool"
component: "safety"
work_type: "feature"
status: PENDING
priority: "Medium"
created: "2026-07-23"
depends_on: []
---

## Goal

Add a `propose_framework_optimization` MCP tool that lets an agent draft a change to Cortex's own Synapse prompts/rules/config, apply and self-test it inside an isolated git worktree, and — only after the self-test passes — produce a reviewable diff/PR draft for explicit human approval. No autonomous merge or auto-push under any circumstance.

## Context

An external proposal ("Git-Backed Harness Isolation / Safety Shield") suggested Cortex be able to self-correct its own system prompts/configurations without risking a broken runtime. Investigation (2026-07-23) confirmed this capability does not exist today: `WorktreeExecutionEnvironment`/`LocalExecutionEnvironment` (`src/cortex/core/execution_env.py`) and `parallel_worktree_merge.py` provide worktree execution for user-invoked parallel task batches (`/cortex/do`), but nothing lets an agent edit its own prompts/rules in isolation, self-test, and propose the result — the archived `execution-environment-abstraction.md` plan scoped only the user-invoked case.

**Why**: Synapse prompts/rules under `.cortex/synapse/` directly govern agent behavior; letting an agent edit them in the live working tree risks a broken or self-reinforcing bad instruction taking effect immediately, with no verification gate. An isolated worktree plus a mandatory self-test plus a human-approval gate closes that gap while staying within this project's non-negotiable safety rule that hard-to-reverse or externally-visible actions (pushing code, opening PRs) require explicit user confirmation.

**How to apply**: Every invocation of this tool must end at a human decision point (approve/reject the drafted diff). The tool itself must never call `git push` or `gh pr create` — it hands a reviewed diff back to the calling agent/user, who decides whether to push, using the existing (user-authorized) commit/PR workflow.

## Scope

**in_scope**:

- A new tool that creates an isolated git worktree (reusing `WorktreeExecutionEnvironment` from `src/cortex/core/execution_env.py`, not a new mechanism), copies/checks out the current `.cortex/synapse/` (and optionally `.cortex/rules/`) state into it.
- Applying a proposed diff (supplied by the calling agent) to the prompt/rule files inside that isolated worktree only — never the live working tree.
- Running a self-test suite inside the worktree: at minimum, JSON/YAML/markdown-frontmatter schema validation for changed prompt/rule files, and `run_quality_gate()`-equivalent checks scoped to the changed paths.
- On self-test success, generating a reviewable artifact (unified diff + a plain-language explanation of why the change addresses a specific observed edge case/failure) returned to the caller — not written anywhere or pushed.
- On self-test failure, discarding the worktree and returning the failure reason; no partial state is left behind.
- Explicit worktree cleanup (removal) after every invocation, success or failure, so no orphaned worktrees accumulate.

**out_of_scope**:

- Any automated `git push` or `gh pr create` call from within this tool — PR creation remains a separate, explicitly user-confirmed step using existing workflows.
- A GitHub PAT / credential-management feature — this plan assumes the human reviewer uses their own already-authorized `gh` session for any resulting push, per this project's "no hardcoded secrets" and "confirm before externally-visible actions" rules.
- Editing arbitrary source code (`src/`) via this tool — scope is limited to `.cortex/synapse/` and `.cortex/rules/` prompt/rule/config files, the actual target of the original proposal.
- A scheduled/autonomous trigger that invokes this tool without a specific, agent-identified edge case to address — every invocation must be tied to a concrete observed problem, not run speculatively.

## Approach

Build a thin orchestration layer on top of the existing `WorktreeExecutionEnvironment`: create worktree → apply diff → run schema + quality checks scoped to changed files → on pass, format a diff+rationale artifact for the caller → always tear down the worktree. Treat this as a read-mostly, propose-only tool: its only side effect on the live repository is the worktree lifecycle (created and destroyed within the call), never a change to the live branch. The human-approval boundary is enforced by simply not implementing any push/PR capability in the tool at all, rather than by a flag that could be misconfigured.

## Implementation Steps

1. Read `src/cortex/core/execution_env.py` and `parallel_worktree_merge.py` in full to confirm the exact API for creating/tearing down an isolated worktree and whether it already supports the "checkout a subset of paths, apply a diff, run a command" flow needed here.
2. Define the tool's input/output models (Pydantic `BaseModel`, no `Any`): input = target file paths + proposed diff/new content + rationale text; output = self-test result, formatted diff, rationale, or failure reason.
3. Implement worktree creation scoped to `.cortex/synapse/` and `.cortex/rules/` using the existing execution-environment abstraction.
4. Implement diff application inside the worktree only (never the live tree) with validation that all target paths are within the allowlisted directories (reject anything outside `.cortex/synapse/` or `.cortex/rules/`).
5. Implement the self-test step: JSON schema validation for skill JSON, YAML/frontmatter validation for `.mdc` rules and prompt markdown, and a scoped `run_quality_gate()`-equivalent check.
6. Implement guaranteed worktree teardown (success and failure paths) using a context manager / `try`/`finally` so no orphaned worktree survives a crash.
7. Wire the new tool into the MCP tool registry following existing patterns (thin handler delegating to core logic, per `python-mcp-development.mdc`).
8. Add unit tests for path-allowlist rejection, self-test pass/fail branches, and guaranteed teardown (including on simulated exceptions mid-run).
9. Run `run_quality_gate()` and confirm no regression elsewhere.

## Verification Checklist

- Step 1: search `src/cortex/core/execution_env.py` for existing teardown/cleanup guarantees; confirm whether they're already exception-safe or need hardening for this use case.
- Step 4: re-read the path-allowlist check after implementation and confirm a path-traversal attempt (e.g. `../../src/cortex/core/...`) is rejected, not silently normalized into the live tree.
- Step 6: re-read the teardown logic and confirm a forced exception mid-self-test still results in worktree removal (test this explicitly, not just by inspection).
- Step 9: re-run `run_quality_gate()` after tests added; confirm coverage threshold met.

## Dependencies

- Builds on `src/cortex/core/execution_env.py` (`WorktreeExecutionEnvironment`) — no changes required there, reused as-is. Independent of the other three plans in this batch (telemetry log, context gating, constraints monitor).

## Success Criteria

- The tool never modifies the live working tree; all edits occur only inside a worktree that is removed by the end of the call.
- The tool has no code path that calls `git push` or `gh pr create` — verified by code review/grep, not just by test.
- Path-allowlist rejects any target outside `.cortex/synapse/` and `.cortex/rules/`.
- Self-test failures return a clear reason and leave no orphaned worktree.
- `run_quality_gate()` passes with new code covered.

## Testing Strategy

Target 95% coverage on new code. Unit tests (AAA pattern) for: path-allowlist accept/reject cases including traversal attempts, self-test pass path (valid schema, valid frontmatter), self-test fail path (invalid JSON skill, malformed frontmatter), guaranteed teardown under a forced mid-run exception. Integration test: end-to-end call with a real small valid rule-file edit, asserting the live `.cortex/synapse/` tree is byte-identical before and after the call, and the worktree directory no longer exists afterward. Negative case: diff targeting a path outside the allowlist is rejected before any worktree file is touched.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| A bug allows the tool to write outside the worktree into the live tree | Allowlist check happens before any file write, and integration test asserts live-tree byte-identity before/after every call |
| Orphaned worktrees accumulate from crashed/interrupted calls | Teardown is implemented via `try`/`finally`, tested explicitly under forced exceptions |
| Self-test is too shallow (schema-only) to catch a rule change that is syntactically valid but behaviorally harmful | Self-test scope is documented as schema + scoped quality-gate only; behavioral review remains the human reviewer's job at the approval step — explicitly not claimed as a substitute for human review |
| Tool is later extended to auto-push without updating this plan's safety boundary | `out_of_scope` explicitly excludes push/PR automation; any future extension must be a new plan with its own explicit review of the safety implications |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
