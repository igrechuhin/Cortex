"""MCP tool: propose an isolated, self-tested Synapse/rules optimization."""

from __future__ import annotations

import json

from pydantic import TypeAdapter, ValidationError

from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.context_logging import MCPContext
from cortex.core.execution_env import LocalExecutionEnvironment
from cortex.core.mcp_annotations import external_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import OperationStatus
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.server import cortex_agent_only_auth, mcp
from cortex.tools.optimization.propose_framework_optimization_core import (
    propose_framework_optimization_core,
)
from cortex.tools.optimization.propose_framework_optimization_models import (
    ProposedFileChange,
    ProposeFrameworkOptimizationRequest,
)

_CHANGES_ADAPTER: TypeAdapter[list[ProposedFileChange]] = TypeAdapter(
    list[ProposedFileChange]
)


def _parse_request(
    changes_json: str, rationale: str
) -> ProposeFrameworkOptimizationRequest:
    changes = _CHANGES_ADAPTER.validate_json(changes_json)
    return ProposeFrameworkOptimizationRequest(changes=changes, rationale=rationale)


@mcp.tool(
    annotations=external_annotations(
        "Propose Framework Optimization", read_only=True, idempotent=False
    ),
    auth=cortex_agent_only_auth,
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def propose_framework_optimization(
    changes_json: str,
    rationale: str,
    ctx: MCPContext | None = None,
) -> str:
    """Draft, isolate, and self-test a change to Cortex's own Synapse prompts/rules.

    USE WHEN: An agent has identified a concrete, observed edge case in a
    ``.cortex/synapse/`` or ``.cortex/rules/`` prompt/rule/config file and
    wants to propose a fix for human review — never for speculative or
    unprompted self-modification. The change is applied and self-tested
    inside a throwaway git worktree; the live working tree is never touched.

    DO NOT: Use this to edit ``src/`` or any path outside ``.cortex/synapse/``
    and ``.cortex/rules/`` — those targets are rejected before any write.
    This tool never pushes or opens a PR; it only returns a diff + rationale.
    Prefer the existing, explicitly human-confirmed commit/PR workflow to act
    on the result — do not wire this tool's output into an automated push.

    EXAMPLES:
    - propose_framework_optimization(
        changes_json='[{"relative_path": ".cortex/rules/general/foo.mdc",
        "new_content": "---\\ndescription: Test\\n---\\nBody"}]',
        rationale="Rule X missed edge case Y observed in session Z")

    RETURNS: JSON with ``result`` (``self_test_passed``, ``diff``,
    ``rationale``, ``failure_reason``, ``changed_paths``). All edits happen
    in an isolated worktree that is always removed before this tool returns.
    """
    try:
        request = _parse_request(changes_json, rationale)
    except (ValidationError, ValueError) as exc:
        return json.dumps(
            {"status": OperationStatus.ERROR.value, "error": str(exc)}, indent=2
        )

    project_root = await get_or_resolve_project_root(ctx)
    result = propose_framework_optimization_core(
        project_root, request, LocalExecutionEnvironment()
    )
    return json.dumps(
        {
            "status": OperationStatus.SUCCESS.value,
            "result": result.model_dump(mode="json"),
        },
        indent=2,
    )
