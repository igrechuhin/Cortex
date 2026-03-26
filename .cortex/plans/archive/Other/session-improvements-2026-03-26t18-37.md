# Session improvements from 2026-03-26T18-37

## Status

IN_PROGRESS

## Goal

Improve end-of-session analysis signal quality by ensuring context analysis telemetry is consistently available.

## Actions

1. Ensure at least one context-loading analysis call is recorded early in each session.
2. Validate usage-pattern and tools analysis target selection path in the current MCP/CLI environment.
3. Add a lightweight regression check that end-of-session analyze does not return no_data when session activity exists.

## Progress Notes (2026-03-26)

- Completed: normalized analysis target selection and alias routing for usage-pattern/tools prompts/rules flows with regression tests.
- Completed: added idempotent early-session telemetry seeding in `session_start` and regression tests so active sessions do not produce false `no_data` due to missing context-call telemetry.
- Remaining: add lifecycle-level regression coverage for end-of-session analyze path to validate `no_data` prevention across MCP/CLI mixed entrypoints.

## Success Criteria

- End-of-session analysis returns actionable metrics (non-empty calls analyzed) in normal sessions.
- Usage-pattern/tool analysis targets are reliably selectable.
