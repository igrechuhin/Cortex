"""Build a genuine wheel and execute only the freshly generated plugin commands."""

import json
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import TextIO

from mcp import StdioServerParameters
from pydantic import BaseModel, Field

from cortex.setup.plugin_package import assemble
from tests.helpers.plugin_launch_models import (
    GeneratedServer,
    StartupCommand,
    read_plugin_launch,
)
from tests.helpers.uv_test_state import UvTestState


class PluginHost(str, Enum):
    CLAUDE = "claude"
    CODEX = "codex"


class StartupContext(BaseModel):
    event: str = Field(alias="hookEventName")
    context: str = Field(alias="additionalContext")


class StartupOutput(BaseModel):
    specific: StartupContext = Field(alias="hookSpecificOutput")


class RealPlugin(BaseModel):
    root: Path
    host: PluginHost
    server: GeneratedServer
    startup: StartupCommand

    def parameters(self, workspace: Path, state: UvTestState) -> StdioServerParameters:
        for key, value in state.directories().environment().items():
            assert self.server.env[key] == value
        args = [
            item.replace("${CLAUDE_PLUGIN_ROOT}", str(self.root))
            for item in self.server.args
        ]
        return StdioServerParameters(
            command=self.server.command,
            args=args,
            cwd=workspace,
            env={**state.environment(), **self.server.env},
        )


def _build_wheel(state: UvTestState, stderr: TextIO) -> Path:
    checkout = Path(__file__).resolve().parents[2]
    dist = state.base / "built-wheel"
    dist.mkdir()
    backend = Path(sys.executable).parent / "uv-build"
    _ = subprocess.run(
        [str(backend), "build-wheel", str(dist)],
        cwd=checkout,
        env=state.environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=stderr,
        text=True,
        check=True,
        timeout=30,
    )
    wheels = list(dist.glob("cortex-*.whl"))
    assert len(wheels) == 1, "Real PEP517 backend did not build one Cortex wheel"
    return wheels[0]


def build_real_plugin(
    state: UvTestState, host: PluginHost, stderr: TextIO
) -> RealPlugin:
    checkout = Path(__file__).resolve().parents[2]
    wheel = _build_wheel(state, stderr)
    output = state.base / "plugin ; $(touch UV_MUST_NOT_RUN)"
    assemble(
        checkout / ".cortex/synapse",
        wheel,
        output,
        checkout / "docs",
        uv_directories=state.directories(),
    )
    root = output / host.value / "plugins/cortex"
    server, startup = read_plugin_launch(root)
    return RealPlugin(root=root, host=host, server=server, startup=startup)


def run_real_startup(
    plugin: RealPlugin, workspace: Path, state: UvTestState, stderr: TextIO
) -> None:
    environment = _startup_environment(plugin, state)
    _assert_no_default_uv_state(state)
    # AI: This is the fixed generated host shell form, never a caller-supplied command.
    result = subprocess.run(
        ["/bin/sh", "-c", plugin.startup.command],
        cwd=workspace,
        env=environment,
        input=_startup_input(workspace),
        stdout=subprocess.PIPE,
        stderr=stderr,
        text=True,
        check=True,
        timeout=plugin.startup.timeout,
    )
    output = StartupOutput.model_validate_json(result.stdout)
    assert output.specific.event == "SessionStart"
    assert 0 < len(output.specific.context) <= 3000
    assert not (workspace / "UV_MUST_NOT_RUN").exists()
    _assert_no_default_uv_state(state)


def _startup_environment(plugin: RealPlugin, state: UvTestState) -> dict[str, str]:
    variable = (
        "CLAUDE_PLUGIN_ROOT" if plugin.host is PluginHost.CLAUDE else "PLUGIN_ROOT"
    )
    environment = {**state.environment(), variable: str(plugin.root)}
    # AI: Only the generated prefix may choose storage in this real hook proof.
    _ = environment.pop("UV_CACHE_DIR")
    _ = environment.pop("UV_TOOL_DIR")
    return environment


def _assert_no_default_uv_state(state: UvTestState) -> None:
    defaults = ("cache/uv", "data/uv/tools", ".cache/uv", ".local/share/uv/tools")
    for relative in defaults:
        assert not (state.home / relative).exists()


def _startup_input(workspace: Path) -> str:
    return json.dumps(
        {
            "hook_event_name": "SessionStart",
            "cwd": str(workspace.resolve()),
            "session_id": "real-plugin-fixture",
            "source": "startup",
        }
    )
