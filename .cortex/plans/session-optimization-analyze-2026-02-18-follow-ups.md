# Session Optimization: Analyze 2026-02-18 Follow-ups

## Status

PENDING

## Source

Created from end-of-session analysis report: `.cortex/reviews/session-optimization-2026-02-18T21-03.md`.

## Goals

1. **Step 12 and MCP stability**: Align with existing roadmap plan "Session Optimization: MCP Connection Stability and Fallback Script Improvements". Ensure Step 12 ordering, retry/backoff for 12.5 and 12.7 on connection close, and user guidance to reconnect Cortex MCP and re-run commit when tools unavailable.
2. **load_context for non-trivial tasks**: In implement/commit/analyze prompts, require non-zero token_budget for refactor/fix/debug/implement (10k–15k fix/debug, 20k–30k implement/add). Document zero-budget/zero-files as configuration error in troubleshooting and context-effectiveness reporting.
3. **manage_file contract**: In memory-bank-updater and commit/analyze orchestration, require every manage_file call to include file_name and operation; add pre-step or documentation that flags manage_file({}) or missing required params.

## References

- Session optimization report: `.cortex/reviews/session-optimization-2026-02-18T21-03.md`
- Roadmap: Session Optimization: MCP Connection Stability and Fallback Script Improvements
- Memory bank workflow rule; commit prompt Pre-Action Checklist
