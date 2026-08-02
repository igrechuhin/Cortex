## Cortex domain glossary

Canonical vocabulary for this project. New plans are checked against this file by
the advisory terminology gate in `plan(operation="create")`. Only terms that carry
a **project-specific** meaning belong here — generic English is deliberately excluded,
because a glossary polluted with common words turns every check into noise.

## Entry schema

Each term is an `###` heading followed by exactly three bullets:

- **Definition** — one sentence stating what the term denotes in Cortex.
- **Aliases** — comma-separated wordings that mean the same thing and should be
  rewritten to the canonical term. `none` when there are no aliases.
- **Not to be confused with** — comma-separated canonical terms that are commonly
  mistaken for this one. `none` when there is no known confusion.

## Terms

### Plan

- **Definition**: A markdown file under `.cortex/plans/` describing one finite, completable unit of work with goal, scope, implementation steps, and success criteria.
- **Aliases**: plan file, plan document, plan doc
- **Not to be confused with**: roadmap entry, implementation step

### Roadmap entry

- **Definition**: A single bullet in `.cortex/memory-bank/roadmap.md` that registers a plan as upcoming work and points at its plan file.
- **Aliases**: roadmap item, roadmap line, roadmap bullet
- **Not to be confused with**: plan, progress entry

### Implementation step

- **Definition**: One numbered item under a plan's `## Implementation Steps` section, executed in order by `/cortex/do`.
- **Aliases**: plan step
- **Not to be confused with**: pipeline phase, subtask, roadmap entry

### Subtask

- **Definition**: A slice of an implementation step that one `implement-code` invocation completes before reporting back to the orchestrator.
- **Aliases**: sub-step
- **Not to be confused with**: implementation step, pipeline phase

### Pipeline

- **Definition**: A named sequence of phases whose state is persisted under `.cortex/.session/` via `pipeline_handoff` (for example `implement` or `commit`).
- **Aliases**: none
- **Not to be confused with**: workflow schema, pipeline phase

### Pipeline phase

- **Definition**: One stage of a pipeline that writes a phase result consumed by the next stage, such as `select`, `code`, `review`, `finalize`, `verify`, or `fix`.
- **Aliases**: none
- **Not to be confused with**: implementation step, pipeline

### Workflow schema

- **Definition**: The ordered list of slash-command phases configured for a project (`plan` to `implement` to `review` to `commit`, or a variant), reported by `session()`.
- **Aliases**: none
- **Not to be confused with**: pipeline, plan

### Prompt

- **Definition**: A markdown procedure under `.cortex/synapse/prompts/` that an agent reads and executes verbatim.
- **Aliases**: synapse prompt
- **Not to be confused with**: slash command, skill, rule

### Slash command

- **Definition**: The `/cortex/<name>` invocation the user types, which resolves to the prompt of the same name.
- **Aliases**: cortex command
- **Not to be confused with**: prompt, MCP tool

### Skill

- **Definition**: A packaged, host-provided capability the agent may invoke by name, distinct from Cortex's own prompts.
- **Aliases**: none
- **Not to be confused with**: prompt, agent

### Agent

- **Definition**: The model-driven executor running a prompt, holding the conversation and the tool budget.
- **Aliases**: none
- **Not to be confused with**: subagent, orchestrator, MCP tool

### Subagent

- **Definition**: A separate agent spawned by an orchestrator for context isolation, defined by a file under `.cortex/synapse/agents/`.
- **Aliases**: delegated agent, child agent
- **Not to be confused with**: agent, orchestrator

### Orchestrator

- **Definition**: The top-level agent that runs a prompt's phases inline and decides when to delegate to a subagent.
- **Aliases**: none
- **Not to be confused with**: agent, subagent

### MCP tool

- **Definition**: A callable exposed by the Cortex MCP server, such as `plan()`, `manage_file()`, or `run_quality_gate()`.
- **Aliases**: cortex tool
- **Not to be confused with**: slash command, cortex resource

### Cortex resource

- **Definition**: A read-only `cortex://` URI served by the MCP server, such as `cortex://context` or `cortex://rules`.
- **Aliases**: mcp resource
- **Not to be confused with**: MCP tool, wiki page

### Memory bank

- **Definition**: The structured project-state files under `.cortex/memory-bank/`, mutated only through `manage_file()` and `update_memory_bank()`.
- **Aliases**: none
- **Not to be confused with**: wiki, experience store

### Wiki

- **Definition**: The curated knowledge tree under `.cortex/wiki/`, organized into category folders and cataloged by `index.md`.
- **Aliases**: cortex wiki, knowledge base
- **Not to be confused with**: memory bank, wiki page

### Wiki page

- **Definition**: A single markdown document inside a wiki category folder, registered as a row in the wiki index.
- **Aliases**: none
- **Not to be confused with**: wiki, memory bank

### Experience store

- **Definition**: The graph of recorded session outcomes used for experience recall and repeated-failure queries.
- **Aliases**: experience graph
- **Not to be confused with**: memory bank, wiki

### Quality gate

- **Definition**: The `run_quality_gate()` check covering tests, coverage, lint, formatting, file size, and type checking.
- **Aliases**: phase a, pre-commit checks
- **Not to be confused with**: docs gate, review gate

### Docs gate

- **Definition**: The `run_docs_gate()` check covering memory-bank timestamps and roadmap synchronization only.
- **Aliases**: phase b, documentation gate
- **Not to be confused with**: quality gate

### Review gate

- **Definition**: The mandatory completion check inside `/cortex/do` that reuses the review contract before a plan may be marked complete.
- **Aliases**: none
- **Not to be confused with**: quality gate, docs gate

### Rule

- **Definition**: A constraint served through `cortex://rules` that governs how code and documents in this project must be written.
- **Aliases**: synapse rule, coding standard
- **Not to be confused with**: prompt, constitution

### Constitution

- **Definition**: The project's `constitution.md` principles file, scanned against new plans for compliance.
- **Aliases**: none
- **Not to be confused with**: rule

### Session

- **Definition**: One working span with a single primary goal, tracked under `.cortex/.session/` and opened by `session()`.
- **Aliases**: cortex session
- **Not to be confused with**: pipeline

### Handoff

- **Definition**: The structured phase result one pipeline phase writes for the next to read, via `pipeline_handoff`.
- **Aliases**: pipeline handoff, phase result
- **Not to be confused with**: session

### Ingest

- **Definition**: The process that pulls an external source into `.cortex/wiki/sources/` and derives a categorized wiki page from it.
- **Aliases**: ingestion
- **Not to be confused with**: wiki page

### Synapse

- **Definition**: The git submodule at `.cortex/synapse/` holding prompts, agents, and rules shared across Cortex-enabled projects.
- **Aliases**: synapse submodule
- **Not to be confused with**: cortex

### Progress entry

- **Definition**: A dated bullet appended to `.cortex/memory-bank/progress.md` recording work that was actually completed.
- **Aliases**: none
- **Not to be confused with**: roadmap entry, active context entry

### Active context entry

- **Definition**: A dated section appended to `.cortex/memory-bank/activeContext.md` describing completed work that changes current project state.
- **Aliases**: none
- **Not to be confused with**: progress entry
