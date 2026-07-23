<!-- memory_type: milestone -->
# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Content-Preserving WAL for AS-OF Reconstruction** - PENDING - WAL stores reverse content deltas keyed by experience-store step numbers, enabling AS-OF reconstruction of memory-bank state at any decision point. Deferred item — execute only after analyze-experience-graph-queries proves valuable. Plan: .cortex/plans/content-preserving-wal-as-of.md
- **Prompt-Cache Payload Stability for Cached MCP Resources** - PENDING - Make cortex://rules and cortex://context payload text deterministic across reads of unchanged state and add a quality-gate audit for volatile content (timestamps, UUIDs) in their construction paths, so the already-implemented cache_control resource hints (add-anthropic-prompt-cache-control) actually produce Anthropic prompt-cache hits instead of silent prefix invalidation. Plan: .cortex/plans/prompt-cache-payload-stability-for-cached-mcp-resources.md
- **Tool-Invocation Telemetry Log to Strengthen Skill-Crystallization Signal** - PENDING - Extends the existing analyze-session/analyze-tools/write_artifact skill-crystallization pipeline with a redacted, session-scoped tool-invocation telemetry log (reusing the WAL append pattern) so consolidation-candidate detection has a proper signal beyond git diff and experience-store graph queries. Sourced from an external self-improvement proposal (2026-07-23); scoped down after finding most of the pipeline already exists. Plan: .cortex/plans/tool-invocation-telemetry-log-to-strengthen-skill-crystallization-signal.md
- **Embedding-Based Relevance Scoring for Context Load/Compaction Gating** - PENDING - Wires the existing experience-store embedding index (src/cortex/experience/hybrid_rank.py, src/cortex/experience/embedding_index_core.py) into src/cortex/tools/context/l0_identity.py/_truncate_to_budget and src/cortex/tools/context/l2_on_demand.py/_truncate_paragraphs so budget-constrained context loading prefers semantically relevant content over positional cuts, with a safe fallback to current behavior. Sourced from an external self-improvement proposal (2026-07-23); scoped down from a full semantic-judge/phase-classifier design to fit existing infra. Plan: .cortex/plans/embedding-based-relevance-scoring-for-context-load-compaction-gating.md
- **Git-Backed Sandboxed Self-Modification Proposal Tool** - PENDING - Net-new propose_framework_optimization tool: creates an isolated git worktree (reusing WorktreeExecutionEnvironment), applies a proposed .cortex/synapse or .cortex/rules edit, self-tests it there, and returns a reviewable diff for explicit human approval. Never pushes or opens a PR itself. Sourced from an external self-improvement proposal (2026-07-23). Plan: .cortex/plans/git-backed-sandboxed-self-modification-proposal-tool.md
- **Task-Level Stuck-Loop Constraints Monitor Beyond MCP Circuit Breaker** - PENDING - Adds a no-progress detector for task-executing subagents (fix-tests, fix-quality, implement-code) that repeat the same failing outcome against the same target, distinct from the existing MCP-transport circuit breaker (src/cortex/core/mcp_stability_retry.py, CRI-3). Pause-and-report only; explicitly excludes dynamic task-decomposer/sub-agent topology construction as a deliberate departure from the intentional fixed-schema pipeline design. Sourced from an external self-improvement proposal (2026-07-23), scoped down to the finite, non-conflicting slice. Plan: .cortex/plans/task-level-stuck-loop-constraints-monitor-beyond-mcp-circuit-breaker.md

### Pipeline Infrastructure

### Tools Infrastructure

### FastMCP v3 Migration

### Fixes

### Quality & Reliability Improvements

### Security

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Improvements

#### Knowledge Base & Wiki (High Priority)

#### Token Efficiency (High Priority)

### Features & Enhancements

#### Token Efficiency (Medium Priority)

#### Claude Code Harness Improvements (High Priority)

#### Annotation Quality (Medium Priority)

#### Planning & Brainstorming (High Priority)

#### Planning & Brainstorming (Medium Priority)

#### Wiki for Attached Projects (High Priority)

#### Planning & Brainstorming (Low Priority)
