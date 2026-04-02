"""
Integration tests for structured plan tools (create_plan, register_plan_in_roadmap).

Verifies end-to-end behavior with a temporary project root: plan file creation
and roadmap registration without mutating the real repository.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.constants import MemoryBankFile
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.operations import (
    CreatePlanResult,
    RegisterPlanResult,
    create_plan,
    register_plan_in_roadmap,
)


def _minimal_roadmap_content() -> str:
    """Minimal roadmap with required section headers for parsing."""
    return (
        "# Roadmap: MCP Memory Bank\n\n"
        "## Blockers (ASAP Priority)\n\n"
        "## Active Work (in progress)\n\n"
        "## Future Enhancements\n\n"
        "## Pending plans (from .cortex/plans)\n\n"
        "- **Existing** - PENDING - Existing entry.\n"
    )


@pytest.fixture
def temp_project_with_roadmap(tmp_path: Path) -> Path:
    """Create a temp project root with .cortex/plans and .cortex/memory-bank/roadmap.md."""
    memory_bank = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    plans_dir = get_cortex_path(tmp_path, CortexResourceType.PLANS)

    memory_bank.mkdir(parents=True)
    plans_dir.mkdir(parents=True)

    roadmap_path = memory_bank / MemoryBankFile.ROADMAP
    _ = roadmap_path.write_text(_minimal_roadmap_content(), encoding="utf-8")

    return tmp_path


class TestCreatePlanIntegration:
    """Integration tests for create_plan tool."""

    @pytest.mark.asyncio
    async def test_create_plan_creates_file_under_plans_dir(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """Call create_plan with minimal content; assert file exists under plans dir."""
        root = temp_project_with_roadmap
        plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
        content = "# Test Plan\n\n**Status**: Pending\n\n## Goal\nTest.\n"

        with patch(
            "cortex.tools.plans.crud.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=root,
        ):
            result_str = await create_plan(
                title="Test Plan",
                content=content,
                slug="test-plan-integration",
                ctx=None,
            )

        result = CreatePlanResult.model_validate_json(result_str)
        assert result.status == "success"
        assert result.file_path is not None
        assert result.error is None

        plan_path = Path(result.file_path)
        assert plan_path.parent == plans_dir
        assert plan_path.name == "test-plan-integration.md"
        assert plan_path.read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_create_plan_with_generated_slug(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """create_plan without slug generates filename from title."""
        root = temp_project_with_roadmap
        content = "# Phase 60 Feature\n\nContent."

        with patch(
            "cortex.tools.plans.crud.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=root,
        ):
            result_str = await create_plan(
                title="Phase 60: Structured plan tools",
                content=content,
                slug=None,
                ctx=None,
            )

        result = CreatePlanResult.model_validate_json(result_str)
        assert result.status == "success"
        assert result.file_path is not None
        plan_path = Path(result.file_path)
        assert "phase-60-structured-plan-tools" in plan_path.name
        assert plan_path.read_text(encoding="utf-8") == content


class TestRegisterPlanInRoadmapIntegration:
    """Integration tests for register_plan_in_roadmap tool."""

    @pytest.mark.asyncio
    async def test_register_plan_in_roadmap_adds_entry_preserves_rest(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """register_plan_in_roadmap adds new entry; existing content unchanged."""
        root = temp_project_with_roadmap
        memory_bank = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
        roadmap_path = memory_bank / MemoryBankFile.ROADMAP

        with patch(
            "cortex.tools.plans.register.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=root,
        ):
            result_str = await register_plan_in_roadmap(
                plan_title="New Plan",
                description="Reference. Plan: .cortex/plans/new-plan.md.",
                status="PENDING",
                section="pending",
                ctx=None,
            )

        result = RegisterPlanResult.model_validate_json(result_str)
        assert result.status == "success"
        assert result.file_name == MemoryBankFile.ROADMAP
        assert result.line_inserted is not None
        assert result.section == "pending"
        assert result.error is None

        new_content = roadmap_path.read_text(encoding="utf-8")
        assert (
            "- **New Plan** - PENDING - Reference. Plan: .cortex/plans/new-plan.md."
            in new_content
        )
        assert "- **Existing** - PENDING - Existing entry." in new_content
        assert "Blockers (ASAP Priority)" in new_content
        assert "Pending plans (from .cortex/plans)" in new_content

    @pytest.mark.asyncio
    async def test_register_plan_in_blockers_section(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """register_plan_in_roadmap can add entry to blockers section."""
        root = temp_project_with_roadmap

        with patch(
            "cortex.tools.plans.register.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=root,
        ):
            result_str = await register_plan_in_roadmap(
                plan_title="Blocker Plan",
                description="Blocks release.",
                status="PENDING",
                section="blockers",
                ctx=None,
            )

        result = RegisterPlanResult.model_validate_json(result_str)
        assert result.status == "success"
        assert result.section == "blockers"

        memory_bank = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
        roadmap_path = memory_bank / MemoryBankFile.ROADMAP
        content = roadmap_path.read_text(encoding="utf-8")
        assert "- **Blocker Plan** - PENDING - Blocks release." in content


class TestCreatePlanThenRegisterIntegration:
    """Simulated plan sequence: create_plan then register_plan_in_roadmap."""

    @pytest.mark.asyncio
    async def test_create_plan_then_register_plan_in_roadmap(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """Full sequence: create plan file then register in roadmap; both succeed."""
        root = temp_project_with_roadmap
        plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
        memory_bank = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
        roadmap_path = memory_bank / MemoryBankFile.ROADMAP

        title = "Structured planning Cortex MCP tools"
        slug = "structured-planning-cortex-mcp-tools"
        content = "# Structured Plan Creation via Cortex MCP Tools\n\n**Status**: Pending\n\n## Goal\nReplace manual plan creation with tool-driven flow.\n"
        description = (
            "Reference. Plan: .cortex/plans/structured-planning-cortex-mcp-tools.md."
        )

        with (
            patch(
                "cortex.tools.plans.crud.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=root,
            ),
            patch(
                "cortex.tools.plans.register.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=root,
            ),
        ):
            create_result_str = await create_plan(
                title=title,
                content=content,
                slug=slug,
                ctx=None,
            )
            create_result = CreatePlanResult.model_validate_json(create_result_str)
            assert create_result.status == "success"
            assert create_result.file_path is not None

            register_result_str = await register_plan_in_roadmap(
                plan_title=title,
                description=description,
                status="PENDING",
                section="pending",
                ctx=None,
            )
            register_result = RegisterPlanResult.model_validate_json(
                register_result_str
            )
            assert register_result.status == "success"

        plan_file = plans_dir / f"{slug}.md"
        assert plan_file.exists()
        assert plan_file.read_text(encoding="utf-8") == content

        roadmap_content = roadmap_path.read_text(encoding="utf-8")
        assert f"- **{title}** - PENDING - {description}" in roadmap_content
        assert "- **Existing** - PENDING - Existing entry." in roadmap_content
