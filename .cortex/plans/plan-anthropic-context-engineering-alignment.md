# Plan: Anthropic Context Engineering Alignment

## Status: IN PROGRESS

## Priority: P1 (High)

## Created: 2026-02-21

## Effort: 2–3 sprints

## Motivation

Anthropic's engineering blog provides state-of-the-art guidance on context engineering, tool design, and agent evaluation that directly applies to Cortex MCP. This plan aligns Cortex with their published best practices.

**Sources:**

- [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Building Effective AI Agents](https://www.anthropic.com/research/building-effective-agents)

---

## Step 1: Tool Description "Right Altitude" Audit

**Status:** In progress. Rubric added (see [Tool Description Altitude Rubric](../../docs/guides/tool-description-altitude-rubric.md)). Pilot: 5 tools improved with EXAMPLES (list_plans, get_plan, add_roadmap_entry, append_progress_entry, append_active_context_entry). Second batch: 5 more (remove_roadmap_entry, remove_roadmap_section, complete_plan, compact_session, register_plan_in_roadmap). Third batch: 5 more (create_plan, run_preflight_checks, run_docs_and_memory_bank_sync, query_memory_bank, query_usage) — 15 tools total with embedded examples. Full audit of remaining 85+ tools pending.

**Insight (from "Effective Context Engineering"):**
> System prompts should be at the "right altitude" — the Goldilocks zone between hardcoding complex, brittle logic and providing vague, high-level guidance.

**Current state:** Cortex has 101+ tool descriptions. Quality varies — some are highly detailed, others are terse.

**Action:**

1. Audit all 101+ `@mcp.tool()` descriptions for "altitude" — is each one specific enough to guide correct usage, yet flexible enough to handle variations?
2. Create a scoring rubric:
   - **Too low altitude** (brittle): step-by-step instructions that break when context varies
   - **Too high altitude** (vague): descriptions like "Manages files" without guidance on when/how
   - **Right altitude**: clear purpose, input expectations, output format, and when-to-use guidance
3. Score each tool 1–5
4. Rewrite descriptions scoring ≤ 3
5. Add examples to tools scoring ≤ 2 (per Phase 49 pattern)

**Acceptance criteria:** All tools score ≥ 4/5 on altitude rubric. 20+ tools with embedded examples.

---

## Step 2: Tool Response Token Efficiency

**Insight (from "Writing Tools for Agents"):**
> Optimize the quantity of context returned in tool responses. Implement pagination, range selection, filtering, and/or truncation with sensible default parameter values.

**Insight (from "Code Execution with MCP"):**
> Code execution with MCP can reduce context overhead by up to 98.7%.

**Current state:** Cortex tools return string responses. No systematic measurement of response token costs. Some responses may be unnecessarily verbose.

**Action:**

1. **Measure**: Add token counting to all tool responses (instrument `mcp_tool_wrapper`)
2. **Track**: Log response token counts per tool per session
3. **Analyze**: Identify top-10 most token-expensive tools
4. **Optimize**: For each expensive tool:
   - Add truncation with sensible defaults
   - Implement pagination for list-heavy responses
   - Add filtering parameters (e.g., `include_details: bool = False`)
   - Return summaries by default, details on request
5. **Benchmark**: Before/after token comparison for typical workflows

**Metrics to track:**

| Metric | Current | Target |
|--------|---------|--------|
| Avg tokens per tool response | Unknown | Measure, then reduce by 30% |
| Tokens per session (load_context + tools) | Unknown | Measure, then reduce by 20% |
| Redundant tool calls per session | Unknown | Reduce by 50% |

**Acceptance criteria:** Token counting instrumented on all tools. Top-10 expensive tools optimized. 20%+ reduction in average session token usage.

---

## Step 3: Redundant Tool Call Detection

**Insight (from "Writing Tools for Agents"):**
> Lots of redundant tool calls might suggest some rightsizing of pagination or token limit parameters is warranted; lots of tool errors for invalid parameters might suggest tools could use clearer description or better examples.

**Current state:** Phase 57 tracks usage counts and success rates, but does not track redundancy patterns.

**Action:**

1. Extend usage tracking to detect **repeated identical calls** within a session
2. Track **sequential calls to the same tool** (may indicate pagination need)
3. Track **tool error rate by parameter** (which params cause most errors)
4. Add redundancy metrics to Phase 57 evaluation dashboard
5. Use redundancy data to improve tool descriptions and defaults

**Acceptance criteria:** Redundancy tracking active. Dashboard shows top redundant call patterns. ≥ 3 tools improved based on redundancy data.

---

## Step 4: Layered Evaluation (Swiss Cheese Model)

**Insight (from "Demystifying Evals"):**
> Like the Swiss Cheese Model from safety engineering, no single evaluation layer catches every issue. With multiple methods combined, failures that slip through one layer are caught by another.

**Layers recommended:**

1. **Pre-launch evals** (automated, CI/CD) — runs on each change
2. **Production monitoring** — detects distribution drift and real-world failures
3. **A/B testing** — validates significant changes with traffic

**Current state:** Cortex has Phase 57 evaluation framework (26 tasks, A/B testing), but:

- No CI/CD integration (evals don't run in pre-commit or CI)
- No production monitoring (no drift detection)
- A/B testing is framework-only, not automated

**Action:**

1. **Layer 1 — CI/CD evals**: Add eval task suite to pre-commit pipeline. Run a fast subset (10 tasks, <30s) on every commit. Full suite in CI.
2. **Layer 2 — Production monitoring**: Track tool usage patterns per-session. Alert on: sudden drop in tool success rate, new error patterns, unusual token consumption.
3. **Layer 3 — A/B testing automation**: When a tool description changes, automatically run A/B comparison against previous version using eval task suite.
4. **Failure-based eval tasks**: Audit current 26 tasks — are they drawn from real failures? If not, add 10+ tasks based on actual session logs where tools failed or were misused.

**Acceptance criteria:** Eval subset runs in pre-commit. Production monitoring active. A/B testing triggers automatically on tool description changes.

---

## Step 5: Long-Running Agent Harness Improvements

**Insight (from "Effective Harnesses for Long-Running Agents"):**
> Use an initializer agent pattern for session setup. Create a progress file for cross-session continuity. Use Git-based checkpoints for state restoration.

**Current state:** Cortex has `session_start` tool and `compact_session` for handoff. Phase 56 implements progressive summarization. But:

- No structured "progress file" format (like `claude-progress.txt` described in the blog)
- No git-based checkpointing for session state
- No initializer agent specialization

**Action:**

1. **Structured progress tracking**: Create a standardized progress format that `session_start` generates and `compact_session` updates. Include: completed steps, current state, next actions, blockers.
2. **Git-checkpoint integration**: After significant milestones (plan completed, feature implemented, tests passing), automatically create a lightweight git tag or stash for rollback.
3. **Session continuity score**: Measure how effectively sessions hand off context. Track: how many turns before a new session is "productive" (making changes vs. re-reading context).

**Acceptance criteria:** Structured progress format implemented. Session continuity score tracked.

---

## Step 6: On-Demand Tool Loading

**Insight (from "Code Execution with MCP"):**
> Loading tools on demand — agents request tool definitions only when needed, rather than receiving all 100+ definitions upfront.

**Current state:** Phase 49 implemented deferred loading for tool search. But all 101+ tool definitions are still loaded into context at session start.

**Action:**

1. **Categorize tools by frequency**: Identify which tools are used in >80% of sessions (core tools) vs. <10% (specialist tools)
2. **Implement tiered loading**:
   - **Tier 1 (always loaded)**: Core tools (session_start, load_context, manage_file, etc.)
   - **Tier 2 (loaded on demand)**: Specialist tools (refactoring, evaluation, analysis)
   - **Tier 3 (hidden until searched)**: Rarely-used admin/debug tools
3. **Measure impact**: Before/after token savings from tiered loading

**Acceptance criteria:** Tool tiers defined. Tier 2+ tools loaded on demand. 15%+ reduction in initial context tokens.

---

## Verification

After all steps:

1. All tool descriptions reviewed and at "right altitude"
2. Token efficiency instrumented and measurable
3. Redundancy detection active
4. Layered evaluation operational
5. Session continuity improved and measured
6. On-demand tool loading reduces initial context
