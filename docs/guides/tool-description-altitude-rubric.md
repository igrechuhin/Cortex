# Tool Description "Right Altitude" Rubric

This rubric is used to audit MCP tool descriptions for the **Anthropic context engineering alignment** plan (Step 1). It defines the "Goldilocks zone" between brittle, step-by-step instructions and vague, high-level guidance.

## Scoring Scale (1–5)

| Score | Altitude | Description |
|-------|----------|-------------|
| **1** | Too low (brittle) | Step-by-step instructions that break when context varies; hardcoded sequences; no flexibility. |
| **2** | Low | Mostly procedural; little guidance on when or why; missing input/output expectations or examples. |
| **3** | Moderate | Purpose and main parameters clear; missing when-to-use, examples, or output format. |
| **4** | Right altitude | Clear purpose, input expectations, output format, and when-to-use guidance; may lack examples. |
| **5** | Right altitude + examples | Same as 4, plus embedded examples (USE WHEN, EXAMPLES, RETURNS, or input_examples). |

## Criteria for "Right Altitude"

A tool description at the right altitude:

1. **Purpose** — States what the tool does in one sentence.
2. **When to use** — Guides the agent on when to call this tool (e.g. "USE WHEN").
3. **Input expectations** — Describes parameters, required vs optional, and valid values.
4. **Output format** — Describes success/error shape and key fields (e.g. "RETURNS").
5. **Examples** (for score 5) — Includes natural-language examples and/or structured `input_examples`.

## Red Flags

- **Too low**: "First call X, then Y, then Z" with no rationale; tool-specific jargon without definition.
- **Too high**: "Manages files" or "Does rules" with no guidance on when, how, or what is returned.

## Target

- All tools score **≥ 4** on this rubric.
- At least **20+ tools** have embedded examples (score 5).

## Validation

Run the altitude audit script to verify compliance:

```bash
uv run python .cortex/synapse/scripts/python/check_tool_description_altitude.py
```

The script scores each `@mcp.tool` docstring and reports tools below 4. Exit code 0 when targets are met.

## Reference

- Plan: Anthropic context engineering alignment (`.cortex/plans/plan-anthropic-context-engineering-alignment.md`) — Step 1.
- Source: [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).
