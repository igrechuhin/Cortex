"""Memory Bank entry points that delegate to manage_file_helpers."""

import json

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM, MemoryBankFile
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.server import cortex_agent_only_auth, mcp
from cortex.tools.artifacts.artifact_types import ArtifactType
from cortex.tools.files.manage_file_helpers import (
    execute_file_operation,
    manage_file_validate_and_run,
)
from cortex.tools.files.operation_helpers import FileOperation
from cortex.tools.structure.categories import ALLOWED_CALLERS_CODE_EXECUTION

MANAGE_FILE_INPUT_EXAMPLES: list[dict[str, object]] = [
    {
        "file_name": MemoryBankFile.PROJECT_BRIEF,
        "operation": "read",
        "include_metadata": True,
    },
    {
        "file_name": MemoryBankFile.ACTIVE_CONTEXT,
        "operation": "write",
        "content": "# Active Context\n\n## Current Work\n\n...",
        "change_description": "Updated current work focus",
    },
    {"file_name": MemoryBankFile.ROADMAP, "operation": "metadata"},
    {
        "file_name": "projectBrief.md",
        "operation": "rollback",
        "version": 3,
    },
]


def _resolve_manage_file_defaults(
    file_name: str | None,
    operation: FileOperation | None,
) -> tuple[str, FileOperation]:
    """Resolve missing params from session config defaults."""
    if file_name is None:
        from cortex.core.session_config import read_session_config

        cfg = read_session_config()
        file_name = str(cfg.get("file_name", "activeContext.md"))
    if operation is None:
        operation = FileOperation.READ
    # AI: init_constitution always targets the canonical memory-bank filename.
    if operation == FileOperation.INIT_CONSTITUTION:
        file_name = MemoryBankFile.CONSTITUTION
    return file_name, operation


def _build_file_artifact_payload(
    operation: FileOperation,
    artifact_type: ArtifactType | None,
    title: str | None,
    content: str | None,
    tags: list[str] | None,
) -> str | None:
    if operation != FileOperation.FILE_ARTIFACT:
        return content
    return json.dumps(
        {
            "artifact_type": artifact_type.value if artifact_type is not None else None,
            "title": title,
            "content": content,
            "tags": tags,
        }
    )


async def _run_manage_file_operation(
    ctx: MCPContext | None,
    file_name: str,
    operation: FileOperation,
    payload: str | None,
    include_metadata: bool,
    change_description: str | None,
    sections: list[str] | None,
    version: int | None,
    skip_classification: bool,
    source: str = "local",
) -> str:
    await log_client(
        ctx,
        "info",
        f"manage_file: starting file_name={file_name!r} operation={operation!r}",
        logger_name=__name__,
    )
    return await manage_file_validate_and_run(
        ctx,
        file_name,
        operation,
        payload,
        include_metadata,
        change_description,
        sections,
        version,
        skip_classification,
        source,
    )


@mcp.tool(
    annotations=safe_write_annotations("Manage Memory Bank Files"),
    auth=cortex_agent_only_auth,
    meta={
        "input_examples": MANAGE_FILE_INPUT_EXAMPLES,
        "allowed_callers": list(ALLOWED_CALLERS_CODE_EXECUTION),
    },
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def manage_file(
    file_name: str | None = None,
    operation: FileOperation | None = None,
    content: str | None = None,
    include_metadata: bool = False,
    change_description: str | None = None,
    sections: list[str] | None = None,
    artifact_type: ArtifactType | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
    version: int | None = None,
    skip_classification: bool = False,
    source: str = "local",
    ctx: MCPContext | None = None,
) -> str:
    """Manage versioned Memory Bank files and Cortex reports.

    USE WHEN: Reading project context, checking versions, filing reports, or
    repairing an existing Cortex document. Prefer `update_memory_bank` for targeted
    roadmap changes and progress or activeContext entries. Pass only the file name
    for routine Memory Bank operations. DO NOT use this tool for generic files.

    PARAMETERS:

    - `read` accepts `include_metadata` and `sections` (Markdown headings or
      parent/child heading paths). With no arguments, read activeContext.md or
      the session-configured file. `source="canonical"` only supports reads of
      approved Memory Bank files or closed reports from the canonical checkout.
    - `metadata` returns metadata without loading file content. `write` requires
      Markdown `content` and an existing file. `rollback` requires a `version`.
    - `list_drafts` and `discard_draft` operate on `.cortex/plans/draft-*.md`.
    - `file_artifact` takes `artifact_type`, `title`, and `content` to file a
      report and reference it from activeContext.
    - `migrate_artifacts` previews relocation of legacy reviews, analyses, and
      queries. To apply, pass JSON in `content` with `apply: true` and
      `expected_preview_digest` from the preview.
    - `patch_document` requires operator approval for the specific repair. Pass
      an existing workspace-relative Markdown path in `.cortex/{plans,analyses,reviews}/`
      or `.cortex/memory-bank/{roadmap,activeContext,progress}.md` as `file_name`.
      Pass JSON in `content` with `expected_sha256` (64 lowercase hex from the raw
      file), unique literal `replacements` with `old`, `new`, and `count: 1`, and
      `dry_run: true` to preview (default false). For activeContext and progress,
      edit single-line entry prose only. Preserve titles, frontmatter, entry
      labels, list syntax, and lifecycle markers.

    EXAMPLES:
    - manage_file(file_name="projectBrief.md", include_metadata=True)
    - manage_file(file_name="roadmap.md", operation="metadata")

    RETURNS: JSON with `status` and operation-specific results or error details.
    See docs/api/tools.md#manage_file for payloads and repair safeguards.
    """
    file_name, operation = _resolve_manage_file_defaults(file_name, operation)
    payload = _build_file_artifact_payload(
        operation, artifact_type, title, content, tags
    )
    return await _run_manage_file_operation(
        ctx,
        file_name,
        operation,
        payload,
        include_metadata,
        change_description,
        sections,
        version,
        skip_classification,
        source,
    )


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def get_file_resource(file_name: str) -> str:
    """Resource: Read a Memory Bank file. Read via cortex://memory-bank/file/{file_name}."""
    root = await get_or_resolve_project_root(None)
    return await execute_file_operation(
        root,
        file_name,
        FileOperation.READ,
        None,
        False,
        None,
        None,  # sections
    )
