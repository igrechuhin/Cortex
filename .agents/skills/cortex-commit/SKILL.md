---
name: cortex-commit
description: Runs the Cortex commit workflow on explicit request.
---

# Cortex Commit

Run only on an explicit user request. Use the current project's Cortex MCP connection. If it is unavailable, report that Cortex Commit requires it and stop.

Read and follow the [canonical Synapse commit prompt](../../../.cortex/synapse/prompts/commit.md). Pass through the user's arguments and stop at the requested boundary. Commit and push each require explicit user authorization for that action.
