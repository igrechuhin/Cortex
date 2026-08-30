---
title: "Document MCP-unavailable fallback for read-only audits"
component: "AGENTS + troubleshooting guidance"
work_type: docs
status: PENDING
priority: Medium
created: 2026-03-20
depends_on: []
---

## Goal

Provide an explicit, auditable fallback workflow when MCP discovery/execution is unavailable, without allowing unsafe writes.

## Context

MCP-first guidance is mandatory, but constrained environments can present unavailable tool/resource states. A documented fallback reduces ambiguity and inconsistent behavior.

## Implementation Steps

1. Define connectivity preflight and diagnostic steps.
2. Define allowed fallback scope (read-only analysis only) and prohibited actions (stateful writes).
3. Add remediation guidance and escalation path for restoring MCP connectivity.
4. Link fallback policy from AGENTS and troubleshooting.

## Verification Checklist

- Step 1:
  - What to search for: MCP preflight/health check instructions
  - Search scope: `AGENTS.md`, troubleshooting docs
  - Files to re-read: `AGENTS.md`, `docs/guides/troubleshooting.md`
- Step 2:
  - What to search for: explicit read-only fallback boundaries
  - Search scope: `AGENTS.md`, docs policies
  - Files to re-read: `AGENTS.md`
- Step 3:
  - What to search for: remediation and escalation actions
  - Search scope: troubleshooting/docs
  - Files to re-read: `docs/guides/troubleshooting.md`
- Step 4:
  - What to search for: cross-links between docs
  - Search scope: onboarding and troubleshooting docs
  - Files to re-read: `README.md`, `AGENTS.md`, troubleshooting docs

## Dependencies

- None; documentation-first improvement.

## Success Criteria

- Fallback behavior is explicit, consistent, and auditable.
- Agents can complete read-only audits when MCP is unavailable without policy violations.
- Connectivity restoration steps are documented and discoverable.

## Testing Strategy (95% coverage target)

- Add docs/tests for fallback reference checks if docs-validation tooling supports it.
- Verify docs gate passes with new policy content.
- Keep >=95% coverage for touched docs-validation logic.
