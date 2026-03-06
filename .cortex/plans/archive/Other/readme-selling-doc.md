# Plan: Update and simplify README as selling doc

## Status

DONE

## Goal

Turn the project README into a **selling doc** that a first-time visitor can use to understand why they need this MCP and how to use it. Keep it simple and comprehensive: what it's for, how to use it, and promote the core workflow **plan → implement → commit**.

## Context

- Current README is long (~244 lines), feature-list heavy, and does not lead with value or the main workflow.
- Target audience: someone opening the repo for the first time (e.g. via Cursor, GitHub, or MCP discovery).
- Requirement: they should quickly see (1) what Cortex is for, (2) how to run it, and (3) that the daily loop is plan → implement → commit.
- Existing Phase 85 (Unify Developer Command Surface) touches README for command consistency but does not address messaging or structure; this plan focuses on messaging and simplification.

## Approach

- **Lead with value**: Open with a short "What it's for?" section (one clear paragraph).
- **Then usage**: "How to use it?" with minimal setup (prerequisites, one recommended run option) and the core workflow.
- **Promote simplicity**: Explicitly call out **plan → implement → commit** as the main loop; link to docs/prompts for details.
- **Keep but trim**: Retain prerequisites, run options (condensed or tabbed), key tools by workflow (short table or bullets), and links to full docs. Remove or shorten long reference tables; move deep tool/prompt lists to docs.
- **Preserve**: Badges, credits (Enlighter, Hyperskill), and link to getting-started / tools API.

## Implementation Steps

1. **Add "What it's for?"** – At or near the top, add a single section (2–4 sentences) that states: Cortex is an MCP server for AI memory and context (Memory Bank pattern); it keeps project context, plans, and quality checks in one place so agents can plan, implement, and commit consistently.

2. **Add "How to use it?"** – A short section covering: (a) prerequisites (Python 3.13+, optional Node for markdown lint), (b) one primary way to run (e.g. uvx or manual `uv run cortex`), (c) first steps: e.g. `session(operation="start")` then plan → implement → commit. Link to getting-started and initialize prompt for new projects.

3. **Promote plan → implement → commit** – Add a dedicated subsection or short list that names the loop and what each step does (plan: create/register plans; implement: next roadmap step with checks; commit: pre-commit pipeline and push). Link to implement and commit prompts/docs.

4. **Simplify body** – Condense "Features" to a short bullet list (no long paragraphs). Keep "Running the Server" but consider one primary option first, then "Other options" (uvx, Smithery, Docker, manual) in a compact form. Replace the large "Available Tools" table with a minimal "Key tools by workflow" (session, memory bank, commit pipeline, plans) and link to docs/api/tools.md for full reference.

5. **Simplify "Available Prompts"** – Keep "Which prompt when?" idea; shorten to a small table or bullets and link to docs/prompts for details.

6. **Trim "Memory Bank Structure"** – Keep storage location and core files list; move DRY linking and legacy formats to a single sentence + link to docs.

7. **Documentation block** – Keep a short "Documentation" section with links (getting started, tools API, troubleshooting, advanced tool use).

8. **Validation** – Run markdown lint on README; fix any MD036 or style issues per docs/guides/markdown-formatting.md. Verify all links resolve.

## Verification Checklist

| What to check | Scope | Expected result |
|---------------|--------|-----------------|
| "What it's for?" section exists | README.md | One clear paragraph at or near top |
| "How to use it?" section exists | README.md | Prerequisites + one run method + first steps |
| "plan → implement → commit" explicit | README.md | At least one dedicated mention and short explanation |
| Long tool table reduced | README.md | Short "key tools" list/table + link to docs |
| Markdown lint | README.md | Zero errors (fix_markdown_lint) |
| Links | README.md | No broken internal links |

## Dependencies

- None. Can run independently of Phase 85; if Phase 85 changes commands later, README can be updated to stay consistent.

## Success Criteria

- A first-time reader can answer "What is this for?" and "How do I use it?" from the README in under ~2 minutes.
- The plan → implement → commit workflow is clearly stated and linked.
- README is shorter and easier to scan than the current version while remaining comprehensive (prereqs, run, key tools, prompts, memory bank overview, docs).
- Markdown lint passes; no broken links.

## Testing Strategy

- **Scope**: Documentation only; no production code changes.
- **Manual**: Have a reviewer (or agent) confirm that (1) "What it's for?" and "How to use it?" are present and clear, (2) plan → implement → commit is explicit, (3) links work.
- **Automated**: Run `fix_markdown_lint` (or project markdown lint check) on README.md; ensure zero errors.
- **Regression**: Ensure existing links to docs/getting-started.md, docs/api/tools.md, and other referenced docs still resolve.

## Risks & Mitigation

- **Over-simplification**: Some power users may want the full tool list in README. Mitigation: keep a minimal "key tools" list and a prominent link to full tool reference.
- **Duplication with Phase 85**: Phase 85 may later change command wording. Mitigation: use generic wording ("run the server", "pre-commit pipeline") and link to authoritative docs; sync with Phase 85 when that plan is implemented.

## Timeline

Small doc change; estimate 1–2 hours including review and lint fix.

## Notes

- Align tone with "selling" but stay accurate (no hype).
- Preserve badges (Smithery, Glama) and credits; they support discoverability and attribution.
