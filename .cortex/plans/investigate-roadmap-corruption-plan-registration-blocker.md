# Blocker: Investigate Roadmap Corruption on Plan Registration

**Status**: PENDING  
**Priority**: BLOCKER (ASAP)  
**Created**: 2026-02-09

## Goal

Eliminate roadmap corruption that occurs on every plan registration by identifying root cause and implementing a solution that makes plan-induced corruption impossible (e.g. dedicated plan/roadmap functions, structured format, or mandatory use of existing safe tools).

## Context

### Observed Behavior

- **Every plan registration corrupts the roadmap** and triggers restoration (e.g. `fix_roadmap_corruption`, rollback, or manual restore).
- **Recent example** (transcript `f9c61588-cf6f-4ed8-9e67-476bf65936c5`): Agent followed create-plan Step 6, read roadmap via `manage_file(read)`, then called `manage_file(write, content=<built string>)`. The **built string** was corrupted:
  - Merged lines: `phase-investigate-write_cache_json-failure-202620431## Session Optimization Plans (2026023 **Analyze prompt...`
  - Digit/date corruption: `2026-02-04` → `22662-4`, `2026-02-03` → `22603md`, `2026-02-07` → `202602d`
  - Missing spaces: `Phase 9` → `Phase9Excellence98`, `Simplify from 4 to 3` → `Simplify from4 to 3ompts`
  - Truncated filenames and section headers
- Root cause is **LLM string assembly**: when the agent constructs the "full roadmap content" to pass to `manage_file(write, content=...)`, the model corrupts the text (context limits, copy-paste errors, or reconstruction errors). The workflow **requires** full-content write in Step 6, which is inherently risky.

### Existing Mitigations (Insufficient)

- Create-plan Step 6 and Step 7 require "full, unabridged" content and prohibit truncation; agents still pass corrupted content.
- **Session optimization plans**: "Roadmap full-content enforcement" (session-optimization-roadmap-full-content-enforcement.md) and "add_roadmap_entry MCP tool" (add-roadmap-entry-mcp-tool.md) address truncation and prefer minimal updates but create-plan still mandates full-content write.
- **register_plan_in_roadmap** MCP tool already exists: it performs server-side read-modify-write and inserts one entry by section. Create-plan prompt does **not** instruct agents to use it; it mandates `manage_file(write, content=...)`.
- **add_roadmap_entry** MCP tool exists and supports section + position + entry_text; same gap—create-plan does not use it for registration.

### Why This Is a Blocker

Until plan registration no longer requires the agent to build and pass the full roadmap string, every registration run risks corruption and restore cycles. This blocks reliable use of create-plan and increases support burden.

## Approach

1. **Investigate** exact failure mode: confirm root cause (string assembly / full-content write), document from transcript and any logs.
2. **Evaluate options** (see Technical Design): dedicated functions (register_plan_in_roadmap / add_roadmap_entry), structured roadmap (JSON/YAML), validation-before-write, or hybrid.
3. **Implement** the chosen fix: make plan registration use a path that cannot corrupt the roadmap (prefer existing tools; change create-plan Step 6 to use register_plan_in_roadmap / add_roadmap_entry instead of manage_file full-content write).
4. **Harden** create-plan and memory-bank-updater so roadmap updates for plan registration never go through full-content write when a single-entry add is intended.

## Implementation Steps

### Step 1: Document Root Cause from Transcript and Code

- Extract from transcript `f9c61588-cf6f-4ed8-9e67-476bf65936c5` (and any similar): exact corruption patterns, tool sequence, and where the content string was built.
- Confirm create-plan Step 6 text: it currently requires `manage_file(roadmap.md, write, content=...)` and does not mention `register_plan_in_roadmap` or `add_roadmap_entry`.
- Document in this plan or a short investigation note: "Root cause: agent builds full roadmap string for manage_file(write); LLM string assembly introduces typos, merged lines, truncation."

**Acceptance**: Written root-cause summary; references to create-plan Step 6 and tool choices.

### Step 2: Evaluate Options and Choose Solution

- **Option A – Use existing tools (recommended)**: Mandate `register_plan_in_roadmap(plan_title, description, status, section)` for adding a new plan entry in create-plan Step 6. For "enrich" case, either use the same tool with updated description or keep a single managed full-content write only when the tool cannot represent the edit (document when that is allowed). Remove or demote the requirement to pass full roadmap content for simple "add one entry" flows.
- **Option B – add_roadmap_entry**: Use `add_roadmap_entry(section, entry_text, position)` so the agent only sends one bullet line; server does read-modify-write. Complements or replaces full-content write for single-entry adds.
- **Option C – Structured roadmap (JSON/YAML)**: Store roadmap as structured data (e.g. `roadmap.json` or `roadmap.yaml`); provide MCP tools to add/update entries by structure. Render to markdown for display if needed. Larger change; consider as future enhancement if A/B are sufficient.
- **Option D – Validation before write**: Keep full-content write but add a pre-write check (e.g. length, section count, or diff against last read) and reject/retry if content looks truncated or corrupted. Reduces but does not eliminate risk.
- **Decision**: Choose Option A (and optionally B for flexibility), document rationale, and scope Step 3–4 to that choice.

**Acceptance**: Options documented; chosen solution (A/B or A+B) and rationale recorded in plan.

### Step 3: Update Create-Plan Step 6 to Use register_plan_in_roadmap

- **Target**: `.cortex/synapse/prompts/create-plan.md` (and any Synapse agent that performs roadmap update).
- **Change**: For **adding a new plan entry**, require agents to call `register_plan_in_roadmap(plan_title=..., description=..., status=..., section=...)` instead of building full roadmap content and calling `manage_file(roadmap.md, write, content=...)`. Section should be chosen from roadmap structure (e.g. blockers vs pending) per existing placement rules. Fallback to `manage_file(write, ...)` only when updating multiple entries or when register_plan_in_roadmap is unavailable (document fallback and retain full-content rule for that path).
- **Remove or soften** the requirement that the agent "must pass the full, unabridged roadmap text" for the **single-entry add** case; replace with "must use register_plan_in_roadmap for adding one plan entry."
- **Verification**: Grep or integration test that create-plan prompt instructs use of register_plan_in_roadmap for new plan registration.

**Acceptance**: Step 6 uses register_plan_in_roadmap for new plan entry; full-content write only for fallback or multi-entry updates.

### Step 4: Update Memory-Bank-Updater Agent (if applicable)

- **Target**: `.cortex/synapse/agents/memory-bank-updater.md` (or equivalent).
- **Change**: Document that for plan creation, roadmap update MUST be done via `register_plan_in_roadmap` when adding a single plan entry; do not build full roadmap content for that case. If the agent delegates to memory-bank-updater, ensure it calls register_plan_in_roadmap, not manage_file(write, full content).

**Acceptance**: Memory-bank-updater instructions aligned with Step 6.

### Step 5: Optional – Integrate add_roadmap_entry for Entry-Text-Only Path

- If a flow needs to add a raw entry line (e.g. preformatted bullet) rather than (plan_title, description, status), document use of `add_roadmap_entry(section, entry_text, position)` in create-plan or memory-bank-updater so agents never build full content for single-entry adds.
- Ensure create-plan Step 6 lists both tools: prefer register_plan_in_roadmap for plan registration; add_roadmap_entry as alternative when entry is a single formatted line.

**Acceptance**: Optional; if done, prompt/agent text updated and consistent.

### Step 6: Consider Structured Roadmap (JSON) as Future Work

- Add a short "Future work" note or roadmap entry: evaluate moving roadmap to a structured format (e.g. JSON) with dedicated read/write APIs so all edits are programmatic and corruption from string assembly is impossible. Do not implement in this blocker; only document and optionally add a follow-up plan.

**Acceptance**: Decision and rationale (defer vs. implement) recorded; follow-up plan or note if deferred.

### Step 7: Testing and Verification

- **Unit**: Existing tests for register_plan_in_roadmap and add_roadmap_entry remain passing; add or adjust tests if contract changes.
- **Integration**: Run create-plan flow (or simulated plan registration) and assert roadmap is updated via register_plan_in_roadmap and that roadmap content is not corrupted (e.g. line count, key sections, no merged lines or date corruption). Optionally add a test that parses roadmap and checks for common corruption patterns.
- **Regression**: Ensure existing plan creation (with fallback) still works when register_plan_in_roadmap is used; no removal of existing entries.

**Acceptance**: Tests added or updated; create-plan run leaves roadmap intact.

## Dependencies

- Existing Cortex MCP tools: `register_plan_in_roadmap`, `add_roadmap_entry`, `manage_file`, `fix_roadmap_corruption`, `rollback_file_version`.
- Create-plan prompt and memory-bank-updater agent in Synapse.
- Session optimization plans: session-optimization-roadmap-full-content-enforcement.md, add-roadmap-entry-mcp-tool.md (context only; this plan unblocks by switching to safe tools).

## Success Criteria

- Root cause of roadmap corruption on plan registration is documented (LLM string assembly when building full content for manage_file write).
- Create-plan Step 6 mandates use of `register_plan_in_roadmap` (and optionally `add_roadmap_entry`) for adding a single plan entry; full-content manage_file(write) is not used for that case.
- One create-plan run that adds a plan entry does not corrupt the roadmap and does not require restoration.
- Options (dedicated functions vs. structured JSON) are evaluated and chosen approach is implemented; structured JSON is at most documented as future work.

## Technical Design

### Root Cause (Confirmed from Transcript)

- Agent reads roadmap with manage_file(read).
- Agent builds a string = original content + one new bullet. While building, the model corrupts the string (merged lines, digit/date errors, truncation).
- Agent calls manage_file(write, content=corrupted_string). Roadmap is overwritten with corrupted content.
- Restoration is required (rollback, fix_roadmap_corruption, or manual).

### Option Summary

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A. register_plan_in_roadmap | Step 6 uses existing MCP tool; server does read-modify-write | No full content in client; already implemented | Enrich/update flow may need clarification |
| B. add_roadmap_entry | Agent sends one line; server inserts | Small payload; no assembly of full file | Agent must format entry line correctly |
| C. Structured roadmap (JSON) | roadmap.json + APIs | No markdown string assembly | Migration, display, and tooling effort |
| D. Validation before write | Check length/structure before manage_file(write) | Can catch some corruption | Does not remove root cause; still risky |

**Recommendation**: Implement Option A (and use B where a single preformatted line is preferred). Document C as future enhancement.

### Testing Strategy (MANDATORY)

- **Coverage target**: Minimum 95% for any new or modified code paths (e.g. prompt tests, integration path).
- **Unit tests**: N/A for prompt-only changes; if any helper or validation is added, unit test it.
- **Integration tests**: (1) Create-plan flow that adds one plan must call register_plan_in_roadmap (or add_roadmap_entry) and must not call manage_file(roadmap.md, write) with full content for that add. (2) After simulated or real plan registration, roadmap.md must retain all prior entries and contain the new entry without corruption (assert section structure, line count, no known corruption patterns).
- **Regression**: Existing register_plan_in_roadmap and add_roadmap_entry tests must pass; roadmap_sync validation must still pass after a plan is added.

## Risks & Mitigation

- **Risk**: register_plan_in_roadmap section/position logic might not match all create-plan placement rules. **Mitigation**: Align section names and placement rules in prompt with tool contract; add tests for blockers vs pending.
- **Risk**: Enriching an existing plan may require editing an existing line rather than adding. **Mitigation**: Document that "enrich" may still use one full-content write if no tool supports in-place line edit; keep that path rare and with strict full-content rules.

## Timeline

- Step 1–2: 1 day (investigation + option choice).
- Step 3–5: 1–2 days (prompt and agent updates, optional add_roadmap_entry).
- Step 6–7: 0.5 day (documentation, tests, verification).

Total estimate: 2–3 days.

## Notes

- Transcript: `f9c61588-cf6f-4ed8-9e67-476bf65936c5.txt` (recent corruption example).
- Related: session-optimization-roadmap-full-content-enforcement.md, add-roadmap-entry-mcp-tool.md, session-optimization-markdown-corruption-progress-plans.md, Phase 24 (fix-roadmap-text-corruption, archived).
