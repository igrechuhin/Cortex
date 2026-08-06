"""Lazy ``anthropic`` adapter for the agentic eval mode.

``anthropic`` is an optional extra. It is imported inside
``resolve_model_client`` only, so every default Cortex code path -- and the
whole test suite -- keeps working in a checkout without the extra installed.
Absence of the package or of ``ANTHROPIC_API_KEY`` yields a typed skip result,
never an exception.
"""

from __future__ import annotations

import importlib
import os
from typing import Protocol, cast

from ._agent_loop import ModelClientProtocol
from ._agentic_models import (
    AgenticSkipReason,
    ModelMessage,
    ModelToolCall,
    ModelToolSchema,
    ModelTurn,
)

DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_MAX_TOKENS = 4096
API_KEY_ENV = "ANTHROPIC_API_KEY"


class MessagesApiProtocol(Protocol):
    """The single Anthropic SDK entry point this adapter uses."""

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> object:
        """Create one message completion."""
        ...


def _message_to_blocks(message: ModelMessage) -> list[dict[str, object]]:
    """Render one transcript entry as Anthropic content blocks."""
    blocks: list[dict[str, object]] = []
    if message.text:
        blocks.append({"type": "text", "text": message.text})
    for call in message.tool_calls:
        blocks.append(
            {
                "type": "tool_use",
                "id": call.call_id,
                "name": call.tool_name,
                "input": call.arguments,
            }
        )
    for result in message.tool_results:
        blocks.append(
            {
                "type": "tool_result",
                "tool_use_id": result.call_id,
                "content": result.content,
                "is_error": result.is_error,
            }
        )
    return blocks


def to_api_messages(messages: list[ModelMessage]) -> list[dict[str, object]]:
    """Convert the SDK-agnostic transcript into Anthropic message payloads."""
    return [
        {"role": m.role, "content": _message_to_blocks(m)}
        for m in messages
        if _message_to_blocks(m)
    ]


def to_api_tools(tools: list[ModelToolSchema]) -> list[dict[str, object]]:
    """Convert registered tool schemas into Anthropic tool definitions."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema or {"type": "object", "properties": {}},
        }
        for tool in tools
    ]


def _block_tool_call(block: object) -> ModelToolCall | None:
    """Normalize one response block into a tool call, if it is one."""
    # BELIEF: SDK response blocks expose .type/.id/.name/.input attributes.
    if getattr(block, "type", "") != "tool_use":
        return None
    raw_input = getattr(block, "input", None)
    arguments: dict[str, object] = (
        cast(dict[str, object], raw_input) if isinstance(raw_input, dict) else {}
    )
    return ModelToolCall(
        call_id=str(getattr(block, "id", "")),
        tool_name=str(getattr(block, "name", "")),
        arguments=arguments,
    )


def normalize_response(raw: object) -> ModelTurn:
    """Convert a raw Anthropic response object into a typed ``ModelTurn``."""
    # BELIEF: the response exposes .content (a sequence) and .stop_reason.
    content = getattr(raw, "content", None)
    blocks: list[object] = (
        list(cast(list[object], content)) if isinstance(content, list) else []
    )
    texts: list[str] = []
    calls: list[ModelToolCall] = []
    for block in blocks:
        if getattr(block, "type", "") == "text":
            texts.append(str(getattr(block, "text", "")))
            continue
        call = _block_tool_call(block)
        if call is not None:
            calls.append(call)
    return ModelTurn(
        text="\n".join(texts),
        tool_calls=calls,
        stop_reason=str(getattr(raw, "stop_reason", "") or ""),
    )


class AnthropicModelClient:
    """Adapter implementing ``ModelClientProtocol`` over the Anthropic SDK."""

    def __init__(
        self,
        messages_api: MessagesApiProtocol,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self._messages_api = messages_api
        self._model = model
        self._max_tokens = max_tokens

    async def complete(
        self, messages: list[ModelMessage], tools: list[ModelToolSchema]
    ) -> ModelTurn:
        """Send one request and return the normalized turn."""
        raw = await self._messages_api.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=to_api_messages(messages),
            tools=to_api_tools(tools),
        )
        return normalize_response(raw)


def resolve_model_client(
    model: str = DEFAULT_MODEL, api_key: str | None = None
) -> ModelClientProtocol | AgenticSkipReason:
    """Build an Anthropic-backed client, or return why the mode must skip."""
    key = api_key if api_key is not None else os.environ.get(API_KEY_ENV, "")
    try:
        # AI: lazy, runtime-only import -- `anthropic` is an optional extra and must
        # never be imported on the default server path. importlib is used instead of
        # a bare `import anthropic` so a checkout without the extra type-checks too.
        module = importlib.import_module("anthropic")
    except ImportError:
        return AgenticSkipReason.DEPENDENCY_MISSING
    if not key:
        return AgenticSkipReason.API_KEY_MISSING
    # AI: single cast at the SDK boundary -- the adapter reads only `messages.create`.
    messages_api = cast(
        MessagesApiProtocol, module.AsyncAnthropic(api_key=key).messages
    )
    return AnthropicModelClient(messages_api, model=model)
