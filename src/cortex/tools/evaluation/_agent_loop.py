"""Bounded agent-in-the-loop driver for the agentic tool-selection eval.

Adapted (not copied) from ``skills/mcp-builder/scripts/evaluation.py`` in the
Anthropic ``skills`` repository (Apache License 2.0). The structured
``<summary>``/``<feedback>``/``<response>`` output contract is preserved because
the feedback block -- the model's critique of tool names and parameter docs --
is the artifact this harness exists to collect. All result structures use
Cortex Pydantic models rather than that script's untyped dict returns.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from ._agentic_models import (
    AgentLoopOutcome,
    ModelMessage,
    ModelToolCall,
    ModelToolResult,
    ModelToolSchema,
    ModelTurn,
    ParsedAgentOutput,
)

DEFAULT_MAX_TURNS = 8

EVALUATION_PROMPT = """You are evaluating an MCP server's tool surface.

Complete the task below using ONLY the tools provided. Choose tools from their
names, descriptions, and parameter schemas alone -- do not guess at tools that
are not listed. If no provided tool is appropriate, use none and say so.

Task: {task_description}

Expected outcome: {expected_outcome}

When you are finished, reply with exactly these three blocks:

<summary>What you did and which tools you called, in one or two sentences.</summary>
<feedback>Critique the tool names, parameter descriptions, and any error
messages you saw. Name the specific tool each point refers to. Say what was
ambiguous or misleading. If nothing was wrong, say so explicitly.</feedback>
<response>Your answer to the task, or NOT_FOUND if it could not be completed.</response>
"""

_BLOCK_RE_TEMPLATE = r"<{tag}>(.*?)</{tag}>"


class ToolSessionProtocol(Protocol):
    """Minimal MCP session surface the agent loop depends on."""

    async def list_tool_schemas(self) -> list[ModelToolSchema]:
        """Return the registered tool schemas to expose to the model."""
        ...

    async def call_tool(self, name: str, arguments: dict[str, object]) -> str:
        """Invoke a tool and return its output rendered as text."""
        ...


@runtime_checkable
class ModelClientProtocol(Protocol):
    """SDK-agnostic model client the agent loop depends on."""

    async def complete(
        self, messages: list[ModelMessage], tools: list[ModelToolSchema]
    ) -> ModelTurn:
        """Send the transcript plus tool schemas and return one normalized turn."""
        ...


def _extract_block(text: str, tag: str) -> str:
    """Return the inner text of the first ``<tag>`` block, or an empty string."""
    pattern = _BLOCK_RE_TEMPLATE.format(tag=re.escape(tag))
    match = re.search(pattern, text, re.DOTALL)
    if match is None:
        return ""
    return match.group(1).strip()


def parse_agent_output(text: str) -> ParsedAgentOutput:
    """Parse the structured output blocks; missing blocks become empty strings."""
    return ParsedAgentOutput(
        summary=_extract_block(text, "summary"),
        feedback=_extract_block(text, "feedback"),
        response=_extract_block(text, "response"),
    )


def build_task_prompt(task_description: str, expected_outcome: str) -> str:
    """Render the evaluation prompt for one task."""
    return EVALUATION_PROMPT.format(
        task_description=task_description, expected_outcome=expected_outcome
    )


async def _execute_tool_calls(
    session: ToolSessionProtocol, calls: list[ModelToolCall]
) -> list[ModelToolResult]:
    """Execute each requested tool call, converting failures into error results."""
    results: list[ModelToolResult] = []
    for call in calls:
        try:
            output = await session.call_tool(call.tool_name, call.arguments)
            results.append(ModelToolResult(call_id=call.call_id, content=output))
        except Exception as exc:
            results.append(
                ModelToolResult(
                    call_id=call.call_id, content=f"error: {exc!s}", is_error=True
                )
            )
    return results


def _append_turn(
    messages: list[ModelMessage], turn: ModelTurn, results: list[ModelToolResult]
) -> None:
    """Append the assistant turn and the corresponding tool results."""
    messages.append(
        ModelMessage(role="assistant", text=turn.text, tool_calls=turn.tool_calls)
    )
    messages.append(ModelMessage(role="user", tool_results=results))


def _finish(
    tools_called: list[str], turns: int, final_text: str, capped: bool, max_turns: int
) -> AgentLoopOutcome:
    """Build the loop outcome for a normal finish or a turn-cap exhaustion."""
    error = (
        f"turn cap of {max_turns} reached without a final answer" if capped else None
    )
    return AgentLoopOutcome(
        tools_called=tools_called,
        turns=turns,
        turn_cap_reached=capped,
        parsed=parse_agent_output(final_text),
        final_text=final_text,
        error=error,
    )


async def run_agent_loop(
    session: ToolSessionProtocol,
    client: ModelClientProtocol,
    prompt: str,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> AgentLoopOutcome:
    """Drive the model against the session until it stops calling tools.

    The loop is bounded by ``max_turns``; hitting the cap is recorded rather
    than raised, because an unbounded loop is an unbounded spend.
    """
    tools = await session.list_tool_schemas()
    messages: list[ModelMessage] = [ModelMessage(role="user", text=prompt)]
    tools_called: list[str] = []
    final_text = ""
    turns = 0

    for _ in range(max_turns):
        try:
            turn = await client.complete(messages, tools)
        except Exception as exc:
            return AgentLoopOutcome(
                tools_called=tools_called, turns=turns, error=f"model error: {exc!s}"
            )
        turns += 1
        final_text = turn.text
        if not turn.tool_calls:
            return _finish(tools_called, turns, final_text, False, max_turns)
        tools_called.extend(call.tool_name for call in turn.tool_calls)
        results = await _execute_tool_calls(session, turn.tool_calls)
        _append_turn(messages, turn, results)

    return _finish(tools_called, turns, final_text, True, max_turns)
