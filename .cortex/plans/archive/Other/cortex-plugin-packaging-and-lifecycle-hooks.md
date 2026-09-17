---
title: Package Cortex commands and thin lifecycle hooks as a plugin
component: distribution
work_type: feature
status: DONE
priority: High
created: 2026-09-16
depends_on: []
execution: agent
---

## Goal

Deliver installable Cortex plugin packaging for Claude Code and Codex plugin hosts, exposing native workflow commands and bounded lifecycle hooks while retaining stateful operations in the existing MCP server.

## Context

The user selected plugin packaging plus small lifecycle hooks, not an MCP replacement. Ponytail provides a packaging reference: <https://github.com/dietrichgebert/ponytail>. Host capabilities and manifest schemas must be verified against current official documentation before implementation; parity between hosts is not assumed.

Existing reuse points include `src/cortex/tools/synapse/prompts_registration.py`, canonical Prompt sources, `src/cortex/setup/hook_models.py`, `hook_templates.py`, and `post_edit_hook_runtime.py`. No plugin manifests were found in the repository's standard plugin directories during planning. This plan authorizes no implementation during its creation.

Implementation and verification evidence (2026-09-17): reproducible local packages
now derive four skills from canonical Synapse content and include the built wheel.
Claude 2.1.273 validates/discovers the package; Codex 0.153.4 installs the native
`.codex-plugin` layout, connects 14 Cortex tools, invokes the planning procedure,
and resolves two concurrent workspaces independently. Startup, native pre-compaction
persistence, and fresh-process resume succeeded. A temporary 0.2.0 → 0.2.1 upgrade
and uninstall preserved ten state files plus unrelated settings in both hosts.
Repository version remains 0.2.0. See `docs/guides/plugins.md` for commands and proof.

Acceptance change: the user explicitly approved cheap best-effort deduplication
instead of strict exactly-once lifecycle delivery. Keep the existing adapters:
Codex uses session/turn/trigger; Claude uses transcript metadata. Identical
fingerprints are suppressed using receipts in the existing handoff. Same-turn
Codex compactions can be skipped, and changed Claude transcript metadata can
cause a repeated write. Startup replay suppression remains process-local.
These are accepted limitations, not unresolved blockers. No transcript parser,
new state store, automatic retries, or stronger delivery guarantee is added.

Authenticated Claude verification (2026-09-17) removed the login blocker.
The actual host discovered all four workflows, connected 14 Cortex tools, and
`/cortex:plan` created and registered a real smoke plan. Native startup supplied
the workspace focus; `/compact` persisted a real handoff; fresh-process resume
restored its snapshot. An injected filesystem error produced Claude's visible
non-blocking PreCompact failure notice, including the unsaved-handoff warning;
compaction continued and the prior handoff was preserved.
An unrelated startup hook and the Cortex hook each ran once in a coexistence
smoke; both context markers reached the model without model tool or gate calls.

Verification used a disposable workspace, session-only plugin loading, empty
setting sources, and the bundled MCP launcher explicitly registered under its
plugin-scoped name with `--strict-mcp-config`, excluding unrelated user servers.
Evidence: `.cortex/.session/claude-plugin-native-evidence.json`.
No product code changed during this authenticated verification pass.

The last full quality worker passed eight checks, 8,100 tests (four skips),
91.71% overall coverage, and 99.26% statement coverage across the two changed hook
runtime modules; 48 focused regressions passed. These results remain applicable
to the unchanged product code. Rebuilt-wheel MCP/CLI error smokes, Claude manifest
validation, and the docs gate passed. Completion is against the explicitly
approved best-effort contract, not a strict exactly-once guarantee.

## Scope

**in_scope**

- Host-native plugin manifests, MCP launch configuration, and discoverable Cortex workflow commands backed by canonical Synapse content.
- Minimal supported session-start/resume and pre-compaction handoff hooks, delegating state changes to existing Cortex operations.
- Installation, update, coexistence, disable/uninstall behavior, and end-to-end host verification.

**out_of_scope**

- Replacing MCP, rewriting workflow orchestration, or creating another state store.
- New hook DSLs, background services, per-prompt context injection, or duplicated quality gates.
- Automatic commits/pushes, marketplace publication, or editing unrelated user configuration.
- Analysis serialization repair, which remains its own registered blocker.

## Approach

Use native host packaging and reuse Cortex's current command and hook ownership. Package or generate host command entries from canonical sources rather than maintaining copied workflow instructions by hand. Keep plan, memory, rules, quality, and pipeline state in MCP. Hook adapters carry only validated event context and bounded calls to existing operations.

Default to explicit commands for expensive work. Startup hooks provide concise orientation; pre-compaction hooks preserve a bounded handoff only where the host supports it. Unsupported events must be documented and retain an explicit command alternative, not silently advertised as working. Do not add dependencies unless native features and the existing runtime cannot satisfy the verified host contract.

## Implementation Steps

1. Verify both hosts' current plugin, command, MCP, and event schemas. Map the existing Cortex installer, prompt manifests, hook models/runtime, and ownership of state. Record exact supported events and command names before editing; escalate any unsupported requested host rather than silently narrowing scope.
2. Add minimal manifests and reproducible package assembly. Include required Synapse content and a documented supported MCP launch path. Verify a clean install without assuming a developer checkout or working-directory-specific paths.
3. Expose canonical Cortex workflows, including plan, do, review, and commit, through native discovery. Preserve their authorization semantics: discovering a commit command never authorizes committing. Avoid duplicate registration when legacy MCP prompt discovery is also enabled.
4. Wire supported startup/resume and pre-compaction events through existing operations. Bound time and output, prevent recursive invocation, apply best-effort deduplication with documented limits, resolve the correct workspace, and retain actionable diagnostics when MCP is unavailable. Never claim a handoff was saved when persistence failed.
5. Preserve user-owned settings and existing hook behavior during install/update. Make disable/uninstall remove only plugin-owned configuration and leave memory, plans, and session history intact. Document migration from existing setup without running two copies of the same hook.
6. Exercise clean installation, command discovery and invocation, hooks, update, and uninstall in both actual hosts. Run focused regressions and the existing gates; update install/troubleshooting documentation. Stop when every supported behavior below is verified.

## Verification Checklist

- [x] Both manifests validate against current host schemas; installed assets resolve outside this checkout.
- [x] Native command discovery lists Cortex workflows, and invocation runs the canonical procedure.
- [x] Startup/resume is bounded, suppresses repeated events within one process, and does not mutate unrelated workspaces; repeated orientation across command processes is accepted.
- [x] Supported pre-compaction events persist a real handoff with best-effort fingerprint deduplication; same-turn suppression and metadata-driven replay writes are accepted, and failures remain visible.
- [x] Missing MCP, malformed events, paths containing spaces, and concurrent workspaces are handled safely.
- [x] Existing hooks are reused without duplicate execution; no unconditional test or quality run occurs per prompt.
- [x] Update and uninstall preserve user configuration and all Cortex state.
- [x] Actual host smoke evidence, focused regressions, and quality/docs gates pass.

## Dependencies

Current host plugin documentation and runtimes; existing Cortex MCP server, Synapse content, and hook infrastructure. Prefer executing the analysis blocker first operationally, but packaging has no artificial code dependency on analytics. Missing host verification capability is an explicit completion blocker, not permission to claim tested support.

## Success Criteria

A user can install the package in each supported target host, discover and run Cortex Slash commands, observe the supported lifecycle hooks, and remove the package without losing project state. Stateful behavior has one owner in MCP; no parallel orchestration system is introduced. Host-specific capability differences are documented and verified. A Session is the execution context; a Handoff is its persisted continuation record, not another Session.

## Testing Strategy

Use actual host installation and CLI interaction as primary proof. Add behavior-level AAA regressions for duplicate events, failure handling, workspace containment, and configuration preservation; target at least 95% coverage of changed runtime behavior. Schema validation alone is not sufficient. Do not pad tests with manifest string or mock-forwarding assertions.

## Risks and Mitigation

- Host API drift: verify official schemas and record tested versions before implementation.
- Duplicate or recursive hooks: reuse existing registration and verify repeated-event behavior.
- Blocking startup: finite deadlines, bounded output, and explicit expensive commands.
- Configuration loss: retain unrelated settings and exercise update/uninstall against customized fixtures.
- Installation-root versus project-root confusion: resolve both separately and test multiple workspaces.
- Packaging drift: derive commands from canonical Synapse sources and validate packaged assets.
