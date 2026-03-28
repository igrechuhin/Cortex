# Synapse and Cursor final report templates

This guide defines the **canonical markdown layout** for agent-to-user **final reports** at the end of Synapse prompts and related Cursor agent instructions.

## MCP JSON vs user-facing markdown

- **MCP tool responses** are JSON payloads returned to the client (fields such as `status`, structured results, errors). Their shape is a separate concern; see the archived Phase 75 plan [phase-75-unify-response-format.md](../../.cortex/plans/archive/Phase75/phase-75-unify-response-format.md) for unifying tool response format.
- **User-facing final reports** are the last narrative the user reads in chat: markdown with headings, lists, and optional tables. This document applies **only** to that markdown narrative—not to tool JSON.

Follow [markdown-formatting.md](markdown-formatting.md): use real heading syntax (`##`, `###`) for section titles; do not use bold alone as a heading (MD036).

## Base template (fixed section order)

Every final report should use these sections in **this order**. Omit a section only when it truly does not apply; if nothing to say, use a one-line explicit negative (for example, `None` under blockers).

In the user-visible message, the six blocks below are **`##` headings** (optionally nested under a single top-level `## Final report` if the prompt requires a wrapper). Subsections inside a block use `###` per [markdown-formatting.md](markdown-formatting.md).

```markdown
## Status

✅ <one-line summary>

## Scope

<prompt or command name>

## What ran

- <action or phase> — pass | fail | skipped
- …

## Key results

- <artifacts, hash, files, counts — prompt-specific>

## Memory bank and roadmap

<what changed, or: Not updated>

## Blockers and follow-ups

None
```

### Status

- First line: one of ✅ (success), ⚠️ (partial / blocked with salvageable outcome), ❌ (failed or aborted).
- Same line or immediately below: **one-line summary** of the outcome (what the user should remember).

### Scope

- Prompt name, slash command, or agent role; the user-visible **label** for what was asked (not internal session IDs).

### What ran

- High-level list of actions. For **pipeline** prompts, include phases or steps with **pass / fail / skipped** per row (or sub-bullets), not only a prose paragraph.

### Key results

- Concrete outputs: artifacts paths, commit hash, files touched, counts, URLs—whatever the workflow produced. Use **placeholders in docs** when describing the template (for example, `<commit-sha>`, `<plan-path>`); agents fill with real values.

### Memory bank and roadmap

- Include when the workflow updates `.cortex/memory-bank/`, roadmap, or plans: **what** changed (file or bullet level), or state **Not updated** if nothing was written.

### Blockers and follow-ups

- Open issues, deferred work, or **explicit `None`** when there are no blockers and no required follow-ups.

## Delta blocks by workflow

Add these subsections **under the base sections** (usually under **What ran** and **Key results**) so pipeline-specific detail stays predictable without breaking the outer skeleton.

### Commit (pipeline)

- **Phase A** — quality gate: pass/fail; if fail, primary error class or tool.
- **Phase B** — docs gate: pass/fail.
- **Step 12** — `run_quality_gate_fresh` (or equivalent final gate): pass/fail.
- Tie each phase to **Key results** (for example, gate log snippet path only if the prompt requires it).

### Implement (pipeline)

- **Selection** — plan step or roadmap item chosen.
- **Code / subagent** — implement-code (or equivalent): files changed, tests added count, coverage if reported.
- **Finalize** — `pipeline_handoff` or orchestrator completion status.
- **Verify** — quality gate iterations (count, pass/fail).
- **Fix path** — if used: note that diagnosis/fix iterations ran and outcome.

### Fix (pipeline)

- **Diagnosis pointer** — where the root cause lives (file, test name, failing check) before listing fixes; keeps the report scannable when many files changed.

### Analyze (single-shot)

- **Session optimization** — path or reference to written analysis (for example, handoff or memory-bank note) and whether `session(compact)` or equivalent was invoked, if applicable.

### Create-plan (meta)

- **Plan path** — new or updated plan file under `.cortex/plans/`.
- **Roadmap** — registration or update (which section or bullet), or **Not registered** if intentionally skipped.

### Review (single-shot)

- Use a **scores / evidence table** (or tight bullet matrix) so criteria, score, and pointer to evidence line up—for example:

| Criterion | Score | Evidence |
| --- | --- | --- |
| … | … | file:line or heading |

Keep the **Overall** row or subsection consistent with [markdown-formatting.md](markdown-formatting.md) (heading for score block, not bold-as-heading).

## Anti-patterns

- **Process-only summaries** — Narrating *"I ran the pipeline"* or *"I called the tools"* without phase pass/fail and without **Key results** the user can verify.
- **Inconsistent emoji** — Mixing ad-hoc symbols with ✅/⚠️/❌ for the same severity levels; pick one scheme per report and match project preferences (✅/⚠️/❌ for status).
- **Burying failures** — Leading with success language or long preamble while ❌ or Phase B failure appears only at the bottom; put **Status** and failed phases **first** in the narrative order.

## References

- Markdown headings: [markdown-formatting.md](markdown-formatting.md)
- MCP tool JSON shape (separate): [phase-75-unify-response-format.md](../../.cortex/plans/archive/Phase75/phase-75-unify-response-format.md)
- Prompt inventory: [REFACTORING_GUIDE.md — Appendix: Synapse prompt inventory](REFACTORING_GUIDE.md#appendix-synapse-prompt-inventory)
