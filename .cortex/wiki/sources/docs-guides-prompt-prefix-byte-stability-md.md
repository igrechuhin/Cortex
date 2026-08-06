# Prompt-Prefix Byte Stability

Which Cortex surfaces are contractually byte-stable, why it matters, and how the
property is enforced.

## Why it matters

Anthropic prompt caching is an exact-prefix byte match over the rendered request
in the order `tools` → `system` → `messages`. Tool schemas render at position
zero, ahead of everything else. If a single byte drifts between two otherwise
identical sessions, the cache is invalidated from that point onward and the
entire downstream prefix is re-billed at full input price.

Cortex is an MCP server. It does not build the request, cannot set
`cache_control` breakpoints, and cannot issue a pre-warming call — those are the
host's job. What Cortex fully controls is the *content* it contributes: the tool
names, descriptions, and JSON Schemas it registers, and the text served for each
`cortex://` resource. Those bytes are the scope of this contract.

## Not `core/cache_warming.py`

`src/cortex/core/cache_warming.py` refers to Cortex's own internal
`AdvancedCacheManager` file cache. It is an unrelated subsystem, is out of scope
for this contract, and must not be modified in the name of prompt-prefix
stability. The phrase "cache warming" is deliberately avoided everywhere in this
document to keep the two apart.

## Contractually byte-stable surfaces

Each of these must produce identical bytes for two reads with no intervening
state change:

| Surface | Rendered by | Locked by |
| --- | --- | --- |
| MCP tool-schema payload | `cortex.discovery.prompt_prefix.render_tool_schema_payload` | `tests/discovery/test_prompt_prefix_stability.py` |
| `cortex://rules` | `cortex.tools.synapse.rules_operations` | `tests/integration/test_resource_byte_stability.py` |
| `cortex://context` | `cortex.tools.optimization.handlers`, `context_appenders` | `tests/integration/test_resource_byte_stability.py` |
| `cortex://structure` | `cortex.tools.structure` | `tests/integration/test_resource_byte_stability.py` |
| `cortex://validation` | `cortex.tools.linking.validation_operations` | `tests/integration/test_resource_byte_stability.py` |
| `cortex://analysis` | `cortex.tools.context.analysis_operations` | `tests/integration/test_resource_byte_stability.py` |
| `cortex://health/connection` | `cortex.tools.session.connection_health` | `tests/integration/test_resource_byte_stability.py` |

## Rules of construction

- Serialize every agent-visible payload with `sort_keys=True`. Without it, key
  order follows dict construction and can differ across processes.
  `cortex.discovery.prompt_prefix.canonical_json` is the canonical helper.
- Sort any collection derived from a `set`, a `dict` iteration, or a filesystem
  `glob` before it reaches a payload. `get_known_tool_names()` and
  `get_known_script_names()` sort at the accessor for this reason.
- Never interpolate a timestamp, hostname, absolute path, counter, PID, random
  identifier, or session identifier into a tool description, a tool JSON Schema,
  or a resource body.
- Relocate volatile diagnostics rather than deleting them: expose them through
  an operation a caller requests explicitly.

## Explicitly volatile — and correctly so

These surfaces legitimately vary and are **out of scope**. Removing time from
them would break correctness:

- WAL entries (`memory_wal`) — an audit log is worthless without time.
- Task locks — expiry requires wall-clock time.
- File snapshots and rollback labels — identity requires time.
- Session handoffs and pipeline phase records — sequencing requires time.
- Progress and operations-log entries — dated by design.

## Documented exceptions on agent-visible surfaces

- `rules` tool, `diagnostics` operation — returns `last_indexed` and is marked
  `"byte_stable": false` in its own payload. It is never embedded in
  `cortex://rules`; a caller must request it. This is the relocation target for
  the `last_indexed` field that previously drifted the rules body on every
  reindex.
- Error responses (`status: "error"`) carry an exception message that varies
  with the failure. They are serialized with `sort_keys=True` but are not
  claimed to be byte-stable, because an error already invalidates the prefix.

## Conditional registration

No Cortex tool is registered conditionally on configuration, environment, or a
feature flag, so the registered set does not vary between sessions. Setup
prompts are the sole conditional surface (see
`cortex.discovery.published_inventory`); they are prompts, not tools, and do not
occupy position zero.

## Enforcement

`cortex.tools.execution.pre_commit_cache_payload_audit` runs inside the
`quality` pre-commit check. It scans the byte-stable payload-construction files
for volatile constructs (`datetime.now()`, `time.time()`, `uuid4()`,
`getpid()`, raw ISO timestamp literals) and for any `json.dumps` call missing
`sort_keys=True`, failing the quality gate automatically.

The two regression tests are the durable deliverable. The tool-schema test
renders in two subprocesses with differing `PYTHONHASHSEED` values, so it
detects cross-process ordering drift that an in-process comparison would miss.
Both suites include mutation-guard tests that reintroduce a timestamp and assert
the comparison fails — a stability test that cannot fail is worthless.
