"""Shared fixtures and builders for session_start tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.managers.types import ManagersDict
from cortex.tools.memory.compaction_operations import compact_session
from cortex.tools.models import SessionStartErrorResult, SessionStartResult
from cortex.tools.session.models import SESSION_SCOPE_PROMPT
from cortex.tools.session.start_tools import session_start_impl
from tests.helpers.managers import make_test_managers
from tests.helpers.path_helpers import ensure_test_cortex_structure
from tests.helpers.tool_call_helpers import get_tool_fn


def mcp_health_json(healthy: bool) -> str:
    """Build valid health_check-style JSON for tests."""
    health = {
        "healthy": healthy,
        "concurrent_operations": 0,
        "max_concurrent": 5,
        "semaphore_available": 5,
        "utilization_percent": 0.0,
        "long_running_holder": None,
    }
    return json.dumps({"status": "success", "health": health})


async def build_minimal_session_managers(tmp_path: Path) -> ManagersDict:
    """Create minimal session_start files/metadata and return managers."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _ = (memory_bank_dir / "activeContext.md").write_text(
        "# Active Context\n\n## Current Focus\n\nWorking on fixes.\n"
    )
    _ = (memory_bank_dir / "roadmap.md").write_text(
        "# Roadmap\n\n## Pending plans (from .cortex/plans)\n\n- **Task** - PENDING - Desc\n"
    )
    _ = (memory_bank_dir / "projectBrief.md").write_text("# Cortex\n")
    for file_name in (
        "progress.md",
        "systemPatterns.md",
        "techContext.md",
        "productContext.md",
    ):
        _ = (memory_bank_dir / file_name).write_text(f"# {file_name}\n")
    fs_manager = FileSystemManager(tmp_path)
    metadata_index = MetadataIndex(tmp_path)
    _ = await metadata_index.load()
    await _seed_basic_metadata(memory_bank_dir, metadata_index)
    return make_test_managers(
        fs=fs_manager, index=metadata_index, tokens=TokenCounter()
    )


async def _seed_basic_metadata(
    memory_bank_dir: Path, metadata_index: MetadataIndex
) -> None:
    """Populate metadata entries for minimal session_start files."""
    for file_name in (
        "activeContext.md",
        "roadmap.md",
        "projectBrief.md",
        "progress.md",
        "systemPatterns.md",
        "techContext.md",
        "productContext.md",
    ):
        await metadata_index.update_file_metadata(
            file_name=file_name,
            path=memory_bank_dir / file_name,
            exists=True,
            size_bytes=100,
            token_count=50,
            content_hash="sha256:test",
            sections=[],
        )


async def build_minimal_session_managers_with_focus(
    tmp_path: Path, focus_body: str
) -> ManagersDict:
    """Like ``build_minimal_session_managers`` but custom Current Focus body."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _ = (memory_bank_dir / "activeContext.md").write_text(
        f"# Active Context\n\n## Current Focus\n\n{focus_body}"
    )
    _ = (memory_bank_dir / "roadmap.md").write_text(
        "# Roadmap\n\n## Pending plans (from .cortex/plans)\n\n- **Task** - PENDING - Desc\n"
    )
    _ = (memory_bank_dir / "projectBrief.md").write_text("# Cortex\n")
    for file_name in (
        "progress.md",
        "systemPatterns.md",
        "techContext.md",
        "productContext.md",
    ):
        _ = (memory_bank_dir / file_name).write_text(f"# {file_name}\n")
    fs_manager = FileSystemManager(tmp_path)
    metadata_index = MetadataIndex(tmp_path)
    _ = await metadata_index.load()
    await _seed_basic_metadata(memory_bank_dir, metadata_index)
    return make_test_managers(
        fs=fs_manager, index=metadata_index, tokens=TokenCounter()
    )


ACTIVE_CONTEXT_PHASE54_FULL = """# Active Context

## Current Focus

Working on Phase 54.

## Completed Work

- ✅ Phase 50 - COMPLETE
- ✅ Phase 51 - COMPLETE

## Next Steps
"""

ROADMAP_PHASE54_PENDING = """# Roadmap

## Pending plans (from .cortex/plans)

- **Phase 54** - PENDING - Session Start Initializer
"""

ROADMAP_PHASE54_TOOL = """# Roadmap

## Pending plans (from .cortex/plans)

- **Phase 54** - PENDING - Description
"""

MEMORY_BANK_ALL_REQUIRED = (
    "projectBrief.md",
    "activeContext.md",
    "roadmap.md",
    "progress.md",
    "systemPatterns.md",
    "techContext.md",
    "productContext.md",
)


async def managers_with_every_memory_bank_file(tmp_path: Path) -> ManagersDict:
    """All seven memory-bank files on disk with metadata (health summary all-files test)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    for file_name in MEMORY_BANK_ALL_REQUIRED:
        _ = (memory_bank_dir / file_name).write_text(f"# {file_name}\n\nContent")
    fs_manager = FileSystemManager(tmp_path)
    metadata_index = MetadataIndex(tmp_path)
    _ = await metadata_index.load()
    for file_name in MEMORY_BANK_ALL_REQUIRED:
        file_path = memory_bank_dir / file_name
        await metadata_index.update_file_metadata(
            file_name=file_name,
            path=file_path,
            exists=True,
            size_bytes=100,
            token_count=50,
            content_hash="sha256:test",
            sections=[],
        )
    return make_test_managers(fs=fs_manager, index=metadata_index)


async def minimal_session_managers_custom_roadmap(
    tmp_path: Path, *, roadmap: str, focus: str = "Test.\n"
) -> ManagersDict:
    """Minimal session files with a custom roadmap body (MCP unhealthy tests)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _ = (memory_bank_dir / "activeContext.md").write_text(
        f"# Active Context\n\n## Current Focus\n\n{focus}"
    )
    _ = (memory_bank_dir / "roadmap.md").write_text(roadmap)
    _ = (memory_bank_dir / "projectBrief.md").write_text("# Cortex\n")
    for file_name in (
        "progress.md",
        "systemPatterns.md",
        "techContext.md",
        "productContext.md",
    ):
        _ = (memory_bank_dir / file_name).write_text(f"# {file_name}\n")
    fs_manager = FileSystemManager(tmp_path)
    metadata_index = MetadataIndex(tmp_path)
    _ = await metadata_index.load()
    await _seed_basic_metadata(memory_bank_dir, metadata_index)
    return make_test_managers(
        fs=fs_manager, index=metadata_index, tokens=TokenCounter()
    )


_LIFECYCLE_ACTIVE = """# Active Context

## Current Focus

Test.

## Completed Work (2026-02-01)

- Old task
"""


def _write_lifecycle_memory_bank_files(memory_bank_dir: Path) -> None:
    """Disk content for compact_session + session_start handoff integration."""
    _ = (memory_bank_dir / "activeContext.md").write_text(_LIFECYCLE_ACTIVE)
    _ = (memory_bank_dir / "progress.md").write_text(
        "# Progress\n\n## 2026-02-21\n\n- Entry\n"
    )
    _ = (memory_bank_dir / "roadmap.md").write_text(
        "# Roadmap\n\n## Pending\n\n- Item\n"
    )
    _ = (memory_bank_dir / "projectBrief.md").write_text("# Cortex\n")
    for f in ["systemPatterns.md", "techContext.md", "productContext.md"]:
        _ = (memory_bank_dir / f).write_text(f"# {f}\n")


async def _build_lifecycle_managers_for_compact(tmp_path: Path) -> ManagersDict:
    """Managers with version index after seeding lifecycle memory-bank files."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_lifecycle_memory_bank_files(memory_bank_dir)
    fs_manager = FileSystemManager(tmp_path)
    token_counter = TokenCounter()
    metadata_index = MetadataIndex(tmp_path)
    _ = await metadata_index.load()
    version_manager = VersionManager(tmp_path)
    await _seed_basic_metadata(memory_bank_dir, metadata_index)
    return make_test_managers(
        fs=fs_manager,
        tokens=token_counter,
        index=metadata_index,
        versions=version_manager,
    )


async def managers_after_compact_lifecycle(tmp_path: Path) -> ManagersDict:
    """Run compact_session then return managers (integration handoff visibility)."""
    managers = await _build_lifecycle_managers_for_compact(tmp_path)
    with (
        patch(
            "cortex.tools.compaction_operations.get_current_managers",
            return_value=managers,
        ),
        patch(
            "cortex.tools.compaction_operations.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
    ):
        tool_fn = get_tool_fn(compact_session)
        _ = await tool_fn(summary="Lifecycle integration test", ctx=None)
    return managers


async def managers_for_phase54_session_start(tmp_path: Path) -> ManagersDict:
    """Full memory-bank + metadata setup for Phase 54 session_start success tests."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _ = (memory_bank_dir / "activeContext.md").write_text(ACTIVE_CONTEXT_PHASE54_FULL)
    _ = (memory_bank_dir / "roadmap.md").write_text(ROADMAP_PHASE54_PENDING)
    _ = (memory_bank_dir / "projectBrief.md").write_text(
        "# Cortex\n\nProject description."
    )
    for file_name in (
        "progress.md",
        "systemPatterns.md",
        "techContext.md",
        "productContext.md",
    ):
        _ = (memory_bank_dir / file_name).write_text(f"# {file_name}\n\nContent")
    fs_manager = FileSystemManager(tmp_path)
    metadata_index = MetadataIndex(tmp_path)
    _ = await metadata_index.load()
    await _seed_basic_metadata(memory_bank_dir, metadata_index)
    return make_test_managers(
        fs=fs_manager, index=metadata_index, tokens=TokenCounter()
    )


def assert_phase54_success_brief(result: SessionStartResult) -> None:
    assert isinstance(result, SessionStartResult)
    assert result.status == "success"
    assert result.brief is not None
    assert result.brief.project_name == "Cortex"
    assert "Phase 54" in result.brief.current_focus
    assert len(result.brief.recent_completed) == 2
    assert result.brief.next_work_item is not None
    assert "Phase 54" in result.brief.next_work_item
    assert result.token_count > 0
    assert result.brief.mcp_healthy is True
    assert result.brief.session_scope
    assert result.brief.session_scope == SESSION_SCOPE_PROMPT
    assert "Session Scope" in result.brief.session_scope
    assert "Defer unrelated issues to a follow-up session" in result.brief.session_scope
    assert result.brief.workflow_schema == "default"
    assert result.brief.workflow_schema_description
    assert any("plan:" in p for p in result.brief.workflow_phases)


async def managers_phase54_variant(
    tmp_path: Path,
    *,
    active_context: str,
    roadmap: str,
    extra_content: str = "\n\nContent",
) -> tuple[Path, ManagersDict]:
    """Memory bank + managers for Phase 54 variants (handoff / missing handoff)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _ = (memory_bank_dir / "activeContext.md").write_text(active_context)
    _ = (memory_bank_dir / "roadmap.md").write_text(roadmap)
    _ = (memory_bank_dir / "projectBrief.md").write_text(
        "# Cortex\n\nProject description."
    )
    for file_name in (
        "progress.md",
        "systemPatterns.md",
        "techContext.md",
        "productContext.md",
    ):
        _ = (memory_bank_dir / file_name).write_text(f"# {file_name}{extra_content}")
    fs_manager = FileSystemManager(tmp_path)
    metadata_index = MetadataIndex(tmp_path)
    _ = await metadata_index.load()
    token_counter = TokenCounter()
    await _seed_basic_metadata(memory_bank_dir, metadata_index)
    managers = make_test_managers(
        fs=fs_manager, index=metadata_index, tokens=token_counter
    )
    return memory_bank_dir, managers


async def run_session_start_patched_mcp_healthy(
    tmp_path: Path, managers: ManagersDict
) -> SessionStartResult | SessionStartErrorResult:
    with patch(
        "cortex.tools.session.health.get_mcp_health_status",
        new_callable=AsyncMock,
        return_value=(True, None),
    ):
        return await session_start_impl(
            None,
            tmp_path,
            managers,  # type: ignore[arg-type]
        )
