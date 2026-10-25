---
title: "Canonical read access to approved plans across worktrees"
component: "plans"
work_type: feat
status: DONE
priority: High
created: 2026-10-24
---

## Problem

A legitimate isolated git worktree resolves its own project root correctly, but `plan()` and `manage_file()` reads then see only the worktree's `.cortex/` tree, which can be missing or stale relative to canonical main while main holds current approved plans and validated conclusions (archived DONE plans, memory-bank Completed Work/progress entries, and the review/analysis reports they reference). Agents lose that context, causing rejected research proposals. No public surface addressed canonical reads; internal root resolution was not exposed. Shared Synapse does not solve project context.

## Result representation (verified in code)

Completion records conclusions in (1) archived Plans under `.cortex/plans/archive/` and (2) memory-bank `activeContext.md`/`progress.md`; summaries reference reports under `.cortex/reviews|analyses|queries`. Canonical coverage therefore spans plan reads (incl. archive), memory-bank reads, and closed artifact reads.

## Implemented design

1. `src/cortex/core/canonical_project.py`: git-verified identity. `resolve_canonical_identity` uses `rev-parse --git-common-dir` + `worktree list --porcelain` (main first, bare rejected; porcelain spaceless flags parsed; local root must be exactly one listed worktree; duplicates rejected). Validates canonical dir, memory-bank presence, same-repository common dir, and real-path containment with symlink rejection on `.cortex`/plans. Typed `CanonicalReadFailure` codes; `CapturedSource` single exact-byte capture (digest + `read_text`-parity newline decode + `unchanged()` recheck); `revalidate_revision` HEAD recheck; shared `local_context_unsafe` guard; `canonical_memory_bank_file`/`canonical_artifact_file` per-directory confinement.
2. `plan()` `source` param (`PlanReadSource` enum): `list`/`get` accept `canonical`; all other operations fail closed before dispatch; defaults unchanged (no provenance block). `canonical_reads.py` reuses `build_plan_result_from_text` (layered out of `get_plan_impl` with identical local behavior), keys captures by resolved path, computes local freshness via the existing plan identity index, and applies a final coherence gate (captures unchanged + directory membership unchanged + HEAD revalidated) after freshness assembly; `revision_changed_during_read` otherwise.
3. `manage_file()` `source` param: `operation="read"` only (others rejected before any handler; `include_metadata` rejected — version history is local state). `canonical_read.py` reads memory-bank filenames and closed artifact paths (`.cortex/reviews|analyses|queries/<name>.md`) with one capture, section extraction, and the same coherence gate; local freshness applies the shared context guard plus per-directory/local-root containment and reports `unsafe` rather than reading through symlinks. No managers initialized for the canonical root; nothing written to either root.
4. Canonical identity is exposed through the existing `cortex://structure` resource as a `structure_info.canonical` block (available/relation/roots/common dir/revision, or typed failure) — no new resource; published inventory unchanged.
5. Provenance (`CanonicalReadProvenance`): source, root, relation, `git_revision` (repository context, not a commit claim), `content_sha256` (exact captured working-tree bytes), `local_state` incl. `ambiguous`/`unsafe`/`unreadable`, and `local_missing`/`local_stale`/`local_ambiguous`/`local_unreadable`/`local_unsafe` lists for list.

## Non-goals

- Canonical variants of other manage_file operations or `plan(operation="graph")`; canonical writes; cross-root execution/change state; `resolve_project_root_async` behavior changes; per-entry list byte manifests (deferred optional); unrelated `cortex://project/root` doc/timeout mismatches.

## Files

- New: `src/cortex/core/canonical_project.py`, `src/cortex/tools/plans/canonical_reads.py`, `src/cortex/tools/files/canonical_read.py`, `tests/core/test_canonical_project.py`, `tests/tools/test_plan_canonical_reads.py`, `tests/tools/test_manage_file_canonical_read.py`, `tests/tools/canonical_read_test_support.py`.
- Modified: `core/models/_enums.py` (+`PlanReadSource`, exported), `plans/plan.py`, `plans/crud.py`, `plans/crud_helpers.py`, `plans/crud_models.py`, `files/crud_operations.py`, `files/manage_file_helpers.py`, `structure/main.py`, `docs/api/tools.md`.

## Acceptance criteria (verified by tests)

1. Missing local plan in a real linked worktree: canonical get returns canonical bytes with provenance (root=main, relation=linked_worktree, git_revision=40-hex HEAD, content_sha256=exact file bytes, local_state=missing).
2. Stale local plan: local_state=diverged with distinct digests; list provenance reports local_missing/local_stale slug lists.
3. Memory-bank conclusions and closed artifact reports readable canonically (identical/missing states); canonical tree byte-identical after reads (no wiki bootstrap/manager dirs).
4. Defaults remain local: identical result shapes, provenance null/absent; a positive isolation test shows canonical read then ordinary local write mutates only the worktree.
5. Fail closed: non-read ops with source=canonical (incl. legacy `create_plan`) reject before mutation; invalid source errors; non-git, unlisted/duplicate local worktree, bare main, cross-repo, non-Cortex canonical root, symlink escapes/indirection (canonical and local, incl. `.cortex` ancestor), traversal names, mutation during assembly (file bytes, list membership, HEAD) each fail with typed codes and no content.
6. CRLF canonical bytes: content newline-normalized to `read_text` parity while content_sha256 covers exact bytes.
7. `cortex://structure` canonical block reports the mapping (local_is_canonical and linked_worktree) and typed unavailability; inventory/resource count unchanged.

## Verification

- `uv run python -m pytest tests/tools/test_plan_canonical_reads.py tests/tools/test_manage_file_canonical_read.py tests/core/test_canonical_project.py -q -p no:randomly` — 40 passed.
- Cortex `autofix()` pass applied; `run_quality_gate()` / `run_docs_gate()` receipts recorded in the session log (see progress entry).

## Change History

- 2026-10-24: Scope expanded to memory-bank conclusions after verifying result representation.
- 2026-10-24: Review fixes: porcelain spaceless flags, exact-one local membership, per-directory symlink containment, single-capture coherence with post-assembly re-verify (bytes/membership/HEAD), local freshness confinement with unsafe reporting, artifact-path normalization, legacy canonical-create rejection, identity folded into cortex://structure instead of a seventh resource.
