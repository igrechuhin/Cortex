---
title: "Add Local Environment Context Memory Artifact"
component: "memory-bank"
work_type: "feature"
status: PENDING
priority: "Medium"
created: "2026-04-17"
depends_on: []
---

## Goal

Define and deliver an automatically managed local-only machine context artifact in `.cortex/memory-bank` so agents can reliably reason about host architecture and environment differences (Apple Silicon dev vs Intel deploy), including startup-time binding validation.

## Context

TradeWing development runs on multiple Apple Silicon machines while deployment targets Intel-based environments. Current prompts and memory-bank guidance do not provide a canonical local machine context source, so agent decisions can miss architecture-specific constraints during debugging and integration work. The request references `.cortex/prompts/debug-external-integration.md` and requires a local, git-untracked data source that remains machine-specific.

The user additionally requires that lifecycle housekeeping be automatic (artifact create/update handled by tooling, with user prompts only when needed) and that Cortex MCP startup validate local-environment binding to detect copied project states from another machine.

## Scope

**in_scope**

- Define one canonical local-only file location and naming convention under `.cortex/memory-bank` for machine/environment metadata.
- Define exact schema fields required for agent reasoning (host CPU architecture, OS, Python/toolchain/runtime context, deploy-target architecture notes).
- Define automatic create/update behavior for the artifact, including when user confirmation is required versus fully automatic refresh.
- Define startup-time Cortex MCP validation flow that checks artifact-machine binding and flags likely cross-environment project copies.
- Define how prompts (including external-integration debug workflow) should consume the local artifact and fallback behavior when absent or invalid.
- Define verification checks that prove the plan is complete and operational.

**out_of_scope**

- Production rollout beyond this plan's finite implementation slice.
- Introducing remote/shared environment inventory systems.
- Covering non-TradeWing projects or cross-repo standardization.

## Approach

Use an implementation-first slice that establishes one canonical machine-local artifact contract, then adds automatic lifecycle handling and startup validation checks as a cohesive behavior set in a controlled follow-up `/cortex/do` execution. The artifact remains untracked in git and intentionally local, while tracked documentation explains expected behavior and recovery.

The plan focuses on deterministic agent behavior: when environment-specific reasoning is needed, agents read the local artifact first; if missing, stale, or mismatched to current machine identity, they trigger automatic refresh/validation flows and explicit remediation messaging. This avoids hidden assumptions about architecture and surfaces cross-machine copy risks early at startup.

## Implementation Steps

1. Define the local artifact contract: file path, git-ignore policy, machine-binding keys, ownership expectations, and required metadata fields.
2. Implement automatic artifact housekeeping flow: create on first run and refresh/update on detected environment drift, with explicit prompts only for ambiguous fields.
3. Implement Cortex MCP startup validation that checks artifact binding against current host and emits actionable warnings/remediation when mismatch indicates likely copied workspace state.
4. Add/adjust memory-bank and prompt guidance (including `.cortex/prompts/debug-external-integration.md`) so runtime workflows consume validation status and architecture context.
5. Add concise operator guidance for override/rebind flows when users intentionally move projects across machines.
6. Validate plan outcomes with checklist-driven evidence and finalize status updates.

## Verification Checklist

1. Search for canonical local artifact reference

- Search: `local machine`, `architecture`, `memory-bank`, and canonical file name token.
- Scope: `.cortex/memory-bank/`, `.cortex/prompts/`.
- Re-read: updated memory-bank guidance file and `.cortex/prompts/debug-external-integration.md`.

2. Confirm untracked/local-only intent is documented

- Search: `untracked`, `local-only`, `gitignore`, `do not commit`.
- Scope: memory-bank guidance and prompt docs touched by this work.
- Re-read: artifact contract section and maintenance instructions.

3. Confirm architecture divergence handling exists

- Search: `Apple Silicon`, `Intel`, `deploy`, `host architecture`.
- Scope: `.cortex/prompts/debug-external-integration.md` and related memory-bank docs.
- Re-read: architecture-specific workflow branch text.

4. Confirm automatic housekeeping behavior exists

- Search: `auto-create`, `auto-update`, `refresh`, `drift`.
- Scope: startup/lifecycle handling paths and related docs.
- Re-read: artifact lifecycle implementation and ambiguity-prompt handling.

5. Confirm startup binding validation exists

- Search: `startup`, `binding`, `mismatch`, `copied`, `rebind`.
- Scope: Cortex MCP startup path and validation utilities.
- Re-read: mismatch detection and remediation messaging.

6. Confirm fallback behavior exists when artifact missing or invalid

- Search: `fallback`, `missing`, `stale`, `invalid`, `regenerate`.
- Scope: updated prompt and guidance docs.
- Re-read: explicit fallback/remediation steps.

7. Confirm completion evidence is binary

- Search: completion checklist and success criteria statements.
- Scope: this plan file and any linked progress entry.
- Re-read: `## Success Criteria` and `## Testing Strategy` sections.

## Dependencies

- No blocking technical dependencies.
- Input dependency: confirmation of final canonical filename if reviewer prefers a specific naming convention.

## Success Criteria

- A single canonical local machine-context artifact path under `.cortex/memory-bank` is defined and documented.
- Documentation explicitly states artifact is local and git-untracked.
- Artifact is automatically created/updated by the system lifecycle without manual housekeeping steps in the normal path.
- Cortex MCP startup validates artifact-machine binding and raises an explicit actionable signal when mismatch suggests copied workspace state.
- `.cortex/prompts/debug-external-integration.md` includes architecture-aware checks using the local artifact.
- Missing/stale/invalid artifact fallback behavior is documented and actionable.
- Verification checklist items are all satisfiable with pass/fail evidence.

## Testing Strategy

- Target at least 95% checklist completion evidence coverage across defined verification items.
- Unit-level validation equivalent: each required assertion (path, schema keys, untracked policy, auto-housekeeping, startup binding validation, fallback behavior) is independently checked.
- Integration-level validation equivalent: run startup + debug-external-integration walkthrough and confirm architecture branch selection plus binding checks are deterministic.
- Negative cases: artifact missing, artifact stale, artifact invalid, and cross-machine copy mismatch scenarios must yield explicit remediation guidance.
- Validation style follows Arrange-Act-Assert structure for reproducible verification notes, with no blanket skip behavior.

## Risks and Mitigation

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Local artifact path ambiguity | Agents read inconsistent files | Define one canonical path and reject alternatives in guidance |
| Artifact becomes stale | Incorrect architecture assumptions | Add update triggers and stale-data fallback instructions |
| Automatic update overwrites user-provided fields | Loss of machine-specific overrides | Separate auto-detected vs user-confirmed fields with merge/precedence rules |
| Startup mismatch checks produce false positives | Developer friction and warning fatigue | Define stable machine identity fingerprint and clear rebind workflow |
| Accidental commit of local machine data | Leaks machine-specific details into repo history | Document untracked requirement and explicit git-ignore policy |
| Prompt references drift from memory-bank contract | Agents miss required checks | Keep canonical contract wording centralized and referenced from prompt |

## Review Follow-Up Gaps

- [ ] Add dedicated unit tests for `local_environment_context` edge cases (invalid JSON recovery, `deploy_target` merge preservation, idempotency, payload-change boundaries). (evidence: `tests/unit`, `src/cortex/structure/lifecycle/local_environment_context.py`)
- [ ] Replace or implement the `/cortex/rebind_local_environment_context` remediation path so mismatch warning text is actionable. (evidence: `src/cortex/structure/lifecycle/local_environment_context.py`)
- [ ] Export local environment context public symbols from lifecycle package `__init__.py` for API consistency. (evidence: `src/cortex/structure/lifecycle/__init__.py`)

## Partial Progress Log

- 2026-04-17: Defined canonical local environment artifact, startup housekeeping/validation, prompt integration, and tests — files: src/cortex/structure/lifecycle/local_environment_context.py, src/cortex/structure/lifecycle/startup_repair.py, tests/unit/test_startup_repair.py, .cortex/prompts/debug-external-integration.md, .gitignore
