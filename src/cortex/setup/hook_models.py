from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


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


class HookEntry(BaseModel):
    type: HookType
    command: str = Field(min_length=1)
    condition: HookCondition | None = None


class PostToolUseBlock(BaseModel):
    matcher: str = Field(min_length=1)
    hooks: list[HookEntry]
