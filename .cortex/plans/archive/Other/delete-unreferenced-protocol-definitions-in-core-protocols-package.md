---
title: "Delete Unreferenced Protocol Definitions in core protocols Package"
component: "core/protocols"
work_type: "refactor"
status: PENDING
priority: "Medium"
created: "2026-08-06"
depends_on: []
---

## Goal

Delete the 14 Protocol classes in `src/cortex/core/protocols/` that are referenced nowhere outside their own package, together with the five files that contain nothing but dead protocols and their `__init__` re-exports, removing roughly 1500 lines with no import or behavior change anywhere else.

## Context

A repo-wide over-engineering audit of 820 Python files found that `src/cortex/core/protocols/` is 2919 lines defining 23 structural Protocols, and that 14 of them are never used as a type annotation, never subclassed, never passed to `isinstance`, and never imported outside the protocols package itself. A `ripgrep` sweep across both `src/` and `tests/` returns zero hits for each of the following names other than their own definition and the package `__init__` re-export:

`LinkParserProtocol`, `TransclusionEngineProtocol`, `LinkValidatorProtocol`, `ProgressiveLoaderProtocol`, `SummarizationEngineProtocol`, `RelevanceScorerProtocol`, `ApprovalManagerProtocol`, `RollbackManagerProtocol`, `LearningEngineProtocol`, `RefactoringEngineProtocol`, `ConsolidationDetectorProtocol`, `ReorganizationPlannerProtocol`, `RulesManagerProtocol`, `VersionManagerProtocol`.

Each is a full method-by-method interface mirroring exactly one concrete class that does not declare it, so the interface and the implementation drift independently and the type checker validates neither against the other. The project rule requiring dependency injection through initializers is satisfied by the concrete types already in use; these protocols add no injection point that is not already there.

Nine protocols are genuinely used and stay: `FileSystemProtocol`, `MetadataIndexProtocol`, `TokenCounterProtocol`, `DependencyGraphProtocol`, `ContextOptimizerProtocol`, `SplitRecommenderProtocol`, `PatternAnalyzerProtocol`, `StructureAnalyzerProtocol`, and `SignatureAware`.

This is the first of several finite slices from the same audit. The remaining findings — the unconstructed DI container stack, the test-only benchmark package, the unwired cache manager, the repo-wide dead-symbol sweep, the duplicated strategy metric builders, and the second retry implementation — are deliberately not in this plan and will be registered as their own plans.

## Scope

**in_scope**

- Delete `src/cortex/core/protocols/linking.py`, `loading.py`, `refactoring_execution.py`, `rules.py`, and `versioning.py` in full — every protocol they define is unreferenced.
- Delete `RefactoringEngineProtocol`, `ConsolidationDetectorProtocol`, and `ReorganizationPlannerProtocol` from `refactoring.py`, keeping `SplitRecommenderProtocol`.
- Delete `RelevanceScorerProtocol` from `optimization.py`, keeping `ContextOptimizerProtocol`.
- Prune the matching entries from `src/cortex/core/protocols/__init__.py` imports and `__all__`.
- Delete any test module that exists solely to assert the shape of a removed protocol.

**out_of_scope**

- The nine protocols confirmed in use, and the files `file_system.py`, `token.py`, `analysis.py`, and `mcp.py`.
- Any change to the concrete classes the removed protocols described.
- The other seven audit findings (DI container, benchmarks package, cache manager, dead-symbol sweep, strategy metric duplicates, `with_retry`, `DictLikeModel`).
- Introducing replacement abstractions of any kind.
- Correctness, security, or performance changes.

## Approach

The work is a verified deletion, not a refactor, so the sequence is verify, delete, prove.

First re-run the reference sweep at implementation time rather than trusting the audit snapshot, because the working tree has changed since the audit and a protocol could have gained a caller. The sweep must cover `src/`, `tests/`, and `docs/`, and must match the bare class name rather than an import line, so that a re-export or a string reference is caught. Any name that now has a real consumer is dropped from the deletion list and recorded in the completion note.

Then delete in two passes: whole files first, since those need no surgery, followed by the individual protocol classes inside `refactoring.py` and `optimization.py`. Update `protocols/__init__.py` in the same pass as each deletion so the package never sits in a state where it re-exports a missing name.

Finally prove the deletion is inert. The type checker with zero suppressions is the strongest available evidence that nothing referenced these names, since a structural Protocol used as an annotation anywhere would surface immediately as an unresolved import. Follow that with the full test suite and the docs gate.

## Implementation Steps

1. Re-run the reference sweep for all 14 candidate names across `src/`, `tests/`, and `docs/`, matching bare class names; record any name that has gained a consumer and remove it from the deletion list.
2. Confirm that `PatternAnalyzerProtocol`, `StructureAnalyzerProtocol`, `MetadataIndexProtocol`, `ContextOptimizerProtocol`, `SplitRecommenderProtocol`, `TokenCounterProtocol`, `DependencyGraphProtocol`, `FileSystemProtocol`, and `SignatureAware` still have real consumers, so the keep list is correct before deleting anything.
3. Delete `src/cortex/core/protocols/linking.py` and remove its three names from `protocols/__init__.py`.
4. Delete `src/cortex/core/protocols/loading.py` and remove its two names from `protocols/__init__.py`.
5. Delete `src/cortex/core/protocols/refactoring_execution.py` and remove its three names from `protocols/__init__.py`.
6. Delete `src/cortex/core/protocols/rules.py` and remove `RulesManagerProtocol` from `protocols/__init__.py`.
7. Delete `src/cortex/core/protocols/versioning.py` and remove `VersionManagerProtocol` from `protocols/__init__.py`.
8. Delete the three dead protocol classes from `refactoring.py`, leaving `SplitRecommenderProtocol` and its imports intact, and prune the corresponding `__init__` entries.
9. Delete `RelevanceScorerProtocol` from `optimization.py`, leaving `ContextOptimizerProtocol` intact, and prune the corresponding `__init__` entry.
10. Remove now-unused imports left behind in the two edited files and in `protocols/__init__.py`.
11. Delete any test module whose only purpose was asserting a removed protocol's shape; keep tests covering the retained protocols.
12. Run `run_quality_gate()` and confirm zero type, lint, format, and markdown errors with no new suppressions.
13. Run `run_docs_gate()` and update any guide or wiki page that named a deleted protocol.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read after change |
|------|--------------------|--------------|-------------------------------|
| 1 | Each of the 14 bare protocol names | `src/`, `tests/`, `docs/` | Audit note recording the sweep result |
| 2 | Each of the 9 retained protocol names | `src/`, `tests/` | `protocols/__init__.py` |
| 3 | `LinkParserProtocol`, `TransclusionEngineProtocol`, `LinkValidatorProtocol` | `src/`, `tests/` | `protocols/__init__.py` |
| 4 | `ProgressiveLoaderProtocol`, `SummarizationEngineProtocol` | `src/`, `tests/` | `protocols/__init__.py`, `optimization/progressive_loader_protocols.py` |
| 5 | `ApprovalManagerProtocol`, `RollbackManagerProtocol`, `LearningEngineProtocol` | `src/`, `tests/` | `protocols/__init__.py` |
| 6 | `RulesManagerProtocol` | `src/`, `tests/` | `protocols/__init__.py`, `rules/synapse_manager.py` |
| 7 | `VersionManagerProtocol` | `src/`, `tests/` | `protocols/__init__.py` |
| 8 | `RefactoringEngineProtocol`, `ConsolidationDetectorProtocol`, `ReorganizationPlannerProtocol`, `SplitRecommenderProtocol` | `src/`, `tests/` | `protocols/refactoring.py`, `refactoring/split_generators.py` |
| 9 | `RelevanceScorerProtocol`, `ContextOptimizerProtocol` | `src/`, `tests/` | `protocols/optimization.py`, `optimization/progressive_loader_protocols.py` |
| 10 | Unused imports | `src/cortex/core/protocols/` | `protocols/__init__.py`, `refactoring.py`, `optimization.py` |
| 11 | Removed protocol names | `tests/` | Affected test modules |
| 13 | Removed protocol names | `docs/`, `.cortex/wiki/` | Any page naming a deleted protocol |

## Dependencies

None. This slice touches only the protocols package and its own tests, and does not overlap the file set of the pending ponytail simplification plan.

## Success Criteria

- All 14 named protocols are deleted, or any exception is recorded with the consumer that justified keeping it.
- Five protocol files are removed; `refactoring.py` and `optimization.py` retain exactly one protocol each.
- `src/cortex/core/protocols/__init__.py` re-exports only protocols that still exist, and `__all__` matches the module contents exactly.
- Net reduction in `src/` of at least 1400 lines.
- `run_quality_gate()` reports zero type, lint, format, and markdown errors, with no new type-checker suppressions anywhere in the repository.
- `run_docs_gate()` passes and no documentation page references a deleted protocol.
- The full test suite passes with no import errors and no test deleted other than those covering removed protocols.

## Testing Strategy

Target 95% coverage on the surviving protocols package, using the AAA pattern.

The primary evidence here is negative: a structural Protocol used anywhere as an annotation, base class, or `isinstance` argument would break the type checker or the import graph the moment it disappears, so a clean `run_quality_gate()` plus a clean full-suite run is stronger proof than any new test could be. No new production code is added, so no new unit tests are warranted.

Retain and re-run the tests covering the nine kept protocols, so that pruning `__init__.py` cannot silently drop a live export. Add one negative assertion to the protocols package test confirming that `__all__` and the module namespace agree, which catches a stale re-export in this change and in future ones.

Integration coverage comes from the existing suites for the concrete classes the deleted protocols described — refactoring engine, link validator, transclusion engine, progressive loader, summarization engine, rules manager, and version manager — all of which must pass unchanged, demonstrating that removing the interface changed no behavior.

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| A protocol gained a consumer after the audit snapshot | A live annotation is deleted and the type checker fails | Step 1 re-runs the sweep at implementation time and drops any name that now has a consumer |
| A protocol is referenced only as a string in a forward annotation or docstring | Text-based sweep misses it, deletion breaks a lazy annotation | Sweep matches the bare class name rather than import statements, covering string occurrences |
| Pruning `__init__.py` drops a live export by mistake | Downstream import error at server start | Add the `__all__`-versus-namespace assertion in the package test and run the full suite |
| Deleting an interface removes a documented extension point | A future second implementation has no declared contract | The concrete classes remain injectable through initializers as they already are; reintroduce a protocol only when a second implementation actually exists |
| Documentation or wiki pages name a deleted protocol | Docs gate fails or guidance goes stale | Step 13 runs the docs gate and sweeps `docs/` and `.cortex/wiki/` for the removed names |
| Concurrent work touches the protocols package | Merge conflict | Slice is confined to one package; run after the in-flight commit pipeline settles |
