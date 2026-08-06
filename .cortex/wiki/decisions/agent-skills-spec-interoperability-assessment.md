---
title: "Agent Skills specification interoperability assessment"
category: decisions
source_count: 1
last_updated: "2026-08-06"
tags:
  - "decisions"
  - "skill-pack"
  - "interoperability"
---

## Agent Skills specification interoperability assessment

**Decision: NO-GO.** Cortex should neither emit nor consume `SKILL.md`-format
Agent Skills at this time. Reasoning, the mapping it follows from, and the
conditions for revisiting are below.

Plan: `.cortex/plans/agent-skills-specification-interoperability-assessment.md`
(documentation only; no source, schema, or manifest was modified).

## Sources and versions

| Source | Version / provenance |
|--------|----------------------|
| Agent Skills specification | <https://agentskills.io/specification>, retrieved 2026-08-06. The spec page carries no explicit version number; it is a living document. |
| Local checkout `~/Repo/skills` | commit `b29e7cf65e5cb78a5ac33d582270551bc74a14eb` (2026-07-24). `spec/agent-skills-spec.md` in that checkout is now only a pointer to the URL above; the normative text was read from the site. |
| Reference validator | `skills-ref validate ./my-skill` (github.com/agentskills/agentskills, `skills-ref`) |
| Examples read | `~/Repo/skills/template/SKILL.md` (minimal), `~/Repo/skills/skills/skill-creator/SKILL.md` (instructions-only), `~/Repo/skills/skills/pdf/` (bundled `scripts/`, `reference.md`, `forms.md`, `LICENSE.txt`) |
| Cortex models | `src/cortex/tools/skill_pack/models.py`; executor `src/cortex/tools/skill_pack/operations.py`; shipped manifests `src/cortex/resources/skills/*.json` (12 packs) |

Licensing note: the specification text is published by the agentskills project
at the URL above; individual skills in the checkout carry their own licenses
(for example `~/Repo/skills/skills/pdf/LICENSE.txt`). Nothing from that
checkout is vendored, copied, or depended on by Cortex as a result of this
assessment.

## The two formats in one paragraph each

**Agent Skills.** A skill is a *directory* whose only required member is
`SKILL.md`: YAML frontmatter (`name`, `description` required; `license`,
`compatibility`, `metadata`, `allowed-tools` optional) followed by unrestricted
Markdown instructions. Optional `scripts/`, `references/`, `assets/`
directories hold code, docs, and resources. Loading is *progressive*: name and
description (~100 tokens) at startup for every skill, the full body (<5000
tokens recommended, <500 lines) on activation, bundled files only on demand.
The artifact is context for a model to read; nothing in it is machine-executed
by the format itself.

**Cortex skill packs.** A pack is a single JSON document validated by
`SkillPackManifest`. Alongside prose guidance (`when_to_use`,
`workflow_sequences`, `example_invocations`, `troubleshooting_tips`) it may
carry a `workflow`: an ordered list of `SkillWorkflowPhase` entries, each
naming an MCP tool and optional operation, with Python-expression
`condition` / `retry_condition` / `success_condition`, a `max_iterations`
retry cap, and `inputs` / `outputs` wiring that passes fields between phases.
`skill_pack(operation="execute")` runs this graph via
`execute_sequential_workflow()` against a real tool registry
(`_build_tool_registry()`), returning a typed `SkillWorkflowResult`.

Packs execute. Skills instruct. Everything below follows from that.

## Field-by-field mapping

Verdicts: **mappable** — survives a round trip with no semantic loss;
**lossy** — representable only as prose an agent must re-interpret;
**unrepresentable** — no target-format construct carries the meaning.

### `SkillPackManifest` → `SKILL.md`

| Cortex field | Agent Skills target | Verdict | Notes |
|--------------|--------------------|---------|-------|
| `name` | frontmatter `name` | mappable | Cortex names (`core`, `quality`, `swiftui-drag-to-dismiss-side-drawer`) already satisfy the lowercase-alphanumeric-hyphen, 1–64 char, no leading/trailing/consecutive hyphen rules. Spec additionally requires the name to equal the parent directory name — trivially satisfiable on export. |
| `description` | frontmatter `description` | mappable | Cortex descriptions are one-liners well under the 1024-char cap. They under-serve the spec's guidance to state *when* to use the skill; `when_to_use` would need to be folded in for trigger quality. |
| `tools` | body prose, or `allowed-tools` | lossy | `allowed-tools` is a space-separated, experimental, client-defined permission list — not a declaration of which MCP tools the skill orchestrates. Mapping Cortex's list there overloads a permission field with semantics it does not have; mapping it to body prose loses machine-readability. |
| `when_to_use` | merged into `description` / body | lossy | No dedicated field. Merging into `description` risks the 1024-char cap and blends two purposes; leaving it in the body removes it from the always-loaded metadata tier where triggering actually happens. |
| `workflow_sequences` | body Markdown | lossy | Becomes advisory prose. The ordering is preserved for a human/model reader but stops being data. |
| `example_invocations` | body Markdown | lossy | Same: prose examples, no structure. |
| `troubleshooting_tips` | body Markdown | lossy | Same. |
| `keywords` | `metadata` map, or body | lossy | `metadata` is string→string only, so a list must be flattened to a delimited string, and no consumer is obliged to read it. Cortex's own scorer (`discover_packs`) would not find these on re-import from another client. |
| `workflow` | — | **unrepresentable** | See below. |

### `SkillWorkflow` → `SKILL.md`

| Cortex field | Verdict | Notes |
|--------------|---------|-------|
| `mode` | unrepresentable | No execution-mode concept exists. Currently only `"sequential"`, so the loss is presently nil in information but total in kind. |
| `phases` | unrepresentable | Reducible only to a numbered prose list, which the target format never executes. |

### `SkillWorkflowPhase` → `SKILL.md`

| Cortex field | Verdict | Notes |
|--------------|---------|-------|
| `name` | lossy | Survives as a heading; no longer an identifier other phases can reference. |
| `tool` | lossy | Survives as prose "call `run_quality_gate`"; the binding to the tool registry is gone. |
| `operation` | lossy | Same, as an argument mentioned in prose. |
| `required` | unrepresentable | No notion of fatal vs. non-fatal steps. |
| `condition` | unrepresentable | A Python expression evaluated against phase context has no target construct; degrades to "if the previous step failed, …", re-interpreted by a model each run. |
| `retry_condition` | unrepresentable | No loop construct. |
| `success_condition` | unrepresentable | No pass/fail predicate; the spec has no result object to evaluate. |
| `max_iterations` | unrepresentable | No retry cap, because there is no retry. |
| `inputs` | unrepresentable | `prior_phase.field` → parameter wiring has no equivalent; data passing becomes the model's memory of what it just read. |
| `outputs` | unrepresentable | No captured result fields. |

Execution-result models (`PhaseResult`, `SkillWorkflowResult`,
`EvaluationReport`) are runtime outputs, not manifest content, and so are out of
the mapping's scope by construction.

### `SKILL.md` → `SkillPackManifest`

| Agent Skills element | Cortex target | Verdict | Notes |
|----------------------|---------------|---------|-------|
| `name` | `name` | mappable | Constraints are strictly tighter than Cortex's, so every valid skill name is a valid pack name. |
| `description` | `description` | mappable | Cap 1024 vs. Cortex's unconstrained `str`. |
| `license` | — | unrepresentable | No field; would need a schema addition. |
| `compatibility` | — | unrepresentable | No field. |
| `metadata` | — | unrepresentable | No free-form map on the manifest. |
| `allowed-tools` | `tools` (approximately) | lossy | Different semantics (permission grant vs. orchestrated tool list), and the values are client tool names such as `Bash(git:*)` and `Read`, not Cortex MCP tools. |
| Markdown body | `when_to_use` + `workflow_sequences` + `troubleshooting_tips` | lossy | An unstructured body must be *split* into Cortex's typed prose fields, which is a lossy heuristic parse, not a mapping. |
| `scripts/`, `references/`, `assets/` | — | **unrepresentable** | A manifest is a single JSON document with no bundle, no file references, and no place to put executable payloads. |
| Progressive disclosure tiers | partially, via `description` + full load | lossy | Cortex loads a whole manifest at `load`; there is no third on-demand tier because there are no bundled files. |
| (none) | `workflow` | **absent at source** | Nothing in a skill supplies phases. |

Every field of all three models appears exactly once across the tables above.

## Export direction: Cortex pack as a `SKILL.md`

A pack without a `workflow` block — several shipped packs are guidance-only —
exports to a valid, useful `SKILL.md` with only the lossy prose flattening
noted above. That is the easy half, and it is also the half with no demand
behind it.

A pack *with* a `workflow` block does not survive. The phase list, its
conditions, retries, success predicates, iteration caps, and input/output
wiring are all unrepresentable, and they are precisely the part that makes a
pack more than a document: `skill_pack(operation="execute")` runs them
deterministically and returns a typed `SkillWorkflowResult` with per-phase
pass/fail. Exported, that becomes a numbered list a model may or may not follow
in order, with no retry semantics and no pass/fail contract. The specific
fidelity loss is therefore: **export discards deterministic execution and
converts a verifiable result into an unverified narrative.** The prose fields
survive; the reason the format exists does not.

There is a second, quieter loss: a pack's tools are Cortex MCP tools. A
`SKILL.md` consumed anywhere other than a Cortex-connected agent names tools
that do not exist in the reader's environment, so even the prose degrades to
non-actionable.

## Import direction: marketplace `SKILL.md` as a Cortex pack

Frontmatter maps cleanly enough to populate `name` and `description`. The body
must then be heuristically split across `when_to_use`, `workflow_sequences`,
`example_invocations`, and `troubleshooting_tips` — a parse that is wrong
often enough to need review on every import. `license`, `compatibility`, and
`metadata` have nowhere to go.

The blocking problem is elsewhere. **Nothing in Cortex would execute an
imported skill.** `execute_sequential_workflow()` requires a `workflow` with
phases bound to entries in `_build_tool_registry()`; an imported skill supplies
neither, so `skill_pack(operation="execute")` has nothing to run and the pack
is reachable only through `discover` and `load` — i.e. it becomes retrievable
prose. Cortex already has retrievable prose: rules, wiki pages, and the memory
bank, all with existing retrieval paths. Import would therefore add a second,
weaker context store rather than a new capability.

Worse, imported skills' bundled `scripts/` are exactly what makes marketplace
skills valuable (see `~/Repo/skills/skills/pdf/scripts/`, eight executable
Python files), and they have no manifest representation at all. Importing the
`SKILL.md` without the bundle imports the part that references the scripts and
drops the scripts. The specific fidelity loss is: **import yields instructions
whose referenced payloads are absent and whose steps nothing executes.**

## Recommendation

**NO-GO**, in both directions, for now.

The mapping shows the two formats are not variants of one idea. Export is
lossless only for the packs that carry the least value and lossy in the single
dimension that defines the rest. Import produces an object Cortex cannot run
and would not retrieve better than its existing context stores. Neither
direction has a requester: no user has asked to publish Cortex packs, and no
workflow currently needs a marketplace skill. Building a converter now would
add a schema surface and a maintenance obligation against an external living
specification, in exchange for capability Cortex already has by other means.

No effort estimate is given, because an estimate is only meaningful for a go.

The cheap insurance is worth naming: the frontmatter half of the spec
(`name` + `description`) is *already* compatible with Cortex manifests by
accident, and staying that way costs nothing. Keeping pack names within the
spec's naming rules and descriptions within 1024 characters preserves the
option to export later without any migration. That is the entire cost of
keeping this door open, and it should be honored as a convention.

## Conditions for revisiting

Reopen this assessment if any of the following becomes true:

1. **A concrete consumer appears** — a user or integration asks to run Cortex
   packs in a non-Cortex agent, or to run a specific marketplace skill inside
   Cortex. A named skill or named consumer, not a general wish.
2. **The specification gains an execution model** — if `SKILL.md` acquires
   structured, machine-executed steps (ordering, conditions, retries, or
   result predicates), the central mismatch disappears and export becomes
   near-lossless. Track the spec at <https://agentskills.io/specification>;
   the version read here is the 2026-08-06 revision.
3. **Cortex grows a bundle concept** — if manifests ever gain file references
   or attached scripts for reasons of their own, the import direction becomes
   cheap enough to reconsider as an addition rather than a redesign.
4. **Guidance-only packs come to dominate** — if most shipped packs stop
   carrying a `workflow` block, the export loss shrinks toward zero and a
   one-way exporter becomes a small, honest piece of work.
5. **A marketplace requirement is imposed externally** — distribution or
   discoverability through a skills marketplace becomes a project goal.

Absent one of these, the answer stands and should not be re-litigated.
