# Session improvements from 2026-03-26T18-37

## Goal

Improve end-of-session analysis signal quality by ensuring context analysis telemetry is consistently available.

## Actions

1. Ensure at least one context-loading analysis call is recorded early in each session.
2. Validate usage-pattern and tools analysis target selection path in the current MCP/CLI environment.
3. Add a lightweight regression check that end-of-session analyze does not return no_data when session activity exists.

## Success Criteria

- End-of-session analysis returns actionable metrics (non-empty calls analyzed) in normal sessions.
- Usage-pattern/tool analysis targets are reliably selectable.
