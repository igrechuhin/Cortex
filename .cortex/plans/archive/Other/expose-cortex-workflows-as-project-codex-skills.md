---
title: "Expose Cortex workflows as project Codex skills"
component: "codex-skills"
work_type: feature
status: DONE
priority: High
created: 2026-11-21
depends_on: []
execution: agent
---

## Goal

Make the existing Cortex plan, do, and commit workflows discoverable by Codex as three project skills in the Cortex checkout.

## Context

Cortex already has canonical Synapse prompts and a working Cortex MCP connection. The operator wants native project skill discovery without duplicating the workflows or running them from the menu during validation. The earlier commit was stopped. Its final gate was closed separately, and its prepared index must be preserved while this task proceeds.

## Scope

**in_scope**

- Add project-local `cortex-plan`, `cortex-do`, and `cortex-commit` skill entry points.
- Point each skill to its corresponding canonical Synapse prompt and use the existing Cortex MCP.
- Verify native Codex discovery for this checkout without invoking the workflows.
- Record standard Cortex plan and implementation results outside the existing Git index.

**out_of_scope**

- Changes to canonical Synapse workflows, installed plugins, MCP configuration, project or global settings, permissions, Git index, history, or remotes.
- Starting a second Cortex MCP, resuming or clearing the stopped commit pipeline, using another checkout, or touching TradeWing.

## Approach

Use existing project skill conventions under `.agents/skills`. Keep each skill short and intended for explicit invocation. Use relative links to the matching Synapse prompt so that the existing workflow remains authoritative. Require the existing MCP and report a blocker if it is unavailable. For `cortex-commit`, require separate explicit authorization for commit and push.

## Implementation Steps

### Step 1: Add and verify the Cortex project skills

1. Add the three `SKILL.md` files and their discovery metadata. Link each to the matching Synapse prompt.
2. Verify the three names and source paths through the native Codex skills listing or the existing desktop skill menu scoped to this checkout. Do not submit or launch a workflow.
3. Check the three files, their links, and Cortex documentation validation. Compare the existing staged diff and Git revision with the recorded baseline before finalizing.

## Verification Checklist

- Inspect the three new skill directories for matching names, concise descriptions, explicit invocation metadata, and valid relative links.
- Resolve the links to `.cortex/synapse/prompts/plan.md`, `.cortex/synapse/prompts/do.md`, and `.cortex/synapse/prompts/commit.md`.
- Confirm native Codex discovery attributes all three skills to the Cortex checkout and only lists them.
- Confirm the staged diff and Git revision are unchanged, and check that only the new skills and authorized Cortex bookkeeping have changed.

## Dependencies

- The existing Cortex MCP connection, checked-in Synapse prompts, and native Codex project skill discovery.
- The authorized closeout of the stopped commit's final phase, with its report preserved.

## Success Criteria

- Native Codex discovery returns all three requested names from the Cortex project paths.
- Each skill resolves to its corresponding canonical prompt and contains no duplicate workflow steps.
- The verification invokes zero workflows from Codex discovery and makes no Git index or configuration changes.

## Testing Strategy

Cover all three skills with the same discovery and link assertions. Check that they resolve one-to-one to the expected workspace paths. Verify the working changes against the pre-existing staged diff and Git revision. Use the standard Cortex documentation validation for plan and memory-bank consistency. No application-code coverage applies to these Markdown entry points.

## Risks and Mitigation

| Risk | Mitigation |
| --- | --- |
| Default discovery finds a same-named skill from another scope | Inspect the discovered source paths for all three entries. |
| A skill drifts from the canonical workflow | Keep only invocation constraints and a reference to the corresponding Synapse prompt. |
| Verification affects stopped work | Keep verification scoped to the current project and read-only discovery. Check the existing staged diff and retain stop-state evidence. |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
