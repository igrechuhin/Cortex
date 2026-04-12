## Cortex project wiki schema

This document defines the default layout and conventions for `.cortex/wiki/` on any project where Cortex is attached. Projects may copy or adapt it; the on-disk conventions stay stable so tooling (`init-wiki`, ingest, lint) can rely on paths and frontmatter keys.

## Directory layout

```text
.cortex/wiki/
  schema.md         # Normative schema (this document)
  index.md          # Catalog: all pages with one-line summaries, grouped by category
  concepts/         # Core concepts, algorithms, data models
  entities/         # Key classes, modules, services
  decisions/        # Architectural decisions (ADRs, design choices)
  workflows/        # End-to-end behavior and pipelines
  sources/          # Ingested external sources (treat as immutable snapshots)
  analyses/         # Review outputs, session analyses, filed reports
```

## Page frontmatter

Each wiki page (except `index.md` and `schema.md`) should start with YAML frontmatter:

- `title` (string, required): Human title for the page.
- `category` (string, required): One of `concepts`, `entities`, `decisions`, `workflows`, `sources`, `analyses`.
- `tags` (list of strings, optional): Free-form labels for search and linking.
- `source_count` (integer, optional): Number of distinct upstream sources merged into the page.
- `last_updated` (ISO date, optional): Last substantive edit.

## Cross-references

Prefer standard Markdown links to sibling pages under `.cortex/wiki/`. Optional wiki-style links (`[[PageName]]`) may be used when a project adopts that convention consistently; tooling should normalize to relative paths when generating `index.md`.

## Index format

`index.md` is a scan-first catalog. Default table columns:

| Page | Category | Summary | Sources |

- Page: link to the markdown file (relative path from `index.md`).
- Category: one of the category directory names.
- Summary: single line, no trailing period required.
- Sources: short list or count pointing at `sources/` entries or external URLs.

## Immutability

Files under `sources/` are append-only snapshots of ingested material. Corrections belong in new pages or explicit errata; do not rewrite history in place without a documented reason.

## Relationship to memory bank

The memory bank (`.cortex/memory-bank/`) remains the session and roadmap surface. The wiki holds durable, interlinked product and architecture knowledge. Ingest and review flows may write to either or both per project policy.
