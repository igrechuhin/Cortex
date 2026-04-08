"""Tests for recent ingested sources in cortex://context payload."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cortex.tools.optimization import load_context
from cortex.tools.optimization.handlers import invalidate_context_resource_cache
from tests.helpers.phase4_optimization_managers import build_phase4_mock_managers


def _get_manager_helper(mgrs: object, key: str, _: object) -> object:
    return getattr(mgrs, key)


def _write_test_ingested_sources(mock_project_root: Path) -> None:
    memory_bank_dir = mock_project_root / ".cortex" / "memory-bank"
    sources = memory_bank_dir / "sources"
    sources.mkdir(parents=True)
    _ = (sources / "ingest-rfc.md").write_text(
        "# Ingest RFC\n\nBody.", encoding="utf-8"
    )


def _build_mock_managers() -> object:
    mock_optimization_result = MagicMock(
        selected_files=["file1.md"],
        selected_sections={},
        total_tokens=1000,
        utilization=0.1,
        excluded_files=[],
        metadata={"relevance_scores": {"file1.md": 1.0}},
    )
    mock_loaded_content = [MagicMock(file_name="file1.md", tokens=1000)]
    return build_phase4_mock_managers(mock_optimization_result, mock_loaded_content)


async def test_load_context_includes_recent_ingested_sources_when_present(
    tmp_path: Path,
) -> None:
    invalidate_context_resource_cache()
    _write_test_ingested_sources(tmp_path)
    with (
        patch(
            "cortex.core.session_config.read_session_config",
            return_value={"task_description": "Test task with ingested sources"},
        ),
        patch(
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            "cortex.tools.optimization.get_managers",
            return_value=_build_mock_managers(),
        ),
        patch(
            "cortex.tools.context.load_operations.get_manager",
            side_effect=_get_manager_helper,
        ),
    ):
        result = json.loads(await load_context())
    assert result["status"] == "success"
    assert "recent_ingested_sources" in result
    assert "## Recently Ingested Sources" in result["recent_ingested_sources"]
    assert "[Ingest RFC](sources/ingest-rfc.md)" in result["recent_ingested_sources"]


async def test_load_context_omits_recent_ingested_sources_when_none(
    tmp_path: Path,
) -> None:
    invalidate_context_resource_cache()
    with (
        patch(
            "cortex.core.session_config.read_session_config",
            return_value={"task_description": "Test task no ingested sources"},
        ),
        patch(
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            "cortex.tools.optimization.get_managers",
            return_value=_build_mock_managers(),
        ),
        patch(
            "cortex.tools.context.load_operations.get_manager",
            side_effect=_get_manager_helper,
        ),
    ):
        result = json.loads(await load_context())
    assert result["status"] == "success"
    assert "recent_ingested_sources" not in result
