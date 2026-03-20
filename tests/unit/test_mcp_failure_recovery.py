"""Unit tests for MCP tool failure recovery (mcp_failure_recovery module).

Tests create_investigation_plan, add_to_roadmap, and plan content/deduplication
using tmp_path, calling the recovery module directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.core.constants import MemoryBankFile
from cortex.core.mcp_failure_recovery import (
    add_to_roadmap,
    create_investigation_plan,
    generate_plan_content,
    generate_user_notification,
)
from cortex.core.path_resolver import CortexResourceType, get_cortex_path


@pytest.fixture
def plans_dir(tmp_path: Path) -> Path:
    """Plans directory under tmp_path."""
    path = tmp_path / ".cortex" / "plans"
    path.mkdir(parents=True)
    return path


@pytest.fixture
def memory_bank_with_roadmap(tmp_path: Path) -> Path:
    """Memory bank dir with existing roadmap."""
    memory_bank = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    memory_bank.mkdir(parents=True)
    roadmap = memory_bank / MemoryBankFile.ROADMAP
    _ = roadmap.write_text(
        "# Roadmap\n\n## Blockers (ASAP Priority)\n\n", encoding="utf-8"
    )
    return tmp_path


class TestGeneratePlanContent:
    """Tests for generate_plan_content."""

    def test_includes_tool_step_and_error(self) -> None:
        error = json.JSONDecodeError("Expecting value", "", 0)
        content = generate_plan_content("my_tool", error, "phase_a")
        assert "my_tool" in content
        assert "phase_a" in content
        assert "JSONDecodeError" in content
        assert "ASAP (Blocker)" in content

    def test_includes_cause_when_present(self) -> None:
        inner = ValueError("inner")
        error = json.JSONDecodeError("outer", "", 0)
        error.__cause__ = inner
        content = generate_plan_content("t", error, "s")
        assert "Caused by" in content
        assert "ValueError" in content
        assert "inner" in content


class TestCreateInvestigationPlan:
    """Tests for create_investigation_plan (recovery module)."""

    @pytest.mark.asyncio
    async def test_creates_file_under_plans_dir(
        self, tmp_path: Path, plans_dir: Path
    ) -> None:
        error = json.JSONDecodeError("Expecting value", "", 0)
        plan_path = await create_investigation_plan(
            plans_dir, tmp_path, "test_tool", error, "test_step", ctx=None
        )
        assert plan_path.exists()
        assert plan_path.parent == plans_dir
        assert plan_path.name.startswith("phase-investigate-test_tool-failure-")
        assert plan_path.suffix == ".md"

    @pytest.mark.asyncio
    async def test_plan_content_matches_template(
        self, tmp_path: Path, plans_dir: Path
    ) -> None:
        error = ConnectionError("Connection closed")
        plan_path = await create_investigation_plan(
            plans_dir, tmp_path, "tool", error, "step", ctx=None
        )
        content = plan_path.read_text(encoding="utf-8")
        assert "## Goal" in content
        assert "## Context" in content
        assert "tool" in content
        assert "step" in content
        assert "ConnectionError" in content

    @pytest.mark.asyncio
    async def test_unsafe_tool_name_sanitized_plan_under_plans_dir(
        self, tmp_path: Path, plans_dir: Path
    ) -> None:
        """Tool names with path or special chars are sanitized; plan stays under plans_dir."""
        error = ValueError("test")
        plan_path = await create_investigation_plan(
            plans_dir,
            tmp_path,
            "server/../evil",
            error,
            "step",
            ctx=None,
        )
        assert plan_path.exists()
        assert plan_path.parent == plans_dir
        assert plan_path.parent.resolve() == plans_dir.resolve()
        assert ".." not in plan_path.name
        assert plan_path.name.startswith("phase-investigate-")
        assert plan_path.name.endswith(".md")


class TestAddToRoadmap:
    """Tests for add_to_roadmap (recovery module)."""

    @pytest.mark.asyncio
    async def test_adds_entry_to_roadmap(
        self, memory_bank_with_roadmap: Path, plans_dir: Path
    ) -> None:
        project_root = memory_bank_with_roadmap
        roadmap_path = (
            get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
            / MemoryBankFile.ROADMAP
        )
        error = json.JSONDecodeError("Expecting value", "", 0)
        plan_path = await create_investigation_plan(
            plans_dir, project_root, "test_tool", error, "step", ctx=None
        )
        await add_to_roadmap(project_root, plan_path, "test_tool", error, ctx=None)

        content = roadmap_path.read_text(encoding="utf-8")
        assert "test_tool" in content
        assert "ASAP (PLANNING)" in content
        rel = plan_path.relative_to(project_root)
        assert str(rel) in content

    @pytest.mark.asyncio
    async def test_deduplicates_same_plan_entry(
        self, memory_bank_with_roadmap: Path, plans_dir: Path
    ) -> None:
        project_root = memory_bank_with_roadmap
        roadmap_path = (
            get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
            / MemoryBankFile.ROADMAP
        )
        error = json.JSONDecodeError("Expecting value", "", 0)
        plan_path = await create_investigation_plan(
            plans_dir, project_root, "tool", error, "step", ctx=None
        )
        await add_to_roadmap(project_root, plan_path, "tool", error, ctx=None)
        await add_to_roadmap(project_root, plan_path, "tool", error, ctx=None)

        content = roadmap_path.read_text(encoding="utf-8")
        rel = plan_path.relative_to(project_root)
        assert content.count(str(rel)) == 1

    @pytest.mark.asyncio
    async def test_creates_blockers_section_if_missing(
        self, tmp_path: Path, plans_dir: Path
    ) -> None:
        memory_bank = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank.mkdir(parents=True)
        roadmap = memory_bank / MemoryBankFile.ROADMAP
        _ = roadmap.write_text("# Roadmap\n\nSome content\n", encoding="utf-8")

        error = json.JSONDecodeError("Expecting value", "", 0)
        plan_path = await create_investigation_plan(
            plans_dir, tmp_path, "tool", error, "step", ctx=None
        )
        await add_to_roadmap(tmp_path, plan_path, "tool", error, ctx=None)

        content = roadmap.read_text(encoding="utf-8")
        assert "## Blockers (ASAP Priority)" in content

    @pytest.mark.asyncio
    async def test_no_roadmap_file_does_not_raise(
        self, tmp_path: Path, plans_dir: Path
    ) -> None:
        # No memory-bank/roadmap.md
        error = json.JSONDecodeError("Expecting value", "", 0)
        plan_path = await create_investigation_plan(
            plans_dir, tmp_path, "tool", error, "step", ctx=None
        )
        await add_to_roadmap(tmp_path, plan_path, "tool", error, ctx=None)
        # Should complete without raising; logs warning


class TestGenerateUserNotification:
    """Tests for generate_user_notification."""

    def test_includes_tool_step_and_error_details(self, tmp_path: Path) -> None:
        error = json.JSONDecodeError("Expecting value", "", 0)
        plan_path = tmp_path / ".cortex" / "plans" / "investigate.md"
        notification = generate_user_notification(
            "my_tool", error, "phase_a", plan_path, tmp_path
        )
        assert "my_tool" in notification
        assert "phase_a" in notification
        assert "JSONDecodeError" in notification
        assert "Expecting value" in notification

    def test_includes_relative_plan_path(self, tmp_path: Path) -> None:
        error = ValueError("test error")
        plan_path = tmp_path / ".cortex" / "plans" / "plan.md"
        notification = generate_user_notification(
            "tool", error, "step", plan_path, tmp_path
        )
        assert ".cortex/plans/plan.md" in notification

    def test_includes_protocol_stop_message(self, tmp_path: Path) -> None:
        error = ConnectionError("closed")
        plan_path = tmp_path / "plan.md"
        notification = generate_user_notification("t", error, "s", plan_path, tmp_path)
        assert "Commit procedure stopped immediately" in notification
        assert "No workarounds or fallbacks allowed" in notification

    def test_includes_fix_recommendation(self, tmp_path: Path) -> None:
        error = RuntimeError("test")
        plan_path = tmp_path / "plan.md"
        notification = generate_user_notification(
            "tool", error, "step", plan_path, tmp_path
        )
        assert "FIX-ASAP" in notification
