"""Typed reads of the existing generated MCP and startup command contracts."""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class GeneratedServer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str
    args: list[str]
    env: dict[str, str]


class StartupKind(str, Enum):
    COMMAND = "command"


class StartupCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: StartupKind = Field(alias="type")
    command: str
    timeout: int


class StartupGroup(BaseModel):
    hooks: list[StartupCommand]


class HookEvents(BaseModel):
    session_start: list[StartupGroup] = Field(alias="SessionStart")


class HookConfiguration(BaseModel):
    hooks: HookEvents


class McpConfiguration(BaseModel):
    servers: dict[str, GeneratedServer] = Field(alias="mcpServers")


def read_plugin_launch(root: Path) -> tuple[GeneratedServer, StartupCommand]:
    server = McpConfiguration.model_validate_json(
        (root / ".mcp.json").read_text()
    ).servers["cortex"]
    hooks = HookConfiguration.model_validate_json(
        (root / "hooks/hooks.json").read_text()
    )
    return server, hooks.hooks.session_start[0].hooks[0]
