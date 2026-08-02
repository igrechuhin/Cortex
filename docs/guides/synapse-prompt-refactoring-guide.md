# Prompt Refactoring Guide: Orchestration vs Implementation

## Clean Semantics

In this guide, **clean** means terminology and workflow guidance are internally consistent, non-conflicting, and aligned with prompt intent. It does not mean git-clean working tree.

## Principle

**Prompts = Orchestration** | **Agents = Implementation**

## Severity Hierarchy

All prompts and agents MUST use these three levels consistently:

- **GATE**: Blocks pipeline/workflow. Failure = stop. Use sparingly for true blockers.
- **CHECK**: Requires explicit verification. Parse output and confirm zero errors.
- **PREFER**: Best practice. Recommended but non-blocking.

**Do NOT use**: CRITICAL, MANDATORY, ABSOLUTE BLOCK, NO EXCEPTIONS, ZERO TOLERANCE, or other ad-hoc emphasis. Map all severity to GATE/CHECK/PREFER.

## What Prompts Should Keep

### ✅ Orchestration Logic

- Step order and dependencies
- Workflow coordination (when to proceed, when to block)
- Error handling between steps
- Critical workflow rules

### ✅ High-Level Descriptions

- What each step accomplishes
- Why steps are in a certain order
- Dependencies between steps

### ✅ Workflow-Specific Rules

- "Step 0 must complete before Step 1"
- "Step 12 must run after Steps 4-11"
- "Block commit if any step fails"

## What Prompts Should Remove

### ❌ Implementation Details

- Specific MCP tool calls and parameters
- Tool response parsing logic
- Detailed validation steps
- Implementation instructions

### ❌ Agent-Specific Logic

- How to use specific tools
- What to check in tool responses
- Detailed error handling for specific tools

## Refactoring Pattern

### Before (Duplicated Implementation)

```markdown
0. **Fix errors and warnings** - **Delegate to `error-fixer` agent**:
   - Use the `error-fixer` agent (Synapse agents directory) for this step
   - The agent will use `execute_pre_commit_checks()` MCP tool:
   - **Call MCP tool**: `execute_pre_commit_checks(checks=["fix_errors"], strict_mode=False)`
   - **CRITICAL - MCP TOOL VALIDATION**: After tool call, validate response:
     - **Automatic validation**: `mcp_tool_wrapper` and `validate_mcp_tool_response()` automatically validate:
       - Response is not None
       - Response is dict (not JSON string)
       - Response has "status" field
   [... 30 more lines of implementation details ...]
```

### After (Orchestration Only)

```markdown
0. **Fix errors and warnings** - **Delegate to `error-fixer` agent**:
   - **Agent**: Use the error-fixer agent (Synapse agents directory) for implementation details
   - **CRITICAL**: This step MUST complete successfully before proceeding to Step 1
   - **BLOCK COMMIT**: If any errors remain after this step, stop immediately
   - **Dependency**: Must run BEFORE all other pre-commit checks
   - **Workflow**: After agent completes, verify zero errors remain before proceeding
```

## Benefits

1. **Single Source of Truth**: Implementation details live in agents only
2. **Easier Maintenance**: Update agent logic in one place
3. **Clear Separation**: Prompts orchestrate, agents implement
4. **Reduced Duplication**: No repeated instructions
5. **Better Focus**: Prompts focus on workflow, agents focus on tasks

## Example: Complete Step Refactoring

### Step 0: Error Fixing

**Orchestration (in prompt):**

- Order: Must be Step 0 (before all other checks)
- Dependency: None (first step)
- Success criteria: Zero errors must remain
- Failure handling: Block commit if errors remain
- Next step: Proceed to Step 1 only if successful

**Implementation (in agent):**

- How to call MCP tool
- Tool parameters
- Response parsing
- Validation logic
- Error reporting

This separation makes the system more maintainable and clear.

## Agent Existence Check (MANDATORY)

Before delegating to any agent, orchestrators MUST verify the agent file exists:

1. Resolve the Synapse agents directory path
2. Check that `{agents_dir}/{agent-name}.md` exists (e.g., `Glob` or `Read`)
3. If the file is missing, report a clear error: `"Agent file '{agent-name}.md' not found in Synapse agents directory at {agents_dir}"`
4. Do NOT hallucinate agent content or proceed without the file

This prevents silent failures when agent files are renamed, deleted, or the Synapse submodule is out of date.

For the complete list of agents and their pipeline assignments, see `agents/agents-manifest.json`. The `agent-health-checker` agent can batch-validate all required agents at pipeline start instead of checking one-by-one.

## Session Model

Each prompt (commit, review, implement, plan, analyze, fix) runs in an **independent agent session**. No agent state carries between sessions.

- The **memory bank** (roadmap.md, activeContext.md, progress.md) is the sole inter-session continuity mechanism.
- Prompts must NOT assume access to outputs from prior sessions or other prompts.
- Within a session, `pipeline-state-tracker` or `commit-state-tracker` may be used for intra-session checkpointing to survive context compression.
- The `analyze` compound step at the end of commit feeds learning back for the next session cycle.

The Plan -> Work -> Review -> Compound loop is **inter-session**:

```text
Session A: plan.md             → plan file + roadmap entry
Session B: implement.md        → code + tests + quality gate + memory bank update
Session C: commit.md           → full pipeline + push + analyze
```

Because memory bank is the sole bridge, its integrity is mission-critical. See `memory-bank-contract.md` for the write discipline.

## Shared Conventions

Cross-cutting conventions (severity levels, pre-flight protocol, path resolution, tooling preferences, max-retry limits, memory bank contract) are defined in `agents/shared-conventions.md`. All orchestration prompts reference it instead of duplicating definitions inline.
