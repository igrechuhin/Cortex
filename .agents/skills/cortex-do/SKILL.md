---
name: cortex-do
description: Implements a Cortex plan on explicit request.
---

# Cortex Do

Run only on an explicit user request. Use the current project's Cortex MCP connection. If it is unavailable, report that Cortex Do requires it and stop.

Read and follow the [canonical Synapse do prompt](../../../.cortex/synapse/prompts/do-loop.md). Pass through the user's plan reference, arguments, and scope.
