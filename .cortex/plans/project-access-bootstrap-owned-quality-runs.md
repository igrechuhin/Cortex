---
title: "Project Access bootstrap and owned quality runs"
component: "development-workflow"
work_type: fix
status: BLOCKED
priority: High
created: 2026-11-15
depends_on: []
execution: agent
---

## Goal

Deliver an isolated, reviewable A/B fix: safe Project Access bootstrap guidance and process-lifetime exclusive quality runs with explicit owned versus foreign responses.

## Context

Ilya approved both fixes and code review: “Годится. Делай план в Cortex и реализуй его. Сообщи как будет готово - проверю код”. The accepted scenarios are useful protected-access denial without blocking normal planning, and a second agent receiving a safe wait response while only one test process runs. Preserve all permissions and mandatory checks.

This separate plan starts from reviewed d896464f29b00cc4303f52f65ad42f1b3f9b07e2 in the linked Cortex worktree /private/tmp/cortex-ab-session-quality-20261115. The canonical checkout's unrelated Stage 1 data-root draft, five source files, 23 cases, index and existing metadata must remain byte-for-byte intact. Do not continue that plan or use its modified loader/handler as a base.

Observed mechanisms: the baseline loader collapses missing policy path and absent/invalid SHA into one exception; bootstrap lacks a safe capability summary. The gate can return a foreign worker's job/result path; the asyncio lock is local to one server and scanning result files before spawn is not atomic across processes. Existing short-lived file locks expire and cannot guard a live worker for its whole lifetime.

The prior native Markdown gate was denied access to /Users/igrechuhin/.cache/uv/sdists-v9/.git. Read-only resolution confirms the unchanged official Markdown command prefers uv run rumdl. Do not retry that denied access, redirect its cache, remove mandatory checks or run alternate tests. Verification that requires this command is blocked until an authorized normal gate environment is available; report exact limits without claiming tests executed.

### Historical checkpoint before cooperative correction (2026-11-15)

A/B is BLOCKED for behavioral verification. The official selected gate executed
124 cases: 121 passed and 3 failed with PermissionError: [Errno 1] Operation not
permitted. The failing nodes are in tests/unit/test_quality_workspace_ownership.py:
worker-death descendant (descendant parameter), legacy dead-supervisor live group,
and terminal-result live group descendant. The bounded recorded output omits
tracebacks, so the exact denied syscall and PID are not established. No affected
action, signal replacement, alternate B selection or permission escalation was used.

The separate scope C plan restored the official Markdown route and passed its
own 45-case selection plus all eight checks and Markdown. Its final static checks
cover the current source, not A/B behavioral acceptance. A/B has 50 authored new
cases in total, including 14 later mocked uncertainty regressions that remain
unexecuted. Subsequent narrow B corrections retain uncertainty after actual test
command timeouts/signal exits and unexpected worker errors; completed assertion
failures and missing tools/config remain normal terminal outcomes.

Real native bootstrap, protected discovery denial and plan creation succeeded
without a Project Access policy. Preserve the isolated draft and the original
checkout. Review artifacts and complete file lists are local to /tmp; no commit,
push, installation, activation or publication occurred.

### Latest authorized execution checkpoint (2026-11-15)

Ilya authorized the cooperative fixture correction and conditional publication of
A/B/C to igrechuhin/Cortex after every mandatory native commit check, including
final Step 12.7 and at least 90% coverage. This supersedes only the earlier
uncommitted-only delivery limit. It does not authorize installation, cache
redirection, permission expansion, a skipped gate or any TradeWing action.
Origin was verified as igrechuhin/Cortex; remote main matched
d896464f29b00cc4303f52f65ad42f1b3f9b07e2. No staging, commit or push occurred.

The signal-based lifecycle fixtures were replaced with bounded cooperative real
processes. Kernel pipe closure and process-group disappearance establish exit;
a real foreign server cannot launch while a descendant lives. Legacy and terminal
paths permit another launch only after exit; abnormal RUNNING uncertainty remains
blocked. Pytest teardown reports cleanup separately from behavioral assertions.
The cooperative A/B gate 3775ec864804 passed eight checks and Markdown with zero
errors/warnings. No denied signal or substitute signal was delivered.

The first fresh full gate f2ad33e30500 executed 8986 tests: 8955 passed, 31 failed,
and four additional cases were skipped. Coverage was 92.15%; all non-test checks
and Markdown passed. This receipt predates the final compatibility corrections
and does not certify the final code. Thirty failures exposed synthetic owner
metadata, per-poll public-client session changes and inherited mocked startup
opt-out. Those fixtures now preserve actual owners and persistent negotiated
sessions, add real foreign-session rejection and isolate only mocked startup
environments. Production A/B/C checks were not relaxed.

Final selected regression 599e9a604f16 passed eight checks plus Markdown, with
zero errors/warnings, observed at 2026-11-15T20:28:19Z. Its successful public
response trims counts; the earlier same-selection diagnostic receipt records
508 run, 508 passed, zero failed and zero skipped. Three new foreign/unowned
cases were added. Neither receipt certifies final full-suite coverage.

The plan remains BLOCKED: the unchanged packaged artifact-migration protocol
case returned MCP Connection closed and invokes uvx with --refresh-package.
The underlying failure is unproven in the bounded public output; its known
installation/cache-dependent command conflicts with this session's limits.
No packaged/full retry, installation, cache relocation or replacement command
will be used. A separately authorized way to execute that required packaged
verification is needed before the complete fresh commit workflow and Step 12.7
can pass. No publication is permitted on selected or stale receipts.

### Authorized packaged-protocol continuation (2026-11-15)

Ilya subsequently authorized diagnosis and correction of the official packaged
protocol smoke: “Нужно править. Должно быть идеально”. The packaging work is now
active in this same plan and worktree, with the same source writer. This updates
the earlier stop-pending-authorization checkpoint; every safety limit remains.

Inspect the sanctioned fixture and retained public evidence first. Preserve the
real uvx --refresh-package cortex --from exact-checkout cortex command, cleared
PYTHONPATH, real packaged install and complete stdio migration assertions. The
tests README and revision acc1b7ff prohibit combining refresh with offline mode.
No skip, fake packaged fixture, mock replacement, weakened assertion, alternate
cache or permission change is allowed. Do not treat Connection closed alone as
evidence of a denied operation.

Add bounded, redacted child stderr/startup diagnostics through the official test
if needed. Test only via existing Cortex gates. Ordinary test-local environment
isolation may preserve the packaged contract; it must not redirect or bypass the
previously refused cache access. If source/preflight proves this mandatory route
necessarily attempts the known prohibited path, stop that exact action, preserve
the evidence and report its legitimate prerequisite. Never retry denied signals.

The host preflight found uv and uvx at the existing local tool installation.
UV_CACHE_DIR, UV_TOOL_DIR and UV_OFFLINE are unset in the caller; the temporary
native MCP launcher supplies UV_NO_SYNC=1. This is configuration evidence only,
not an established failure cause. No uv command was executed during preflight.

After correcting an evidenced cause, reverify affected scopes, the complete fresh
90% gate, final Step 12.7 and docs workflow. Publication authorization remains
conditional on every required check passing and the verified normal main push.

## Scope

**in_scope**

- A: safe session bootstrap state and protected-operation names; closed actionable policy failure reasons distinguishing missing path, missing SHA and invalid SHA.
- Preserve every existing approval/hash/root/path/schema/size/secret check and fail-closed discovery; no policy contents, protected names/paths, approval identities or hashes in the bootstrap summary.
- B: immutable owner/request identity and safe same-owned resume versus foreign pending/busy response.
- Atomic checkout-level cross-process exclusion covering startup, cancellation, worker lifetime and descendants that can continue tests; reuse compatible process coordination and fail closed on uncertainty.
- Synthetic unit/integration/cross-process regressions and concise API documentation; native Cortex planning, implementation handoff, review and verification evidence.

**out_of_scope**

- TradeWing chat, files, data, jobs, adapter/dataroot plan, production runs and the unrelated working draft.
- Permission/authentication expansion, policy activation/configuration, global/duplicate MCP, release, reset or TradeWing publishing. Cortex source staging, commit and push require the fully green official workflow under the latest authorization.
- Retrying the previous uv-cache denial, environment detours, alternate verification commands or weakening mandatory checks.

## Approach

Keep protected data access behind its existing loader. Add a bounded typed public state/reason model that exposes only configuration state and fixed protected-operation vocabulary, with planning explicitly independent. Reuse it for safe structured denial without reading or returning policy content during bootstrap. Where full validation is needed for protected discovery, retain the original checks and redact failures.

For B, establish ownership before looking up or delivering an existing result. The same request owned by the same Cortex session resumes its exact job; other owners receive busy/pending without job adoption or private result metadata. Add the smallest compatible OS/filesystem coordination that atomically spans server processes and remains held while worker/test descendants may still run. Never use timestamp expiry to unlock live work, and never leave a spawned worker unguarded after a canceled waiter or parent exit.

## Implementation Steps

1. Complete native plan creation/readback/roadmap registration in the isolated baseline; record source and preservation evidence.
2. Implement A in the baseline policy/handler/session seams with closed safe bootstrap status and structured error reasons, preserving all validation checks. Add synthetic unconfigured/invalid/denied planning and disclosure tests.
3. Implement B at job selection/spawn/worker lifetime seams; add owned-resume, foreign occupancy, simultaneous server-process launch, cancellation, crashed-parent and test-descendant lifetime regressions with harmless synthetic processes.
4. Review the complete diff, update docs, run only authorized native checks that cannot repeat the forbidden cache access; mark gate-dependent proof blocked if necessary. Retain exact native task state and uncommitted patch for Ilya's code review; verify original checkout hashes/index/status remain unchanged.

## Verification Checklist

- Re-read baseline loader and handler against d896464f; account for every existing check and verify no data-root draft code entered this worktree.
- Inspect bootstrap serialization and all exception paths for policy paths, protected item names, approvals, hashes, raw validation text and secrets.
- Verify native planning without Project Access and fail-closed protected discovery using temporary fixtures.
- Trace request ownership through find/start/poll/cached/delivered paths; check foreign callers cannot adopt a matching job hash or clear another owner's evidence.
- Re-read lock acquire/spawn/pass-through/cleanup and signal/cancellation paths; prove descendants retain exclusion and no second test process starts during parent loss.
- Inspect tests and official gate command selection before running; no forbidden uv-cache read or alternate test command.
- Compare canonical preservation manifest and staged/unstaged/untracked state; provide exact review paths and checks actually performed.

## Dependencies

- Healthy native Cortex session/plan/context/rules/handoff entry points in the separate linked worktree, using existing installed tools read-only.
- Existing local pinned Synapse commit 43d1d387a01468e43c6f20e66de4025855fc968f, attached without network or modifying its canonical checkout.
- A normal authorized native quality environment for executable test proof; the prior cache denial remains a verification blocker, not permission to bypass it.

## Success Criteria

- Session/bootstrap gives fixed safe Project Access state/operation guidance; no policy content is disclosed.
- Missing policy path, absent SHA and invalid SHA have distinct safe structured reasons, while discovery and all protected operations remain fail closed.
- Planning/unrelated workflows work without policy; loader checks and 14-tool arrangement are preserved.
- One owned request is idempotent; a foreign caller gets safe wait status; cross-process/worker/test lifetime is guarded atomically.
- Exact code/test paths, actual check results and remaining verification blockers are recorded; original draft/index/state stay unchanged; publication remains blocked until the complete fresh workflow passes; no permission expansion occurs.

## Testing Strategy

Use Arrange-Act-Assert synthetic fixtures only. Target at least 95% new-branch coverage when the official native gate can run; never infer coverage from authored tests or blocked checks. Add redaction/default/invalid policy and actual planning/bootstrap regressions, then cross-process start-race, owned retry, foreign same-hash/different-hash, cancellation and worker/descendant lifetime cases using temporary roots and harmless marker/sleep processes. No TradeWing job or real test workload is used by coordination regression fixtures. Verify only through authorized Cortex entry points; if a required check cannot run, report that check as unexecuted, preserve actual test counts from prior authorized receipts, and keep full verification blocked.

## Risks and Mitigation

| Risk | Mitigation |
| --- | --- |
| Dirty adapter code leaks into this fix | Separate linked baseline, worktree source precedence, preservation manifest and isolated review diff. |
| Bootstrap reveals protected policy details | Closed typed states, fixed vocabulary and no policy file reads for configuration summary; explicit disclosure assertions. |
| PID/job hash mistaken for ownership | Bind a session/request identity and redact foreign result details before delivery. |
| Parent cancellation/crash releases exclusion early | Process-lifetime lock ownership inherited across the worker/test execution chain and adversarial process fixtures. |
| Stale lock cleanup allows overlap | No time-based unlock of live work; OS lifetime or explicit safe refusal on uncertainty. |
| Native verification touches previously denied cache | Read-only command preflight; no retry, redirection, substituted runner or disabled mandatory check. |

## Change History

- 2026-11-15: Recorded cooperative lifecycle correction, genuine session ownership fixtures, exact native receipts and the unchanged packaged-verification blocker; publication remains conditional and unperformed.

## Packaged Verification Work

1. Inspect fixture, retained evidence and relevant packaging/runtime configuration.
2. Instrument actual child startup with bounded redacted diagnostics if needed.
3. Repair only an evidenced product or sanctioned test-infrastructure defect.
4. Run affected scopes and complete fresh official gates without weakening the packaged contract.

## Observed Packaged Startup Blocker

The authorized diagnostic gate b6a74bed1d02, observed at
2026-11-15T20:52:34Z, executed nine selected cases: eight passed, one failed,
zero skipped. Editable protocol and all seven synthetic diagnostics passed;
the other seven checks plus Markdown passed with zero warnings. The exact
failed node is the packaged artifact-migration stdio protocol. Its unchanged
uvx refresh command failed to open <home>/.cache/uv/sdists-v9/.git with
Operation not permitted (os error 1), before a successful MCP initialization.
The syscall variant and PID are not exposed and must not be inferred.

This establishes the previously prohibited target as the blocker; Connection
closed alone did not establish it. No retry, alternate package command, offline
mode, cache redirection, permission change or substitute signal followed.
The legitimate prerequisite is an authorized executor/toolchain where the
unchanged packaged fixture's required access is permitted. Current session
constraints do not authorize making that access available here.

The narrow test-infrastructure patch captures child stderr in an unlinked
temporary stream, reads a bounded tail, removes terminal escapes before secret
matching, redacts credentials/URLs/private paths and retains a short single-line
JSON failure with the original exception chained. Exact checkout, refresh,
cleared PYTHONPATH, transport and migration assertions remain intact. Synthetic
receipt 1e3b97d656b3 passed all eight checks plus Markdown.

Final full-suite proof, Step 12.7, every remaining commit phase and publication
remain blocked. The earlier full 92.15% coverage receipt predates final fixtures
and is not a final pass. Do not run a selector containing the packaged node or
the full suite until the legitimate prerequisite changes under new applicable
authorization. Preserve this plan, pipeline state, original draft and all code
for review; do not stage, commit or push while blocked.

## Approved Per-Run Packaged Cache Isolation (2026-11-16)

Ilya answered yes to the specific proposal that the real packaged installation
and startup test receives its own temporary uv cache on each run, without any
change to the home cache or its permissions. This narrowly supersedes the older
ban on test-local cache isolation; the known home-cache target remains prohibited
and must not be probed or retried. The guard must remain enabled.

Repair only the sanctioned test fixture. Use a uniquely owned temporary cache
whose lifetime covers actual installation and stdio protocol execution. Verify
that the cache setting reaches real uv, not merely a mocked parameter object.
Preserve refresh, exact checkout, cleared PYTHONPATH, genuine packaged install,
all protocol assertions, and bounded redacted diagnostics. No offline, skipped
checks, mocks replacing the package route, global cache/environment changes,
permission changes, or guard disabling is authorized.

First run the affected installation/protocol test through native Cortex, then
the complete mandatory fresh gate on final code. Finish the ordinary commit
workflow including final Step 12.7 and docs checks. Existing authorization to
publish the A/B/C set remains conditional on every required check passing and
verified normal publication to the agreed GitHub target; preserve the original
draft and TradeWing. If blocked, record exact refusal, phase, results and minimal
legitimate prerequisite instead of publishing.

## Cortex and uv launch contract continuation (2026-11-16)

Owner authorized repository-only repair of the Cortex/uv launch contract and real
integration tests. Existing A/B/C remain intact. No live installation, user config,
TradeWing, permissions, uv binary or denied home storage may be changed or probed.

Evidence: both local uv and uvx are standalone arm64 0.7.9 (13a86a23b,
2025-05-30), /Users/igrechuhin/.local/bin. Installed-tool preparation precedes
Cortex for GitHub uvx and both generated wheel-based plugin commands. Native
receipt a5e12a001e04 confirmed real temporary cache selection, then tool-storage
EPERM; 14 selected, 13 passed, one failed. Exact syscall was not traced. This is
not evidence of a production Cortex crash or a cold-start timeout.

1. Add the smallest explicit opt-in launch-directory contract using standard uv
   mechanisms. Defaults preserve existing launch behavior. Configured paths must
   be explicit and validated; apply identical cache/tools choices to generated
   MCP and SessionStart commands without inventing unsupported host schema keys,
   shell passthrough, implicit activation or retry/fallback on denial. Generated
   output is a new disposable distribution, never an installed plugin or settings.
2. Extend the real exact-checkout packaged protocol fixture to owned storage and
   controlled child state; verify actual uv directory selection. Preserve refresh,
   real installation, cleared source overlay and all migration/protocol assertions.
3. Exercise a real built wheel with the actually generated plugin MCP command and
   SessionStart in synthetic workspaces. Unit wheels alone do not prove packaging.
   Keep bounded redacted diagnostics and fail visibly on denied operations.
4. If permitted network/executor prerequisites are established without accessing
   denied storage, separately compare the documented GitHub uvx entry point cold
   and warm at one full published SHA with owned storage, fixed uv/Python and
   phase timings. Preserve GitHub as source. Baseline remote SHA does not contain
   this unpublished patch and cannot validate it or replace mandatory gates.
5. Run focused native proof first, then final fresh complete 90-percent gate,
   docs and mandatory Step 12.7/parity. Conditional publication remains authorized
   only for the agreed scope after the official workflow passes. Stop affected
   actions at a new refusal; report the exact error and prerequisite.

Acceptance: real install and MCP protocol pass in explicitly allowed disposable
state, generated MCP and startup select the same agreed uv directories, legacy
launch defaults remain unchanged, no home state or live config is altered, and
all final mandatory gates pass before selective commit and normal verified push.

Cold-start hypothesis remains separate: fixture timeout 120 seconds, gate test
budget 600 seconds, plugin startup command 15 seconds and inner adapter 12 seconds.
Actual MCP host startup deadline and Git fetch/build durations were not captured.
Neither the previous EPERM nor Connection closed proves a timeout.

## UV Launch Verification Checkpoint (2026-11-16)

The optional repository launch contract is implemented and remains uncommitted.
Generated MCP and SessionStart receive the same explicit cache/tools pair; default
launches remain unchanged. Real fixtures own home/config/netrc/Python state and
preserve checkout refresh, actual installation and every protocol assertion.

- Separate owner-authorized standalone update succeeded: uv and uvx 0.13.8,
  3d97a6aad, aarch64-apple-darwin, same local bin paths and 0755 modes. The updater
  used UV_NO_MODIFY_PATH=1. This update is not proof that EPERM is fixed.
- Contract gate 003582c4b59d and final unit/static gate e8c6b1827929 passed all eight
  checks and Markdown, with zero errors and warnings. Successful public responses
  trim counts; do not substitute historical counts for those final responses.
- Real selected gate f9e5b4ab269d ran 32 cases: 31 passed, one failed, zero skipped.
  Actual uv cache/tool probes and version matched the owned state. UVX then failed
  before successful Cortex Initialize: DNS lookup failed after three internal
  retries in 4.7 seconds. The redacted response does not identify the hostname or
  dependency; neither is inferred. A spelling token from this run was fixed and
  the final independent unit/static selection passed without retrying UVX.
- Real wheel/plugin MCP/SessionStart, current controlled editable stdio, installed
  METADATA, GitHub cold/warm and full final-code gate/Step 12.7 are unverified.
  No real install route was retried after the DNS failure. No commit or push.

The remaining prerequisite is an authorized normal executor/network with working
DNS and access for the genuine declared dependency fetch. No DNS/proxy/TLS,
permission, home-cache, active config, guard or executor workaround is authorized
by this result. Existing A/B/C and the unrelated original checkout remain intact.

Evidence: /tmp/cortex-uv-launch-final-summary.json and native public records 235,
247 and 255; /tmp/cortex-uv-0.13.8-update-result.json records the separate update.

## Network Diagnosis Checkpoint (2026-11-16)

Read-only diagnosis of retained public receipt f9e5b4ab269d confirms a DNS
resolution error during UVX preparation before Cortex Initialize. The command
uses the local exact checkout, so this was not a GitHub source fetch. The receipt
redacts each full URL to <url>; the original unlinked stderr stream was closed.
The exact historical hostname, package and index-versus-build-download phase
cannot be recovered from that evidence and are not guessed.

The fixture disables uv configuration and does not inherit index overrides. Its
configured standard registry is PyPI. Current proxy and index override variables
are absent. One normal OS resolver call in the same M1 default executor for
pypi.org:443 failed with socket.gaierror errno 8: nodename nor servname provided,
or not known. No permission exception or explicit network-policy rejection was
returned; the underlying DNS cause remains unproven. No alternate resolver,
route, DNS/proxy/TLS modification, escalation or HTTPS/install retry followed.

The temporary-failure recovery condition was not met. Real packaged/plugin,
GitHub experiment, mandatory full gate, Step 12.7 and publication remain blocked.
Required environment: the same authorized Cortex workflow with functioning
normal DNS and HTTPS to its configured registry/dependency endpoints, retaining
uv 0.13.8 and owned test storage. Mac mini readiness was not tested; no checkout,
settings or draft was moved and no separate chat was opened.

Evidence: /tmp/cortex-uv-network-diagnosis-20261116.json and
/tmp/cortex-uv-network-environment-summary.json. No source or test code changed.

## One Authorized Verbose Diagnostic Retry (2026-11-16)

Ilya explicitly requested native verbose logging and one targeted repeat of the
same real packaged installation test on M1. The ordinary DNS check failed with
gaierror errno 8, not an observed PermissionError or explicit policy rejection.
This new authorization permits one diagnostic attempt in the same executor;
it does not permit alternate routes, resolver/proxy/TLS, permissions or home
storage changes. Stop immediately if the executor or network policy refuses.

Use the existing single implement-code writer and native Cortex gates. Add only
bounded safe diagnostics to the real fixture: standard uv verbosity, child stderr
separate from MCP stdout, and retained redacted endpoint-host/phase/error data.
Protect URL userinfo/query credentials, auth headers and terminal-control cases;
run synthetic redaction/contract checks first. Keep genuine checkout refresh,
installation, test-local state, real stdio and all guard/protocol assertions.
Never invent child exit status if the supported SDK does not expose it.

Then execute exactly one targeted packaged diagnostic attempt, without duplicate
plugin or full runs. Return the safe exact error, endpoint host and phase when
observable, with pytest/child exit status only when evidenced. If it passes,
continue already-authorized generated-plugin and mandatory final workflow. If it
fails or policy refuses, stop the affected route and record the exact blocker.

## Verbose Diagnostic Result (2026-11-16)

The single explicitly authorized packaged repeat was accepted as native job
13e8c975f82d and completed: one selected test, zero passed, one failed, zero
skipped; pytest exit 1. The supported SDK does not expose the UV child exit code.
The fixed verbose option, real checkout refresh/install, test-local storage,
original stdio transport and every protocol/guard assertion remain intact.

Retained sanitized stderr now identifies pypi.org, simple-index metadata for
fastmcp during dependency resolution before successful Cortex Initialize. The
final cause was: Request failed after 3 retries in 3.2s; Failed to fetch the
fastmcp simple-index endpoint; failed to lookup address information: nodename nor
servname provided, or not known. This was not a successful GitHub fetch or a
Cortex handshake. DNS failed again; no temporary recovery is established and no
explicit network-policy rejection was observed.

Synthetic security receipt 336a6fd61885 passed 23 of 23 tests. Its length/spelling
findings were corrected before the actual attempt; 13e8c975f82d passed every
seven non-test checks and Markdown with zero warnings. No additional synthetic
run, second real attempt, plugin/full gate or DNS experiment followed. The current
run uses the separately approved standalone uv/uvx 0.13.8.

Diagnostics changed only three test files. Raw stderr stays unlinked; retained
JSON is sanitized and bounded to 64 KiB. The actual retained report is 9085 bytes,
truncated=true, with seven safe PyPI index endpoints. URL userinfo/query data,
auth and cookie headers, terminal controls and partial-record cases are covered.

Evidence: /tmp/cortex-verbose-diagnostic-summary.json; public records 301 and 306;
/tmp/cortex-verbose-sanitized-stderr-13e8c975f82d.json. Root independently reviewed
the safe final cause and retained a matching copy. Existing A/B/C remain intact.

The owner authorized continuing only after a green actual repeat. That condition
was not met. Real generated plugin/SessionStart, complete fresh final gate,
Step 12.7 and publication remain blocked. Required next prerequisite is working
normal DNS/HTTPS to PyPI in an authorized executor. No DNS/proxy/TLS, permissions,
home cache, active installation, alternative machine/chat or route was changed.

## Read-Only Execution Context Comparison (2026-11-16)

The owner requested a bounded diagnosis, without another package test. The same
M1 checkout, Python 3.13.14, system getaddrinfo and fixture environment constructor
were used for pypi.org and the neutral github.com control. Only a short HTTPS
HEAD followed successful DNS. No dependency install, uv process, alternative DNS,
route, proxy, VPN, settings or permission change was performed.

| Context | PyPI DNS | GitHub DNS | HTTPS HEAD |
| --- | --- | --- | --- |
| Managed SDK parent | errno 8, 0.99 ms | errno 8, 0.19 ms | Not attempted |
| Managed fixture child | errno 8, 1.96 ms | errno 8, 0.19 ms | Not attempted |
| Approved ordinary M1 parent | Success, 14.57 ms | Success, 9.71 ms | Both 200 |
| Approved ordinary M1 fixture child | Success, 5.32 ms | Success, 2.63 ms | Both 200 |

Ordinary fixture-child HTTPS times were 146.98 ms for the PyPI fastmcp index
endpoint and 166.97 ms for GitHub. The ordinary-host operation was separately
approved for this read-only comparison; it was not used for package downloads or
Cortex verification. No persistent access setting was changed.

An execution-context difference is measured, and changing the fixture environment
alone does not reproduce or remove it. The managed executor declares restricted
network access. A context network restriction is the leading explanation; the
precise mechanism returning resolver errno 8 is not established by these probes.
This is not evidence of broken system DNS on M1, or a proven Cortex/uv defect.

Keep the plan BLOCKED: networked official Cortex gates need a supported authorized
execution mode while retaining filesystem safeguards. Do not change system DNS,
move the checkout/settings or download dependencies around restrictions. No
packaged, plugin, full or Step 12.7 test was rerun; no publishing occurred.
Evidence: /tmp/cortex-dns-context-comparison-20261116.json.

## Release Preparation: 1.2.0 (2026-11-16)

The owner explicitly requested a proper Cortex release, preserving the existing
patch and TradeWing configuration. This preparation extends the existing plan;
there is no second implementation or competing writer. Keep status BLOCKED.

GitHub read-only evidence confirms latest published release 1.1.1, published
2026-04-22, and remote main still d896464f29b00cc4303f52f65ad42f1b3f9b07e2.
Local release tag 1.1.1 resolves to 5ca73c9728cdc4aa10e477ed1b613dcdf4acdc39.
The public release list and local tags agree; the generic GitHub tags endpoint
was unsupported by the connector and was not retried through a different route.

The checked-in release guide is docs/development/releasing.md. It prescribes
semantic versioning, annotated v-prefixed tags, aligned package metadata, a root
changelog, complete tests with at least 90 percent coverage, maintainer review,
built wheel and source artifacts, installation proof, and GitHub release notes.
Raw legacy test examples do not override mandatory native Cortex gates. The guide
also describes TestPyPI/PyPI publishing; no publishing identity or credentials
were inspected or presumed, and no package upload is prepared as an executed step.
There is no checked-in automated release workflow.

Select backward-compatible minor version 1.2.0 and future annotated tag v1.2.0.
The existing GitHub release numbering is ahead of stale 0.2.0 package metadata;
align pyproject.toml, src/cortex/__init__.py and only the editable cortex entry in
uv.lock, preserving every dependency resolution and all earlier rumdl pin edits.
Add CHANGELOG.md with explicitly unreleased notes. Manual lock metadata alignment
is a reviewable draft, not evidence that uv lock or a locked build has passed.

Release acceptance remains sequential:

1. Obtain a supported network grant for the official executor while retaining the
   current filesystem restrictions and guard. No request_permissions capability is
   exposed here; require_escalated runs unsandboxed and is not permitted for gates.
   An owner-managed network-enabled workspace permission profile is required.
2. Reverify the real packaged installation and actual generated Claude/Codex wheel
   plugin commands including SessionStart; retain real stdio and all assertions.
3. Run fresh complete native Cortex quality and documentation gates, at least
   90 percent coverage, all mandatory CI parity checks, review and Step 12.7.
   No current selected or stale receipt replaces this final proof.
4. After green final code and maintainer review, reverify origin and remote main,
   use the native commit procedure, and push normally to the authorized target.
   Exclude unrelated drafts, runtime links and temporary review artifacts.
5. Build and verify version-aligned wheel and source distributions, then publish
   the annotated tag and GitHub release with exact-SHA CI evidence and artifact
   checksums. Resolve approved package publishing prerequisites separately before
   any TestPyPI or PyPI upload; never probe or transmit credentials.

No active configuration, installed Cortex/TradeWing, network settings or filesystem
permissions change in this preparation. No build, package retry, fresh full gate,
Step 12.7, commit, push, tag or release publication is claimed.

### Release Preparation Result

Prepared only pyproject.toml, src/cortex/__init__.py, the editable project version
in uv.lock, and a new CHANGELOG.md. Static AST/TOML inspection confirms all three
versions are 1.2.0 and the parsed lock differs from its pre-release snapshot only
in that project version. Existing rumdl pins and all dependency resolution data
remain unchanged. This is not uv lock verification or a test receipt.

A separate release-only patch is available at
/tmp/cortex-release-1.2.0-preparation.patch. No final build or new test ran. The
latest packaged receipt remains 13e8c975f82d, one failed before Initialize; the
selected synthetic security receipt is 336a6fd61885, 23 passed. Full current
coverage and Step 12.7 remain unverified. Source version changed, so every older
full or selected receipt remains historical evidence rather than final proof.

Supported owner action: grant network access to this executor in the existing
workspace permission profile, preserving its filesystem rules and approval
policy. Public Codex documentation names sandbox_workspace_write.network_access
for workspace-write, or network.enabled on a named permission profile. This
managed session does not expose its profile name or a request_permissions tool;
no local config edit can be assumed to override its policy. The only exposed
require_escalated path is unsandboxed and is not used for gates. The owner must
apply the appropriate network-only setting at the policy source and resume the
same session, without changing TradeWing configuration or using full access.
Reference: https://learn.chatgpt.com/docs/agent-approvals-security
