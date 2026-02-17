# Session Optimization: Phase 58 multi-agent follow-ups

**Status:** PENDING
**Created:** 2026-02-17
**Priority:** MEDIUM

## Goal

Harden Phase 58 multi-agent specialization by wiring AgentRole into context-effectiveness logging and analysis, and by evolving role-aware guidance in implement/analyze prompts once role data is available.

## Context

Phase 58 introduced `AgentRole` and role profiles plus role-aware `load_context` output, but context-effectiveness logging and analysis still operate at the verb-based task_type level only. This plan captures follow-up work to:

- Record agent roles for `load_context` calls in session logs
- Extend context-effectiveness analysis models to include role dimension
- Use role-aware statistics to tune default budgets and essential file sets per role
- Update prompts/rules to use role terminology consistently

## Implementation Steps

- [ ] **Step 1: Extend load_context logging with roles**
  - [ ] Add optional `role` field to `LoadContextLogEntry` and `ContextUsageEntry` models
  - [ ] Update `log_load_context_call` to record the inferred or explicit role
  - [ ] Ensure analyze_context_effectiveness can read older logs without roles (role field optional)

- [ ] **Step 2: Role-aware context effectiveness models**
  - [ ] Extend context analysis operations to break down statistics by AgentRole (feature/quality/testing/docs/etc.)
  - [ ] Add role-aware budget recommendations (e.g. quality vs testing vs docs) on top of existing task_type patterns
  - [ ] Add tests for mixed-role logs (multiple roles per project) and ensure stats remain stable

- [ ] **Step 3: Prompt and rule updates for roles**
  - [ ] Update implement/analyze prompts to mention AgentRole explicitly when describing task-type budgets and context loading
  - [ ] Add a short section to AGENTS.md and CLAUDE.md describing roles and when to select each
  - [ ] Ensure rules or docs reference AgentRole names consistently (no drift between code and prompts)

- [ ] **Step 4: Validation and evaluation**
  - [ ] Add evaluation tasks for role-aware context loading (quality agent, testing agent, docs agent)
  - [ ] Confirm that Analyze end-of-session reports can surface role-aware insights once logs contain roles
  - [ ] Run full quality gate and tests, and update memory bank/roadmap on completion

## Success Criteria

- Agent roles are recorded for new `load_context` calls without breaking existing logs
- Context-effectiveness statistics can be filtered and summarized per AgentRole
- Implement/analyze prompts and AGENTS docs consistently describe roles and their budgets
- Evaluation tasks exist to guard against regressions in role-aware context loading
