# Evaluate .cortex/history vs git history

**Status**: PENDING  
**Created**: 2026-03-03  
**Goal**: Decide whether the `.cortex/history` directory is still needed now that git already versions files, and, if it is needed, narrow its scope so it delivers unique value instead of redundant history.

## Context

- The Cortex MCP `manage_file` tool writes versioned snapshots for memory-bank files into `.cortex/history/` on each write.
- Git already tracks all committed changes to `.cortex/memory-bank/` and other project files.
- The current setup feels like a "dog-nail" to the user: extra surface area (snapshots, cleanup, disk usage) without clearly visible benefit over git.
- Past plans have touched `.cortex/history` in passing (e.g., legacy path fixes, empty-file cleanup), but there is no focused, up-to-date plan asking whether the history directory is still worth its complexity.

## Questions to Answer

1. What concrete problems does `.cortex/history` solve that git alone does *not* solve (e.g., pre-commit rollback, per-write snapshots across branches, IDE-local history, safety when git is misconfigured)?
2. How often are `.cortex/history` snapshots used in practice (e.g., via `manage_file(operation="rollback")`), and by whom (agents vs humans)?
3. What are the costs: disk growth, extra cleanup logic, potential confusion vs git history, extra complexity in tools and docs?
4. What are the realistic alternatives:
   - Rely solely on git for history.
   - Narrow `.cortex/history` to short-term safety snapshots (e.g., last N versions per file, or last 7 days).
   - Move history into a different storage model (e.g., a single JSON index, compressed archives) if that simplifies UX.
5. How would any change impact existing tools (`manage_file`, `query_memory_bank`, session optimization, commit pipeline) and existing `.cortex/history` contents?

## Approach

1. **Document current behavior**: Precisely document how `.cortex/history` is written and read today (which tools touch it, snapshot naming, retention rules, rollback semantics).
2. **Compare against git**: For each behavior, decide whether git already covers it well enough or whether `.cortex/history` provides unique safety/UX benefits.
3. **Measure usage and costs**: Use existing MCP tools and simple metrics (disk size, snapshot counts, rollback usage if logged) to get real data instead of guesses.
4. **Design options**: Propose at least three options (keep as-is with better docs, simplify/limit, or phase out) with pros/cons and migration impact.
5. **Select and implement**: Choose the preferred option with the user, then update tools, docs, and cleanup scripts accordingly.

## Implementation Steps

### Step 1: Inventory `.cortex/history` behavior and callers

- Read the `manage_file` implementation and docs to confirm when snapshots are written and how rollback works.
- Enumerate which tools and flows rely on `.cortex/history` today (e.g., rollback, version history views, session optimization, any refactoring helpers).
- Capture this as a short "Current Behavior" subsection in `techContext.md` or an appropriate memory-bank file.

**Success criteria**:

- Clear list of all write paths into `.cortex/history` and all read/rollback paths.
- Short narrative of how a typical snapshot lifecycle works from write to potential rollback.

### Step 2: Compare capabilities with git

- For each behavior from Step 1, ask whether git already provides an equivalent:
  - Per-commit history and diffs.
  - Ability to recover older versions across branches.
  - Safety when users accidentally delete or mangle a memory-bank file.
- Identify behaviors where `.cortex/history` is strictly redundant vs where it provides unique value (e.g., pre-commit recovery, uncommitted local snapshots, or finer-grained history if memory bank changes more frequently than commits).

**Success criteria**:

- A table or bullet list mapping `.cortex/history` behaviors to git features, marked as **redundant**, **complementary**, or **unique**.

### Step 3: Measure usage and cost

- Measure total disk usage of `.cortex/history` (and, if feasible, per-file snapshot counts).
- Check whether there is any observable usage of `manage_file(operation="rollback")` or related rollback helpers in recent sessions (if usage metrics are available).
- Note whether the history directory has ever been a source of bugs or cleanup work (e.g., empty snapshot files, stale paths) from recent plans and reviews.

**Success criteria**:

- Rough numbers for disk usage, snapshot counts, and any observed rollback usage.
- At least one paragraph summarizing cost vs observed benefit.

### Step 4: Design options and recommendation

- Define at least three options:
  1. **Keep and clarify**: Keep `.cortex/history` but tighten docs (why it exists, how to use rollback safely, when to prefer git), and possibly add retention policy knobs.
  2. **Simplify and limit**: Keep history only for a short rolling window (time- or count-based), or only for certain critical files, and ensure aggressive cleanup.
  3. **Phase out**: Remove `.cortex/history` snapshots from normal flows and rely on git, keeping only minimal safety nets if absolutely necessary.
- For each option, describe:
  - Impact on tools (especially `manage_file` and any rollback flows).
  - Migration and cleanup steps (how to safely delete or compress existing snapshots).
  - Risks and mitigations.
- Make a concrete recommendation for the next phase (e.g., "simplify and limit" with specific retention settings), including when to revisit the decision.

**Success criteria**:

- Written design section with options, pros/cons, and a recommended path.

### Step 5: Implement chosen option and clean up

- Update `manage_file` and any other tools that write into `.cortex/history` to match the chosen policy (e.g., retention limits, or no longer writing snapshots by default).
- Add or update documentation (e.g., `systemPatterns.md`, `techContext.md`, and user-facing docs) so that the role of `.cortex/history` is clear and not redundant with git.
- Implement any necessary cleanup/migration script or one-off operation to bring the existing `.cortex/history` directory into compliance (e.g., prune old snapshots).
- Ensure commit pipeline and session optimization flows do not assume a specific history layout that has been removed or changed.

**Success criteria**:

- Code, tools, and docs reflect the new policy.
- `.cortex/history` contents match the intended usage (no obvious stale or unbounded growth).

## Testing Strategy

- **Configuration and migration tests**:
  - Add or update tests around `manage_file` versioning and rollback to cover the new policy (e.g., retention limits or disabled snapshots) and ensure old snapshots do not cause regressions.
  - If a cleanup/migration script is introduced, add tests that run it against a synthetic `.cortex/history` tree and verify that only intended files are removed.
- **Safety tests**:
  - Ensure that attempting to rollback to a version that has been pruned fails with a clear, non-destructive error and that git-based recovery remains available.
  - Verify that removing or limiting `.cortex/history` does not break existing memory-bank workflows or the commit pipeline.
- **Documentation tests (lightweight)**:
  - Add linters or schema checks, if appropriate, to ensure any new docs describing `.cortex/history` remain consistent (e.g., references to its purpose and relationship with git).

## Risks and Open Questions

- Risk of removing `.cortex/history` features that some users rely on (e.g., local rollbacks) without adequate replacement.
- Potential hidden dependencies in tools that assume snapshots exist in a particular layout.
- Open question: Should `.cortex/history` be entirely internal to MCP tools (never surfaced to users), or should users be encouraged to interact with it directly for advanced recovery scenarios?

## Success Criteria

- Clear written justification for either keeping, simplifying, or phasing out `.cortex/history` in light of git.
- Tools and docs no longer treat `.cortex/history` as unexplained extra complexity; its purpose and limits are explicit.
- Any remaining use of `.cortex/history` demonstrably adds value beyond what git already provides.
