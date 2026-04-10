"""Sequential thinking MCP tool for stepwise, reflective problem-solving.

Exposes one unified tool:
- `think`: Lightweight by default (just thought); use optional params for full
  sequential thinking (thought history, revisions, branches) compatible with
  the reference MCP sequential thinking server API.
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
    """Response shape for full-mode think (serialized with camelCase keys)."""

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

    def get_history_length(self) -> int:
        """Get the current length of thought history."""
        return len(self._thought_history)

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


# Injected core (composition root); lazy fallback for tests after reset
_injected_core: SequentialThinkingCore | None = None


def configure_sequential_thinking_core(core: SequentialThinkingCore | None) -> None:
    """Inject or clear the SequentialThinkingCore (composition root).

    Call with a core instance at server startup. Call with None to reset
    (e.g. reset_core_for_testing). Enables constructor-injection pattern.
    """
    global _injected_core
    _injected_core = core


def _get_core() -> SequentialThinkingCore:
    global _injected_core
    if _injected_core is not None:
        return _injected_core
    # Lazy fallback for tests after reset_core_for_testing(); production
    # injects at startup so this path is not hit there.
    _injected_core = SequentialThinkingCore()
    return _injected_core


def reset_core_for_testing() -> None:
    """Reset the shared core to None. For use in tests only."""
    configure_sequential_thinking_core(None)


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


def _format_think_response(lightweight: bool, out: SequentialThinkingOutput) -> str:
    """Format think tool response (lightweight vs full mode)."""
    if lightweight:
        return json.dumps(
            {"status": "thought_logged", "thought_number": out.thought_number}
        )
    return _output_to_json_string(out)


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
# MCP tool handler (unified think)
# =============================================================================


def _resolve_think_mode(
    core: SequentialThinkingCore,
    thought_number: int | None,
    total_thoughts: int | None,
    next_thought_needed: bool | None,
) -> tuple[int, int, bool, bool]:
    """Resolve thought_number, total_thoughts, next_thought_needed; return (tn, tt, ntn, lightweight)."""
    lightweight = (
        thought_number is None
        and total_thoughts is None
        and next_thought_needed is None
    )
    if lightweight:
        tn = core.get_history_length() + 1
        tt = max(tn, 1)
        ntn = False
    else:
        tn = thought_number if thought_number is not None else 1
        tt = total_thoughts if total_thoughts is not None else max(tn, 1)
        ntn = next_thought_needed if next_thought_needed is not None else False
    return (tn, tt, ntn, lightweight)


def _resolve_thought_from_config(thought: str | None) -> str:
    if thought:
        return thought
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    return str(cfg.get("task_description", "Reflect on current task"))


def _build_thinking_input(
    thought: str,
    thought_number: int,
    total_thoughts: int,
    next_thought_needed: bool,
    is_revision: bool,
    revises_thought: int | None,
    branch_from_thought: int | None,
    branch_id: str | None,
    needs_more_thoughts: bool,
) -> SequentialThinkingInput:
    return SequentialThinkingInput(
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


@mcp.tool(annotations=safe_write_annotations("Thinking"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def think(
    thought: str | None = None,
    thought_number: int | None = None,
    total_thoughts: int | None = None,
    next_thought_needed: bool | None = None,
    is_revision: bool = False,
    revises_thought: int | None = None,
    branch_from_thought: int | None = None,
    branch_id: str | None = None,
    needs_more_thoughts: bool = False,
) -> str:
    """Append a thought to internal scratchpad.

    USE WHEN: Agent needs reasoning before action or multi-step deliberation.
    EXAMPLES: think(thought="Check constraints"), think(thought="Step 1", thought_number=1, total_thoughts=2, next_thought_needed=True).
    """
    core = _get_core()
    thought = _resolve_thought_from_config(thought)
    thought_number, total_thoughts, next_thought_needed_val, lightweight = (
        _resolve_think_mode(core, thought_number, total_thoughts, next_thought_needed)
    )
    inp = _build_thinking_input(
        thought=thought,
        thought_number=thought_number,
        total_thoughts=total_thoughts,
        next_thought_needed=next_thought_needed_val,
        is_revision=is_revision,
        revises_thought=revises_thought,
        branch_from_thought=branch_from_thought,
        branch_id=branch_id,
        needs_more_thoughts=needs_more_thoughts,
    )
    _maybe_log_thought(inp.thought_number, inp.total_thoughts, inp.thought)
    out = core.process_thought(inp)
    return _format_think_response(lightweight, out)
