# AI code comments and BELIEF annotations

## AI Comment Convention

Use `# AI:` on its own line **before** unobvious logic, agent-specific decisions, surprising dependencies, or optimizations that are easy to misread in review. The text should explain **why** the code is written this way (intent, tradeoffs, invariants), not restate **what** the next line does.

## BELIEF Declaration Convention

Use `# BELIEF:` on its own line to document assumptions about runtime state, configuration, or environment that the implementation relies on. Format: `# BELIEF: <assumption in plain language>`. Update or remove the BELIEF when the code or its preconditions change so the annotation stays true.

## When NOT to use

Do not annotate self-evident code. Avoid stacking annotations: aim for at most one `# AI:` or `# BELIEF:` per roughly ten lines of new agent-written code in a region unless multiple distinct decisions need separate notes.

## Format

Place `# AI: <why, not what>` or `# BELIEF: <assumption>` on its own line immediately above the block they apply to (or directly above the single line, if the note is line-local). Use the same `#` comment style as the surrounding language (e.g. `#` in Python, `//` in C-style languages where project conventions allow).
