# TradeWing connection plan

Status: review only, 2026-11-14. No TradeWing installation, connection restart,
policy activation, calculation, data copy, or source-path switch is authorized by
this document. Use it with [Approved project access](project-access.md).

## Target and evidence

The existing visible Codex chat is **Провести тренировку модели**, thread
`01a1da1d-d562-7c23-aa25-ec706b3aaeaf`, app host `local`, project directory
`/Users/igrechuhin/Repo/TradeWing`. Do not create, move, interrupt, or send a new
task to that chat as part of this plan. Its preparation work and the separate
**Вынести данные TradeWing из Git** chat have their own owners and work boundaries.

Read-only app history supplied the paths and command below. The relevant completed
turns are `01a1da4a-fc92-74b2-8721-652a484860bf` (profile contract),
`01a1da68-e4e0-7eb3-8f16-e0fb23fc8f1f` (verified v5 copy), and
`01a1da7b-a7d9-7e21-ad97-ea433457552a` (v6 preparation script).
The storage chat reports `COPIES_VERIFIED_CUTOVER_PENDING`: sources and reader
defaults remain in place. These are historical observations, not a fresh seal of
currently changing files. This planning pass did not open a TradeWing database or
reuse a preparation/migration artifact as a test fixture.

The delivered Cortex source is in `/Users/igrechuhin/Repo/Cortex`, with development
entrypoint `/Users/igrechuhin/Repo/Cortex/.venv/bin/cortex`. The reviewed change
adds `manage_file(operation="project_access")` while retaining 14 published tools.
Record the exact commit containing this document before deployment. Do not infer
the visible TradeWing chat's installed Cortex command/version from this development
environment. Its editable package metadata is `0.2.0`, which alone does not identify
this unreleased change. Its current server configuration and resolved MCP root still require
read-only verification; the storage task reported a local diagnostic returning
Cortex context despite a TradeWing roots callback. A root mismatch blocks activation.
Use the existing `cortex://structure` canonical-root fields and `cortex://context`
for that check. Whether its connection/configuration is shared with other chats is
also unverified: a global restart or a change affecting other active chats is outside
this plan and needs a separate reviewed scope and explicit owner consent.

## Exact known locations

Paths in the first five rows are relative to `/Users/igrechuhin/Repo/TradeWing`.

| Purpose | Known path |
| --- | --- |
| Point-profile contract | `research/point-reversal-evaluation-20261113/original-market-profile-prep-v3/point-profile-contract.md` |
| Existing v5 reader | `research/point-reversal-evaluation-20261113/original-market-profile-prep-v5/read_profile.py` |
| Existing v5 builder | `research/point-reversal-evaluation-20261113/original-market-profile-prep-v5/build_profiles.py` |
| v5 source receipt and database | `research/point-reversal-evaluation-20261113/original-market-profile-prep-v5/build-receipt.json`, `market-profiles.sqlite` in the same directory |
| v6 preparation entrypoint | `research/point-reversal-evaluation-20261113/original-market-profile-prep-v6/prepare_profiles.py`, with `README.md` in the same directory |
| Verified external v5 copy | `/Users/igrechuhin/Repo/TradeWing_Data/original-market-profile-prep-v5/market-profiles.sqlite` |
| Preparation script's documented output | `/Users/igrechuhin/Repo/TradeWing_Data/original-market-profile-prep-v6` |
| Migration evidence in TradeWing | `docs/data/storage-migration-receipt-20261114.json`, `docs/data/storage-migration-status-20261114.md` |

The v5 receipt/history reports 183,689,216 bytes and SHA-256
`bb86a2dfe5d298d13f8096c58a2771a1b10ada6a90884870a8cf8bf2469d3030`
for the source and external copy. Recheck both stability and identity with the
preparation/migration owner before any future working-data read. Do not copy it
again for a smoke test or treat the earlier digest as a current filesystem check.
Never overwrite or reuse the documented v6 destination; its current existence and
ownership have not been checked by this planning pass.

## Existing command and its limits

The preparation chat documents this command, run from the TradeWing root:

```sh
python3 -B research/point-reversal-evaluation-20261113/original-market-profile-prep-v6/prepare_profiles.py \
  --output-dir /Users/igrechuhin/Repo/TradeWing_Data/original-market-profile-prep-v6 \
  --interval 1
```

This is evidence of an existing command, not an instruction to execute it now.
Its observed default source is the external v5 database above. The script supports
`--source`, `--estimate-only`, `--verify-only`, and `--in-memory`; preparation and
readback progress are printed to standard output. Even estimate mode hashes and
reads the real archive, so it is not the proposed harmless smoke test.

The existing v5 reader exposes `reader(path)`, `read_point(connection, figi, time)`,
and `read_contract(connection)`. Its observed CLI reads the default v5 database
and prints JSON to standard output. No confirmed CLI database-path or output-file
option was shown in the reviewed evidence. Do not invent one.

No command producing certified complete original profiles is established in the
confirmed delivery. v6 materializes and verifies a partial archive: 13,293 points,
1,794 events, and zero complete profiles. The observed v5 schema explicitly uses
`complete INTEGER CHECK(complete=0)`; v6 copies that schema. It does not settle the
causal population of all trainable points, missing consumer coverage, or historical
availability of fitted parameters. Do not relabel copying/readback as full-profile
calculation or authorize training through this connection.

## Configuration-only activation is blocked

1. **Separate data root.** The delivered policy binds to one canonical project
   root. `TradeWing_Data` is a sibling of `TradeWing`, so the external source and
   desired output cannot be enabled with `../TradeWing_Data`, an absolute output,
   or a symlink. Widening the root to `/Users/igrechuhin/Repo` would also expose
   unrelated repositories and is not an acceptable shortcut. A later, separately
   reviewed Cortex extension must model one explicit data root with independent
   read/write allowlists and owner approval.
2. **Output-directory contract.** Cortex precreates a reserved `output` directory.
   The reviewed v6 script requires its destination to be new and creates it with
   `exist_ok=False`. Passing `{output_directory}` directly therefore conflicts.
   A narrow adapter can select a new child inside Cortex's reservation and call
   the existing entrypoint; do not rewrite the exporter or edit its sealed inputs.
3. **Original payloads.** The archive's `points` table has `point_id`, `figi`,
   `decision_timestamp`, and `complete`. These scalar columns fit the structured
   query interface. `blocks`, `waves`, `compression`, `gaps`, and `contracts` store
   compressed BLOB payloads. Raw dataset queries neither join nor decompress them;
   use the existing approved reader through a reviewed adapter. The current job
   runner discards standard output, so simply registering its JSON-printing CLI
   would not deliver the original profile file.
4. **Size and progress.** v5 exceeds the default 128 MiB snapshot limit; an eventual
   approved snapshot dataset needs at least 183,689,216 bytes, such as a 256 MiB
   cap, below the 512 MiB hard limit. Active WAL/journal sources remain refused.
   The current job status is terminal/reserved state, not live progress; exposing
   the preparation script's progress requires bounded, structured progress fields,
   not unrestricted stdout/stderr. Script/dependency hashes and the exact interpreter
   are not sealed by this plan and must be checked after a safe work boundary.

These are follow-up requirements, not changes implemented or permissions granted
by the commit containing this document. Keep working datasets and preparation jobs
absent from any initial test policy.

## Expected permission boundary

- Bind the connection to the existing TradeWing chat and exact project root. Verify
  the root through the existing connection before changing its configuration.
- Read only individually approved contract/reader files. Approve an ordinary,
  quiescent SQLite snapshot by exact path and explicit table/column set; no arbitrary
  SQL, BLOB decoding, source updates, checkpoints, or automatic WAL conversion.
- After the separate data-root/adapter work, permit writes only to a new reserved
  subdirectory under the explicitly approved `TradeWing_Data` output base. Preserve
  all existing databases, manifests, readers, source paths, and data-migration work.
- Permit only fixed, reviewed existing Python entrypoints with hashes and finite
  parameters. No general shell, arbitrary argv, environment credentials, training,
  trading, evaluation, deployment, or task-router changes. Reviewed jobs remain
  trusted code; Cortex is not an OS filesystem sandbox.
- The external policy and its `CORTEX_PROJECT_ACCESS_POLICY_SHA256` pin are supplied
  by the owner/operator. The agent does not approve or enable its own access.

## Small safe test after explicit approval

First agree a safe boundary with the profile and migration owners. Record the old
MCP command/configuration and disabled policy state. Do not interrupt their work.

For a future chat-level smoke test, the owner can approve a unique isolated area,
for example `research/cortex-access-smoke-<unique>` under TradeWing, containing only
new synthetic text, a tiny SQLite fixture, a harmless marker-writing script, and
an empty `runs` directory. That path is a proposal, not an existing artifact or an
area created by this planning pass. Allow only those exact fixture files, one
dataset, and that one fixture job. Do not include a real v5/v6 file or any migration
copy in the test policy.

After an approved installation/reconnection, verify in the same visible chat:

1. Existing context resolves to `/Users/igrechuhin/Repo/TradeWing`; the tool schema
   contains `project_access` and still lists 14 tools. A mismatch stops the test.
2. `discover`, exact sentinel read, and a one-row fixture query return the expected
   full values. Traversal, a symlink, unknown dataset, and raw SQL fields are refused.
3. Start the harmless fixture job, read status and its exact marker output, and
   repeat the identical start. It must return existing state rather than launch
   again. No working calculations or archive reads participate.
4. Restore access to disabled. Retain the test receipt; remove only that disposable
   fixture area after checking it contains no unrelated work. Never delete a real
   reservation to cause a retry.

## Rollback and approval request

Revoke the policy/pin in the owner-controlled configuration and reconnect only
that Cortex connection at an agreed safe boundary. Restore its previously recorded
command/configuration if the new delivery must be rolled back. Preserve all job
reservations and outputs, and inspect an uncertain worker outcome before any
cleanup. Revocation blocks subsequent tool access; it does not prove that a
previously started worker stopped. This plan changes no source/data paths, so no
migration reversal or Git history rewrite is involved.

The next confirmation should cover the fixture-only connection step, not working
profile preparation. Proposed owner request, after configuration review:

> After your safe preparation/migration boundary, may I install the reviewed Cortex
> commit and reconnect only Cortex for the existing TradeWing chat, then temporarily
> allow the new isolated synthetic smoke area described above (text, tiny SQLite,
> one marker job)? No working profiles, TradeWing_Data access, shell, training, or
> trading will be enabled, and access will return to disabled after the test.

Obtain a separate concrete approval for the exact data root, stable source,
adapter/script hashes, finite parameters, and fresh output destination only after
the listed blockers are resolved. No approval is recorded by this document.
