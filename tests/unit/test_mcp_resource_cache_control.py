"""Governance: cache hints and in-process caching for cortex://rules and cortex://context."""

import json
from collections.abc import Generator
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.server import mcp
from cortex.tools.optimization.handlers import (
    invalidate_context_resource_cache,
    load_context,
)
from cortex.tools.synapse.rules_operations import (
    get_relevant_rules,
    invalidate_rules_resource_cache,
)
from tests.helpers.managers import make_test_managers


@pytest.fixture(autouse=True)
def clear_mcp_static_resource_caches() -> Generator[None]:
    """Reset rules/context in-process caches so order-independent tests stay isolated."""
    invalidate_rules_resource_cache()
    invalidate_context_resource_cache()
    yield
    invalidate_rules_resource_cache()
    invalidate_context_resource_cache()


async def _cache_control_for_uri(uri: str) -> dict[str, object] | None:
    """Resolve cache_control from list_resources() (public MCP surface)."""
    resources = await mcp.list_resources()
    for res in resources:
        if str(res.uri) == uri:
            meta = res.meta
            if meta is None:
                return None
            raw = meta.get("cache_control")
            if isinstance(raw, dict):
                return cast(dict[str, object], raw)
            return None
    return None


@pytest.mark.asyncio
async def test_cortex_rules_resource_registers_cache_control_meta() -> None:
    cc = await _cache_control_for_uri("cortex://rules")
    assert cc is not None
    assert cc.get("type") == "ephemeral"
    assert cc.get("ttl") == "1h"


@pytest.mark.asyncio
async def test_cortex_context_resource_registers_cache_control_meta() -> None:
    cc = await _cache_control_for_uri("cortex://context")
    assert cc is not None
    assert cc.get("type") == "ephemeral"
    assert cc.get("ttl") == "5m"


@pytest.mark.asyncio
async def test_get_relevant_rules_second_call_hits_in_process_cache(
    tmp_path: Path,
) -> None:
    """Second read with the same session task does not call rules() again."""
    (tmp_path / ".cortex" / "rules").mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"status": "success", "operation": "get_relevant", "task_description": "cached"}
    )
    ro = "cortex.tools.synapse.rules_operations"
    with (
        patch(
            "cortex.core.session_config.read_session_config",
            return_value={"task_description": "same-task"},
        ),
        patch(f"{ro}.resolve_project_root_async", AsyncMock(return_value=tmp_path)),
        patch(f"{ro}.get_managers", AsyncMock(return_value=make_test_managers())),
        patch(f"{ro}.rules", new_callable=AsyncMock) as mock_rules,
    ):
        mock_rules.return_value = payload
        first, second = await get_relevant_rules(), await get_relevant_rules()
    assert first == second and mock_rules.call_count == 1


@pytest.mark.asyncio
async def test_load_context_second_call_hits_in_process_cache() -> None:
    """Second read with same session task+budget skips load_context_impl."""
    with (
        patch(
            "cortex.core.session_config.read_session_config",
            return_value={"task_description": "cache-test", "token_budget": 10000},
        ),
        patch(
            "cortex.tools.optimization.handlers.load_context_impl",
            new_callable=AsyncMock,
        ) as mock_impl,
    ):
        mock_impl.return_value = json.dumps(
            {
                "status": "success",
                "task_description": "cache-test",
                "strategy": "dependency_aware",
                "total_tokens": 1,
                "utilization": 0.1,
                "file_names": [],
            }
        )
        first, second = await load_context(), await load_context()
    assert first == second and mock_impl.call_count == 1
