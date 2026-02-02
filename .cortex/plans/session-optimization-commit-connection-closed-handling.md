# Session Optimization: Commit "Connection Closed" Handling (Blocker)

**Status**: COMPLETE (2026-02-01)  
**Priority**: FIX-ASAP (Blockers ASAP Priority)  
**Created**: 2026-02-01  
**Source**: `.cortex/reviews/session-optimization-2026-02-01T23-07.md` (Recommendation 2)

## Goal

Define explicit "Connection closed" handling in the commit workflow and MCP docs so that when a long-running MCP tool (e.g. `fix_markdown_lint`) completes on the server but the client has already closed the connection, the pipeline can retry once and then perform a documented fallback instead of blocking.

## Context

During a `/commit` run, `fix_markdown_lint(check_all_files=True)` (178+ files) completed on the server and logged "fix_markdown_lint: completed," but when the MCP server tried to send the response, the client had already closed the connection. The transport raised `anyio.ClosedResourceError` and the client saw `{"error":"MCP error -32000: Connection closed"}`. The commit prompt does not tell the agent to retry or fall back for this class of error, so the pipeline blocks or fails without clear guidance.

Root causes identified in the review:

- No guidance in commit prompt for "Connection closed" (retry then fallback).
- MCP failure protocol focuses on tool crashes and invalid JSON; client-initiated closure is a different case (tool succeeded, response undeliverable).
- Long-running tools may finish after the client has closed; no documented "client timeout vs tool duration" guidance.

## Approach

1. **Commit prompt**: Add explicit handling in "MCP Tool Failure" / "Failure Handling": when the tool error indicates "Connection closed" (or "ClosedResourceError" in message/code), retry the tool once; if it fails again with the same class, perform a documented fallback for that step (e.g. for `fix_markdown_lint`, run markdown lint via shell with same scope) and record "MCP connection closed; fallback used" so the pipeline can proceed.
2. **Docs**: Add a short "Client connection closed during long tools" subsection in `docs/mcp-tool-timeouts.md`: explain that long-running tools may complete after the client has closed; "Connection closed" can mean client timeout/disconnect, not necessarily tool failure; recommend retry then fallback.

## Implementation Steps

1. **Edit commit prompt** (`.cortex/synapse/prompts/commit.md`):
   - In "MCP Tool Failure" or "Failure Handling", add: when an MCP tool returns an error whose message or code indicates "Connection closed" or "ClosedResourceError": (1) Retry the tool once. (2) If it fails again with the same class of error, perform a documented fallback for that step (e.g. for `fix_markdown_lint`, run markdown lint via shell with the same scope) and record "MCP connection closed; fallback used" so the pipeline can proceed.
2. **Edit `docs/mcp-tool-timeouts.md`**:
   - Add subsection "Client connection closed during long tools": explain that long-running tools may complete after the client has closed; "Connection closed" can mean client timeout/disconnect, not necessarily tool failure; recommend retry once then fallback (document fallback in commit prompt).
3. **Optional**: In commit Step 12.6 (or "Connection closed" handling text), note that if `fix_markdown_lint(check_all_files=True)` has previously timed out or returned "Connection closed," the agent may run markdown lint on modified/added markdown files only (with a one-line note) to reduce duration.

## Dependencies

- Phase 59 (investigate `fix_markdown_lint` MCP connection closed) addresses server-side investigation; this plan addresses commit workflow and docs so the pipeline can proceed even when client disconnects.
- Existing MCP failure protocol and commit prompt structure.

## Success Criteria

- Commit prompt explicitly instructs: on "Connection closed" (or equivalent), retry once, then fallback and record "MCP connection closed; fallback used."
- `docs/mcp-tool-timeouts.md` contains a "Client connection closed during long tools" subsection with the above semantics.
- Pipeline can complete (or proceed past the step) when the client disconnects after a long tool run, using fallback where defined.

## Testing Strategy

- **Coverage target**: Minimum 95% for any new code (e.g. helpers or docs scripts); prompt/docs changes are not code-covered but are verified by review.
- **Unit tests**: N/A for prompt/docs-only changes.
- **Integration tests**: Optional integration test that runs commit prompt steps and verifies fallback path is documented (e.g. grep for "Connection closed" and "fallback" in commit prompt).
- **Verification**: Manual or automated check that commit prompt contains the new "Connection closed" retry/fallback text and that `docs/mcp-tool-timeouts.md` contains the new subsection.
- **Regression**: Ensure existing commit steps and MCP failure handling still work; no removal of existing failure handling.

## Risks & Mitigation

- **Risk**: Fallback (e.g. shell markdown lint) may diverge from tool behavior. **Mitigation**: Document fallback scope (e.g. same file set) and note "MCP connection closed; fallback used" in commit output so it can be audited.
- **Risk**: Retry could double work. **Mitigation**: Retry only once; second failure triggers fallback.

## Timeline

- Estimate: 1–2 hours (prompt edit + docs subsection + optional Step 12.6 note).

## Notes

- MCP log reference: anysphere.cursor-mcp.MCP user-cortex lines 2687–2739 (`fix_markdown_lint: completed` → TaskGroup error → `ClosedResourceError` in `_send_response`).
- Recommendation 4 (optional narrower scope for Step 12.6) can be a one-sentence addition in the same edit.
