# Cortex Project Review and Improvement Recommendations

Reviewed: 2026-09-08. Scope: current checkout; public MCP resources/tools, rules retrieval, plan lifecycle, context budgeting, WAL boundaries, CI, and representative tests. This is a focused project review, not an exhaustive security or dependency audit. Source code was not edited and no commit/push was performed. Existing uncommitted changes were present before the review.

## Verification

- Fresh Cortex MCP quality gate: **7,737 tests passed**, **4 skipped**, **91.42% coverage**. Type checks, source formatting, Synapse formatting/lint, and spelling passed.
- Overall quality gate: **FAILED**. Seven function-length violations in the pre-existing, untracked `.agents/skills/caveman-compress` tree, plus Markdown formatting/broken-link diagnostics under `.agents/skills`. The gate reported no modified files; its Markdown output was truncated, so no complete Markdown violation count is claimed.
- Cortex MCP docs gate: **PASSED** for timestamps, roadmap sync, and roadmap/progress consistency. This does not establish semantic agreement between archived plan status and completion records.
- A safe live WAL probe returned only the project's package manifest. Destructive snapshot behavior was inspected in source, not executed. No external private files were read.
- Normal MCP calls updated operational logs and derived state. Findings below concern existing behavior; fixes are recommendations.

## Priority

Address F1–F3 first, then plan lifecycle F4–F5, followed by context budgeting and workflow verification F6–F7. Small means a localized change plus regression coverage; medium means coordination across a workflow or multiple modules. These are relative effort estimates.

## F1 · P1 · Constrain snapshot labels before any filesystem mutation

MemoryWAL.snapshot joins an unrestricted label to the snapshot directory, then recursively deletes an existing destination. MemoryWALInput accepts any string, and the handler passes it through. An absolute label or parent traversal can therefore select another directory writable by the server.

**Impact:** A malformed snapshot request can recursively delete data outside the snapshot store. This requires a caller with access to the MCP tool; it is not a claim of unauthenticated remote access.

**Improvement:** Use one shared label validator for snapshot and restore: require a single nonempty component, reject dot segments and separators, resolve the destination under the snapshot root, and reject escapes and symlinks. Validate before creating or deleting anything.

**Acceptance:** In temporary fixtures, reject absolute paths, parent traversal, dot labels, and symlink escapes; assert unrelated sentinel files survive. Preserve a valid snapshot/restore round trip.

**Evidence confidence:** Source-confirmed; destructive operation not executed. **Effort:** Small.

Sources: [src/cortex/memory/wal.py:286](/Users/igrechuhin/Repo/Cortex/src/cortex/memory/wal.py:286), [src/cortex/tools/memory/wal_tool.py:49](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/memory/wal_tool.py:49), [src/cortex/tools/memory/wal_tool.py:99](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/memory/wal_tool.py:99).

## F2 · P1 · Restrict historical reads to the memory bank

wal_as_of builds project_root / file and reads the result without checking containment or the permitted file scope. The public handler checks only that file is nonempty. A live MCP call with file='pyproject.toml' returned the manifest as current, unverified content.

**Impact:** The endpoint exposes files beyond its documented memory-bank scope; absolute paths and parent traversal can also reach files readable by the server outside the project.

**Improvement:** Resolve the requested path through the project path resolver, require it to stay within the memory-bank root, and apply the memory-bank filename and symlink policy before reading current content.

**Acceptance:** Cover valid historical reconstruction and rejection of project source files, absolute external paths, parent traversal, and escaping symlinks. Use only synthetic fixtures for external-file checks.

**Evidence confidence:** Live scope violation reproduced with a harmless project manifest; external files not accessed. **Effort:** Small.

Sources: [src/cortex/memory/wal_content.py:240](/Users/igrechuhin/Repo/Cortex/src/cortex/memory/wal_content.py:240), [src/cortex/tools/memory/wal_tool.py:79](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/memory/wal_tool.py:79).

## F3 · P1 · Preserve selected generic rules in the response

The category enum distinguishes UNKNOWN, GENERIC, and GENERAL. _categorize_rules puts only UNKNOWN in generic_rules; _categorize_non_generic_rule accepts a detected language or a local source. Shared GENERIC and GENERAL rules fall through. The live rules resource returned rules_count=0 and rules=[], while reporting 702 selected tokens and 56 indexed files.

**Impact:** Agents can follow the mandatory rules-loading workflow yet receive none of the selected shared coding standards. Separately injected communication and reflection text does not restore those missing rules.

**Improvement:** Map GENERIC and GENERAL explicitly into the generic bucket. Ensure every selected rule appears exactly once in the returned categories and compute token totals from the delivered rules.

**Acceptance:** Add shared-rule fixtures for GENERIC and GENERAL, alongside language and local rules; assert no loss or duplication and consistent counts/tokens at the public resource boundary.

**Evidence confidence:** Live symptom observed; deterministic categorization defect identified. **Effort:** Small.

Sources: [src/cortex/optimization/rules_hybrid.py:214](/Users/igrechuhin/Repo/Cortex/src/cortex/optimization/rules_hybrid.py:214), [src/cortex/optimization/rules_hybrid.py:234](/Users/igrechuhin/Repo/Cortex/src/cortex/optimization/rules_hybrid.py:234), [src/cortex/optimization/models/_rules.py:24](/Users/igrechuhin/Repo/Cortex/src/cortex/optimization/models/_rules.py:24).

## F4 · P1 · Persist DONE when completing a plan

complete_plan updates the memory bank and archives the plan without setting its frontmatter status to DONE. Dependency resync then reads the archived status. The recently completed analytics plan still returns status: PENDING through plan(get), and session/context list it as READY. The session summary reported 551 READY plans, including QUICK_START and historical work; graph enumeration accepts every Markdown file and defaults missing status to PENDING.

**Impact:** Completed work can be recommended again, and dependent plans can remain blocked despite completion. Archive inclusion is needed for dependency resolution but currently also pollutes the actionable queue.

**Improvement:** Set canonical DONE metadata as part of completion before dependency resync. Separate the dependency lookup set from active actionable plans; exclude scaffolding. Repair historical metadata using recorded completion evidence, without assuming every archived plan is done.

**Acceptance:** Exercise create/register → complete/archive → graph/session/context from PENDING input. Assert the completed plan disappears from READY and its dependent unblocks. Include legacy metadata, scaffold files, and declined archived work.

**Evidence confidence:** Live metadata mismatch plus source-confirmed missing transition. **Effort:** Medium.

Sources: [src/cortex/tools/plans/completion.py:77](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/plans/completion.py:77), [src/cortex/tools/plans/completion_archive.py:79](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/plans/completion_archive.py:79), [src/cortex/tools/plans/register_artifact_graph.py:194](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/plans/register_artifact_graph.py:194), [src/cortex/core/artifact_graph.py:185](/Users/igrechuhin/Repo/Cortex/src/cortex/core/artifact_graph.py:185), [tests/tools/test_plan_completion_archive.py:86](/Users/igrechuhin/Repo/Cortex/tests/tools/test_plan_completion_archive.py:86).

## F5 · P2 · Make multi-file completion recoverable

do_complete_plan removes the roadmap bullet before reading/writing activeContext. Progress and archive operations run afterward; archiving still proceeds following a progress failure. Input validation covers the date and progress text but not the later plan filename validation. Existing tests document that missing progress data produces an error after earlier writes.

**Impact:** An I/O error or invalid archive filename can leave a plan partly completed. A retry then cannot find the removed roadmap bullet, requiring manual repair.

**Improvement:** Validate all inputs and read prerequisites before writes, then use the existing snapshot/rollback primitives under a consistent lock boundary. Restore earlier state on failure or persist a resumable completion record so retries finish safely.

**Acceptance:** Inject failure at each write/archive step and assert state is restored or the next retry completes exactly once. Include invalid plan filename, missing progress, lock denial, and archive failure.

**Evidence confidence:** Source-confirmed and explicitly covered as partial failure in existing tests; no production mutation reproduced. **Effort:** Medium.

Sources: [src/cortex/tools/plans/completion_ops.py:199](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/plans/completion_ops.py:199), [src/cortex/tools/plans/completion_ops.py:325](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/plans/completion_ops.py:325), [src/cortex/tools/plans/completion.py:74](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/plans/completion.py:74), [tests/tools/test_plan_completion_archive.py:590](/Users/igrechuhin/Repo/Cortex/tests/tools/test_plan_completion_archive.py:590).

## F6 · P2 · Budget the complete context response

The base context carries total_tokens, then graph metadata and layered context are appended without recalculating or enforcing that budget. The observed response reported 1,522 tokens but contained 35,347 characters; its 551-item READY list alone occupied 24,229 characters in compact JSON. Character counts are payload measurements, not tokenizer estimates.

**Impact:** The reported utilization understates the delivered context, and archive growth can make a nominally concise resource expensive and distracting.

**Improvement:** Allocate one total response budget across governance, essential context, and optional sections. Return bounded actionable-plan summaries with a route to detailed graph data; count the final serialized payload and expose component costs.

**Acceptance:** Use a fixture with hundreds of plans and long appended sections. Tokenize the final resource response, assert it meets the configured budget, and check essential governance survives truncation.

**Evidence confidence:** Live payload measured; unbudgeted append paths identified. **Effort:** Medium.

Sources: [src/cortex/tools/optimization/handlers.py:375](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/optimization/handlers.py:375), [src/cortex/tools/optimization/handlers.py:160](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/optimization/handlers.py:160), [src/cortex/tools/optimization/handlers_format.py:230](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/optimization/handlers_format.py:230), [src/cortex/tools/plans/plan_graph.py:90](/Users/igrechuhin/Repo/Cortex/src/cortex/tools/plans/plan_graph.py:90).

## F7 · P2 · Test real workflow outcomes in CI

The only checked-in workflow excludes tests marked slow. Both commit-pipeline E2E tests are slow, and the gate test only asserts that a status or preflight_passed key exists, so an error response can satisfy it. The shared-rules integration fixture constructs RulesManager without SynapseManager, while the plan resync fixture starts with an already-DONE dependency.

**Impact:** The green unit-test count does not prove the public workflow supplies rules, transitions plan state, or completes a successful quality gate. The observed gaps cross exactly these boundaries.

**Improvement:** Add a bounded public-MCP lifecycle smoke suite with real shared rules and a PENDING plan, assert semantic outcomes, and exercise a deliberate failing gate as well as a successful one. Schedule the remaining slow suite separately so it actually runs.

**Acceptance:** CI must show the lifecycle smoke tests ran; assert nonempty mandatory rules, DONE/archive state, dependency unblocking, and correct gate pass/fail behavior. Keep fast per-change feedback while recording slow-suite results.

**Evidence confidence:** Source-confirmed CI exclusion and weak outcome assertions. **Effort:** Medium.

Sources: [.github/workflows/quality.yml:313](/Users/igrechuhin/Repo/Cortex/.github/workflows/quality.yml:313), [tests/e2e/test_commit_pipeline.py:52](/Users/igrechuhin/Repo/Cortex/tests/e2e/test_commit_pipeline.py:52), [tests/e2e/test_commit_pipeline.py:85](/Users/igrechuhin/Repo/Cortex/tests/e2e/test_commit_pipeline.py:85), [tests/test_rules_enhancement.py:270](/Users/igrechuhin/Repo/Cortex/tests/test_rules_enhancement.py:270), [tests/tools/test_plan_completion_archive.py:86](/Users/igrechuhin/Repo/Cortex/tests/tools/test_plan_completion_archive.py:86).

## Workspace hygiene

Restore the current gate by deciding which installed skills are project-owned. Fix project-owned skill code and broken links; keep externally installed artifacts outside the repository's owned-code lint scope through an explicit, tested policy. Do not silently weaken source/test standards. The current failures were already present in untracked skill artifacts, so they do not establish a regression in committed main.

## Suggested completion criterion

The improvement pass is complete when WAL operations enforce their declared paths, selected rules survive serialization, plan completion is consistent and retry-safe, the full context response honors its budget, and the workflow tests plus quality/docs gates are green. Prefer strengthening these existing entrypoints over adding tools.

## Remediation evidence (2026-09-16)

The original findings above describe the reviewed baseline; they are retained as
historical evidence. The remediation plan records the implementation and rollback
details for Steps 1–6.

- F1: Snapshot label, replacement, symlink, and external-sentinel regressions pass.
- F2: Historical-read scope regressions reject out-of-scope paths and preserve valid history.
- F3: Real shared-rule integration tests preserve selected rules and accounting.
- F4: Plan graph tests and the public MCP smoke prove PENDING → DONE/archive and dependency unblocking.
- F5: Transaction and recovery tests cover write/archive faults, interruption, retry, and conflicting edits.
- F6: Complete serialized context accounting, mandatory content, invalid/tiny budgets,
  and bounded graph previews pass. Numeric utilization now reflects the complete
  response. Both the existing latency test and the hundreds-of-plans assembly
  regression retain the 100 ms median / 250 ms upper envelope.
- F7: Four public MCP smoke cases pass, including a real successful quality gate
  followed by a deliberately failing test. Twenty-one slow tests execute successfully.
  CI now runs the smoke explicitly on pull requests, rejects missing/empty/skipped
  JUnit results, and runs the slow suite on scheduled/manual workflows.

The smoke exposed two additional defects at the reviewed public boundaries:
FastMCP authorization received no client identity from `AuthContext`, and forced
quality runs retained a fingerprint that could skip tests. Request-session identity
now preserves the trusted-client filter, with an untrusted-client regression;
forced runs invalidate both result caches and the persisted fingerprint.

Focused evidence: 205 safety/rules/completion/context regressions and all nine public
workflow tests passed. The fresh forced quality gate passed with 8,042 passing
tests, four skipped tests, 91.56% global coverage, and zero reported errors or
warnings. The docs gate passed timestamps, roadmap synchronization, and progress
consistency. Remote CI has not been run. The remediation plan and atomic completion
entry retain the final evidence and session lessons.
