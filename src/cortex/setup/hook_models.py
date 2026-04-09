from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_serializer


class HookType(str, Enum):
    COMMAND = "command"
    PROMPT = "prompt"
    AGENT = "agent"


class HookCondition(BaseModel):
    tool: str = Field(min_length=1)
    pattern: str | None = None

    def to_matcher_string(self) -> str:
        normalized_tool = self.tool.strip()
        if not normalized_tool:
            raise ValueError("tool must be non-empty")
        if self.pattern is None:
            return normalized_tool

        normalized_pattern = self.pattern.strip()
        if not normalized_pattern:
            return normalized_tool
        # AI: Claude matcher DSL embeds the condition pattern inline as Tool(pattern).
        return f"{normalized_tool}({normalized_pattern})"


class HookConditionPayload(BaseModel):
    tool: str = Field(min_length=1)
    pattern: str = Field(min_length=1)


class CommandHookEntry(BaseModel):
    type: HookType = HookType.COMMAND
    command: str = Field(min_length=1)
    once: bool = False
    timeout: int | None = None

    @model_serializer(mode="plain")
    def serialize_minimal(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": self.type.value,
            "command": self.command,
        }
        if self.once:
            payload["once"] = True
        if self.timeout is not None:
            payload["timeout"] = self.timeout
        return payload


class _PromptAgentHookBase(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: "".join(
            word if idx == 0 else word.capitalize()
            for idx, word in enumerate(field_name.split("_"))
        ),
    )

    type: HookType
    prompt: str = Field(min_length=1)
    model: str | None = None
    timeout: int | None = None
    status_message: str | None = None

    @model_serializer(mode="plain")
    def serialize_minimal(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": self.type.value,
            "prompt": self.prompt,
        }
        if self.model is not None:
            payload["model"] = self.model
        if self.timeout is not None:
            payload["timeout"] = self.timeout
        if self.status_message is not None:
            payload["statusMessage"] = self.status_message
        return payload


class PromptHookEntry(_PromptAgentHookBase):
    type: HookType = HookType.PROMPT


class AgentHookEntry(_PromptAgentHookBase):
    type: HookType = HookType.AGENT


HookEntry = CommandHookEntry | PromptHookEntry | AgentHookEntry


class PostToolUseBlock(BaseModel):
    matcher: str = Field(min_length=1)
    hooks: list[HookEntry]
