# MCP Tools API Reference

Complete reference for all MCP tools provided by Cortex.

## Overview

Cortex provides tools organized by functionality phases. Tools return JSON responses with consistent error handling.

**Project root:** Tools do **not** accept a `project_root` parameter. Each tool resolves the project root internally (via MCP roots when available, or current working directory). Do not pass `project_root` when calling tools.

### Tools vs Resources (naming and when to use which)

Cortex follows MCP semantics: **Resources** are GET-like (read-only, load data into context); **Tools** are POST-like (side effects, e.g. write, update, run).

- **Tools** use imperative verb names: `manage_file`, `apply_refactoring`, `configure`, `fix_markdown_lint`. Do not use `get_*` for operations that mutate state.
- **Resources** are identified by `cortex://` URIs (e.g. `cortex://memory-bank/stats`, `cortex://optimization/load-context/{task_description}`). Read-only operations are exposed as both a Tool (for backward compatibility) and a Resource.
- **Prefer Resources for read-only operations** when your client supports MCP resources: use the `cortex://` URI to load data. Use Tools for any operation that writes or changes state.
- **No `get_*` Tool performs writes**; all current `get_*` tools are read-only and have a corresponding Resource. See Phase 43 plan (`.cortex/plans/phase-43-reconsider-tools-registration.md`) for the full inventory and naming conventions.

### MCP Tool Annotations

All Cortex MCP tools include **annotations** that provide metadata about tool behavior without consuming token context in LLM prompts. Annotations help client applications categorize and discover tools more effectively.

**Annotation Types:**

- **`readOnlyHint`** (bool): Indicates tool only reads data (no side effects)
- **`destructiveHint`** (bool): Indicates tool may cause destructive changes (delete, overwrite)
- **`idempotentHint`** (bool): Indicates tool produces same result for repeated calls
- **`openWorldHint`** (bool): Indicates tool accesses external data sources (network, subprocess)

**Annotation Patterns:**

- **Read-only tools**: `readOnlyHint=True`, `idempotentHint=True` (queries, stats, validation)
- **Safe write tools**: `readOnlyHint=False`, `destructiveHint=False` (create, update, append)
- **Destructive tools**: `readOnlyHint=False`, `destructiveHint=True` (delete, rollback, overwrite)
- **External tools**: `openWorldHint=True` (subprocess execution, network calls)

For details on adding annotations to custom tools, see the [Extension Development Guide](../guides/advanced/extension-development.md#mcp-tool-annotations).

**Total Tools by Phase:**

| Phase | Tools | Category |
|-------|-------|----------|
| [Phase 1](#phase-1-foundation-tools) | 9 | Foundation (initialization, file ops, versioning) |
| [Phase 50](#phase-50-consolidated-query-tools) | 2 | Consolidated query (memory bank, usage) |
| [Phase 2](#phase-2-link-management-tools) | — | Link ops via [query_memory_bank](#query_memory_bank) |
| [Phase 3](#phase-3-validation-and-quality-tools) | 5 | Validation & Quality (schema, duplication, scoring) |
| [Phase 4](#phase-4-token-optimization-tools) | 6 | Token Optimization (context, summarization, rules) |
| [Phase 5.1](#phase-51-pattern-analysis-and-insights) | 3 | Pattern Analysis & Insights |
| [Phase 5.2](#phase-52-refactoring-suggestions) | 4 | Refactoring Suggestions |
| [Phase 5.3-5.4](#phase-53-54-safe-execution-and-learning) | 6 | Safe Execution & Learning |
| [Phase 6](#phase-6-shared-rules-repository) | 4 | Shared Rules Repository |
| [Phase 8](#phase-8-project-structure-management) | 7 | Project Structure Management |
| [Phase 5 Evaluation](#phase-5-evaluation-tools) | 4 | Tool evaluation, error patterns, anomalies, optimization workflow |
| [Phase 58](#phase-58-multi-agent-task-locking) | 4 | Multi-agent task locking (claim, release, list, check) |
| [Health-Check](#health-check-analysis) | 1 | Health-Check (prompts, rules, tools analysis) |
| [Sequential Thinking](#sequential-thinking) | 1 | Stepwise reasoning and planning |
| [Legacy](#legacy-tools) | 3 | Legacy Support |

**Phase 50 consolidation (2026-02):** Memory bank read operations (stats, version_history, dependency_graph, link_graph, parse_links, validate_links, resolve_transclusions) are available via **`query_memory_bank`**. Usage analytics (stats, unused, report, recommendations, search, events, observation, timeline, **tool_description_optimization**) are available via **`query_usage`**. Context loading supports progressive strategy via **`load_context(strategy="progressive", ...)`**. File writes and config updates use **`manage_file`** and **`configure`**.

**Tool optimization (reduced surface):** Tool count is kept down by consolidating into **`query_usage`** and **`query_memory_bank`** instead of adding new tools. Tool description optimization (suggestions and A/B plan from usage/error data) is **`query_usage(query_type="tool_description_optimization", tool_name="...", days=90)`** — no standalone tool. For usage-based optimization (finding tools below a usage threshold), use **`query_usage(query_type="unused")`** and **`query_usage(query_type="recommendations")`**. See [Tool optimization baseline](../architecture/tool-optimization-baseline.md) and [tool-optimization-mapping](../architecture/tool-optimization-mapping.md).

**Pruned tools (no longer in the tool list; use consolidated alternatives):**

| Former tool | Use instead |
|-------------|-------------|
| `get_session_tool_anomalies` | `query_usage(query_type="anomalies", hours=24)` |
| `run_tool_optimization_workflow` | `query_usage(query_type="unused")`, `query_usage(query_type="recommendations")`, and [tool-optimization-baseline](../architecture/tool-optimization-baseline.md) workflow |

These tools were removed from the published tool list to reduce tool count; use the alternatives above. See [tool-optimization-mapping](../architecture/tool-optimization-mapping.md).

### Advanced Tool Use (Phase 49)

Cortex supports Anthropic's advanced tool use features for lower token usage and better tool selection:

- **Tool Use Examples** – Tools such as `manage_file` and `validate` expose `input_examples` in tool `meta` (and in docstrings) so clients can improve parameter accuracy. See [Advanced Tool Use](../guides/advanced-tool-use.md#1-tool-use-examples-accuracy).
- **Tool Search** – Tools are categorized into always-loaded vs deferred. The **`search_tools`** tool discovers deferred tools by query; when MCP supports `defer_loading`, only always-loaded tools are sent initially. See [Tool Categorization](../guides/advanced-tool-use.md#tool-categorization-phase-49-step-4) and [Configuration](../guides/advanced-tool-use.md#configuration).
- **Programmatic Tool Calling** – `validate`, `suggest_refactoring`, `apply_refactoring`, and `manage_file` expose `allowed_callers` in `meta` for code-execution orchestration when the client/API supports it. See [Programmatic Tool Calling](../guides/advanced-tool-use.md#programmatic-tool-calling--orchestration-analysis-phase-49-step-7).

Full research, configuration, and usage: [Advanced Tool Use (Anthropic)](../guides/advanced-tool-use.md).

---

## Phase 1: Foundation Tools

Core tools for Memory Bank initialization, file operations, metadata management, versioning, and migration.

### initialize_memory_bank

Initialize Memory Bank in a project directory.

**Parameters:**

None (project root is resolved internally by the tool).

**Description:**

Creates the memory-bank/ directory, generates all 7 core files from templates, initializes the metadata index, and auto-migrates if an old format is detected.

**Returns:**

JSON string with initialization status:

```json
{
  "status": "success",
  "message": "Memory Bank initialized successfully",
  "project_root": "/path/to/project",
  "files_created": ["projectBrief.md", "..."],
  "total_files": 7
}
```

**Status Values:**

- `success` - New Memory Bank created successfully
- `already_initialized` - Memory Bank already exists
- `migrated` - Existing Memory Bank migrated to Phase 1 format
- `error` - Initialization failed

---

### read_memory_bank_file

Read a Memory Bank file with optional metadata.

**Parameters:**

- `file_name` (str) - Name of the file to read (e.g., "projectBrief.md")
- `include_metadata` (bool) - If True, include metadata (tokens, versions, usage stats)

**Description:**

Reads file content with automatic locking and conflict detection. Optionally includes detailed metadata about the file.

**Returns:**

```json
{
  "status": "success",
  "file_name": "projectBrief.md",
  "content": "# Project Brief\n...",
  "metadata": {
    "token_count": 1234,
    "version": 5,
    "sections": ["# Project Brief", "## Goals"]
  }
}
```

---

### write_memory_bank_file

Write or update a Memory Bank file with automatic versioning.

**Parameters:**

- `file_name` (str) - Name of the file to write (e.g., "projectBrief.md")
- `content` (str) - New content for the file
- `change_description` (str | None) - Optional description of changes made

**Description:**

Writes file with automatic versioning, conflict detection, and metadata updates. Creates a snapshot before modification for rollback capability.

**Returns:**

```json
{
  "status": "success",
  "file_name": "projectBrief.md",
  "version": 6,
  "change_type": "modified",
  "token_count": 1250,
  "size_bytes": 5120,
  "content_hash": "abc123...",
  "sections_count": 4
}
```

**Change Types:**

- `created` - File was newly created
- `modified` - Existing file was updated

---

### get_file_metadata

Get detailed metadata for a Memory Bank file.

**Parameters:**

- `file_name` (str) - Name of the file (e.g., "projectBrief.md")

**Description:**

Returns comprehensive metadata including token counts, sections, version history, usage statistics, and file status.

**Returns:**

```json
{
  "status": "success",
  "file_name": "projectBrief.md",
  "metadata": {
    "token_count": 1234,
    "version": 5,
    "size_bytes": 5120,
    "content_hash": "abc123...",
    "sections": ["# Project Brief", "## Goals", "## Scope"],
    "last_modified": "2025-12-25T10:30:00Z",
    "access_count": 42,
    "last_accessed": "2025-12-25T15:00:00Z"
  }
}
```

---

### manage_file

Unified Memory Bank file management tool for read/write/metadata operations.

**USE WHEN:**

- You need a **single entry point** to read, write, or query metadata for Memory Bank files (instead of separate read/write/metadata tools).
- You are building **automated workflows** (commit, roadmap, review) that must safely read/write `.cortex/memory-bank/*.md` with versioning and conflict detection.
- You want **structured error responses** for missing/invalid parameters or file/path issues (safe path construction, conflict, lock, or Git conflicts).

**REQUIRED PARAMETERS:**

- `file_name` (str) - Name of the file within the Memory Bank directory.
  - Examples: `"projectBrief.md"`, `"activeContext.md"`, `"systemPatterns.md"`.
  - Must be a safe filename (no `..`, `/`, `\` or path traversal).
- `operation` (str enum) - Operation to perform:
  - `"read"` - Read file content (optionally with metadata).
  - `"write"` - Write content with versioning and metadata updates.
  - `"metadata"` - Return metadata only (no file content).

**Optional Parameters:**

- `content` (str | None) - Content to write (required when `operation="write"`).
- `include_metadata` (bool) - When `operation="read"`, include metadata block.
- `change_description` (str | None) - Human-friendly description stored in version history.

**Description:**

`manage_file` is the canonical Memory Bank file tool used by higher-level workflows and prompts (roadmap, commit, review). It:

- Resolves `.cortex/memory-bank/` via `get_cortex_path()` and validates `file_name` with safe path construction.
- Provides **rich error responses** for:
  - Missing required parameters (`file_name`, `operation`) with `details.missing`, `details.required`, and `details.operation_values`.
  - Invalid operations (`operation` not in `["read", "write", "metadata"]`) with `valid_operations` and a usage `hint`.
  - Invalid file names and path traversal attempts.
  - Non-existent files (including an `available_files` list for discovery).
  - Write-time conflicts (file conflict, lock timeout, Git conflict) with recovery suggestions.
- Treats Memory Bank files as a **fixed, user-controlled set**: write operations **cannot create new files** under `.cortex/memory-bank/` and will return a structured error if the target file does not already exist.
- For writes, it:
  - Computes file metrics (size, tokens, hash).
  - Creates a new version snapshot with metadata.
  - Updates the metadata index (sections, version history).

**Error UX:**

- Missing required parameters:

  ```json
  {
    "status": "error",
    "error": "Missing required parameters: file_name, operation",
    "details": {
      "missing": ["file_name", "operation"],
      "required": ["file_name", "operation"],
      "operation_values": ["read", "write", "metadata"]
    },
    "hint": "Call manage_file(file_name=..., operation=...) for read/write/metadata operations. See docs/api/tools.md#manage_file."
  }
  ```

- Invalid operation value:

  ```json
  {
    "status": "error",
    "error": "Invalid operation: delete",
    "valid_operations": ["read", "write", "metadata"],
    "hint": "Use one of: 'read', 'write', or 'metadata' for the operation parameter."
  }
  ```

- Attempt to create a new Memory Bank file (disallowed):

  ```json
  {
    "status": "error",
    "error": "Cannot create new Memory Bank file via manage_file: newfile.md does not exist. Only existing Memory Bank files may be modified.",
    "file_name": "newfile.md",
    "available_files": [
      "projectBrief.md",
      "productContext.md",
      "activeContext.md",
      "systemPatterns.md",
      "techContext.md",
      "progress.md",
      "roadmap.md"
    ],
    "hint": "Memory Bank files are managed as a fixed set under .cortex/memory-bank/. Create new files there manually (with explicit user approval) before using manage_file(operation=\"write\") to modify them."
  }
  ```

**Returns:**

- **Read operation (`operation="read"`):**

  ```json
  {
    "status": "success",
    "file_name": "projectBrief.md",
    "content": "# Project Brief\n\n## Overview\n...",
    "metadata": {
      "size_bytes": 2048,
      "token_count": 512,
      "content_hash": "e3b0c442...",
      "sections": [
        {"heading": "## Overview", "level": 2},
        {"heading": "## Goals", "level": 2}
      ],
      "version_history": [
        {
          "version": 1,
          "timestamp": "2026-01-04T10:00:00Z",
          "change_description": "Initial version"
        }
      ]
    }
  }
  ```

- **Write operation (`operation="write"`):**

  ```json
  {
    "status": "success",
    "file_name": "activeContext.md",
    "message": "File activeContext.md written successfully",
    "snapshot_id": "/path/to/.cortex/history/activeContext.md.v3.snapshot",
    "version": 3,
    "tokens": 128
  }
  ```

- **Metadata operation (`operation="metadata"`):**

  ```json
  {
    "status": "success",
    "file_name": "systemPatterns.md",
    "metadata": {
      "size_bytes": 4096,
      "token_count": 1024,
      "content_hash": "f7c3bc1d...",
      "sections": [
        {"heading": "## Architecture Patterns", "level": 2},
        {"heading": "## Design Principles", "level": 2}
      ],
      "version_history": [
        {
          "version": 1,
          "timestamp": "2026-01-03T14:00:00Z",
          "change_description": "Initial patterns documentation"
        }
      ]
    }
  }
  ```

**EXAMPLES:**

- **Example 1 – Read file with metadata:**

  ```python
  await manage_file(
      file_name="projectBrief.md",
      operation="read",
      include_metadata=True,
  )
  ```

- **Example 2 – Write file with versioning:**

  ```python
  await manage_file(
      file_name="activeContext.md",
      operation="write",
      content=(
          "# Active Context\n\n"
          "## Current Work\n\nImplementing DRY linking..."
      ),
      change_description="Updated current work focus",
  )
  ```

- **Example 3 – Get metadata only:**

  ```python
  await manage_file(
      file_name="systemPatterns.md",
      operation="metadata",
  )
  ```

---

### add_roadmap_entry

Add entry to roadmap section, avoiding truncation from full updates.

**USE WHEN:** Create-plan Step 6 needs to register a new plan entry.

**RETURNS:** JSON with operation status, line inserted, error if any.

**Parameters:**

- `section` (str) - **Required.** Section identifier: `"blockers"`, `"active_work"`, `"future"`, or `"pending"`.
- `entry_text` (str) - **Required.** Single bullet line text (e.g., `"- **Title** - PENDING - Description. Plan: .cortex/plans/slug.md."`). If missing leading `"- "`, it will be auto-added.
- `position` (str) - Position within section: `"first"` or `"last"` (default: `"last"`).
- `change_description` (str | None) - Optional description for change tracking.

**Description:**

Performs server-side insertion into `roadmap.md` without requiring the client to send the full roadmap content. This avoids truncation risks from full-content serialization. The tool:

- Parses roadmap sections by header patterns (`## Blockers (ASAP Priority)`, `## Active Work (in progress)`, etc.)
- Validates section identifier and rejects unknown sections
- Rejects completed entries (entries containing `- COMPLETED`, `- COMPLETE`, or `- DONE`) — roadmap records future/upcoming work only
- Inserts the entry at the specified position (first or last bullet in section)
- Applies roadmap corruption fixes before writing
- Uses lock-guarding and conflict detection (same as `manage_file`)

**Section Mapping:**

- `"blockers"` → `## Blockers (ASAP Priority)`
- `"active_work"` → `## Active Work (in progress)` or `### Active Work`
- `"future"` → `## Future Enhancements`
- `"pending"` → `## Pending plans (from .cortex/plans)`

**Returns:**

**Success:**

```json
{
  "status": "success",
  "file_name": "roadmap.md",
  "message": "Entry added to 'pending' section at line 45",
  "line_inserted": 45,
  "section": "pending",
  "error": null
}
```

**Error (unknown section):**

```json
{
  "status": "error",
  "file_name": "roadmap.md",
  "message": "Unknown section: invalid_section",
  "line_inserted": null,
  "section": null,
  "error": "Section must be one of: blockers, active_work, future, pending"
}
```

**Error (completed entry rejected):**

```json
{
  "status": "error",
  "file_name": "roadmap.md",
  "message": "Completed entries not allowed in roadmap",
  "line_inserted": null,
  "section": null,
  "error": "Roadmap records future/upcoming work only. Do not add COMPLETED entries here; record completed work in activeContext.md."
}
```

**Examples:**

- **Add plan entry to pending section:**

  ```python
  await add_roadmap_entry(
      section="pending",
      entry_text="- **Phase 50: Consolidated query tools** - PENDING - Plan: .cortex/plans/phase-50-consolidated-query-tools.md.",
      position="last"
  )
  ```

- **Add blocker entry:**

  ```python
  await add_roadmap_entry(
      section="blockers",
      entry_text="- **Critical bug fix** - PENDING - Blocks all other work.",
      position="first"
  )
  ```

**See also:** `remove_roadmap_entry`, `register_plan_in_roadmap`, `create_plan`, `complete_plan`, `manage_file` (fallback for multi-entry updates).

---

### create_plan

Create, list, or get plan files (single tool for plan CRUD).

**USE WHEN:** Creating a plan (`operation="create"`), listing plans (`operation="list"`), or reading a plan by slug (`operation="get"`). Prefer this over writing the plan file with the Write tool so path resolution and filename sanitization are handled consistently.

**RETURNS:** JSON — `CreatePlanResult` (create), `ListPlansResult` (list), or `GetPlanResult` (get).

**Parameters:**

- `operation` (str) - `create` (default), `list`, or `get`.
- `title` (str | None) - Plan title (required when `operation="create"`).
- `content` (str | None) - Full markdown content (required when `operation="create"`).
- `slug` (str | None) - Filename without `.md` (optional for create; required when `operation="get"`).
- `include_archive` (bool) - Include archive plans when `operation="list"` (default: false).
- `response_format` (str) - `content` or `metadata` when `operation="get"` (default: `content`).

**Description:**

- **create:** Resolves plans directory via project structure; sanitizes slug/filename; writes content to `{plans_dir}/{slug}.md`; creates plans directory if needed.
- **list:** Returns list of plan entries (slug, optional title) under plans directory; optionally includes archive.
- **get:** Reads plan by slug; returns full content or metadata (title, **Status** value).

**Returns:**

**Success:**

```json
{
  "status": "success",
  "file_path": "/path/to/.cortex/plans/phase-x-feature.md",
  "message": "Plan created at ...",
  "error": null
}
```

**Error:**

```json
{
  "status": "error",
  "file_path": null,
  "message": "Failed to create plan file",
  "error": "Could not generate valid filename from title or slug"
}
```

**Examples:**

```python
# Create plan
await create_plan(
    operation="create",
    title="Phase 60: Structured plan tools",
    content="# Phase 60\n\n**Status**: Pending\n\n## Goal\n...",
    slug="phase-60-structured-plan-tools",
)
# List plans
await create_plan(operation="list", include_archive=False)
# Get plan content or metadata
await create_plan(operation="get", slug="phase-60-feature", response_format="content")
await create_plan(operation="get", slug="phase-60-feature", response_format="metadata")
```

**See also:** `register_plan_in_roadmap`, `add_roadmap_entry`, `get_structure_info`.

---

### register_plan_in_roadmap

Register a plan entry in the roadmap using structured merging.

**USE WHEN:** Registering a newly created plan in roadmap.md during the create-plan workflow. Prefer this over building full roadmap content and calling `manage_file(write)` for a single new entry to avoid truncation.

**RETURNS:** JSON with `status`, `file_name`, `message`, `line_inserted`, `section`, and `error` (if any).

**Parameters:**

- `plan_title` (str) - **Required.** Title of the plan (used in roadmap entry).
- `description` (str) - **Required.** One-line or short description for the roadmap entry.
- `status` (str) - Plan status: use `PENDING` or `IN PROGRESS` only (default: `PENDING`). Completed work belongs in activeContext.md; COMPLETED/COMPLETE/DONE are rejected.
- `section` (str) - Roadmap section: `blockers`, `active_work`, `future`, or `pending` (default: `pending`).

**Description:**

- Reads `roadmap.md` via the same path as memory-bank operations.
- Inserts one bullet in the requested section (format: `- **Title** - STATUS - description`).
- Writes updated content with lock-guarding and corruption fixes; no truncation of existing entries.

**Returns:**

**Success:**

```json
{
  "status": "success",
  "file_name": "roadmap.md",
  "message": "Plan registered in 'pending' section at line 45",
  "line_inserted": 45,
  "section": "pending",
  "error": null
}
```

**Error (completed status rejected):**

```json
{
  "status": "error",
  "file_name": "roadmap.md",
  "message": "Failed to register plan",
  "line_inserted": null,
  "section": null,
  "error": "Roadmap records future/upcoming work only. ..."
}
```

**Example:**

```python
await register_plan_in_roadmap(
    plan_title="Phase 60: Structured plan tools",
    description="Reference. Plan: .cortex/plans/phase-60-structured-plan-tools.md.",
    status="PENDING",
    section="pending"
)
```

**See also:** `create_plan`, `add_roadmap_entry`, `remove_roadmap_entry`, `complete_plan`, `manage_file` (fallback).

---

### list_plans (use create_plan(operation="list"))

List plan files: use `create_plan(operation="list", include_archive=False)`. Returns `ListPlansResult` JSON with `status`, `plans` (list of `{slug, title}`), `message`, and `error` (if any).

---

### get_plan (use create_plan(operation="get"))

Read a plan by slug: use `create_plan(operation="get", slug="phase-60-feature", response_format="content"|"metadata")`. Returns `GetPlanResult` JSON with `status`, `slug`, and either full `content` or `title`/`plan_status`.

---

## Phase 50: Consolidated query tools

Single-entry-point tools for Memory Bank and usage analytics (replacing multiple per-operation tools). Use when you need stats, version history, graphs, link parsing/validation, or usage data.

### query_memory_bank

Query Memory Bank with a single tool. Replaces standalone `get_memory_bank_stats`, `get_version_history`, `get_dependency_graph`, `get_link_graph`, `parse_file_links`, `validate_links`, and `resolve_transclusions`.

**USE WHEN:** You need memory bank stats, version history, dependency/link graphs, link parsing or validation, or transclusion resolution. Prefer this over calling multiple separate tools.

**Parameters:**

- `query_type` (str) - **Required.** One of: `stats`, `version_history`, `dependency_graph`, `link_graph`, `parse_links`, `validate_links`, `resolve_transclusions`.
- `file_name` (str | None) - Required for `version_history`, `parse_links`, `validate_links`, `resolve_transclusions`; optional for others.
- `limit` (int) - Max items for version_history (default: 10).
- `format` (str) - Output format for graph types: `"json"` or `"mermaid"` (default: `"json"`).
- `include_transclusions` (bool) - Include transclusions in link_graph (default: True).
- `max_depth` (int) - Max transclusion depth for resolve_transclusions (default: 5).
- `include_token_budget` (bool) - Include token budget in stats (default: True).
- `include_refactoring_history` (bool) - Include refactoring history in stats (default: False).
- `refactoring_days` (int) - Days for refactoring history (default: 90).
- `response_format` (str) - `"concise"` (default) or `"detailed"`. Concise reduces token count.

**Returns:** JSON string. Structure varies by `query_type`. Use `response_format="detailed"` when you need full payloads.

**Example:**

```python
await query_memory_bank(query_type="stats", response_format="concise")
await query_memory_bank(query_type="version_history", file_name="projectBrief.md", limit=5)
await query_memory_bank(query_type="validate_links", file_name="activeContext.md")
```

---

### query_usage

Query usage analytics with a single tool. Replaces standalone `get_tool_usage_stats`, `get_unused_tools`, `get_tool_usage_report`, `get_optimization_recommendations`, `search_usage`, `get_usage_events`, `get_usage_observation`, and `get_usage_timeline`.

**USE WHEN:** You need tool usage stats, unused tools, reports, recommendations, or event/observation/timeline search. Prefer this over calling multiple usage tools.

**Parameters:**

- `query_type` (str) - **Required.** One of: `stats`, `unused`, `report`, `recommendations`, `search`, `events`, `observation`, `timeline`, `anomalies`, `tool_description_optimization`.
- `start_date`, `end_date` (str | None) - Date range for stats/events.
- `tool_name` (str | None) - Filter by tool. **Required** for `tool_description_optimization` (target tool to analyze).
- `response_format` (str) - `"concise"` (default) or `"detailed"`.
- `days` (int) - Days for unused/report (default: 90).
- `min_usage_count`, `min_usage_threshold` (int) - Thresholds for unused.
- `ids`, `observation_id`, `around_id` - For events/observation/timeline.
- `success` (bool | None) - Filter by success.
- `limit` (int) - Max results (default: 50).
- `query` (str | None) - Search query for search type.
- `format` (str) - Output format for report (default: `"markdown"`).
- `include_recommendations` (bool) - Include recommendations (default: True).
- `hours` (int | None) - For `anomalies`: session window in hours (default: 24).

**Returns:** JSON string. Structure varies by `query_type`. Use `response_format="detailed"` for full payloads. For `tool_description_optimization`, returns error_rate, suggestions, ab_test_plan, and meets_optimization_threshold.

**Example:**

```python
await query_usage(query_type="stats", response_format="concise")
await query_usage(query_type="search", query="load_context", limit=20)
await query_usage(query_type="tool_description_optimization", tool_name="load_context", days=30)
```

---

### rollback_file_version

Rollback a Memory Bank file to a previous version.

**Parameters:**

- `file_name` (str) - Name of the file (e.g., "projectBrief.md")
- `version` (int) - Version number to rollback to
**Description:**

Restores content from a snapshot and creates a new version entry. Does not delete history - the rollback itself becomes a new version.

**Returns:**

```json
{
  "status": "success",
  "file_name": "projectBrief.md",
  "rolled_back_from_version": 3,
  "new_version": 6,
  "token_count": 490
}
```

---

### check_migration_status

Check if Memory Bank needs migration from old format.

**Parameters:**

**Description:**

Detects if the project uses the old (pre-Phase 1) format and provides information about what migration will do.

**Returns:**

```json
{
  "status": "migration_needed",
  "message": "Old format detected. Run migrate_memory_bank() to upgrade.",
  "old_format_details": {
    "has_old_files": true,
    "missing_metadata": true
  }
}
```

**Status Values:**

- `migration_needed` - Old format detected, migration required
- `up_to_date` - Already using Phase 1 format
- `not_initialized` - No Memory Bank exists yet
- `error` - Check failed

---

### migrate_memory_bank

Migrate Memory Bank from old format to Phase 1 format.

**Parameters:**

- `auto_backup` (bool) - If True, creates timestamped backup (default: True)

**Description:**

Creates backup, initializes metadata index, generates version history, and verifies the migration. Safe to run multiple times - idempotent operation.

**Returns:**

```json
{
  "status": "success",
  "message": "Migration completed successfully",
  "backup_created": true,
  "backup_path": "/path/to/memory-bank-backup-20251225",
  "files_migrated": 7,
  "metadata_created": true
}
```

---

## Phase 2: Link Management Tools

Link parsing, validation, transclusion resolution, and link graph are available via **`query_memory_bank`** with `query_type` set to `parse_links`, `validate_links`, `resolve_transclusions`, or `link_graph`. See [Phase 50: query_memory_bank](#query_memory_bank).

---

## Phase 3: Validation and Quality Tools

Tools for schema validation, duplication detection, quality metrics, and token budget management.

### validate_memory_bank

Run comprehensive validation on Memory Bank files.

**Parameters:**

- `file_name` (str | None) - Optional specific file to validate (if None, validates all files)
- `strict` (bool) - Enable strict validation (warnings treated as errors)

**Description:**

Validates files against schemas checking: required sections presence, recommended sections, heading hierarchy, overall quality.

**Returns:**

```json
{
  "status": "success",
  "validation_passed": true,
  "strict_mode": false,
  "summary": {
    "files_validated": 7,
    "errors": 0,
    "warnings": 2,
    "passed": 7,
    "failed": 0
  },
  "results": [
    {
      "file": "projectBrief.md",
      "passed": true,
      "errors": [],
      "warnings": ["Missing recommended section: ## Constraints"],
      "suggestions": ["Consider adding a Constraints section"]
    }
  ]
}
```

---

### check_duplications

Find duplicate or highly similar content across files.

**Parameters:**

- `threshold` (float) - Similarity threshold (0.0-1.0) to flag as duplicate (default: 0.85)
- `suggest_fixes` (bool) - Include refactoring suggestions in output (default: True)

**Description:**

Scans all files for duplicated content and suggests refactoring opportunities using transclusions.

**Returns:**

```json
{
  "status": "success",
  "threshold": 0.85,
  "summary": {
    "files_scanned": 7,
    "exact_duplicates": 2,
    "similar_sections": 5,
    "total_issues": 7,
    "potential_token_savings": 1200
  },
  "exact_duplicates": [
    {
      "content": "## Project Goals\n...",
      "files": ["projectBrief.md", "productContext.md"],
      "token_count": 150,
      "suggestion": "Extract to shared-goals.md and use {{include: shared-goals.md}}"
    }
  ],
  "similar_content": [
    {
      "files": ["file1.md", "file2.md"],
      "similarity": 0.92,
      "sections": ["## Architecture", "## System Design"]
    }
  ]
}
```

---

### get_quality_score

Calculate Memory Bank quality score and health metrics.

**Parameters:**

- `detailed` (bool) - Include detailed breakdown and recommendations (default: True)

**Description:**

Analyzes Memory Bank providing: overall quality score (0-100), category breakdown, letter grade (A/B/C/D/F), health status and recommendations.

**Returns:**

```json
{
  "status": "success",
  "overall_score": 87,
  "grade": "B+",
  "status_health": "healthy",
  "breakdown": {
    "completeness": {"score": 90, "weight": 25, "weighted": 22.5},
    "consistency": {"score": 85, "weight": 25, "weighted": 21.25},
    "freshness": {"score": 80, "weight": 15, "weighted": 12.0},
    "structure": {"score": 90, "weight": 20, "weighted": 18.0},
    "token_efficiency": {"score": 85, "weight": 15, "weighted": 12.75}
  },
  "issues": [
    {
      "category": "consistency",
      "severity": "medium",
      "description": "3 duplicate sections found"
    }
  ],
  "recommendations": [
    "Consider consolidating duplicate content using transclusions",
    "Update stale files that haven't been modified in 90+ days"
  ]
}
```

**Grade Scale:**

- A: 90-100 (Excellent)
- B: 80-89 (Good)
- C: 70-79 (Fair)
- D: 60-69 (Needs Improvement)
- F: 0-59 (Poor)

---

### check_token_budget

Check token usage against budget and get projections.

**Parameters:**

- `include_projections` (bool) - Include growth projections (default: True)

**Description:**

Analyzes current token usage across all files and compares to configured budgets.

**Returns:**

```json
{
  "status": "success",
  "budget_status": "healthy",
  "current_usage": {
    "total_tokens": 8500,
    "average_per_file": 1214
  },
  "budget_limits": {
    "max_total_tokens": 50000,
    "max_per_file": 5000,
    "warning_threshold": 80
  },
  "usage_percentage": 17.0,
  "remaining_tokens": 41500,
  "per_file_breakdown": [
    {
      "file": "projectBrief.md",
      "tokens": 1234,
      "percentage": 14.5,
      "status": "healthy"
    }
  ],
  "projections": {
    "at_current_rate": {
      "days_until_warning": 120,
      "days_until_limit": 180
    }
  }
}
```

**Budget Status:**

- `healthy` - Under warning threshold
- `warning` - Over warning threshold but under limit
- `over_budget` - Exceeds configured limit

---

### configure_validation

View or update validation configuration.

**Parameters:**

- `config_key` (str | None) - Configuration key to set (dot notation: "token_budget.max_total_tokens")
- `config_value` (str | None) - Value to set (will be parsed as JSON)
- `show_current` (bool) - Show current configuration (default: False)

**Description:**

Allows viewing/updating validation settings stored in `.cortex/config/validation.json`.

**Returns:**

View configuration:

```json
{
  "status": "success",
  "action": "view",
  "configuration": {
    "token_budget": {
      "max_total_tokens": 50000,
      "max_per_file": 5000
    },
    "validation": {
      "strict_mode": false,
      "check_links": true
    }
  }
}
```

Update configuration:

```json
{
  "status": "success",
  "action": "updated",
  "key": "token_budget.max_total_tokens",
  "value": 60000,
  "message": "Configuration updated successfully"
}
```

---

## Phase 4: Token Optimization Tools

Tools for smart context loading, relevance scoring, summarization, and custom rules integration.

**Context workflow (two-step pattern for efficiency)**: Use the two-step pattern for optimal token efficiency:

1. **First**: Call `load_context(task_description="...", depth="metadata_only", token_budget=...)` to get a lightweight context map (~500 tokens) with file names, sections, token counts, and relevance scores.
2. **Then**: Use `manage_file(file_name="[file]", operation="read", sections=["## Section Name"])` to drill into specific relevant sections on demand.
This provides 90%+ token savings compared to full file loads. Essential sections (e.g., "## Current Focus" and "## Next Steps" from activeContext.md) are automatically loaded in full via the hybrid retrieval strategy even when `depth="metadata_only"`.

**Alternative workflows**: For full context upfront, use `load_context(depth="full")` or `depth="summary"`. For incremental loading, use `load_context(strategy="progressive", loading_strategy="by_relevance"|"by_priority"|"by_dependencies")`. When usage search or fetch-by-ID tools are available, prefer `query_usage(query_type="search", ...)` then fetch by ID instead of loading full history.

### load_context

Load relevant context for a task within token budget.

This tool should be called at the START of any task to:

- Load memory bank files relevant to the task
- Load applicable rules and patterns
- Provide project context before making changes

**Parameters:**

- `task_description` (str) - Description of the task or work to be done
- `token_budget` (int | None) - Maximum tokens allowed (defaults to config value)
- `strategy` (str) - Loading strategy (default: "dependency_aware")
  - `"priority"` - Greedy selection by predefined priority
  - `"dependency_aware"` - Includes dependency trees
  - `"section_level"` - Partial file inclusion
  - `"hybrid"` - Combines multiple strategies
  - `"progressive"` - Incremental loading (replaces former `load_progressive_context`); use with `loading_strategy` for order (e.g. `by_relevance`, `by_priority`, `by_dependencies`)
- `depth` (str | None) - Content depth level (default: auto-selects based on token_budget)
  - `"metadata_only"` - Returns context map (file names, sections, token counts, relevance) without full content (~500 tokens). Essential sections (e.g., "## Current Focus" from activeContext.md) are automatically loaded in full via hybrid retrieval strategy.
  - `"summary"` - Returns first paragraph of each file + section headings (~5000-15000 tokens)
  - `"full"` - Returns full file contents (default for budgets > 15000)
  - Auto-selection: budget < 5000 → metadata_only, budget 5000-15000 → summary, budget > 15000 → full
- `loading_strategy` (str | None) - Required when strategy="progressive". Options: "by_relevance" (default), "by_priority", "by_dependencies"
- `response_format` (str) - Response format: "concise" (default) or "detailed"

**Explicit budget for non-trivial tasks:** For **non-trivial** tasks (implement, fix, debug, refactor, test, optimize), an **explicit non-zero** `token_budget` is required. **Omitting** `token_budget` or passing `token_budget=0` returns a **validation error**; use e.g. 10,000 for implement/add, 15,000 for fix/debug. For **trivial** tasks, omitting `token_budget` or passing 0 uses the config default. Always pass an explicit budget for implement, fix, debug, and planning flows.

**Description:**

Uses relevance scoring and loading strategies to select the best subset of Memory Bank files that fit within a token budget. Supports hybrid retrieval strategy: when `depth="metadata_only"`, essential sections from configured files (e.g., "## Current Focus" and "## Next Steps" from activeContext.md) are automatically loaded in full, while other files return metadata only. Use the two-step pattern: `load_context(depth="metadata_only")` → `manage_file(sections=[...])` for optimal token efficiency (90%+ savings).

**Returns:**

For `depth="full"` or `depth="summary"`:

```json
{
  "status": "success",
  "task_description": "Implement authentication system",
  "token_budget": 10000,
  "strategy": "dependency_aware",
  "depth": "full",
  "selected_files": ["systemPatterns.md", "techContext.md"],
  "selected_sections": {"techContext.md": ["## Security"]},
  "total_tokens": 8500,
  "utilization": 85.0,
  "excluded_files": ["progress.md"],
  "relevance_scores": {
    "systemPatterns.md": 0.95,
    "techContext.md": 0.88
  }
}
```

For `depth="metadata_only"` (hybrid retrieval):

```json
{
  "status": "success",
  "task_description": "Implement authentication system",
  "token_budget": 10000,
  "strategy": "dependency_aware",
  "depth": "metadata_only",
  "files": [
    {
      "name": "systemPatterns.md",
      "total_tokens": 1500,
      "last_modified": "2026-02-16T10:00:00",
      "relevance_score": 0.95,
      "sections": [
        {"heading": "## Architecture", "tokens": 500, "level": 2},
        {"heading": "## Security Patterns", "tokens": 1000, "level": 2}
      ]
    }
  ],
  "total_files": 7,
  "total_tokens_available": 15000,
  "always_loaded": {
    "activeContext.md": "## Current Focus\n\nWorking on Phase 51.\n\n## Next Steps\n\nComplete Step 5."
  },
  "always_loaded_tokens": 50,
  "total_tokens": 550,
  "utilization": 0.06
}
```

---

### summarize_content

Summarize Memory Bank content to reduce token usage.

**Parameters:**

- `file_name` (str | None) - File to summarize (None for all files)
- `target_reduction` (float) - Target token reduction (0.5 = reduce by 50%, default: 0.5)
- `strategy` (str) - Strategy (default: "extract_key_sections")
  - `"extract_key_sections"` - Keep most important sections
  - `"compress_verbose"` - Remove examples, compress code
  - `"headers_only"` - Outline view with headers
**Description:**

Generates summaries of files to fit within token budgets while preserving key information.

**Returns:**

```json
{
  "status": "success",
  "strategy": "extract_key_sections",
  "target_reduction": 0.5,
  "files_summarized": 7,
  "total_original_tokens": 8500,
  "total_summarized_tokens": 4100,
  "total_reduction": 0.52,
  "results": [
    {
      "file": "projectBrief.md",
      "original_tokens": 1234,
      "summarized_tokens": 600,
      "reduction": 0.51,
      "summary": "# Project Brief\n## Goals\n..."
    }
  ]
}
```

---

### get_relevance_scores

Get relevance scores for all Memory Bank files.

**Parameters:**

- `task_description` (str) - Description of the task
- `include_sections` (bool) - Whether to include section-level scores (default: False)

**Description:**

Scores files and optionally sections based on their relevance to a given task description using TF-IDF and dependency-based scoring.

**Returns:**

```json
{
  "status": "success",
  "task_description": "Implement authentication",
  "files_scored": 7,
  "file_scores": {
    "systemPatterns.md": 0.95,
    "techContext.md": 0.88,
    "projectBrief.md": 0.72,
    "progress.md": 0.15
  },
  "section_scores": {
    "techContext.md": {
      "## Security": 0.95,
      "## Architecture": 0.70
    }
  }
}
```

---

### configure_optimization

View or update optimization configuration.

**Parameters:**

- `config_key` (str | None) - Configuration key in dot notation (e.g., "token_budget.default_budget")
- `config_value` (str | None) - New value to set (as JSON string)
- `show_current` (bool) - Show current configuration (default: False)
**Description:**

Allows viewing and modifying optimization settings like token budgets, loading strategies, and relevance weights stored in `.cortex/config/optimization.json`.

**Returns:**

View configuration:

```json
{
  "status": "success",
  "action": "view",
  "configuration": {
    "token_budget": {
      "default_budget": 10000,
      "max_budget": 50000
    },
    "loading": {
      "default_strategy": "by_relevance",
      "default_priority": ["projectBrief.md", "..."]
    },
    "summarization": {
      "default_strategy": "extract_key_sections",
      "target_reduction": 0.5
    }
  },
  "config_file": "/path/to/.cortex/config/optimization.json"
}
```

---

### index_rules

Index custom rules from configured rules folder.

**Parameters:**

- `force` (bool) - Force reindexing even if recently indexed (default: False)
**Description:**

Scans the rules folder (e.g., `.cursorrules`) and indexes all rule files for use in context optimization.

**Returns:**

```json
{
  "status": "success",
  "message": "Indexed 12 rules from .cursorrules",
  "rules_indexed": 12,
  "total_tokens": 3500,
  "rules_by_category": {
    "python": 5,
    "testing": 3,
    "security": 4
  },
  "last_indexed": "2025-12-25T15:00:00Z"
}
```

---

### get_relevant_rules

Get custom rules relevant to a task description.

**Parameters:**

- `task_description` (str) - Description of the task
- `max_tokens` (int | None) - Maximum tokens for rules (defaults to config)
- `min_relevance_score` (float | None) - Minimum relevance score (defaults to config)
**Description:**

Retrieves indexed rules that are relevant to the given task, useful for providing context-specific guidelines.

**Returns:**

```json
{
  "status": "success",
  "task_description": "Write unit tests for authentication",
  "max_tokens": 2000,
  "min_relevance_score": 0.3,
  "rules_count": 5,
  "total_tokens": 1800,
  "rules": [
    {
      "file": "testing-standards.md",
      "relevance_score": 0.92,
      "tokens": 450,
      "content": "# Testing Standards\n..."
    },
    {
      "file": "python-best-practices.md",
      "relevance_score": 0.75,
      "tokens": 380,
      "content": "# Python Best Practices\n..."
    }
  ]
}
```

---

## Phase 5.1: Pattern Analysis and Insights

Tools for analyzing usage patterns and structure to identify optimization opportunities.

### analyze_usage_patterns

Analyze Memory Bank usage patterns.

**Parameters:**

- `time_range_days` (int) - Number of days to analyze (default: 30)
- `min_access_count` (int) - Minimum access count to include (default: 1)
- `include_co_access` (bool) - Include frequently co-accessed file pairs (default: True)
- `include_unused` (bool) - Include analysis of unused/stale files (default: True)
- `include_task_patterns` (bool) - Include task-based access patterns (default: True)
- `include_temporal` (bool) - Include temporal patterns (default: True)
**Description:**

Tracks file access frequency, identifies frequently co-accessed files, detects unused/stale content, and analyzes task-based and temporal access patterns.

**Returns:**

```json
{
  "status": "success",
  "time_range_days": 30,
  "analysis": {
    "access_frequency": {
      "projectBrief.md": 45,
      "activeContext.md": 38,
      "progress.md": 12
    },
    "co_access_patterns": [
      {
        "files": ["systemPatterns.md", "techContext.md"],
        "co_access_count": 25,
        "confidence": 0.85
      }
    ],
    "unused_files": [
      {
        "file": "old-notes.md",
        "days_since_access": 120,
        "recommendation": "Consider archiving"
      }
    ],
    "task_patterns": {
      "authentication": ["systemPatterns.md", "techContext.md"],
      "testing": ["progress.md", "activeContext.md"]
    },
    "temporal_patterns": {
      "hourly": {"peak_hour": 14, "access_count": 25},
      "daily": {"peak_day": "Monday", "access_count": 150},
      "weekly": {"trend": "increasing"}
    }
  }
}
```

---

### analyze_structure

Analyze Memory Bank structure and organization.

**Parameters:**

- `include_organization` (bool) - Include file organization analysis (default: True)
- `include_anti_patterns` (bool) - Check for organizational anti-patterns (default: True)
- `include_complexity` (bool) - Calculate complexity metrics (default: True)
- `include_dependency_chains` (bool) - Find long dependency chains (default: True)
- `max_chain_length` (int) - Maximum chain length to search for (default: 10)
**Description:**

Analyzes file organization, detects anti-patterns, measures complexity metrics, and identifies problematic dependency chains.

**Returns:**

```json
{
  "status": "success",
  "analysis": {
    "organization": {
      "total_files": 7,
      "average_size_tokens": 1214,
      "file_size_distribution": {
        "small (<500 tokens)": 1,
        "medium (500-2000 tokens)": 5,
        "large (>2000 tokens)": 1
      }
    },
    "anti_patterns": [
      {
        "type": "oversized_file",
        "file": "systemPatterns.md",
        "size_tokens": 3500,
        "recommendation": "Consider splitting into smaller files"
      },
      {
        "type": "orphaned_file",
        "file": "notes.md",
        "recommendation": "No dependencies - consider removing or linking"
      }
    ],
    "complexity": {
      "max_dependency_depth": 3,
      "cyclomatic_complexity": 12,
      "fan_in_fan_out": {
        "projectBrief.md": {"fan_in": 0, "fan_out": 3}
      }
    },
    "dependency_chains": [
      {
        "chain": ["projectBrief.md", "productContext.md", "techContext.md"],
        "length": 3,
        "complexity_score": 0.6
      }
    ]
  }
}
```

---

### get_optimization_insights

Generate AI-driven insights and recommendations.

**Parameters:**

- `min_impact_score` (float) - Minimum impact score (0-1) to include (default: 0.5)
- `categories` (str | None) - Comma-separated list of categories or None for all
  - Categories: `usage`, `organization`, `redundancy`, `dependencies`, `quality`
- `include_reasoning` (bool) - Include detailed reasoning for insights (default: True)
- `export_format` (str) - Export format: `json`, `markdown`, or `text` (default: "json")
**Description:**

Combines pattern and structure analysis to generate actionable insights with specific recommendations for improvement.

**Returns:**

JSON format:

```json
{
  "status": "success",
  "insights": [
    {
      "category": "usage",
      "severity": "high",
      "impact_score": 0.85,
      "title": "Frequently co-accessed files should be consolidated",
      "description": "systemPatterns.md and techContext.md are accessed together 85% of the time",
      "recommendation": "Consider using transclusions to reduce duplication",
      "estimated_token_savings": 500,
      "reasoning": "High co-access pattern indicates related content"
    }
  ],
  "summary": {
    "total_insights": 8,
    "high_impact": 3,
    "medium_impact": 4,
    "low_impact": 1,
    "estimated_total_savings": 1200
  }
}
```

Markdown format:

```markdown
# Memory Bank Optimization Insights

## High Impact (3)

### Frequently co-accessed files should be consolidated
**Category:** Usage | **Impact Score:** 0.85

systemPatterns.md and techContext.md are accessed together 85% of the time.

**Recommendation:** Consider using transclusions to reduce duplication

**Estimated Token Savings:** 500 tokens
...
```

---

## Phase 5.2: Refactoring Suggestions

Tools for generating intelligent refactoring suggestions based on pattern analysis.

### suggest_consolidation

Suggest content consolidation opportunities.

**Parameters:**

- `min_similarity` (float) - Minimum similarity score for consolidation (0-1, default: 0.80)
- `target_reduction` (float) - Target token reduction ratio (0-1, default: 0.30)
- `suggest_transclusion` (bool) - Include transclusion syntax suggestions (default: True)
- `files` (str | None) - Comma-separated list of files to analyze, or None for all
**Description:**

Detects duplicate and similar content across files and suggests consolidation strategies using transclusion and shared sections.

**Returns:**

```json
{
  "status": "success",
  "total_opportunities": 5,
  "total_token_savings": 1200,
  "opportunities": [
    {
      "id": "consol-001",
      "type": "exact_duplicate",
      "files": ["projectBrief.md", "productContext.md"],
      "content_preview": "## Project Goals\nOur primary objectives are...",
      "similarity_score": 1.0,
      "tokens": 250,
      "suggestion": {
        "action": "extract",
        "target_file": "shared/project-goals.md",
        "transclusion": "{{include: shared/project-goals.md}}"
      },
      "estimated_savings": 250
    },
    {
      "id": "consol-002",
      "type": "similar_content",
      "files": ["systemPatterns.md", "techContext.md"],
      "sections": ["## Architecture", "## System Design"],
      "similarity_score": 0.87,
      "tokens": 450,
      "suggestion": {
        "action": "consolidate",
        "approach": "Merge into single section with transclusions"
      },
      "estimated_savings": 180
    }
  ],
  "summary": {
    "top_opportunity": {
      "id": "consol-001",
      "savings": 250
    },
    "average_savings": 240
  }
}
```

---

### suggest_file_splits

Suggest files that should be split.

**Parameters:**

- `max_file_size` (int) - Maximum recommended file size in tokens (default: 5000)
- `max_sections` (int) - Maximum recommended number of sections per file (default: 10)
- `files` (str | None) - Comma-separated list of files to analyze, or None for all
**Description:**

Identifies large or complex files and recommends splitting strategies to improve context loading efficiency and maintainability.

**Returns:**

```json
{
  "status": "success",
  "total_recommendations": 2,
  "recommendations": [
    {
      "id": "split-001",
      "file": "systemPatterns.md",
      "current_tokens": 6500,
      "current_sections": 15,
      "reason": "File exceeds recommended size and section count",
      "strategy": "by_topics",
      "split_points": [
        {
          "line": 45,
          "section": "## Authentication Patterns",
          "new_file": "patterns/authentication.md",
          "tokens": 1500
        },
        {
          "line": 120,
          "section": "## Data Access Patterns",
          "new_file": "patterns/data-access.md",
          "tokens": 1800
        }
      ],
      "estimated_impact": {
        "original_load_time": "high",
        "new_load_time": "medium",
        "maintainability_improvement": "significant",
        "context_efficiency": "+35%"
      }
    }
  ],
  "summary": {
    "files_to_split": 2,
    "total_new_files": 5,
    "average_reduction": "55%"
  }
}
```

---

### suggest_reorganization

Suggest structural reorganization.

**Parameters:**

- `optimize_for` (str) - Optimization goal (default: "dependency_depth")
  - `"dependency_depth"` - Minimize dependency chain length
  - `"category_based"` - Organize by inferred categories
  - `"complexity"` - Reduce overall complexity
- `suggest_new_structure` (bool) - Include detailed new structure proposal (default: True)
- `preserve_history` (bool) - Preserve version history when reorganizing (default: True)
**Description:**

Analyzes current structure and proposes improvements to reduce complexity, optimize dependencies, and improve file organization.

**Returns:**

```json
{
  "status": "success",
  "plan": {
    "id": "reorg-001",
    "optimization_goal": "dependency_depth",
    "current_state": {
      "max_depth": 5,
      "avg_depth": 2.8,
      "complexity_score": 0.72
    },
    "proposed_state": {
      "max_depth": 3,
      "avg_depth": 1.9,
      "complexity_score": 0.45
    },
    "actions": [
      {
        "type": "move",
        "file": "techContext.md",
        "from": "memory-bank/",
        "to": "memory-bank/technical/",
        "reason": "Groups with similar technical files"
      },
      {
        "type": "rename",
        "file": "progress.md",
        "new_name": "status/current-progress.md",
        "reason": "Better categorization"
      },
      {
        "type": "create_category",
        "name": "technical",
        "files": ["techContext.md", "systemPatterns.md"],
        "reason": "Group related technical documentation"
      }
    ],
    "estimated_impact": {
      "files_moved": 3,
      "categories_created": 2,
      "complexity_reduction": "38%",
      "dependency_improvement": "45%"
    },
    "risks": [
      "May break external references to moved files"
    ],
    "benefits": [
      "Clearer organization",
      "Reduced dependency depth",
      "Improved context loading efficiency"
    ]
  },
  "preview": {
    "before": "memory-bank/\n  projectBrief.md\n  techContext.md\n  ...",
    "after": "memory-bank/\n  core/\n    projectBrief.md\n  technical/\n    techContext.md\n  ..."
  }
}
```

---

### preview_refactoring

Preview the impact of a refactoring suggestion.

**Parameters:**

- `suggestion_id` (str) - ID of the refactoring suggestion to preview
- `show_diff` (bool) - Include diff preview of changes (default: True)
- `estimate_impact` (bool) - Include estimated impact analysis (default: True)
**Description:**

Shows detailed information about what changes would be made, which files would be affected, and what the estimated impact would be.

**Returns:**

```json
{
  "status": "success",
  "suggestion_id": "consol-001",
  "preview": {
    "type": "consolidation",
    "files_affected": ["projectBrief.md", "productContext.md"],
    "files_created": ["shared/project-goals.md"],
    "changes": [
      {
        "file": "projectBrief.md",
        "action": "replace_section",
        "section": "## Project Goals",
        "with": "{{include: shared/project-goals.md}}",
        "diff": "- ## Project Goals\n- Our primary objectives...\n+ {{include: shared/project-goals.md}}"
      }
    ]
  },
  "estimated_impact": {
    "token_savings": 250,
    "files_modified": 2,
    "files_created": 1,
    "complexity_change": "-15%",
    "maintainability_improvement": "+20%"
  },
  "risks_and_benefits": {
    "risks": [
      "Adds transclusion dependency",
      "Slightly increases loading complexity"
    ],
    "benefits": [
      "Eliminates duplicate content",
      "Single source of truth for project goals",
      "Easier to maintain consistency"
    ]
  }
}
```

---

## Phase 5.3-5.4: Safe Execution and Learning

Tools for safe refactoring execution with rollback support and learning from user feedback.

### approve_refactoring

Approve a refactoring suggestion.

**Parameters:**

- `suggestion_id` (str) - ID of the suggestion to approve
- `auto_apply` (bool) - If True, automatically apply after approval (default: False)
- `user_comment` (str | None) - Optional comment explaining the approval
**Description:**

Marks a suggestion as approved and optionally applies it immediately. Approved suggestions can be executed using `apply_refactoring`.

**Returns:**

```json
{
  "status": "success",
  "approval_id": "appr-001",
  "suggestion_id": "consol-001",
  "approved_at": "2025-12-25T15:30:00Z",
  "applied": false,
  "message": "Suggestion approved successfully",
  "next_steps": [
    "Use apply_refactoring(suggestion_id='consol-001') to execute"
  ]
}
```

With auto_apply=True:

```json
{
  "status": "success",
  "approval_id": "appr-001",
  "suggestion_id": "consol-001",
  "applied": true,
  "execution_id": "exec-001",
  "message": "Suggestion approved and applied successfully"
}
```

---

### apply_refactoring

Apply an approved refactoring suggestion.

**Parameters:**

- `suggestion_id` (str) - ID of the suggestion to apply
- `approval_id` (str | None) - Optional approval ID (auto-finds if not provided)
- `dry_run` (bool) - If True, simulate without making actual changes (default: False)
- `validate_first` (bool) - If True, validate before executing (default: True)
**Description:**

Executes the refactoring operations defined in a suggestion. Creates a snapshot before making changes and validates the operations.

**Returns:**

```json
{
  "status": "success",
  "execution_id": "exec-001",
  "suggestion_id": "consol-001",
  "executed_at": "2025-12-25T15:35:00Z",
  "files_modified": 2,
  "files_created": 1,
  "snapshot_created": true,
  "snapshot_id": "snap-001",
  "changes_made": [
    {
      "file": "projectBrief.md",
      "action": "modified",
      "changes": "Replaced section with transclusion"
    },
    {
      "file": "shared/project-goals.md",
      "action": "created",
      "content_tokens": 250
    }
  ],
  "validation": {
    "passed": true,
    "warnings": [],
    "errors": []
  },
  "message": "Refactoring applied successfully"
}
```

Dry run:

```json
{
  "status": "success",
  "dry_run": true,
  "would_modify": 2,
  "would_create": 1,
  "preview": "..."
}
```

---

### rollback_refactoring

Rollback a previously applied refactoring.

**Parameters:**

- `execution_id` (str) - ID of the execution to rollback
- `restore_snapshot` (bool) - If True, restore from pre-refactoring snapshot (default: True)
- `preserve_manual_changes` (bool) - If True, try to preserve manual edits (default: True)
- `dry_run` (bool) - If True, simulate without making changes (default: False)
**Description:**

Restores files to their state before the refactoring was applied. Can detect and preserve manual changes made after the refactoring.

**Returns:**

```json
{
  "status": "success",
  "execution_id": "exec-001",
  "rolled_back_at": "2025-12-25T16:00:00Z",
  "snapshot_id": "snap-001",
  "files_restored": 2,
  "files_removed": 1,
  "manual_changes_detected": true,
  "manual_changes_preserved": true,
  "conflicts": [],
  "changes": [
    {
      "file": "projectBrief.md",
      "action": "restored",
      "from_snapshot": true
    },
    {
      "file": "shared/project-goals.md",
      "action": "removed",
      "reason": "Created by refactoring"
    }
  ],
  "message": "Refactoring rolled back successfully"
}
```

---

### get_refactoring_history

Get history of applied refactorings.

**Parameters:**

- `time_range_days` (int) - Number of days to include in history (default: 90)
- `include_rollbacks` (bool) - Include rolled back executions (default: True)
**Description:**

Shows all refactorings that have been executed, including their status, impact, and whether they were rolled back.

**Returns:**

```json
{
  "status": "success",
  "time_range_days": 90,
  "total_executions": 12,
  "active_executions": 10,
  "rolled_back_executions": 2,
  "executions": [
    {
      "execution_id": "exec-001",
      "suggestion_id": "consol-001",
      "type": "consolidation",
      "executed_at": "2025-12-25T15:35:00Z",
      "status": "active",
      "files_modified": 2,
      "token_savings": 250,
      "rolled_back": false
    },
    {
      "execution_id": "exec-002",
      "suggestion_id": "split-001",
      "type": "file_split",
      "executed_at": "2025-12-20T10:00:00Z",
      "status": "rolled_back",
      "rolled_back_at": "2025-12-22T14:00:00Z",
      "rollback_reason": "User preferred original structure"
    }
  ],
  "statistics": {
    "total_token_savings": 1200,
    "average_savings_per_execution": 120,
    "success_rate": 0.83
  }
}
```

---

### provide_feedback

Provide feedback on a refactoring suggestion.

**Parameters:**

- `suggestion_id` (str) - ID of the suggestion to provide feedback on
- `feedback_type` (str) - Type of feedback: `"helpful"`, `"not_helpful"`, or `"incorrect"`
- `comment` (str | None) - Optional comment explaining the feedback
- `adjust_preferences` (bool) - If True, update learning preferences (default: True)
**Description:**

Allows giving feedback that helps the system learn and improve future suggestions. Feedback can be "helpful", "not_helpful", or "incorrect".

**Returns:**

```json
{
  "status": "success",
  "suggestion_id": "consol-001",
  "feedback_recorded": true,
  "feedback_type": "helpful",
  "recorded_at": "2025-12-25T16:30:00Z",
  "preferences_updated": true,
  "learning_summary": {
    "pattern_reinforced": "consolidation_for_duplicates",
    "confidence_adjustment": "+0.05",
    "total_feedback_count": 45,
    "positive_feedback_rate": 0.87
  },
  "message": "Thank you for your feedback! This helps improve future suggestions."
}
```

---

### configure_learning

Configure learning and adaptation behavior.

**Parameters:**

- `action` (str) - Action to perform (default: "view")
  - `"view"` - View current configuration
  - `"update"` - Update configuration
  - `"reset"` - Reset all learning data (use with caution)
  - `"export"` - Export learned patterns
  - `"insights"` - Get learning insights
- `config_key` (str | None) - Configuration key to update (e.g., "learning.enabled")
- `config_value` (str | None) - New value for the configuration key
- `reset_learning` (bool) - If True, reset all learning data (default: False)
- `export_patterns` (bool) - If True, export learned patterns (default: False)
**Description:**

Allows viewing/updating learning settings, resetting learning data, or exporting learned patterns for analysis.

**Returns:**

View action:

```json
{
  "status": "success",
  "action": "view",
  "configuration": {
    "learning": {
      "enabled": true,
      "confidence_threshold": 0.7,
      "min_feedback_count": 5,
      "pattern_retention_days": 180
    },
    "adaptation": {
      "auto_adjust_thresholds": true,
      "learning_rate": 0.1
    }
  }
}
```

Insights action:

```json
{
  "status": "success",
  "action": "insights",
  "insights": {
    "total_suggestions": 125,
    "total_feedback": 87,
    "feedback_rate": 0.70,
    "patterns_learned": 15,
    "most_successful_pattern": {
      "type": "consolidation_for_duplicates",
      "success_rate": 0.92,
      "usage_count": 42
    },
    "least_successful_pattern": {
      "type": "aggressive_splitting",
      "success_rate": 0.45,
      "usage_count": 8
    },
    "confidence_trends": {
      "consolidation": "increasing",
      "splitting": "stable",
      "reorganization": "decreasing"
    }
  }
}
```

---

## Phase 6: Shared Rules Repository

Tools for managing shared rules across multiple projects using git submodules.

### setup_shared_rules

Initialize shared rules repository as git submodule.

**Parameters:**

- `repo_url` (str) - Git repository URL for shared rules (e.g., `git@github.com:org/shared-rules.git`)
- `local_path` (str) - Local path for shared rules folder (default: ".shared-rules")
- `force` (bool) - Force re-initialization even if submodule exists (default: False)

**Description:**

Sets up a shared rules repository that can be used across multiple projects. Rules are stored in a git submodule and automatically synced with other projects using the same repository.

**Returns:**

```json
{
  "status": "success",
  "message": "Shared rules repository initialized successfully",
  "repo_url": "git@github.com:org/shared-rules.git",
  "local_path": ".shared-rules",
  "submodule_added": true,
  "rules_manifest_found": true,
  "categories": ["generic", "python", "swift", "javascript"],
  "total_rules": 25
}
```

---

### sync_shared_rules

Sync shared rules repository with remote.

**Parameters:**

- `pull` (bool) - Pull latest changes from remote (default: True)
- `push` (bool) - Push local changes to remote (default: False)

**Description:**

Synchronizes the local shared rules with the remote repository. Use `pull=True` to get latest changes from other projects, and `push=True` to share your local rule changes with other projects.

**Returns:**

```json
{
  "status": "success",
  "message": "Shared rules synchronized successfully",
  "changes_pulled": {
    "files_updated": 3,
    "files_added": 1,
    "files_removed": 0,
    "commit": "abc123..."
  },
  "changes_pushed": {
    "files_updated": 0,
    "commit": null
  },
  "reindex_triggered": true,
  "current_commit": "abc123..."
}
```

---

### update_shared_rule

Update a shared rule and push to all projects.

**Parameters:**

- `category` (str) - Category name (e.g., "python", "generic", "swift")
- `file` (str) - Rule filename (e.g., "style-guide.md")
- `content` (str) - New content for the rule
- `commit_message` (str) - Git commit message describing the change

**Description:**

Updates a rule in the shared rules repository and commits/pushes the changes so they propagate to all other projects using the same shared rules repository.

**Returns:**

```json
{
  "status": "success",
  "message": "Shared rule updated and pushed successfully",
  "category": "python",
  "file": "style-guide.md",
  "file_updated": ".shared-rules/python/style-guide.md",
  "commit_hash": "def456...",
  "commit_message": "Update Python style guide with new naming conventions",
  "pushed_to_remote": true,
  "propagation_note": "Other projects will receive this update on their next sync"
}
```

---

### get_rules_with_context

Get intelligently selected rules based on task context.

**Parameters:**

- `task_description` (str) - Description of the current task
- `max_tokens` (int) - Maximum tokens to include (default: 10000)
- `min_relevance_score` (float) - Minimum relevance score to include (0.0-1.0, default: 0.3)
- `project_files` (str | None) - Optional comma-separated list of file paths for context detection
- `rule_priority` (str) - Priority strategy (default: "local_overrides_shared")
  - `"local_overrides_shared"` - Local rules take precedence
  - `"shared_overrides_local"` - Shared rules take precedence
- `context_aware` (bool) - Enable intelligent context detection (default: True)

**Description:**

Analyzes the task description and project context to intelligently select the most relevant rules from both shared and local sources. Automatically detects programming languages, frameworks, and task types to load appropriate rules.

**Returns:**

```json
{
  "status": "success",
  "task_description": "Implement JWT authentication for Flask API",
  "context": {
    "detected_languages": ["python"],
    "detected_frameworks": ["flask"],
    "detected_task_types": ["authentication", "api"],
    "confidence": 0.92
  },
  "rules_loaded": {
    "generic": [
      {
        "file": "security.md",
        "source": "shared",
        "relevance_score": 0.95,
        "tokens": 450
      },
      {
        "file": "coding-standards.md",
        "source": "shared",
        "relevance_score": 0.75,
        "tokens": 380
      }
    ],
    "python": [
      {
        "file": "best-practices.md",
        "source": "shared",
        "relevance_score": 0.88,
        "tokens": 520
      },
      {
        "file": "testing-standards.md",
        "source": "local",
        "relevance_score": 0.82,
        "tokens": 400
      }
    ],
    "local_overrides": [
      {
        "file": "auth-guidelines.md",
        "source": "local",
        "relevance_score": 0.98,
        "tokens": 350,
        "overrides": "shared/generic/auth-patterns.md"
      }
    ]
  },
  "total_rules": 8,
  "total_tokens": 2100,
  "token_budget": 10000,
  "utilization": 21.0,
  "merge_strategy": "local_overrides_shared"
}
```

---

## Phase 8: Project Structure Management

Tools for managing standardized `.memory-bank/` project structure with migration support.

### setup_project_structure

Initialize comprehensive project structure with optional interactive setup.

**Parameters:**

- `project_name` (str | None) - Name of the project
- `project_type` (str | None) - Type of project (web, mobile, backend, library, etc.)
- `primary_language` (str | None) - Primary programming language
- `frameworks` (str | None) - Main frameworks/libraries used
- `use_shared_rules` (bool) - Whether to setup shared rules as git submodule (default: False)
- `shared_rules_repo` (str | None) - Git repository URL for shared rules
- `force` (bool) - Force recreation even if structure exists (default: False)

**Description:**

Creates the standardized `.memory-bank/` directory structure including:

- `knowledge/` directory for Memory Bank files
- `rules/` directory (local and optional shared via git submodule)
- `plans/` directory with templates
- `config/` directory for configuration
- Cursor IDE integration via symlinks

**Returns:**

```json
{
  "success": true,
  "message": "Project structure created successfully",
  "report": {
    "directories_created": [
      ".memory-bank/knowledge",
      ".memory-bank/rules/local",
      ".memory-bank/plans/templates",
      ".memory-bank/config"
    ],
    "files_created": [
      ".memory-bank/knowledge/projectBrief.md",
      ".memory-bank/rules/local/main.cursorrules",
      ".cortex/config/structure.json"
    ],
    "symlinks_created": [
      ".cursor/knowledge -> ../.memory-bank/knowledge",
      ".cursorrules -> .memory-bank/rules/local/main.cursorrules"
    ],
    "shared_rules_setup": false
  },
  "next_steps": [
    "Edit .memory-bank/knowledge/projectBrief.md to document your project",
    "Customize rules in .memory-bank/rules/local/",
    "Use setup_cursor_integration() if symlinks weren't created"
  ]
}
```

---

### migrate_project_structure

Migrate from legacy structure to standardized `.memory-bank/` structure.

**Parameters:**

- `legacy_type` (str | None) - Type of legacy structure (auto-detected if not provided)
  - `"tradewing-style"` - Files in root + .cursor/plans
  - `"doc-mcp-style"` - docs/memory-bank structure
  - `"scattered-files"` - Memory bank files throughout project
  - `"cursor-default"` - Just .cursorrules file
- `backup` (bool) - Create backup of existing files before migration (default: True)
- `archive` (bool) - Archive legacy files after migration (default: True)
- `dry_run` (bool) - Preview migration without making changes (default: False)

**Description:**

Migrates from various legacy structures to the standardized format. Supports multiple legacy types with automatic detection.

**Returns:**

```json
{
  "success": true,
  "message": "Migration completed successfully",
  "report": {
    "legacy_type": "tradewing-style",
    "backup_created": true,
    "backup_path": "/path/to/project/.memory-bank-backup-20251225",
    "files_migrated": {
      "knowledge": 7,
      "rules": 3,
      "plans": 5
    },
    "files_archived": {
      "old_memory_bank": 7,
      "old_cursorrules": 1
    },
    "structure_created": true,
    "symlinks_created": true
  },
  "next_steps": [
    "Review migrated files in .memory-bank/",
    "Update any broken links using validate_links()",
    "Archive old structure if everything looks correct"
  ]
}
```

---

### setup_cursor_integration

Setup Cursor IDE integration via symlinks.

**Parameters:**

- `force` (bool) - Force recreation of symlinks even if they exist (default: False)

**Description:**

Creates symlinks in `.cursor/` directory pointing to `.memory-bank/` structure. Works cross-platform (Unix/macOS with symlinks, Windows with junctions).

**Returns:**

```json
{
  "success": true,
  "message": "Cursor integration setup successfully",
  "report": {
    "platform": "darwin",
    "symlinks_created": [
      ".cursor/knowledge -> ../.memory-bank/knowledge",
      ".cursor/rules -> ../.memory-bank/rules",
      ".cursor/plans -> ../.memory-bank/plans",
      ".cursorrules -> .memory-bank/rules/local/main.cursorrules"
    ],
    "symlinks_recreated": 0,
    "errors": []
  }
}
```

---

### check_structure_health

Analyze project structure health and provide recommendations.

**Parameters:**

**Description:**

Checks:

- All required directories exist
- Symlinks are valid and not broken
- Configuration file exists and is valid
- Files are organized properly
- No orphaned or misplaced files

**Returns:**

```json
{
  "success": true,
  "health": {
    "score": 85,
    "grade": "B",
    "status": "good",
    "checks": [
      {
        "name": "Required directories",
        "passed": true,
        "message": "All required directories exist"
      },
      {
        "name": "Symlinks",
        "passed": true,
        "message": "All symlinks are valid"
      },
      {
        "name": "Configuration",
        "passed": true,
        "message": "Configuration file is valid"
      },
      {
        "name": "File organization",
        "passed": true,
        "message": "Files are properly organized"
      },
      {
        "name": "Orphaned files",
        "passed": false,
        "message": "Found 2 misplaced files",
        "details": ["old-file.md in root", "temp.md in .memory-bank/"]
      }
    ],
    "issues": [
      {
        "severity": "warning",
        "category": "organization",
        "message": "Found 2 misplaced files",
        "files": ["old-file.md", ".memory-bank/temp.md"],
        "recommendation": "Move to appropriate directory or archive"
      }
    ],
    "recommendations": [
      "Move misplaced files to correct locations",
      "Run cleanup_project_structure() to automate cleanup"
    ]
  },
  "summary": "Structure is in good health with minor issues",
  "action_required": false
}
```

**Health Grades:**

- A (90-100): Excellent
- B (80-89): Good
- C (70-79): Fair
- D (60-69): Poor
- F (0-59): Critical

---

### cleanup_project_structure

Perform automated housekeeping on project structure.

**Parameters:**

- `actions` (list[str] | None) - List of actions to perform (all if not specified)
  - `"archive_stale"` - Archive stale plans
  - `"organize_plans"` - Organize plans by status
  - `"fix_symlinks"` - Fix broken symlinks
  - `"update_index"` - Update metadata index
  - `"remove_empty"` - Remove empty directories
- `stale_days` (int) - Days of inactivity before considering plan stale (default: 90)
- `dry_run` (bool) - Preview actions without making changes (default: True)

**Description:**

Performs automated maintenance tasks to keep the structure clean and organized.

**Returns:**

```json
{
  "success": true,
  "message": "Cleanup completed successfully",
  "report": {
    "dry_run": false,
    "actions_performed": {
      "archive_stale": {
        "plans_archived": 3,
        "files": [
          "old-feature-plan.md",
          "abandoned-refactor.md",
          "obsolete-research.md"
        ]
      },
      "organize_plans": {
        "plans_moved": 5,
        "active_to_completed": 2,
        "completed_to_archived": 3
      },
      "fix_symlinks": {
        "symlinks_fixed": 1,
        "broken_symlinks_removed": 0
      },
      "update_index": {
        "entries_updated": 15,
        "stale_entries_removed": 2
      },
      "remove_empty": {
        "directories_removed": 2
      }
    },
    "total_changes": 11
  }
}
```

---

### get_structure_info

Get current project structure configuration, paths, and status. No parameters (project root resolved internally).

**USE WHEN:** Resolving memory bank/plans/rules paths, checking structure health, or discovering project layout at session start.

**EXAMPLES:** 'get structure info', 'show structure paths', 'get memory bank path'.

**Description:** Returns structure version, configured paths (memory_bank, plans, rules, config, reviews), configuration, existence flags, and health summary.

**Returns:**

```json
{
  "success": true,
  "structure_info": {
    "version": "1.0.0",
    "root": "/path/to/project",
    "paths": {
      "memory_bank": ".memory-bank",
      "knowledge": ".memory-bank/knowledge",
      "rules_local": ".memory-bank/rules/local",
      "rules_shared": ".memory-bank/rules/shared",
      "plans": ".memory-bank/plans",
      "config": ".memory-bank/config"
    },
    "configuration": {
      "project_name": "My Project",
      "project_type": "web",
      "primary_language": "python",
      "use_shared_rules": true,
      "shared_rules_repo": "git@github.com:org/shared-rules.git"
    },
    "statistics": {
      "knowledge_files": 7,
      "local_rules": 5,
      "shared_rules": 25,
      "active_plans": 3,
      "completed_plans": 12,
      "archived_plans": 45
    },
    "cursor_integration": {
      "enabled": true,
      "symlinks": [
        ".cursor/knowledge -> ../.memory-bank/knowledge",
        ".cursor/rules -> ../.memory-bank/rules",
        ".cursor/plans -> ../.memory-bank/plans",
        ".cursorrules -> .memory-bank/rules/local/main.cursorrules"
      ]
    },
    "health": {
      "score": 85,
      "grade": "B",
      "status": "good"
    }
  },
  "message": "Structure information retrieved successfully"
}
```

### cortex://project/root (resource)

Idempotent MCP resource that returns the resolved project root path. Single recommended entry point for obtaining project root via MCP; use instead of parsing `get_structure_info` / `cortex://structure/info` when only the root path is needed.

**URI:** `cortex://project/root`

**Method:** GET (resource read).

**Returns:**

```json
{
  "project_root": "/absolute/path/to/project"
}
```

Repeated reads in the same context return the same path (idempotent). Resolution uses the same logic as tools (MCP roots when available, else current working directory / script-based fallback).

---

## Phase 5 Evaluation Tools

Tools for evaluating MCP tool behavior, analyzing error patterns, and running optimization workflows. Used for quality assurance and session optimization.

### run_tool_evaluation

Run the evaluation suite for MCP tools and return metrics.

**Parameters:**

- `task_ids` (list[str] | None) - Optional list of task IDs to run; if omitted, all tasks from `.cortex/evals/tasks` are loaded
- `ctx` (MCPContext | None) - MCP context (injected by server)

**Returns:** JSON string with `status`, `project_root`, `tasks_loaded`, `generated_at`, `cache_file`, `suite`, `analysis`, and `dashboard_path`. Results are also written to `.cortex/.cache/evals/last_suite.json` and a dashboard at `.cortex/.cache/evals/dashboard.md`.

---

### tool_error_pattern_analysis

Analyze aggregated error patterns from the latest evaluation suite. Writes a compact payload to `.cortex/.cache/evals/error_patterns.json`.

**Parameters:**

- `ctx` (MCPContext | None) - MCP context (injected by server)

**Returns:** JSON string with top error patterns and summary statistics.

---

### get_session_tool_anomalies (removed from tool list)

**Pruned.** This tool is no longer in the MCP tool list. Use **`query_usage(query_type="anomalies", hours=24)`** for the same behavior. See [tool-optimization-mapping](../architecture/tool-optimization-mapping.md).

---

### run_tool_optimization_workflow (removed from tool list)

**Pruned.** This tool is no longer in the MCP tool list. For usage-based optimization use **`query_usage(query_type="unused")`** and **`query_usage(query_type="recommendations")`** and the workflow in [tool-optimization-baseline](../architecture/tool-optimization-baseline.md). See [tool-optimization-mapping](../architecture/tool-optimization-mapping.md).

---

## Phase 58: Multi-Agent Task Locking

Tools for coordinating multiple agents via task locks. Use when multiple sessions or agents may work on the same project to avoid conflicting edits.

### claim_task_lock

Claim an exclusive lock on a task (by task_id). Fails if the task is already locked by another session.

**Parameters:**

- `task_id` (str) - Unique task identifier
- `session_id` (str) - Session claiming the lock
- `ctx` (MCPContext | None) - MCP context (injected by server)

**Returns:** JSON with `status` ("success" | "error") and lock details or error message.

---

### release_task_lock

Release a previously claimed task lock.

**Parameters:**

- `task_id` (str) - Task identifier
- `session_id` (str) - Session that holds the lock
- `ctx` (MCPContext | None) - MCP context (injected by server)

**Returns:** JSON with `status` and confirmation or error.

---

### list_active_task_locks

List all currently active task locks (read-only).

**Parameters:**

- `ctx` (MCPContext | None) - MCP context (injected by server)

**Returns:** JSON with list of active locks (task_id, session_id, etc.).

---

### check_task_availability

Check whether a task is available (not locked) or locked by another session.

**Parameters:**

- `task_id` (str) - Task identifier
- `ctx` (MCPContext | None) - MCP context (injected by server)

**Returns:** JSON with `available` (bool) and optional `locked_by` session id.

---

## Health-Check Analysis

Tools for analyzing prompts, rules, and MCP tools for merge and optimization opportunities.

### analyze_health_check

Analyze prompts, rules, and/or MCP tools for merge and optimization opportunities.

**USE WHEN:** User wants health-check analysis of prompts, rules, or tools; merge/optimization suggestions; dependency mapping.

**Parameters:**

- `analysis_type` (Literal["prompts", "rules", "tools", "all"]) - What to analyze (default: "all")
- `similarity_threshold` (float) - Similarity threshold 0.0–1.0 (default: 0.75)
- `include_dependencies` (bool) - Include prompt/rule dependency maps (default: true)
- `validate_quality` (bool) - Run quality validation on merge opportunities (default: true)
**Returns:** JSON string with `status`, `analysis_type`, `prompts`, `rules`, `tools`, `recommendations`, and optionally `prompt_dependencies` and `rule_dependencies`.

**See:** [Health-Check API](health-check.md) and [Health-Check Guide](../guides/health-check.md).

---

## Legacy Tools

Legacy tools maintained for backward compatibility.

### get_memory_bank_structure

Get a detailed description of the Memory Bank file structure.

**Parameters:** None

**Description:**

Returns a description of the recommended Memory Bank structure and file organization.

**Returns:**

String with structure description:

```text
Memory Bank Structure:

memory-bank/
├── projectBrief.md - Foundation document
├── productContext.md - Product context
├── activeContext.md - Completed work only (summaries of done work)
├── systemPatterns.md - Architecture
├── techContext.md - Technical details
├── progress.md - Development progress
└── roadmap.md - Future/upcoming work only (when work is done, move to activeContext)

Responsibilities: activeContext = completed work; roadmap = future work; no overlap.
Each file serves a specific purpose in maintaining context for AI assistants...
```

---

### generate_memory_bank_template

[LEGACY] Generate a template for a specific Memory Bank file.

**Parameters:**

- `file_name` (str) - The name of the file to generate a template for (e.g., "projectBrief.md")

**Description:**

**NOTE:** This tool is legacy. For new projects, use `initialize_memory_bank()` instead, which creates all files at once with proper metadata tracking.

Returns a template for the specified file.

**Returns:**

String with template content:

```markdown
# Project Brief

## Overview
[Brief description of the project]

## Goals
[Key objectives and goals]

## Scope
[What's in scope and out of scope]
...
```

---

### analyze_project_summary

Analyze a project summary and provide suggestions for Memory Bank content.

**Parameters:**

- `project_summary` (str) - A summary of the project

**Description:**

Analyzes a project description and suggests what should go into each Memory Bank file.

**Returns:**

```json
{
  "status": "success",
  "suggestions": {
    "projectBrief.md": [
      "Include project goals and objectives",
      "Define scope and boundaries",
      "List key stakeholders"
    ],
    "productContext.md": [
      "Describe target users",
      "Explain problem being solved",
      "Outline solution approach"
    ],
    "techContext.md": [
      "List technologies used",
      "Document architecture decisions",
      "Note development setup requirements"
    ]
  }
}
```

---

## Sequential Thinking

Stepwise, reflective problem-solving compatible with the MCP sequential thinking contract (thought history, revisions, branches).

### sequentialthinking

Run one step of sequential thinking and return structured state.

**USE WHEN:** Breaking down complex problems, multi-step planning, analysis with revision, unclear scope, or when you need to filter irrelevant information (e.g. plan a refactor, debug a failing test, design an API).

**Parameters:**

- `thought` (str) - Current thinking step (required)
- `next_thought_needed` (bool) - Whether another thought step is needed (required)
- `thought_number` (int) - Current thought index, 1-based (required)
- `total_thoughts` (int) - Estimated total thoughts; can be adjusted (required)
- `is_revision` (bool) - This thought revises previous thinking (optional, default: false)
- `revises_thought` (int | None) - Which thought number is being revised (optional)
- `branch_from_thought` (int | None) - Branching point thought number (optional)
- `branch_id` (str | None) - Branch identifier when branching (optional)
- `needs_more_thoughts` (bool) - More thoughts needed than estimated (optional, default: false)

**Returns:**

JSON with camelCase keys: `thoughtNumber`, `totalThoughts`, `nextThoughtNeeded`, `branches` (list of branch IDs), `thoughtHistoryLength`. Compatible with the reference MCP sequential thinking server.

---

## Error Handling

All tools follow consistent error handling:

### Success Response

```json
{
  "status": "success",
  ...
}
```

### Error Response

```json
{
  "status": "error",
  "error": "Error message describing what went wrong",
  "error_type": "FileNotFoundError",
  "details": {
    "file": "missing-file.md",
    "attempted_path": "/path/to/memory-bank/missing-file.md"
  }
}
```

### Common Error Types

- `FileNotFoundError` - Requested file doesn't exist
- `FileConflictError` - File was modified externally during operation
- `FileLockTimeoutError` - Couldn't acquire file lock (file in use)
- `CircularDependencyError` - Circular transclusion detected
- `MaxDepthExceededError` - Transclusion nesting too deep
- `ValidationError` - Invalid input parameters
- `MigrationFailedError` - Migration process failed
- `GitConflictError` - Git operation conflict

---

## See Also

- [Architecture Documentation](../architecture.md) - System architecture details
- [API Modules Reference](modules.md) - Module-level API documentation
- [Configuration Guide](../guides/configuration.md) - Configuration options
- [Troubleshooting Guide](../guides/troubleshooting.md) - Common issues and solutions
