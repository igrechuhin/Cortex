---
title: Investigate Cortex quality gate MCP transport timeout
status: DONE
execution: agent
priority: ASAP
created: 2026-09-16
component: mcp-transport
work_type: investigation
---

## Goal

Recover the outstanding quality-gate outcome and identify why the MCP request expired despite detached-worker heartbeat polling.

## Evidence

The zero-argument run_quality_gate call failed at stdio receive with Request timeout after 30000ms. Pipeline checks configured force_fresh=true and test_timeout=600. The detached job .cortex/.session/pre_commit_result_5738f00f2f71.json still reported running, pid 28131, when inspected. Do not launch duplicate gates while it runs.

The same worker subsequently completed in 109.14 seconds. It reported 8,038 passing
tests, four skipped, and 91.42% coverage; the gate failed on three concrete type
errors in the new budget helper. Those errors were corrected and a focused
Pyright run returned zero errors and warnings. No duplicate worker was launched.
The transport deadline did not stop the server's background work. Final verification
will use a fresh FastMCP client with an explicit 900-second request timeout and
the unchanged 600-second worker timeout.

## Implementation Steps

1. Read the existing detached result and worker log until completion; preserve its actual success or failure output.
2. Trace the client request deadline versus server heartbeat/progress and detached polling. Determine whether the deadline is client configuration or a server transport defect.
3. Apply the smallest verified configuration or transport fix; prove a gate longer than 30 seconds returns its final outcome without duplicate workers.
4. Resume remediation verification using recovered worker outcomes; do not treat the client timeout as a failed or canceled worker.

## Verification

A fresh quality gate exceeding 30 seconds returns an authoritative terminal result. Worker outcome and MCP outcome agree. No duplicate gate is spawned and failed checks remain failures.

## Current Remediation Evidence

Twenty-eight focused context/graph regression tests passed. A fresh Python process exercised the context resource: 3074 actual serialized tokens within 10000, accounting sum correct, cached response byte-identical. Source edits are uncommitted; full quality result and Steps 8–9 are not complete.

## Recommendation

Check or increase the client's MCP request timeout to exceed the configured worker timeout, unless tracing shows heartbeat handling is defective. Server test_timeout does not establish the client transport deadline.

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
