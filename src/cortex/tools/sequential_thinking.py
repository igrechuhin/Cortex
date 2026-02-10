"""Sequential thinking MCP tool for stepwise, reflective problem-solving.

Exposes a single tool `sequentialthinking` compatible with the reference
MCP sequential thinking server API (thought history, revisions, branches).
"""

import json
import os

from pydantic import BaseModel, Field

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp

# =============================================================================
# Pydantic models (input/output and internal state)
# =============================================================================


class ThoughtEntry(BaseModel):
    """Single thought step stored in history or a branch."""

    thought_number: int = Field(..., ge=1, description="1-based thought index")
    thought: str = Field(..., description="Thought text")


class SequentialThinkingInput(BaseModel):
    """Input for one sequential thinking step. MCP clients send camelCase; map at boundary."""

    thought: str = Field(..., description="Current thinking step")
    next_thought_needed: bool = Field(
        ..., description="Whether another thought is needed"
    )
    thought_number: int = Field(
        ..., ge=1, description="Current thought index (1-based)"
    )
    total_thoughts: int = Field(..., ge=1, description="Estimated total thoughts")
    is_revision: bool = Field(
        False, description="This thought revises previous thinking"
    )
    revises_thought: int | None = Field(
        None, ge=1, description="Which thought is revised"
    )
    branch_from_thought: int | None = Field(
        None, ge=1, description="Branching point thought number"
    )
    branch_id: str | None = Field(None, description="Branch identifier")
    needs_more_thoughts: bool = Field(
        False, description="More thoughts than initially estimated"
    )


class SequentialThinkingOutput(BaseModel):
    """Response shape for the sequentialthinking tool (serialized with camelCase keys)."""

    thought_number: int = Field(..., description="Current thought index")
    total_thoughts: int = Field(..., description="Total thoughts (may be adjusted)")
    next_thought_needed: bool = Field(
        ..., description="Whether more thoughts are needed"
    )
    branches: list[str] = Field(..., description="List of branch IDs")
    thought_history_length: int = Field(..., description="Length of thought history")


# =============================================================================
# Core logic (pure, synchronous, stateful via injected instance)
# =============================================================================


class SequentialThinkingCore:
    """Holds thought history and branches; processes one thought at a time."""

    __slots__ = ("_thought_history", "_branches")

    def __init__(self) -> None:
        self._thought_history: list[ThoughtEntry] = []
        self._branches: dict[str, list[ThoughtEntry]] = {}

    def process_thought(self, inp: SequentialThinkingInput) -> SequentialThinkingOutput:
        """Append thought to history (and optionally to a branch); return output."""
        total = inp.total_thoughts
        if inp.thought_number > total:
            total = inp.thought_number
        entry = ThoughtEntry(
            thought_number=inp.thought_number,
            thought=inp.thought,
        )
        self._thought_history.append(entry)
        if inp.branch_from_thought is not None and inp.branch_id is not None:
            bid = inp.branch_id
            if bid not in self._branches:
                self._branches[bid] = []
            self._branches[bid].append(entry)
        return SequentialThinkingOutput(
            thought_number=inp.thought_number,
            total_thoughts=total,
            next_thought_needed=inp.next_thought_needed,
            branches=sorted(self._branches),
            thought_history_length=len(self._thought_history),
        )


# One shared core per process (single-client stdio usage)
_core: SequentialThinkingCore | None = None


def _get_core() -> SequentialThinkingCore:
    global _core
    if _core is None:
        _core = SequentialThinkingCore()
    return _core


def reset_core_for_testing() -> None:
    """Reset the shared core to None. For use in tests only."""
    global _core
    _core = None


def _output_to_json_string(output: SequentialThinkingOutput) -> str:
    """Serialize output with camelCase keys for client compatibility."""
    return json.dumps(
        {
            "thoughtNumber": output.thought_number,
            "totalThoughts": output.total_thoughts,
            "nextThoughtNeeded": output.next_thought_needed,
            "branches": output.branches,
            "thoughtHistoryLength": output.thought_history_length,
        }
    )


def _maybe_log_thought(thought_number: int, total_thoughts: int, thought: str) -> None:
    """Log formatted thought to stderr unless DISABLE_THOUGHT_LOGGING is set."""
    if os.environ.get("DISABLE_THOUGHT_LOGGING", "").lower() in ("1", "true", "yes"):
        return
    prefix = f"Thought {thought_number}/{total_thoughts}"
    preview = (thought[:80] + "…") if len(thought) > 80 else thought
    msg = f"{prefix}: {preview}\n"
    try:
        import sys

        _ = sys.stderr.write(msg)
        _ = sys.stderr.flush()
    except OSError:
        pass


# =============================================================================
# MCP tool handler
# =============================================================================


@mcp.tool(annotations=safe_write_annotations("Sequential Thinking"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def sequentialthinking(
    thought: str,
    next_thought_needed: bool,
    thought_number: int,
    total_thoughts: int,
    is_revision: bool = False,
    revises_thought: int | None = None,
    branch_from_thought: int | None = None,
    branch_id: str | None = None,
    needs_more_thoughts: bool = False,
) -> str:
    """Run one step of sequential thinking and return structured state.

    USE WHEN: Breaking down complex problems, multi-step planning, analysis
    with revision, unclear scope, or when you need to filter irrelevant
    information. Use for refactoring plans, debugging failing tests, or
    designing APIs.

    EXAMPLES: "Plan a refactor", "Debug a failing test", "Design an API",
    "Break down migration steps".

    RETURNS: JSON with thoughtNumber, totalThoughts, nextThoughtNeeded,
    branches (list of branch IDs), thoughtHistoryLength. Compatible with
    the MCP sequential thinking server contract.

    Parameters:
        thought: Current thinking step (required).
        next_thought_needed: Whether another thought step is needed (required).
        thought_number: Current thought index, 1-based (required).
        total_thoughts: Estimated total thoughts; can be adjusted (required).
        is_revision: This thought revises previous thinking (optional).
        revises_thought: Which thought number is being revised (optional).
        branch_from_thought: Branching point thought number (optional).
        branch_id: Branch identifier when branching (optional).
        needs_more_thoughts: More thoughts needed than estimated (optional).
    """
    inp = SequentialThinkingInput(
        thought=thought,
        next_thought_needed=next_thought_needed,
        thought_number=thought_number,
        total_thoughts=total_thoughts,
        is_revision=is_revision,
        revises_thought=revises_thought,
        branch_from_thought=branch_from_thought,
        branch_id=branch_id,
        needs_more_thoughts=needs_more_thoughts,
    )
    _maybe_log_thought(inp.thought_number, inp.total_thoughts, inp.thought)
    core = _get_core()
    output = core.process_thought(inp)
    return _output_to_json_string(output)
