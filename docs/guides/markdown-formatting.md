# Markdown Formatting Guide

This guide summarizes when to use **headings** vs **emphasis** in markdown to avoid MD036 and other lint violations. The authoritative rule is in Synapse: `.cortex/synapse/rules/markdown/markdown-formatting.mdc`. Use `get_synapse_rules(task_description="markdown formatting")` to load it during markdown work.

## Headings vs emphasis

### Use headings for

- **Section titles** – Major divisions (e.g. `## Context`, `### Success Criteria`)
- **Scores or metrics that introduce a section** – e.g. `### Overall Score: 8.3/10`
- **Subsection titles** – e.g. `### Key Findings`, `### Recommendations`
- **Plan status as a section** – Use `Status: PENDING` or `### PENDING` (heading), not `**PENDING**` alone

Use proper heading syntax: `#`, `##`, `###`, etc.

### Use emphasis (bold) for

- **Inline emphasis** – Highlighting a word or phrase inside a sentence
- **Labels before a list** – e.g. `**Strengths**:` or `**Review Date**:` when followed by content on the next line
- **Metadata labels** – e.g. `**Status**:` when the value is on the same or next line

### MD036: No emphasis as heading

**Rule**: Bold text must not be used in place of a heading. Use heading syntax for section titles.

**Incorrect (triggers MD036)**:

```markdown
**Section Title**

- List item

**Overall Code Quality Score: 8.3/10**
```

**Correct**:

```markdown
### Section Title

- List item

### Overall Code Quality Score: 8.3/10
```

**Correct (bold as label, not heading)**:

```markdown
**Review Date**: 2026-02-12

**Strengths**:

- Item 1
```

## Other enforced rules (summary)

- **MD040**: Fenced code blocks must specify a language (e.g. ` ```python `).
- **MD031 / MD032**: Blank lines around fenced code blocks and lists.
- **MD022**: Blank lines around headings.
- **MD009**: No trailing spaces (or exactly two for a hard line break).
- **MD012**: No multiple consecutive blank lines.
- **MD037**: Code identifiers with `_` or `*` must use inline code (backticks).

Full rules, examples, and validation steps are in the Synapse rule file. Run `read_lints` on markdown files after editing and fix all reported violations before considering the file complete.

## References

- Synapse rule: `.cortex/synapse/rules/markdown/markdown-formatting.mdc`
- Commit prompt: Step 1.5 (Markdown linting) and Step 12.5
- Pre-commit: Markdown lint runs on staged `.md`/`.mdc` files (see `docs/getting-started.md`)
