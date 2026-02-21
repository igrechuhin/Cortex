# Plan: Agent Skills Pattern & Tool Composability

## Status: PLANNED

## Priority: P2 (Medium)

## Created: 2026-02-21

## Effort: 2 sprints

## Motivation

Anthropic's "Equipping Agents for the Real World with Agent Skills" and "Code Execution with MCP" describe patterns for making agent tools more composable and dynamically loadable. Cortex can benefit from:

1. **Agent Skills pattern** — organized folders of instructions, scripts, and resources that agents discover and load dynamically
2. **Tool composition via code execution** — reducing round-trips by letting agents compose multiple tool calls into scripts
3. **Dynamic tool discovery** — agents request tool definitions only when needed

**Sources:**

- [Equipping Agents for the Real World with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)

---

## Step 1: Define Cortex Skill Packs

**Concept:** Group related tools, prompts, and examples into "Skill Packs" — self-contained capability bundles that agents can discover and load.

**Proposed skill packs:**

| Skill Pack | Tools | Description |
|-----------|-------|-------------|
| `core` | session_start, load_context, manage_file, think | Essential session operations |
| `quality` | execute_pre_commit_checks, fix_quality_issues, validate_links | Code quality operations |
| `planning` | create_plan, update_plan_step, manage_roadmap, archive_plan | Planning and tracking |
| `refactoring` | analyze_patterns, detect_consolidation, execute_refactoring | Code refactoring |
| `evaluation` | run_evaluation, analyze_results, compare_ab | Evaluation and optimization |
| `context` | load_context, optimize_context, compact_session | Context management |
| `rules` | get_synapse_rules, rules, validate_rule_compliance | Rules and standards |

**Each skill pack includes:**

- Tool list with when-to-use guidance
- Common workflow sequences
- Example invocations
- Troubleshooting tips

**Action:**

1. Define skill pack manifest format (Pydantic model)
2. Create manifest files for each pack
3. Add `discover_skills(task_description)` tool that recommends relevant packs
4. Add `load_skill_pack(pack_name)` tool that loads pack's tools and context

**Acceptance criteria:** 7+ skill packs defined. Discovery tool recommends correct packs for common tasks.

---

## Step 2: Implement Tool Composition Patterns

**Insight (from "Code Execution with MCP"):**
> Agents can compose multiple tool calls into a single code execution step, reducing round-trips and context overhead.

**Current state:** Each Cortex tool call is an independent round-trip. Common workflows require 5–10 tool calls in sequence.

**Action:**

1. Identify top-5 most common tool call sequences from session logs
2. Create **composite tools** for frequent sequences:
   - `quick_start()` = session_start + load_context (for fast orientation)
   - `quality_check()` = pre_commit_checks + fix_quality_issues (single-step quality)
   - `safe_manage_file()` = validate + manage_file + validate (write with guard)
3. Implement as thin wrappers that call underlying tools
4. Measure: round-trip reduction per session

**Acceptance criteria:** 3+ composite tools. 20%+ reduction in average tool calls per session.

---

## Step 3: Dynamic Tool Registry

**Current state:** All 101+ tools registered at startup via decorator side-effects.

**Proposed change:** Two-tier registry:

- **Core registry** (always available): ~20 tools used in >80% of sessions
- **Extended registry** (loaded on demand): remaining tools

**Action:**

1. Analyze usage data to classify tools into core vs. extended
2. Modify tool registration to support lazy loading:
   - Core tools: registered at startup (current behavior)
   - Extended tools: registered when their skill pack is loaded
3. Add `list_available_tools(category?)` for tool discovery
4. Ensure backward compatibility: all tools still accessible, just not all loaded initially

**Acceptance criteria:** Core tools load in <1s. Extended tools load on demand. No functionality regression.

---

## Step 4: Workflow Templates

**Concept:** Pre-defined sequences of tool calls for common tasks, loadable as "recipes."

**Templates:**

1. **New Feature Development**

   ```text
   session_start → load_context(task="implement X") → create_plan → [implement] → pre_commit_checks → fix_issues → compact_session
   ```

2. **Bug Investigation**

   ```text
   session_start → load_context(task="debug X") → search tools → read code → think → implement fix → test
   ```

3. **Quality Review**

   ```text
   session_start → load_context(task="review quality") → analyze_patterns → detect_issues → create_plan(fixes) → execute
   ```

4. **Session Handoff**

   ```text
   compact_session → update_memory_bank → create_progress_entry → end
   ```

**Action:**

1. Define template format (YAML with tool call sequences and branching)
2. Create templates for 4+ common workflows
3. Add `suggest_workflow(task_description)` tool that recommends templates
4. Templates are guidance, not automation — agent follows the sequence but adapts as needed

**Acceptance criteria:** 4+ workflow templates. Suggestion tool functional.

---

## Verification

After all steps:

1. Skill packs defined and discoverable
2. Composite tools reduce round-trips measurably
3. Two-tier tool registry functional
4. Workflow templates guide common tasks
5. No regression in tool functionality
