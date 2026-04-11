"""
Integration tests for structured plan tools (create_plan, register_plan_in_roadmap).

Verifies end-to-end behavior with a temporary project root: plan file creation
and roadmap registration without mutating the real repository.
"""

import json
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.constants import MemoryBankFile
from cortex.core.parallel_worktree_merge import (
    clarification_markers_for_shared_paths,
    merge_order_for_parallel_batch,
)
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_change_history import (
    CHANGE_HISTORY_HEADING,
    change_history_stats,
)
from cortex.core.plan_utils import (
    next_execution_frontier,
    parse_task_graph,
)
from cortex.tools.plans.completion import complete_plan
from cortex.tools.plans.enrich import enrich_plan
from cortex.tools.plans.enrich_models import EnrichPlanResult
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


def _depends_on_integration_plan_bodies() -> tuple[str, str]:
    foundation = (
        "---\n"
        "title: foundation\n"
        "status: PENDING\n"
        "depends_on: []\n"
        "---\n\n"
        "### Step 1\n\nx\n"
    )
    leaf = (
        "---\n"
        "title: leaf\n"
        "status: PENDING\n"
        "depends_on: [foundation]\n"
        "---\n\n"
        "### Step 1\n\ny\n"
    )
    return foundation, leaf


async def _register_foundation_and_leaf_plans(root: Path) -> None:
    with patch(
        "cortex.tools.plans.register.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=root,
    ):
        for title, rel, desc in (
            ("Foundation", ".cortex/plans/foundation.md", "Base."),
            ("Leaf", ".cortex/plans/leaf.md", "Follower."),
        ):
            raw = await register_plan_in_roadmap(
                plan_title=title,
                description=desc,
                status="PENDING",
                section="pending",
                plan_relative_path=rel,
                ctx=None,
            )
            assert RegisterPlanResult.model_validate_json(raw).status == "success"


@contextmanager
def _patch_roots_for_complete_plan(root: Path):
    with ExitStack() as stack:
        for mod in (
            "cortex.tools.plans.completion.resolve_project_root_async",
            "cortex.tools.plans.operations_log_hooks.resolve_project_root_async",
            "cortex.tools.plans.crud.resolve_project_root_async",
        ):
            _ = stack.enter_context(
                patch(mod, new_callable=AsyncMock, return_value=root)
            )
        yield


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


async def _enrich_plan_with_root_patched(
    root: Path,
    *,
    plan_relative_path: str,
    resolved_clarifications: dict[str, str],
) -> str:
    """Invoke ``enrich_plan`` with ``resolve_project_root_async`` returning ``root``."""
    with patch(
        "cortex.tools.plans.enrich.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=root,
    ):
        return await enrich_plan(
            plan_relative_path=plan_relative_path,
            resolved_clarifications=resolved_clarifications,
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

    @pytest.mark.asyncio
    async def test_create_plan_applies_parallel_markers_disjoint_steps(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """Disjoint ``src/`` footprints get ``[P]`` on later steps (plan create path)."""
        root = temp_project_with_roadmap
        content = (
            "## Goal\n\nWork.\n\n"
            "## Implementation Steps\n\n"
            "### Step 1: First\n\n"
            "Edit `src/a/one.py`.\n\n"
            "### Step 2: Second\n\n"
            "Edit `src/b/two.py`.\n"
        )
        with patch(
            "cortex.tools.plans.crud.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=root,
        ):
            result_str = await create_plan(
                title="Parallel markers plan",
                content=content,
                slug="parallel-markers-create",
                ctx=None,
            )
        result = CreatePlanResult.model_validate_json(result_str)
        assert result.status == "success" and result.file_path is not None
        written = Path(result.file_path).read_text(encoding="utf-8")
        assert "### Step 1: First" in written
        assert "### [P] Step 2: Second" in written
        assert written.index("### Step 1:") < written.index("### [P] Step 2:")


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


class TestEnrichPlanDeltaIntegration:
    """Integration tests for enrich_plan delta tracking (delta-specs feature).

    Delta entries are appended when ``resolved_clarifications`` actually change
    implementation-step text.  Tests use ``[NEEDS CLARIFICATION: ...]`` markers
    inside step bodies so that resolving them produces a real text diff.
    """

    def _make_plan_file(self, plans_dir: Path, slug: str, content: str) -> Path:
        plans_dir.mkdir(parents=True, exist_ok=True)
        path = plans_dir / f"{slug}.md"
        _ = path.write_text(content, encoding="utf-8")
        return path

    @pytest.mark.asyncio
    async def test_enrich_appends_delta_entry_when_step_text_changes(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """Resolving a clarification marker inside a step body appends one delta entry."""
        root = temp_project_with_roadmap
        plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Setup\n\n"
            "Use [NEEDS CLARIFICATION: framework] to scaffold.\n\n"
            "## Change History\n\n"
            "_No revisions recorded yet._\n"
        )
        plan_path = self._make_plan_file(plans_dir, "enrich-delta-test", content)

        result_str = await _enrich_plan_with_root_patched(
            root,
            plan_relative_path=".cortex/plans/enrich-delta-test.md",
            resolved_clarifications={"framework": "FastAPI"},
        )

        result = EnrichPlanResult.model_validate_json(result_str)
        assert result.status == "success"
        assert result.resolved_markers == 1

        written = plan_path.read_text(encoding="utf-8")
        assert CHANGE_HISTORY_HEADING in written
        count, latest = change_history_stats(written)
        assert count == 1
        assert latest is not None
        assert "FastAPI" in written

    @pytest.mark.asyncio
    async def test_enrich_idempotent_on_unchanged_steps(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """Enriching a plan whose steps are unchanged appends no history entry."""
        root = temp_project_with_roadmap
        plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Only step\n\nDo the thing.\n\n"
            "## Change History\n\n"
            "_No revisions recorded yet._\n"
        )
        plan_path = self._make_plan_file(plans_dir, "enrich-idempotent-test", content)

        result_str = await _enrich_plan_with_root_patched(
            root,
            plan_relative_path=".cortex/plans/enrich-idempotent-test.md",
            resolved_clarifications={},
        )

        result = EnrichPlanResult.model_validate_json(result_str)
        assert result.status == "success"

        written = plan_path.read_text(encoding="utf-8")
        count, _ = change_history_stats(written)
        assert count == 0

    @pytest.mark.asyncio
    async def test_enrich_history_grows_monotonically(
        self, temp_project_with_roadmap: Path
    ) -> None:
        """Two enrichments that each resolve a marker produce two distinct entries."""
        root = temp_project_with_roadmap
        plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
        # Two independent clarification markers — resolve one per call.
        content = (
            "## Implementation Steps\n\n"
            "### Step 1: Alpha\n\n"
            "Use [NEEDS CLARIFICATION: db] for storage.\n\n"
            "### Step 2: Beta\n\n"
            "Use [NEEDS CLARIFICATION: cache] for caching.\n\n"
            "## Change History\n\n"
            "_No revisions recorded yet._\n"
        )
        plan_path = self._make_plan_file(plans_dir, "enrich-monotonic-test", content)

        _ = await _enrich_plan_with_root_patched(
            root,
            plan_relative_path=".cortex/plans/enrich-monotonic-test.md",
            resolved_clarifications={"db": "PostgreSQL"},
        )

        after_first = plan_path.read_text(encoding="utf-8")
        count_after_first, _ = change_history_stats(after_first)
        assert count_after_first == 1

        _ = await _enrich_plan_with_root_patched(
            root,
            plan_relative_path=".cortex/plans/enrich-monotonic-test.md",
            resolved_clarifications={"cache": "Redis"},
        )

        after_second = plan_path.read_text(encoding="utf-8")
        count_after_second, _ = change_history_stats(after_second)
        assert count_after_second == 2


class TestParallelPlanFrontierAndMergeIntegration:
    """Integration tests for parallel task markers: frontier + merge strategy."""

    _PLAN_WITH_PARALLEL_STEPS = (
        "## Implementation Steps\n\n"
        "### Step 1: Foundation\n\nBuild `src/core/base.py`.\n\n"
        "### [P] Step 2: Module A\n\nBuild `src/a/alpha.py`.\n\n"
        "### [P] Step 3: Module B\n\nBuild `src/b/beta.py`.\n\n"
        "### Step 4: Integration\n\nWire modules together.\n"
    )

    def test_frontier_after_step1_complete_yields_parallel_batch(self) -> None:
        """After step 1 finishes, frontier returns steps 2 and 3 as a parallel batch."""
        nodes = parse_task_graph(self._PLAN_WITH_PARALLEL_STEPS)
        frontier = next_execution_frontier(nodes, completed={1}, max_parallel=3)
        frontier_ids = {n.step_id for n in frontier}
        assert frontier_ids == {2, 3}
        assert all(n.parallel for n in frontier)

    def test_frontier_before_any_complete_yields_sequential_step1(self) -> None:
        """With nothing complete, frontier returns only step 1 (sequential)."""
        nodes = parse_task_graph(self._PLAN_WITH_PARALLEL_STEPS)
        frontier = next_execution_frontier(nodes, completed=set(), max_parallel=3)
        assert len(frontier) == 1
        assert frontier[0].step_id == 1
        assert not frontier[0].parallel

    def test_frontier_after_all_parallel_complete_yields_step4(self) -> None:
        """After steps 1–3 complete, frontier is the final sequential step 4."""
        nodes = parse_task_graph(self._PLAN_WITH_PARALLEL_STEPS)
        frontier = next_execution_frontier(nodes, completed={1, 2, 3}, max_parallel=3)
        assert len(frontier) == 1
        assert frontier[0].step_id == 4

    def test_merge_order_for_independent_parallel_batch(self) -> None:
        """Independent parallel steps merge in ascending step_id order."""
        nodes = parse_task_graph(self._PLAN_WITH_PARALLEL_STEPS)
        batch = [n for n in nodes if n.step_id in {2, 3}]
        order = merge_order_for_parallel_batch(batch)
        assert order == [2, 3]

    def test_no_conflict_markers_for_disjoint_paths(self) -> None:
        """Steps touching different files produce no clarification markers."""
        nodes = parse_task_graph(self._PLAN_WITH_PARALLEL_STEPS)
        batch = [n for n in nodes if n.step_id in {2, 3}]
        changed: dict[int, set[str]] = {
            2: {"src/a/alpha.py"},
            3: {"src/b/beta.py"},
        }
        markers = clarification_markers_for_shared_paths(batch, changed)
        assert markers == []

    def test_conflict_markers_for_shared_path(self) -> None:
        """Steps that both touch the same file produce one blocking marker."""
        nodes = parse_task_graph(self._PLAN_WITH_PARALLEL_STEPS)
        batch = [n for n in nodes if n.step_id in {2, 3}]
        changed: dict[int, set[str]] = {
            2: {"src/shared/utils.py"},
            3: {"src/shared/utils.py"},
        }
        markers = clarification_markers_for_shared_paths(batch, changed)
        assert len(markers) == 1
        assert markers[0].blocking is True
        assert "src/shared/utils.py" in markers[0].reason


class TestPlanDependsOnRegisterThenCompleteIntegration:
    """End-to-end: register dependent plan as BLOCKED, then unblock via complete_plan."""

    @pytest.mark.asyncio
    async def test_complete_base_unblocks_registered_dependent_plan(
        self, temp_project_with_roadmap: Path
    ) -> None:
        root = temp_project_with_roadmap
        memory_bank = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
        _ = (memory_bank / "activeContext.md").write_text(
            "# Active Context\n\n## Completed Work (2026-04-10)\n\n",
            encoding="utf-8",
        )
        plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
        foundation_body, leaf_body = _depends_on_integration_plan_bodies()
        leaf_path = plans_dir / "leaf.md"
        _ = (plans_dir / "foundation.md").write_text(foundation_body, encoding="utf-8")
        _ = leaf_path.write_text(leaf_body, encoding="utf-8")
        await _register_foundation_and_leaf_plans(root)
        assert "status: BLOCKED" in leaf_path.read_text(encoding="utf-8")
        done_body = foundation_body.replace("status: PENDING", "status: DONE", 1)
        _ = (plans_dir / "foundation.md").write_text(done_body, encoding="utf-8")
        with _patch_roots_for_complete_plan(root):
            out = await complete_plan(
                plan_title="Foundation",
                summary="Base done.",
                completion_date="2026-04-11",
            )
        result = json.loads(out)
        assert result["status"] == "success"
        assert result.get("plans_unblocked") == 1
        assert "status: READY" in leaf_path.read_text(encoding="utf-8")
