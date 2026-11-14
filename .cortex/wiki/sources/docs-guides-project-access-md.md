# Approved project access

`manage_file(operation="project_access", content=<JSON>)` provides one explicitly
approved project capability boundary. The MCP inventory remains 14 tools.
Routine Memory Bank operations keep their existing scope and defaults.
`pipeline_handoff` still exchanges state; the script registry still catalogs scripts.

## Approval and installation

Access is disabled by default. No MCP operation enables it or writes its policy.
The server operator must obtain the project's required approval for the exact
files, datasets, existing calculations, parameters, and output location. That
approval does not authorize experiments, training, trading, deployment, or unrelated
project changes.

After approval, the operator supplies two environment variables to the existing
Cortex MCP server configuration:

- `CORTEX_PROJECT_ACCESS_POLICY`: a canonical absolute path to a JSON policy
  outside the attached project, with no symlink components.
- `CORTEX_PROJECT_ACCESS_POLICY_SHA256`: the SHA-256 of that exact policy file.

The operator preserves the existing MCP project roots, caller authorization,
transport, and other permissions. The policy binds to the canonical project root
resolved by Cortex. A request cannot supply another root or policy. Any policy edit
requires a new operator-approved hash and server restart. This is an approval pin,
not a substitute for the host's access controls or project rules.

Install the reviewed Cortex revision in the environment used by that project's MCP
server, then restart its connection. An editable installation reflects source edits;
a separately installed release must be updated first. Do not assume updating the
Cortex checkout updates TradeWing's installed server. No installation, policy, or
TradeWing activation is performed by the fixture tests for this feature.

## Policy shape

This illustrative policy is disabled and grants no working access. Replace names,
paths, hashes, and arguments with verified project values after approval. The job
must be an existing reviewed Python entry script, using its actual command-line
interface. Do not create another exporter or change a task router to fit this example.

```json
{
  "enabled": false,
  "project_root": "/absolute/project",
  "files": ["docs/profile-contract.md"],
  "datasets": {
    "profiles": {
      "path": "data/profiles-snapshot.sqlite",
      "table": "profiles",
      "columns": ["figi", "profile"],
      "max_bytes": 134217728
    }
  },
  "jobs": {
    "export_profiles": {
      "interpreter": "/absolute/project/.venv/bin/python",
      "script": "tools/existing_profile_export.py",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "arguments": ["--output-directory", "{output_directory}", "--figi", "{figi}"],
      "parameters": {"figi": ["APPROVED_FIGI"]},
      "timeout": 600
    }
  },
  "output_directory": "artifacts/approved-profile-runs"
}
```

The output base must already exist inside the project. Every distinct job and
parameter combination receives a new exclusively reserved child directory;
calculation outputs go in its `output` subdirectory. No caller-supplied destination
is accepted. Reservations survive connection restarts, code changes, and failures.
One job may be active per output base. Keep the approved output base stable; changing
it or deleting a reservation bypasses historical deduplication and requires manual
review rather than an automatic retry.

## Requests in a separate TradeWing chat

After installation and explicit policy activation, first ask the agent to load
TradeWing's own rules and contract. These calls verify access without starting a
calculation:

```text
manage_file(operation="project_access", content='{"action":"discover"}')
manage_file(operation="project_access", content='{"action":"read","path":"docs/profile-contract.md"}')
manage_file(operation="project_access", content='{"action":"query","dataset":"profiles","filters":{"figi":"APPROVED_FIGI"},"limit":1}')
```

Use the exact names returned by `discover`, rather than the illustrative names
above. Compare the complete text and selected rows with approved source evidence.
Text reads return character offsets, `next_offset`, and total length. Continue at
`next_offset` to obtain the complete original; do not replace it with a summary.
SQLite returns all configured columns, full scalar values, and a snapshot SHA-256.
It rejects oversized results instead of silently truncating profiles.

For an independently approved preparation job, use its exact finite parameters:

```text
manage_file(operation="project_access", content='{"action":"start","job":"export_profiles","parameters":{"figi":"APPROVED_FIGI"}}')
manage_file(operation="project_access", content='{"action":"status","job":"export_profiles","parameters":{"figi":"APPROVED_FIGI"}}')
manage_file(operation="project_access", content='{"action":"read_output","job":"export_profiles","parameters":{"figi":"APPROVED_FIGI"},"path":"original-profile.json"}')
```

Verification should first use an operator-approved harmless fixture job. The example
`start` call is not permission to run a working TradeWing experiment. A repeated
start returns existing state and never launches a second copy. Missing terminal
publication means reserved/running or interrupted; inspect it rather than rerunning.
Timeouts kill the child process group. A worker interrupted before publication can
leave the active lock in place; recovery requires manual investigation.

## Boundaries and limits

- File paths are exact, canonical project-relative paths. Traversal, absolute paths,
  hidden/sensitive names, symlinks at any level, hardlinks, and nonregular files are
  refused. Credential screening checks the complete text before pagination. It is
  defense in depth: operators must approve only nonsensitive data, since arbitrary
  unlabeled secrets cannot reliably be inferred from their bytes.
- Text files are at most 16 MiB; pages contain at most 8,192 characters. Requests
  are at most 16 KiB. SQLite queries return at most 200 rows and 128 KiB, with at most
  eight equality filters and an offset at most 10,000. Identifiers come from the
  policy; filter values are bound parameters. SQL, table names, shell commands, and
  argv are not request fields. Query execution has a two-second progress budget.
- SQLite sources must be quiescent ordinary snapshots, without WAL or rollback
  journal sidecars. The source is read through a bounded no-follow descriptor and
  queried in memory with a read-only authorizer. Snapshot size defaults to 128 MiB
  and cannot exceed 512 MiB. Use the project's existing snapshot/export calculation
  for an active database; this implementation does not checkpoint or modify it.
- Jobs have a fixed reviewed script hash, an approved absolute interpreter, fixed
  arguments, and finite string parameter choices. Only complete argument placeholders
  are substituted. The approved script bytes execute with their original `__file__`,
  project working directory, and import locations. Existing dependencies and the
  interpreter are trusted operator-approved code; the wrapper is not an OS sandbox.
  Review the calculation to ensure it honors the fresh output destination and does
  not write elsewhere. Host permissions remain authoritative.
- Child processes receive a minimal environment without inherited credentials or
  shell configuration. Standard output/error are discarded to avoid exposing secrets;
  status contains only validated outcome and exit code. Applications requiring
  additional credentials or environment settings are outside this feature.
- The worker publishes complete status files atomically and reserves tasks before
  launch. There is no automatic deletion, restart, cancellation, policy mutation,
  production deployment, or general-purpose filesystem write operation.

## Local validation

`tests/tools/test_project_access.py` and `tests/tools/test_project_access_jobs.py`
use shared temporary fixtures from `tests/helpers/project_access_fixtures.py`,
a fixture SQLite database, and a harmless script writing fixture text. They exercise the existing
`manage_file` dispatch, approval boundaries, file aliases, query injection, output
limits, duplicate execution, child environment isolation, errors, and timeouts.
Run it through the Cortex quality gate with `test_filter="project_access"`; run a
fresh unrestricted gate before declaring whole-repository validation complete.

The remaining integration step is an operator-approved policy using verified
TradeWing paths, table/column names, existing script/CLI, interpreter and output
directory, followed by installation/restart of the server used in its separate chat.
