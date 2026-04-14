from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastmcp import FastMCP

from cortex.server import (
    build_transforms_for_tool_compat,
    cortex_agent_only_auth,
    ingest_caller_auth,
    server_lifespan,
)


def test_cortex_agent_only_auth_allows_trusted_client() -> None:
    ctx = SimpleNamespace(client_info=SimpleNamespace(name="cursor-agent"))
    assert cortex_agent_only_auth(ctx) is True


def test_cortex_agent_only_auth_denies_untrusted_client() -> None:
    ctx = SimpleNamespace(client_info=SimpleNamespace(name="browser-user"))
    assert cortex_agent_only_auth(ctx) is False


def test_ingest_caller_auth_allows_commit_pipeline_name() -> None:
    ctx = SimpleNamespace(client_info=SimpleNamespace(name="commit-pipeline"))
    assert ingest_caller_auth(ctx) is True


def test_build_transforms_uses_tool_compat_flags() -> None:
    with (
        patch("cortex.server.Path.cwd", return_value=Path("/tmp/test-project")),
        patch("cortex.server.Path.exists", return_value=True),
        patch(
            "cortex.server.Path.read_text",
            return_value=json.dumps(
                {
                    "tool_compat": {
                        "expose_resources_as_tools": True,
                        "expose_prompts_as_tools": True,
                    }
                }
            ),
        ),
    ):
        transforms = build_transforms_for_tool_compat()
    assert len(transforms) == 2


@pytest.mark.asyncio
async def test_lifespan_injects_sequential_thinking_core_once() -> None:
    with patch(
        "cortex.tools.session.sequential_thinking.configure_sequential_thinking_core"
    ) as configure_mock:
        async with server_lifespan(FastMCP("cortex-test")):
            pass
    configure_mock.assert_called_once()
