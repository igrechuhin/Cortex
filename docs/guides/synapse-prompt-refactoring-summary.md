# Prompt Refactoring Summary

## Clean Semantics

In this summary, **clean** means the documented refactoring state is coherent and aligned with the orchestration model. It does not require a git-clean tree.

## Principle

**Prompts = Orchestration** | **Agents = Implementation**

Prompts focus on workflow orchestration (step order, dependencies, blocking conditions). Agents contain all implementation details (tool calls, validation logic, parsing).

## Severity Hierarchy

All prompts and agents use a three-tier severity system:

- **GATE**: Blocks pipeline/workflow. Failure means stop. Replaces: CRITICAL, MANDATORY, ABSOLUTE BLOCK, NO EXCEPTIONS, ZERO TOLERANCE.
- **CHECK**: Requires explicit verification. Parse output and confirm. Replaces: VALIDATION, MUST verify.
- **PREFER**: Best practice. Recommended but non-blocking. Replaces: optional, recommended.

This eliminates attention dilution from overuse of "CRITICAL" and provides clear priority for the agent.

## Refactoring Pattern

Each step follows this pattern:

```markdown
X. **Step Name** - **Delegate to `agent-name` agent**:

- **Agent**: Use the agent-name agent (Synapse agents directory)
- **Dependency**: Must run AFTER Step Y (or BEFORE Step Z)
- **GATE**: Success criteria that blocks workflow
- **CHECK**: Conditions that require verification
- **Output**: Structured result per shared-handoff-schema.md
```

## Shared Infrastructure

### Typed Inter-Agent Handoff (`shared-handoff-schema.md`)

- Defines JSON schemas for every agent-to-orchestrator result
- Orchestrators validate required fields before passing data downstream
- Eliminates state loss from implicit LLM memory
- New schemas added: `FinalGateValidatorResult`, `CommitStateTrackerResult`

### Common Pre-Action Checklist (`common-checklist.md`)

- Single agent that loads structure, memory bank, rules, and detects primary language
- Referenced by: `plan.md`, `review.md`, `do.md`, `analyze.md`, `commit.md`
- Eliminates ~300 lines of duplicated `manage_file` calls across prompts

### Language-Aware Review

- `common-checklist` detects `primary_language` from `techContext.md`
- `bug-detector` agent filters checks by language (Python, Swift, TypeScript, etc.)
- `review.md` passes `primary_language` to all sub-agents

### Analyze Ownership

- `analyze.md` runs ONLY from `commit.md` Step 15 (always runs, mandatory)
- Other prompts (`review.md`, `plan.md`, `do.md`) do NOT run analyze
- Users can invoke `/cortex/analyze` directly if needed
- Eliminates unverifiable "is this the last workflow?" branch from 4 prompts

### Simplified Roadmap Registration

- `plan(operation="register")` is the **sole API** for adding new roadmap entries
- Full-content `manage_file(write)` fallback removed from `plan.md`

### Final Gate Validator (`final-gate-validator.md`)

- New agent extracting Step 12 (500+ lines) from `commit.md`
- Implements state-machine fix loop (fix -> re-run dependents -> verify)
- Handles all connection error fallback logic
- Supports dirty-state optimization (Phase 89)
- Reduces commit.md from 1,842 to 275 lines

### Commit State Tracker (`commit-state-tracker.md`)

- New agent for pipeline state checkpointing
- Writes JSON state to `.cortex/.session/commit-pipeline-state.json`
- Prevents state loss from context compression in long pipelines
- Tracks: rules_loaded, phase_a results, coverage, step outcomes, final gate

### Error Pattern Detector (`error-pattern-detector.md`)

- Reference catalog of known error patterns
- Extracted from commit.md "Common Errors to Catch" section (~160 lines)
- Referenced by error-fixer, quality-checker, type-checker, test-executor, final-gate-validator
- Defines 12 error patterns + 7 anti-patterns with detection/action/blocking rules

### Agents Manifest (`agents-manifest.json`)

- Discovery manifest for all agent files, grouped by pipeline category
- Categories: commit (12), review (8), implement (5), analyze (5), shared (4+), reference (4)
- Each entry: file, name, description, keywords; reference docs marked `invocable: false`
- Used by `agent-health-checker` for batch pre-flight validation
- Follows same pattern as `rules-manifest.json` and `prompts-manifest.json`

### Agent Health Checker (`agent-health-checker.md`)

- Pre-flight agent that batch-validates all required agent files exist before pipeline execution
- Replaces per-step "VERIFY agent file exists" prose in all orchestrators
- Cross-checks against `agents-manifest.json` (optional, non-blocking)
- Returns `AgentHealthCheckerResult` with found/missing/malformed agent lists

### Pipeline State Tracker (`pipeline-state-tracker.md`)

- Generalized state persistence for review and analyze pipelines
- Mirrors `commit-state-tracker` pattern but with generic step-accumulation schema
- Writes to `.cortex/.session/{pipeline_name}-pipeline-state.json`
- Prevents state loss from context compression in long 8-agent review or 5-agent analyze pipelines
- Best-effort / non-blocking (write failure does not block pipeline)

### Unified Fix Helper (`fix.md`)

- Consolidated fix-quality.md, fix-tests.md, and docs-sync.md into single parameterized prompt
- Target parameter: `quality | tests | docs`
- Shared sections: severity levels, goals, failure handling
- Target-specific sections: tooling, pre-action checklist, execution steps, success criteria
- Reduces 259 lines across 3 files to ~120 lines in 1 file

### Review Output Schema (`review-output-schema.md`)

- Extracted review report format from review.md (~200 lines)
- Defines issue, violation, completeness, and improvement templates
- Structured for plan-ready consumption by plan.md
- Reduces review.md from 434 to 152 lines

## Status

- ✅ Shared handoff schema created (original + 2 new schemas)
- ✅ Common checklist agent created
- ✅ Final gate validator agent created (Step 12 extraction)
- ✅ Commit state tracker agent created (pipeline state)
- ✅ Error pattern detector reference created (error catalog)
- ✅ Review output schema reference created (report templates)
- ✅ commit.md rewritten as orchestration-only (1,842 -> 275 lines)
- ✅ review.md rewritten with schema reference (434 -> 152 lines)
- ✅ plan.md simplified (conditional analyze removed, severity levels added)
- ✅ do.md updated (conditional analyze removed, severity levels)
- ✅ analyze.md updated (severity levels, common-checklist delegation)
- ✅ fix-quality.md updated (severity levels)
- ✅ fix-tests.md updated (severity levels)
- ✅ docs-sync.md updated (severity levels)
- ✅ validate-roadmap-sync.md updated (severity levels)
- ✅ Severity hierarchy (GATE/CHECK/PREFER) applied across all prompts
- ✅ Conditional analyze removed from non-commit prompts
- ✅ bug-detector.md rewritten (language-aware)
- ✅ agent-workflow.mdc rule updated (conditional analyze)
- ✅ Agents manifest created (`agents-manifest.json`) with 6 pipeline categories
- ✅ Agent health checker created (batch pre-flight validation)
- ✅ Pipeline state tracker created (review/analyze state persistence)
- ✅ fix-quality.md, fix-tests.md, docs-sync.md consolidated into fix.md
- ✅ Deterministic plan deduplication scoring added to plan.md

### Reliability Hardening (Post-Review)

- ✅ `shared-conventions.md` created — severity levels, pre-flight protocol, path resolution, tooling preferences, max-retry limits, session model
- ✅ `memory-bank-contract.md` created — write discipline, allowed/forbidden tools, post-write verification, integrity rules
- ✅ Max-retry counts (3 iterations) added to fix loops in commit.md, fix.md, do.md
- ✅ Similarity scoring in plan.md simplified (45 lines → 15 lines; removed fragile keyword counting)
- ✅ Steps 9-11 in commit.md made deterministic (removed conditional parallelism)
- ✅ All orchestration prompts reference `shared-conventions.md` instead of inline severity/pre-flight boilerplate
- ✅ Memory bank integrity check added to common-checklist agent (blocks on empty/corrupted core files)
- ✅ Inter-session model documented in [synapse-prompt-refactoring-guide.md](synapse-prompt-refactoring-guide.md)

## Line Count Impact

| File | Before | After | Reduction |
|---|---|---|---|
| commit.md | 1,842 | 275 | -85% |
| review.md | 434 | 152 | -65% |
| plan.md | 339 | 330 | -3% |
| do.md | 125 | 119 | -5% |
| **Total prompt lines** | **2,740** | **876** | **-68%** |

New agents created: 4 files, ~520 lines total (net complexity moved to dedicated, testable agents).
