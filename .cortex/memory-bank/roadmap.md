# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### FastMCP v3 Migration

### Fixes

### Quality & Reliability Improvements

### Security

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

- **Enforce Post-Implementation Review Loop in /do Pipeline** - PENDING - Add mandatory post-completion review in /cortex/do; if review finds gaps, record them in the plan and return status to PENDING. Plan: .cortex/plans/enforce-post-implementation-review-loop-in-do-pipeline.md

### Improvements

#### Knowledge Base & Wiki (High Priority)

#### Token Efficiency (High Priority)

### Features & Enhancements

#### Token Efficiency (Medium Priority)

#### Claude Code Harness Improvements (High Priority)

#### Annotation Quality (Medium Priority)

- **BELIEF Annotation Enforcement — Emit Guidance and Mid-Function Heuristics** - PENDING - Add When-to-write-BELIEF triggers to rule file, add BELIEF-emission instruction to implement-code cursor-agent, and extend reflection heuristic to detect risky mid-function patterns (dict key access, chained attribute access) in new diffs. Plan: .cortex/plans/belief-annotation-enforcement-guidance-mid-function-heuristics.md
- **Fix-Loop Exhaustion — Root-Cause Reframe Output** - PENDING - Add a mandatory post-exhaustion analysis block to fix.md, fix-tests.md, and fix-quality.md so that when the 3-iteration limit is reached, the agent produces a root-cause hypothesis, a reformulated brief, and an explicit directive to open a new session. Prompt-only change. Plan: .cortex/plans/fix-loop-exhaustion-root-cause-reframe-output.md

#### Planning & Brainstorming (High Priority)

#### Planning & Brainstorming (Medium Priority)

#### Wiki for Attached Projects (High Priority)

#### Planning & Brainstorming (Low Priority)
