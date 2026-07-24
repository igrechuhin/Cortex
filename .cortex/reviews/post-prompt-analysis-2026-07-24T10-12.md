# Post-Prompt Analysis Report — 2026-07-24T10-12

## Summary

This is a standalone invocation of the post-prompt self-improvement hook, not
chained after a specific completed prompt with visible session history in
this agent's context. The hook agent's available toolset in this invocation
does not include a generic MCP resource-read tool (e.g. `ReadMcpResource`),
so `cortex://analysis` could not be queried for Steps 4-6.

## Context Effectiveness (Step 4)

Context effectiveness analysis unavailable (no resource-read tool available
in this invocation's toolset).

## Session Optimization (Step 5)

Session optimization analysis unavailable (no resource-read tool available;
usage_patterns target could not be queried). No multi-goal session scope
risk could be assessed from available data.

## Tools Optimization (Step 6)

Tools optimization skipped (no usage data available in this invocation).

## Memory Bank Compaction (Step 8)

Compaction skipped (not required for this prompt; no prior full-session
compaction context available to confirm status).

## Post-Prompt Hook Result

| Artifact Type | Produced | Location or Notes |
|---------------|----------|-------------------|
| Skill         | No       | No actionable recommendations — analysis data unavailable |
| Plan          | No       | No actionable recommendations — analysis data unavailable |
| Rule          | No       | No actionable recommendations — analysis data unavailable |
