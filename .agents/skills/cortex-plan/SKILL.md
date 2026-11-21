---
name: cortex-plan
description: Runs Cortex planning and registers a plan on explicit request.
---

# Cortex Plan

Run only on an explicit user request. Use the current project's Cortex MCP connection. If it is unavailable, report that Cortex Plan requires it and stop.

Read and follow the [canonical Synapse plan prompt](../../../.cortex/synapse/prompts/plan.md). Pass through the user's arguments and scope.
