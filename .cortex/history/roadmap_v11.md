<!-- memory_type: milestone -->
# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Pipeline Resume as a Frontier Query** - PENDING - Resume interrupted /cortex/commit and /cortex/fix runs from the last committed experience-store node instead of restarting; maps node status onto pipeline_handoff snapshot/rollback state. Depends on unified-experience-store. Plan: .cortex/plans/pipeline-resume-frontier-query.md
- **Vector-Seeded Experience Recall in Session Start** - PENDING - Task-description embeddings alongside BM25; session() surfaces similar prior tasks' highest-fitness fixes and dead ends within token budget. Depends on unified-experience-store. Plan: .cortex/plans/vector-seeded-experience-recall.md
- **Rewire /cortex/analyze from Transcript Scraping to Experience Queries** - PENDING - Mistake-pattern detection via sibling-node preference-pair queries (pass/fail under same parent) with evidence links into the failure-based evals task registry; transcript scraping becomes fallback. Depends on unified-experience-store. Plan: .cortex/plans/analyze-experience-graph-queries.md
- **Synapse Rule Provenance from Experience Pairs** - PENDING - Rule recommendations cite the failure→fix node pairs justifying them; rules whose failure class stops occurring are flagged as pruning candidates. Depends on unified-experience-store and analyze-experience-graph-queries. Plan: .cortex/plans/synapse-rule-provenance.md
- **Content-Preserving WAL for AS-OF Reconstruction** - PENDING - WAL stores reverse content deltas keyed by experience-store step numbers, enabling AS-OF reconstruction of memory-bank state at any decision point. Deferred item — execute only after analyze-experience-graph-queries proves valuable. Plan: .cortex/plans/content-preserving-wal-as-of.md

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
