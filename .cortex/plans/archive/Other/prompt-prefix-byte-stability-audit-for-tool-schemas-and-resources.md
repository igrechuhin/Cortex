---
title: "Prompt-Prefix Byte Stability Audit for Tool Schemas and Resources"
component: "core"
work_type: optimize
status: DONE
priority: High
created: 2026-08-06
depends_on: []
---

## Goal

Make the Cortex MCP tool-schema payload and the `cortex://` resource bodies byte-identical across repeated renders, and lock that property with a regression test, so that host prompt caching can reuse them instead of paying a fresh cache write on every session.

## Context

Anthropic prompt caching is a prefix match over the rendered request in the order `tools` → `system` → `messages`. Any byte that changes invalidates the cache from that point onward. Tool schemas render at position zero, ahead of everything else, which makes them the single highest-leverage block in the request: if they are byte-stable they are reused, and if any byte drifts the entire downstream prefix is re-billed at full input price.

Cortex is an MCP server, so it does not build the request and cannot set `cache_control` breakpoints or issue a pre-warming call — that is the host's job. What Cortex fully controls is the *content* it contributes: the tool names, descriptions, and JSON Schemas it registers, and the text served for each `cortex://` resource. Those bytes either are stable or they are not, and today nothing verifies which.

There is direct evidence of drift. A single read of `cortex://rules` in this session returned `"last_indexed": "2026-08-06T13:57:20.352954"` embedded in the resource body — a value that changes on every reindex and therefore differs between reads of otherwise identical content. A repository-wide scan found 113 `datetime.now` / `time.time()` / `uuid4` call sites across `src/cortex/tools/` and `src/cortex/core/`; most are legitimate (task locking, WAL, snapshots), but they have never been separated from the ones that reach agent-visible payloads. Several `json.dumps` call sites also serialize without `sort_keys`, which makes key order dependent on dict construction rather than fixed.

A second, subtler risk is registration order. `tool_registry.py` exposes `get_known_tool_names()`, and `categories.py` enforces a hard cap on registered tool count. If the registered set or its order varies with configuration, feature flags, or set/dict iteration, then two otherwise identical sessions produce different position-zero bytes and neither can reuse the other's cache.

One naming caution: `src/cortex/core/cache_warming.py` already exists and refers to Cortex's internal `AdvancedCacheManager` file cache. That is a completely unrelated subsystem. This plan concerns the *host's prompt cache* and deliberately avoids the phrase "cache warming" to prevent the two from being conflated.

## Scope

**in_scope**

- Classify every `datetime.now` / `time.time()` / `uuid4` / `utcnow` call site in `src/cortex/tools/` and `src/cortex/core/` as either agent-visible payload or internal-only.
- Remove or relocate volatile values from tool descriptions, tool JSON Schemas, and `cortex://` resource bodies, including the `last_indexed` field in the rules resource.
- Make tool registration order deterministic and independent of set/dict iteration and configuration.
- Make JSON serialization deterministic (`sort_keys`) for any payload that reaches an agent-visible surface.
- A regression test asserting that two independent renders of the tool-schema payload are byte-identical.
- A regression test asserting that two consecutive reads of each `cortex://` resource, with no intervening state change, are byte-identical.
- A short document recording which surfaces are contractually byte-stable and why.

**out_of_scope**

- Any change to how the host builds requests, sets `cache_control` breakpoints, or paces requests — Cortex cannot control these.
- Adding a pre-warming request or any client-side caching behavior.
- `src/cortex/core/cache_warming.py` and the internal `AdvancedCacheManager`; unrelated subsystem.
- Removing timestamps from genuinely stateful surfaces: WAL entries, task locks, file snapshots, session handoffs, and progress entries all legitimately vary.
- Reducing tool count or consolidating tools (covered by the agentic evaluation harness plan).
- Measuring realized cache-hit rates in a live host session.

## Approach

Audit first, then fix, then lock. The audit is a classification pass, not a deletion pass: the great majority of the 113 timestamp call sites are correct and must stay. The deliverable of the audit stage is a written list splitting call sites into "reaches an agent-visible payload" and "internal state", so that the fix stage touches only the first group and the second group is explicitly justified.

For each genuinely volatile value on an agent-visible surface, prefer relocation over deletion. Diagnostic values like `last_indexed` are useful; they simply must not sit inside a block that is expected to be byte-stable. Move them to a dedicated diagnostics operation that a caller requests explicitly, rather than embedding them in the body every reader receives.

Determinism of ordering is enforced by construction: sort tool names before registration, sort glob results, and pass `sort_keys=True` wherever a payload is serialized for an agent. This is cheap and eliminates a whole class of drift that is otherwise invisible until it costs money.

The regression test is the durable artifact and the real point of the plan. Rendering the tool-schema payload twice within one process can pass while cross-process order still varies, so the test must defeat hash seeding — either by rendering in two subprocesses with different `PYTHONHASHSEED` values, or by rendering twice with the relevant registries rebuilt from scratch. Without that, the test gives false confidence.

## Implementation Steps

1. Enumerate every `datetime.now`, `datetime.utcnow`, `time.time()`, and `uuid4` call site in `src/cortex/tools/` and `src/cortex/core/`, and write the classification list (agent-visible vs internal) to a working document.
2. Identify every code path that produces a tool `description` or `input_schema`, and confirm none interpolates a timestamp, hostname, path, counter, or session identifier.
3. Identify every `cortex://` resource handler and capture its current rendered body for comparison.
4. Remove `last_indexed` from the `cortex://rules` body and expose it instead through an explicit diagnostics path; update any caller that reads it.
5. Apply the same relocation to every other volatile value the audit flagged on an agent-visible surface.
6. Make tool registration order deterministic: sort tool names at the registration site, and confirm `get_known_tool_names()` and `get_known_script_names()` return sorted output.
7. Add `sort_keys=True` to every `json.dumps` call whose output reaches a tool result, a tool schema, or a resource body; leave internal serialization unchanged unless it feeds those surfaces.
8. Confirm no tool is registered conditionally on configuration, environment, or feature flags; if any is, record it as a documented, intentional exception.
9. Write the tool-schema byte-stability test: render the payload in two subprocesses with different `PYTHONHASHSEED` values and assert the serialized bytes are identical.
10. Write the resource byte-stability test: read each `cortex://` resource twice with no intervening state change and assert identical bytes.
11. Write `docs/` guidance recording which surfaces are contractually byte-stable, why it matters for the host prompt cache, and the explicit distinction from `core/cache_warming.py`.
12. Run `run_quality_gate()` and `run_docs_gate()` and resolve every finding.

## Verification Checklist

- Step 1: re-run the enumeration greps after the fix stage and confirm every remaining agent-visible hit appears in the justified-exception list.
- Step 4: read `cortex://rules` twice in one session and diff the two bodies; the diff must be empty.
- Step 6: run `get_known_tool_names()` under at least two different `PYTHONHASHSEED` values and assert identical ordering.
- Step 7: grep for `json.dumps` across `src/`; re-read each hit and confirm it is either `sort_keys=True` or documented as internal-only.
- Step 8: grep the registration site for `if` guards around tool registration; re-read each hit.
- Steps 9–10: verify the tests fail when a timestamp is deliberately reintroduced — a stability test that cannot fail is worthless.
- Step 12: re-read every file the gates modified.

## Dependencies

- None on other Cortex plans.
- No external dependencies.

## Success Criteria

- Two independent renders of the tool-schema payload, under different hash seeds, are byte-identical.
- Two consecutive reads of every `cortex://` resource with no state change are byte-identical.
- `cortex://rules` no longer embeds `last_indexed` in its body, and the value remains reachable through an explicit diagnostics path.
- Every remaining timestamp or identifier on an agent-visible surface is listed with a written justification.
- Both stability tests demonstrably fail when volatility is reintroduced.
- Test coverage for changed modules is at least 95%; `run_quality_gate()` and `run_docs_gate()` report zero errors.

## Testing Strategy

Target 95% coverage on changed modules, AAA pattern, fully deterministic.

- Unit — ordering: assert `get_known_tool_names()` and `get_known_script_names()` return sorted output regardless of underlying filesystem or dict order.
- Unit — serialization: assert flagged `json.dumps` call sites emit identical bytes for semantically equal inputs built in different key orders.
- Integration — tool-schema stability: two subprocesses with differing `PYTHONHASHSEED`, assert byte equality of the serialized schema payload.
- Integration — resource stability: parametrized over every `cortex://` resource, read twice, assert byte equality.
- Negative — mutation guard: a test that injects a timestamp into a schema description and asserts the stability test fails, proving the check has teeth.
- Regression — the existing suite passes unchanged; the rules-resource consumers still resolve `last_indexed` from its new location.

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Over-eager timestamp removal breaks stateful subsystems | WAL, locking, or snapshots lose required time data | Audit stage classifies before the fix stage touches anything; WAL, locks, snapshots, and handoffs are explicitly out of scope |
| Removing `last_indexed` breaks a consumer | Runtime error or lost diagnostics | Grep all consumers in step 4 and relocate rather than delete; keep the value reachable |
| Stability test passes in-process but order still varies across processes | False confidence, no real protection | Test renders across subprocesses with differing hash seeds; mutation-guard test proves it can fail |
| Confusion with the existing internal `cache_warming.py` | Wrong subsystem modified | Explicit out-of-scope entry and a documented distinction in the guidance doc |
| Realized cache benefit is unmeasurable from the server side | Effort with unverifiable payoff | Success criteria are byte-stability properties Cortex fully controls, not host-side hit rates |
| Some volatility is genuinely required on an agent-visible surface | Cannot reach full stability | Documented-exception list is an accepted outcome, not a failure |
