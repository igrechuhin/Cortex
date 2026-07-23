---
title: "Prompt-Cache Payload Stability for Cached MCP Resources"
component: "context-optimization"
work_type: "optimize"
status: PENDING
priority: "Medium"
created: "2026-07-23"
depends_on: []
---

## Goal

Make the byte content of `cortex://rules` and `cortex://context` deterministic across repeated
reads of unchanged underlying state, and add an automated audit that flags volatile content
(timestamps, random IDs) introduced into their payload-construction code paths — so the
`cache_control` hints already wired into those two resources actually yield Anthropic prompt-cache
hits instead of silent prefix invalidation.

## Context

An external document (user-supplied, `~/Downloads/I want a structured document_plan for this
integration.md`) proposed integrating ideas from `audit-prompt-caching` into Cortex: a custom
Anthropic message compiler with `cache_control` anchors on content blocks, interception of
`anthropic_api_response.usage` fields, and OpenAI-style 1024-token block-aligned truncation.

Verifying the codebase before planning found two things that reshape this proposal:

1. **Cortex is a pure FastMCP server** (`src/cortex/server.py` uses `FastMCP`) with no Anthropic or
   OpenAI SDK dependency anywhere in `src/` or `pyproject.toml`, and no code path that constructs a
   `messages.create(...)` call or reads a raw API `usage` object. The IDE/API client (Claude Code,
   Cursor) — not Cortex — assembles the Anthropic messages array and receives the API response.
   Most of the source document's proposal (message compiler, block-aligned truncation, intercepting
   `cache_read_input_tokens` from an API response) targets a surface Cortex does not own.
2. **The one idea that Cortex does own — resource-level cache hints — is already implemented.**
   Plan `.cortex/plans/archive/Other/add-anthropic-prompt-cache-control.md` (archived, with a
   "Partial Progress Log" dated 2026-04-03) added `CORTEX_RULES_RESOURCE_READ_META` and
   `CORTEX_CONTEXT_RESOURCE_READ_META` (`src/cortex/core/constants.py:168-173`), wired them into
   `@mcp.resource(uri="cortex://rules", meta=...)` (`src/cortex/tools/synapse/rules_operations.py:380`)
   and `@mcp.resource(uri="cortex://context", meta=...)` (`src/cortex/tools/optimization/handlers.py:352`),
   added a `TTLCache`-backed in-process cache for both, and a regression test
   (`tests/unit/test_mcp_resource_cache_control.py`). This is the FastMCP-supported mechanism
   (`resources/read` → `_meta`) for forwarding `cache_control` hints to an MCP client.

What remains unaddressed: `cache_control` hints only produce Anthropic cache hits if the payload
text is byte-identical across reads of unchanged state, since Anthropic caching is exact-prefix
matching. Nothing today verifies that `load_context()` and `get_relevant_rules()` produce
deterministic output, and nothing prevents a future change from embedding a call-time value (e.g.
an inline timestamp or generated ID) into either payload, which would silently defeat the caching
investment already made without any test failing.

## Scope

**in_scope**

- Audit `load_context()` (`src/cortex/tools/optimization/handlers.py`) and `get_relevant_rules()`
  (`src/cortex/tools/synapse/rules_operations.py`) for non-deterministic ordering (unsorted dict/set
  iteration, unsorted globs/file lists) and for any per-call volatile content (current-time strings,
  random/UUID values, PIDs) that would change output bytes without an underlying state change.
- Fix any non-deterministic ordering found by enforcing a stable, explicit sort order in the
  aggregation step (e.g., alphabetical by file or rule name), matching the pattern already used for
  reproducible output elsewhere in the codebase.
- Add a reusable audit function (e.g. `audit_cache_payload_stability(text: str) -> list[str]`)
  detecting volatile-content patterns (inline `datetime.now()`/`today is`-style strings, `uuid4()`
  literals, raw PIDs) and wire it into the existing quality-gate pipeline
  (`src/cortex/tools/execution/pre_commit_zero_arg_tools.py`, or the nearest existing check
  registration point for `run_quality_gate()`) so a future regression fails the gate automatically.
- Unit tests: two consecutive calls to `load_context()` / `get_relevant_rules()` against the same
  underlying memory-bank/rules state produce byte-identical strings; the audit function flags a
  synthetic volatile-pattern fixture and passes on a stable fixture.

**out_of_scope**

- Any Anthropic/OpenAI API client code inside Cortex (message-array compilation, `cache_control` on
  message `content[]` blocks, reading `usage.cache_read_input_tokens` from an API response) — this
  is the IDE/API client's responsibility, not Cortex's; Cortex has no API client dependency and no
  code path that sees a raw completion response.
- OpenAI-style fixed 1024-token block-aligned truncation/compaction — inapplicable to Anthropic's
  exact-prefix caching model, which is what this project's MCP clients use.
- Re-implementing or modifying the already-completed `_meta`/`cache_control` resource-hint wiring,
  `TTLCache` instances, or `MCP_STATIC_RESOURCE_CACHE_TTL_SECONDS` from
  `add-anthropic-prompt-cache-control` — only the payload-determinism gap on top of that existing
  work is in scope here.
- New third-party dependencies.

## Approach

Treat this as a correctness/regression-prevention pass on top of already-shipped caching
infrastructure rather than a new caching feature. First inspect the two resource handlers for
sources of non-determinism (dict ordering, glob ordering, embedded call-time values) and fix any
found with explicit deterministic sorting — this is the direct analogue of the source document's
"static prefix sorting" idea, scoped to what Cortex actually assembles. Second, add a small,
dependency-free audit helper that scans generated payload text for volatile-content regexes and
register it as an additional check inside the existing `run_quality_gate()` machinery, so future
edits to either resource handler cannot silently reintroduce non-determinism without a test/gate
failure. No new modules, message compilers, or telemetry surfaces are introduced — everything is a
targeted addition to the two existing resource-handler files and the existing quality-gate check
registry.

## Implementation Steps

1. Read `load_context()` in `src/cortex/tools/optimization/handlers.py` end-to-end; identify every
   point where memory-bank files, wiki pages, or other inputs are aggregated into the output string,
   and check whether iteration order is guaranteed deterministic (explicit `sorted()`/fixed list) or
   depends on filesystem/dict iteration order.
2. Read `get_relevant_rules()` in `src/cortex/tools/synapse/rules_operations.py` end-to-end with the
   same lens — rule file discovery/ordering and any manifest-driven ordering.
3. Where non-deterministic ordering is found, add explicit `sorted(...)` (by filename or rule name)
   at the aggregation point so output ordering is a pure function of the current file set's names,
   not of filesystem/dict iteration order.
4. Grep both files (and any helper they call into) for volatile-content sources: `datetime.now()`,
   `time.time()`, `uuid`, `os.getpid()`, or any f-string interpolating one of these directly into the
   returned payload text. Remove or relocate any found (payload text must depend only on persisted
   file/rule state, not on wall-clock time or process identity).
5. Add `audit_cache_payload_stability(text: str) -> list[str]` (new small function, colocated with
   the other quality-gate check helpers under `src/cortex/tools/execution/` or wherever
   `run_quality_gate()`'s check registry lives) returning a list of human-readable violation
   messages for regexes matching `datetime.now`, `time.time()`, `uuid4()`/`uuid1()`, `getpid()`, and
   raw ISO-timestamp literals appearing in a call-time-generated (not persisted-file) context.
6. Register the new audit as an additional check step inside `run_quality_gate()`'s check pipeline
   (or `autofix()`'s reflection path, whichever existing extension point fits with the least
   structural change) so it runs automatically; a violation should surface as a gate failure with
   the file/line and matched pattern.
7. Add unit tests in `tests/unit/` (colocated near `test_mcp_resource_cache_control.py` or the
   handlers'/rules_operations' existing test modules): (a) two sequential calls to `load_context()`
   with unchanged fixture state return identical strings; (b) two sequential calls to
   `get_relevant_rules()` with unchanged fixture state return identical strings; (c)
   `audit_cache_payload_stability()` flags each volatile pattern on a synthetic fixture and returns
   an empty list on a stable fixture.
8. Run `run_quality_gate()` and confirm `preflight_passed: true` with the new check included and no
   regressions in the existing `test_mcp_resource_cache_control.py` suite.

## Verification Checklist

- Step 3: re-read `load_context()` and `get_relevant_rules()` after edits; search for any remaining
  unsorted iteration over files/rules/memory-bank sections in both files.
- Step 4: re-run the volatile-content grep (`datetime.now\(\)|time.time\(\)|uuid[14]\(\)|getpid\(\)`)
  across `src/cortex/tools/optimization/handlers.py` and `src/cortex/tools/synapse/rules_operations.py`
  to confirm zero matches remain in payload-construction paths.
- Step 6: re-read the `run_quality_gate()` check registry file to confirm the new audit function is
  registered and reachable, not just defined.
- Step 7: re-read the new test file(s) to confirm all three test cases (context determinism, rules
  determinism, audit function true/false positives) are present and use the AAA pattern.
- Step 8: re-run `run_quality_gate()` a second time after the first pass to confirm the result is
  stable (not flaky) and `test_mcp_resource_cache_control.py` still passes unmodified.

## Dependencies

- `.cortex/plans/archive/Other/add-anthropic-prompt-cache-control.md` — prior (already-implemented)
  plan that added the `cache_control` `_meta` hints this plan builds determinism guarantees on top
  of. Informational reference only; not a blocking dependency (that work is already merged).
- `src/cortex/tools/optimization/handlers.py`
- `src/cortex/tools/synapse/rules_operations.py`
- `src/cortex/core/constants.py` (read-only reference for `CORTEX_*_RESOURCE_READ_META`)
- `src/cortex/tools/execution/pre_commit_zero_arg_tools.py` (or equivalent quality-gate check
  registry — confirm exact registration point via Grep during implementation)
- `tests/unit/test_mcp_resource_cache_control.py` (existing regression suite to keep green)

## Success Criteria

1. `load_context()` called twice in succession against unchanged fixture state returns byte-identical
   strings (asserted by a new unit test).
2. `get_relevant_rules()` called twice in succession against unchanged fixture state returns
   byte-identical strings (asserted by a new unit test).
3. `audit_cache_payload_stability()` exists, is unit-tested (true positive and true negative), and is
   invoked as part of `run_quality_gate()`'s check pipeline.
4. `run_quality_gate()` returns `preflight_passed: true` with the new check active and zero
   regressions in `test_mcp_resource_cache_control.py`.
5. No new third-party dependency and no Anthropic/OpenAI API client code added to `src/cortex/`.

## Testing Strategy

- Unit tests only (no integration/E2E surface changes); AAA pattern; target ≥95% coverage on the new
  `audit_cache_payload_stability()` function and any modified branches in `load_context()` /
  `get_relevant_rules()`.
- Positive case: stable fixture (fixed memory-bank/rules content) → two calls produce identical
  output.
- Negative case: fixture instrumented to previously iterate a `dict`/`set` in undefined order (if
  found in Step 1-2) → confirm the fix produces stable output regardless of insertion order.
- Audit function: parametrized test over each volatile-pattern regex (positive) and one representative
  stable payload sample (negative), matching the AAA pattern used elsewhere in the test suite.
- Regression: full `run_quality_gate()` run after all changes; existing
  `test_mcp_resource_cache_control.py` must pass unmodified.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Step 1-2 finds no actual non-determinism (both handlers already sort deterministically) | Reduce scope to the audit function + tests only; note the negative finding in the plan's progress log rather than inventing a fix for a non-issue |
| New quality-gate check produces false positives on legitimate uses of `datetime`/`uuid` elsewhere in the codebase | Scope the audit regex to the two specific payload-construction files/functions, not a codebase-wide scan |
| Registration point for `run_quality_gate()` checks is unclear or requires broader refactor | Grep the existing check registry first (Step 6); if wiring is non-trivial, fall back to a standalone test-only enforcement (Success Criteria 1-2) and defer gate wiring to a follow-up plan |
| Fix to ordering changes cache-relevant byte content once (one-time cache invalidation) | Acceptable and expected — a one-time cache miss to establish a now-stable prefix is the intended outcome |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
