# Investigation: Roadmap Update Workflow (Plan Creation) — Slow and Fragile

**Date**: 2026-02-02  
**Trigger**: User report that adding a new blocker to the roadmap "always takes long" and involves "restoring the roadmap from git and re-adding the new blocker."

## Summary

Adding a plan entry to `roadmap.md` during plan creation (`/cortex/plan`) is slow and error-prone because:

1. **Full-content write is mandatory**: The create-plan prompt requires `manage_file(file_name="roadmap.md", operation="write", content=<complete resulting text>)` with the **full, unabridged** roadmap. StrReplace and direct Write on the roadmap file are prohibited.
2. **Roadmap is large**: `roadmap.md` is ~32 KB (~150 lines). The agent must pass this entire string as the `content` argument in one MCP tool call.
3. **Truncation risk**: When the agent builds the write call, the model or the tool layer may truncate the content (e.g. "Content truncated for length"), which corrupts the roadmap and forces a recovery flow.
4. **Recovery is slow**: Recovery requires restoring the full file from git, re-applying the new entry (e.g. `head -20` + `tail -n +21` from git, or StrReplace), and optionally syncing via `manage_file` again. Multiple steps and manual reassembly.

There is **no MCP tool for minimal roadmap updates** (e.g. "insert this bullet at section X"); the only supported path is read full → edit in memory → write full.

## Root Causes

### 1. Create-plan prompt design (Step 6)

- **Location**: `.cortex/synapse/prompts/create-plan.md`, Step 6 and "Roadmap update" / "ERROR HANDLING".
- **Rule**: "PROHIBITED: Updating the roadmap during plan creation by any method other than `manage_file(..., operation='write', content=..., change_description=...)`. This includes: using StrReplace (or any search_replace) on the roadmap file, using the Write tool to write directly to the roadmap file path."
- **Rule**: "The `content` parameter MUST be the full, unabridged roadmap text. If the content is large, the agent must still pass the full content in one call. **Never truncate, summarize, or shorten existing roadmap bullets** to fit length limits."

So the workflow intentionally forces a single full-content write to avoid partial edits that could drop content. The side effect is that the agent must serialize the entire roadmap in one tool call.

### 2. No minimal-update API

- `manage_file` supports only `read`, `write`, and `metadata`. There is no operation such as `insert_roadmap_entry(section, position, text)` or `patch_roadmap(anchor, new_bullet)` that would perform a server-side insert.
- Therefore any "add one bullet" operation is implemented as: read full file → modify in agent context → write full file. As the roadmap grows, this becomes the bottleneck and the main source of truncation.

### 3. Payload size and truncation

- **Roadmap size**: ~31,764 bytes (~32 KB) in the current repo.
- **Tool call size**: The MCP tool call includes the full `content` string. LLM output or tool-argument size limits can cause the agent to truncate the value (e.g. substituting a placeholder like "Content truncated for length - full roadmap preserved in memory bank"), which overwrites the roadmap with incomplete content.
- **Cortex code**: No server-side limit on `content` length was found in `file_operations.py` or `file_system.py`; validation is about presence and conflict markers, not size. The truncation happens **before** the request reaches Cortex (in the client/LLM side).

### 4. Recovery flow

- When truncation is detected (or the user notices a corrupted roadmap), the prompt says: "restore the full content and repeat the update using `manage_file(..., operation='write', content=<complete content>, ...)` with the complete content—**not** StrReplace or direct Write."
- In practice the agent may restore by: `git show HEAD:.cortex/memory-bank/roadmap.md` → merge with the new entry (e.g. `head -20` of current + `tail -n +21` of git) → then either StrReplace/Write to disk or another `manage_file(write, ...)`. That flow is multi-step, easy to get wrong (e.g. missing the last bullet), and "always takes long."

## Why it always takes long

1. **Read**: `manage_file(roadmap.md, read)` returns a large payload; the agent and context must process it.
2. **Edit**: The agent edits the string in context (add/update one entry).
3. **Write**: The agent must emit a tool call with the **entire** modified roadmap as `content`. For a 32 KB file, that is a large outgoing argument; generation can be slow and is prone to truncation.
4. **If truncation happens**: Detect corruption → restore from git → re-apply new entry → verify. Extra steps and re-reading/re-writing.

So the "always takes long" experience comes from (a) the mandatory full read + full write cycle, and (b) the recovery path when that write is truncated.

## Recommendations

### Option A: Add an MCP tool for minimal roadmap updates (preferred)

- **Tool**: e.g. `add_roadmap_entry(section, position, entry_text)` or `insert_roadmap_entry(anchor_line_or_section, entry_text, after_before)`.
- **Behavior**: Server reads `roadmap.md`, finds the right section/line, inserts the new bullet, writes the file (and optionally updates version/history). No need for the client to send the full file.
- **Benefits**: Small request (section + one bullet), no full-content serialization, less truncation risk, faster and more reliable plan creation.
- **Create-plan change**: Step 6 would call this tool for "add one plan entry" instead of `manage_file(write, content=<full roadmap>)`. Full-content `manage_file(write)` remains for cases that need it (e.g. bulk edits or when the new tool is unavailable).

### Option B: Allow a single StrReplace for "add one entry" with verification

- **Rule change**: In create-plan Step 6, allow one **constrained** StrReplace (or direct Write) **only** for adding a single new bullet at a specified location (e.g. "after line 6 in Blockers"), with an **immediate** follow-up `manage_file(roadmap.md, read)` to verify line count and that the new entry is present; if verification fails, require fallback to full-content `manage_file(write)` or recovery.
- **Risks**: StrReplace can still be misused (wrong anchor, multiple edits). Verification mitigates but does not remove the risk of accidental overwrites.

### Option C: Chunked or section-based roadmap writes

- **Idea**: Add a tool that writes only a **section** of the roadmap (e.g. "Blockers (ASAP Priority)") with a clear contract (e.g. replace only that section, leave rest unchanged). The agent would call it once per modified section.
- **Pros**: Smaller payloads than full file. **Cons**: More complex contract and implementation; overlapping edits could still corrupt the file if not designed carefully.

### Option D: Keep full-content write but harden the flow

- **Mitigations**: (1) In create-plan, add an explicit step: "Before calling manage_file(write), verify that the string you will pass has the same line count as the read roadmap + 1 (or 0 for update). If you cannot fit the full content in one call, do not truncate; instead call [new minimal tool] or document failure and ask the user to add the entry manually." (2) Document that if the client/tool has a max argument size, the agent must use the minimal-update tool (Option A) when available.
- This reduces accidental truncation but does not remove the fundamental cost of sending the full roadmap.

## Implementation plan (if Option A)

1. **Design**: Define `add_roadmap_entry` (or equivalent) parameters: e.g. `section` ("blockers" | "active_work" | "future" | "pending"), `position` ("first" | "last" | after "title"), `entry_text` (single bullet string), optional `change_description`.
2. **Implement**: In Cortex, implement the tool: resolve roadmap path, read file, parse sections (e.g. by `##` headers), insert the bullet at the right place, write file, update history. Reuse existing roadmap corruption checks if applicable.
3. **Create-plan**: Update Step 6 to use `add_roadmap_entry` for adding a new plan entry; keep `manage_file(roadmap.md, read)` for "parse roadmap structure" and fallback to `manage_file(write, content=...)` if the new tool is unavailable or for non-append edits.
4. **Memory-bank-updater**: Document that when invoked from plan creation, prefer `add_roadmap_entry` for single-entry adds.
5. **Tests**: Unit tests for the new tool (insert at first/last, correct section); integration test that create-plan adds an entry and roadmap stays valid.

## Expected impact

- **Option A**: Plan creation (especially adding a blocker) becomes one small tool call instead of read-full + write-full; less context use, no full roadmap in the write call, and recovery from truncation should no longer be needed for simple adds.
- **Option B**: Fewer full-content writes when the agent would otherwise use StrReplace anyway; verification catches some mistakes but does not eliminate truncation on full writes.
- **Option C**: Smaller writes per section; implementation and contract are heavier.
- **Option D**: Fewer unintentional truncations if the agent follows the check; full-content cost remains.

## References

- Create-plan prompt: `.cortex/synapse/prompts/create-plan.md` (Step 6, roadmap update, ERROR HANDLING).
- Memory-bank-updater agent: `.cortex/synapse/agents/memory-bank-updater.md` ("Roadmap writes", "Roadmap update (plan creation)").
- manage_file implementation: `src/cortex/tools/file_operations.py` (no content size limit; `fix_roadmap_content_if_needed` for roadmap.md writes).
- Roadmap size: `wc -c .cortex/memory-bank/roadmap.md` → ~31,764 bytes (2026-02-02).
