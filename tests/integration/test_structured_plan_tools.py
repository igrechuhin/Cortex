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


async def _create_then_register_in_temp(
    root: Path, *, title: str, slug: str, content: str, description: str
) -> tuple[CreatePlanResult, RegisterPlanResult]:
    cr = patch(
        "cortex.tools.plans.crud.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=root,
    )
    rg = patch(
        "cortex.tools.plans.register.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=root,
    )
    with cr, rg:
        cs = await create_plan(title=title, content=content, slug=slug, ctx=None)
        cr_out = CreatePlanResult.model_validate_json(cs)
        rs = await register_plan_in_roadmap(
            plan_title=title,
            description=description,
            status="PENDING",
            section="pending",
            ctx=None,
        )
        rr = RegisterPlanResult.model_validate_json(rs)
    return cr_out, rr


async def _register_pending_new_plan(root: Path) -> RegisterPlanResult:
    with patch(
        "cortex.tools.plans.register.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=root,
    ):
        raw = await register_plan_in_roadmap(
            plan_title="New Plan",
            description="Reference. Plan: .cortex/plans/new-plan.md.",
            status="PENDING",
            section="pending",
            ctx=None,
        )
    return RegisterPlanResult.model_validate_json(raw)


async def _register_plan_with_marker(
    root: Path,
    *,
    plan_name: str,
    marker: str,
    title: str,
    status: str,
) -> str:
    plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
    _ = (plans_dir / plan_name).write_text(marker, encoding="utf-8")
    with patch(
        "cortex.tools.plans.register.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=root,
    ):
        return await register_plan_in_roadmap(
            plan_title=title,
            description="Needs details.",
            status=status,
            section="pending",
            plan_relative_path=f".cortex/plans/{plan_name}",
            ctx=None,
        )


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
        written = plan_path.read_text(encoding="utf-8")
        assert written.startswith(content.rstrip())
        assert "## Change History" in written

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
        written = plan_path.read_text(encoding="utf-8")
        assert written.startswith(content.rstrip())
        assert "## Change History" in written

    @pytest.mark.asyncio
    async def test_create_plan_injects_clarifications_needed_section(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """Plans with NEEDS CLARIFICATION markers get an auto summary section."""
        root = temp_project_with_roadmap
        plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
        content = (
            "## Goal\n\nDo [NEEDS CLARIFICATION: pick color].\n\n"
            "## Context\n\nNotes.\n"
        )
        with patch(
            "cortex.tools.plans.crud.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=root,
        ):
            result_str = await create_plan(
                title="Clarifications Plan",
                content=content,
                slug="clarifications-plan",
                ctx=None,
            )
        result = CreatePlanResult.model_validate_json(result_str)
        assert result.status == "success" and result.file_path is not None
        plan_path = Path(result.file_path)
        assert plan_path.parent == plans_dir
        written = plan_path.read_text(encoding="utf-8")
        assert "## Clarifications Needed" in written and written.index(
            "## Clarifications Needed"
        ) < written.index("## Context")
        assert "pick color" in written and "Summary of inline" in written


class TestRegisterPlanInRoadmapIntegration:
    """Integration tests for register_plan_in_roadmap tool."""

    @pytest.mark.asyncio
    async def test_register_plan_in_roadmap_adds_entry_preserves_rest(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """register_plan_in_roadmap adds new entry; existing content unchanged."""
        root = temp_project_with_roadmap
        rp = (
            get_cortex_path(root, CortexResourceType.MEMORY_BANK)
            / MemoryBankFile.ROADMAP
        )
        r = await _register_pending_new_plan(root)
        assert (
            r.status == "success"
            and r.file_name == MemoryBankFile.ROADMAP
            and r.line_inserted is not None
            and r.section == "pending"
            and r.error is None
        )
        nc = rp.read_text(encoding="utf-8")
        want = "- **New Plan** - PENDING - Reference. Plan: .cortex/plans/new-plan.md."
        assert want in nc and "- **Existing** - PENDING - Existing entry." in nc
        assert (
            "Blockers (ASAP Priority)" in nc
            and "Pending plans (from .cortex/plans)" in nc
        )

    @pytest.mark.asyncio
    async def test_register_plan_in_roadmap_appends_plan_path_when_provided(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """When plan_relative_path is provided, tool appends canonical `Plan:` path."""
        root = temp_project_with_roadmap
        memory_bank = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
        roadmap_path = memory_bank / MemoryBankFile.ROADMAP

        with patch(
            "cortex.tools.plans.register.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=root,
        ):
            result_str = await register_plan_in_roadmap(
                plan_title="Auto Path Plan",
                description="Reference.",
                status="PENDING",
                section="pending",
                plan_relative_path=".cortex/plans/auto-path-plan.md",
                ctx=None,
            )

        result = RegisterPlanResult.model_validate_json(result_str)
        assert result.status == "success"

        new_content = roadmap_path.read_text(encoding="utf-8")
        assert (
            "- **Auto Path Plan** - PENDING - Reference. Plan: .cortex/plans/auto-path-plan.md"
            in new_content
        )

    @pytest.mark.asyncio
    async def test_register_plan_in_roadmap_prefers_relative_path_over_file_name(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """When both fields are set, canonical relative path takes precedence."""
        root = temp_project_with_roadmap
        memory_bank = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
        roadmap_path = memory_bank / MemoryBankFile.ROADMAP

        with patch(
            "cortex.tools.plans.register.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=root,
        ):
            result_str = await register_plan_in_roadmap(
                plan_title="Preferred Path Plan",
                description="Reference.",
                status="PENDING",
                section="pending",
                plan_file_name="legacy-fallback.md",
                plan_relative_path=".cortex/plans/preferred-path-plan.md",
                ctx=None,
            )

        result = RegisterPlanResult.model_validate_json(result_str)
        assert result.status == "success"

        new_content = roadmap_path.read_text(encoding="utf-8")
        assert "Plan: .cortex/plans/preferred-path-plan.md" in new_content
        assert "Plan: .cortex/plans/legacy-fallback.md" not in new_content

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

    @pytest.mark.asyncio
    async def test_register_plan_sets_blocked_when_blocking_markers_exist(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """Blocking markers force BLOCKED status and append blocking note."""
        root = temp_project_with_roadmap
        result_str = await _register_plan_with_marker(
            root,
            plan_name="gated-plan.md",
            marker="## Goal\n\nUse [NEEDS CLARIFICATION(blocking): auth flow].\n",
            title="Gated Plan",
            status="PENDING",
        )
        result = RegisterPlanResult.model_validate_json(result_str)
        assert result.status == "success"
        roadmap_path = (
            get_cortex_path(root, CortexResourceType.MEMORY_BANK)
            / MemoryBankFile.ROADMAP
        )
        roadmap = roadmap_path.read_text(encoding="utf-8")
        assert "- **Gated Plan** - BLOCKED -" in roadmap
        assert "Blocked: 1 clarifications required before implementation." in roadmap

    @pytest.mark.asyncio
    async def test_register_plan_keeps_pending_for_non_blocking_markers(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """Non-blocking markers keep PENDING status and append pending note."""
        root = temp_project_with_roadmap
        result_str = await _register_plan_with_marker(
            root,
            plan_name="pending-plan.md",
            marker="## Goal\n\nUse [NEEDS CLARIFICATION: naming].\n",
            title="Pending Clarification Plan",
            status="IN PROGRESS",
        )
        result = RegisterPlanResult.model_validate_json(result_str)
        assert result.status == "success"
        roadmap_path = (
            get_cortex_path(root, CortexResourceType.MEMORY_BANK)
            / MemoryBankFile.ROADMAP
        )
        roadmap = roadmap_path.read_text(encoding="utf-8")
        assert "- **Pending Clarification Plan** - PENDING -" in roadmap
        assert "1 clarifications pending (non-blocking)." in roadmap


class TestCreatePlanThenRegisterIntegration:
    """Simulated plan sequence: create_plan then register_plan_in_roadmap."""

    @pytest.mark.asyncio
    async def test_create_plan_then_register_plan_in_roadmap(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """Full sequence: create plan file then register in roadmap; both succeed."""
        root = temp_project_with_roadmap
        plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
        roadmap_path = (
            get_cortex_path(root, CortexResourceType.MEMORY_BANK)
            / MemoryBankFile.ROADMAP
        )
        title = "Structured planning Cortex MCP tools"
        slug = "structured-planning-cortex-mcp-tools"
        content = (
            "# Structured Plan Creation via Cortex MCP Tools\n\n**Status**: Pending\n\n"
            "## Goal\nReplace manual plan creation with tool-driven flow.\n"
        )
        description = (
            "Reference. Plan: .cortex/plans/structured-planning-cortex-mcp-tools.md."
        )
        create_result, register_result = await _create_then_register_in_temp(
            root, title=title, slug=slug, content=content, description=description
        )
        assert create_result.status == "success" and create_result.file_path
        assert register_result.status == "success"
        plan_file = plans_dir / f"{slug}.md"
        assert plan_file.exists()
        written = plan_file.read_text(encoding="utf-8")
        assert written.startswith(content.rstrip())
        assert "## Change History" in written
        roadmap_content = roadmap_path.read_text(encoding="utf-8")
        assert f"- **{title}** - PENDING - {description}" in roadmap_content
        assert "- **Existing** - PENDING - Existing entry." in roadmap_content
