"""register_plan_in_roadmap task graph and artifact-graph validation tests."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.constants import MemoryBankFile
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.models_base import ToolResultStatus
from cortex.tools.plans.operations import RegisterPlanResult, register_plan_in_roadmap


class TestRegisterPlanTaskGraphValidation:
    """register_plan_in_roadmap validates parse_task_graph when plan path is known."""

    @staticmethod
    def _minimal_roadmap() -> str:
        return (
            "# Roadmap: MCP Memory Bank\n\n"
            "## Blockers (ASAP Priority)\n\n"
            "## Active Work (in progress)\n\n"
            "## Future Enhancements\n\n"
            "## Pending plans (from .cortex/plans)\n\n"
            "- **Existing** - PENDING - Existing entry.\n"
        )

    def _init_register_workspace(self, tmp_path: Path) -> Path:
        memory_bank = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        plans_dir = get_cortex_path(tmp_path, CortexResourceType.PLANS)
        memory_bank.mkdir(parents=True)
        plans_dir.mkdir(parents=True)
        roadmap_path = memory_bank / MemoryBankFile.ROADMAP
        _ = roadmap_path.write_text(self._minimal_roadmap(), encoding="utf-8")
        return plans_dir

    async def _register_plan_patched(
        self, tmp_path: Path, *, plan_title: str, plan_relative_path: str
    ) -> RegisterPlanResult:
        with patch(
            "cortex.tools.plans.register.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            raw = await register_plan_in_roadmap(
                plan_title=plan_title,
                description="Desc.",
                status="PENDING",
                section="pending",
                plan_relative_path=plan_relative_path,
                ctx=None,
            )
        return RegisterPlanResult.model_validate_json(raw)

    @pytest.mark.asyncio
    async def test_register_rejects_cyclic_plan_file(self, tmp_path: Path) -> None:
        """Cyclic [P:after=] dependencies block registration."""
        plans_dir = self._init_register_workspace(tmp_path)
        cyclic = "### [P:after=2] Step 1: A\n\n" + "### [P:after=1] Step 2: B\n\n"
        _ = (plans_dir / "bad-cycle.md").write_text(cyclic, encoding="utf-8")
        result = await self._register_plan_patched(
            tmp_path,
            plan_title="Bad Cycle",
            plan_relative_path=".cortex/plans/bad-cycle.md",
        )
        assert result.status == ToolResultStatus.ERROR
        assert result.error is not None
        assert "cyclic" in result.error.lower()

    @pytest.mark.asyncio
    async def test_register_returns_step_counts_when_valid(
        self, tmp_path: Path
    ) -> None:
        """Successful registration includes parallel/sequential counts."""
        plans_dir = self._init_register_workspace(tmp_path)
        plan_body = "### [P] Step 1: A\n\nx\n\n### Step 2: B\n\ny\n"
        _ = (plans_dir / "good.md").write_text(plan_body, encoding="utf-8")
        result = await self._register_plan_patched(
            tmp_path,
            plan_title="Good Plan",
            plan_relative_path=".cortex/plans/good.md",
        )
        assert result.status == ToolResultStatus.SUCCESS
        assert result.parallel_steps_count == 1
        assert result.sequential_steps_count == 1

    @pytest.mark.asyncio
    async def test_register_rejects_plan_dependency_cycle_in_yaml(
        self, tmp_path: Path
    ) -> None:
        """Cyclic depends_on between plan files blocks registration."""
        plans_dir = self._init_register_workspace(tmp_path)
        a = (
            "---\ntitle: a\nstatus: PENDING\ndepends_on: [dep-b]\n---\n\n"
            "### Step 1\n\nx\n"
        )
        b = (
            "---\ntitle: b\nstatus: PENDING\ndepends_on: [dep-a]\n---\n\n"
            "### Step 1\n\ny\n"
        )
        _ = (plans_dir / "dep-a.md").write_text(a, encoding="utf-8")
        _ = (plans_dir / "dep-b.md").write_text(b, encoding="utf-8")
        result = await self._register_plan_patched(
            tmp_path,
            plan_title="Dep A",
            plan_relative_path=".cortex/plans/dep-a.md",
        )
        assert result.status == ToolResultStatus.ERROR
        assert result.error is not None
        assert "cycle" in result.error.lower()

    @pytest.mark.asyncio
    async def test_register_writes_blocked_frontmatter_when_dep_pending(
        self, tmp_path: Path
    ) -> None:
        """After successful register, plan YAML status becomes BLOCKED when a dep is not DONE."""
        plans_dir = self._init_register_workspace(tmp_path)
        base = (
            "---\ntitle: base\nstatus: PENDING\ndepends_on: []\n---\n\n"
            "### Step 1\n\nx\n"
        )
        leaf = (
            "---\ntitle: leaf\nstatus: PENDING\ndepends_on: [base]\n---\n\n"
            "### Step 1\n\ny\n"
        )
        _ = (plans_dir / "base.md").write_text(base, encoding="utf-8")
        leaf_path = plans_dir / "leaf.md"
        _ = leaf_path.write_text(leaf, encoding="utf-8")
        result = await self._register_plan_patched(
            tmp_path,
            plan_title="Leaf",
            plan_relative_path=".cortex/plans/leaf.md",
        )
        assert result.status == ToolResultStatus.SUCCESS
        updated = leaf_path.read_text(encoding="utf-8")
        assert "status: BLOCKED" in updated

    @pytest.mark.asyncio
    async def test_register_keeps_pending_frontmatter_when_dep_done(
        self, tmp_path: Path
    ) -> None:
        """When all declared dependencies are DONE, plan frontmatter stays PENDING."""
        plans_dir = self._init_register_workspace(tmp_path)
        base = (
            "---\ntitle: base\nstatus: DONE\ndepends_on: []\n---\n\n"
            "### Step 1\n\nx\n"
        )
        leaf = (
            "---\ntitle: leaf\nstatus: PENDING\ndepends_on: [base]\n---\n\n"
            "### Step 1\n\ny\n"
        )
        _ = (plans_dir / "base.md").write_text(base, encoding="utf-8")
        leaf_path = plans_dir / "leaf.md"
        _ = leaf_path.write_text(leaf, encoding="utf-8")
        result = await self._register_plan_patched(
            tmp_path,
            plan_title="Leaf",
            plan_relative_path=".cortex/plans/leaf.md",
        )
        assert result.status == ToolResultStatus.SUCCESS
        updated = leaf_path.read_text(encoding="utf-8")
        assert "status: PENDING" in updated
