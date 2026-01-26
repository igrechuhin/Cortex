"""
Tests for ReorganizationPlanner

This module tests the reorganization planner that plans structural reorganization
of Memory Bank files to improve dependency structure and optimize file organization.
"""

from pathlib import Path

import pytest

from cortex.refactoring.models import (
    DependencyGraphInput,
    DependencyInfo,
    MemoryBankStructureData,
    ReorganizationActionModel,
    ReorganizationImpactModel,
    ReorganizationPlanModel,
)
from cortex.refactoring.reorganization_planner import ReorganizationPlanner


@pytest.fixture
def reorganization_planner(tmp_path: Path):
    """Create reorganization planner instance"""
    return ReorganizationPlanner(
        memory_bank_path=tmp_path, max_dependency_depth=5, enable_categories=True
    )


@pytest.fixture
def sample_structure_data() -> MemoryBankStructureData:
    """Sample structure analysis data"""
    return MemoryBankStructureData(
        organization="flat",
        dependency_depth=7,
        complexity_score=0.8,
        orphaned_files=["orphan1.md", "orphan2.md", "orphan3.md"],
        total_files=10,
        files=["projectBrief.md", "activeContext.md", "progress.md", "techContext.md"],
    )


@pytest.fixture
def sample_dependency_graph() -> DependencyGraphInput:
    """Sample dependency graph data"""
    return DependencyGraphInput(
        dependencies={
            "projectBrief.md": DependencyInfo(
                depends_on=[],
                dependents=["activeContext.md", "progress.md", "techContext.md"],
            ),
            "activeContext.md": DependencyInfo(
                depends_on=["projectBrief.md"],
                dependents=[],
            ),
            "progress.md": DependencyInfo(
                depends_on=["projectBrief.md"],
                dependents=[],
            ),
            "techContext.md": DependencyInfo(
                depends_on=["projectBrief.md"],
                dependents=[],
            ),
        }
    )


class TestReorganizationPlannerInitialization:
    """Test ReorganizationPlanner initialization"""

    def test_initialization_with_defaults(self, tmp_path: Path):
        """Test planner initialization with default values"""
        planner = ReorganizationPlanner(memory_bank_path=tmp_path)

        assert planner.memory_bank_path == tmp_path
        assert planner.max_dependency_depth == 5
        assert planner.enable_categories is True
        assert planner.plan_counter == 0

    def test_initialization_with_custom_values(self, tmp_path: Path):
        """Test planner initialization with custom values"""
        planner = ReorganizationPlanner(
            memory_bank_path=tmp_path,
            max_dependency_depth=3,
            enable_categories=False,
        )

        assert planner.max_dependency_depth == 3
        assert planner.enable_categories is False

    def test_path_conversion(self, tmp_path: Path):
        """Test that path is converted to Path object"""
        planner = ReorganizationPlanner(memory_bank_path=str(tmp_path))

        assert isinstance(planner.memory_bank_path, Path)
        assert planner.memory_bank_path == tmp_path


class TestPlanIDGeneration:
    """Test plan ID generation"""

    def test_generate_unique_ids(self, reorganization_planner: ReorganizationPlanner):
        """Test that generated IDs are unique"""
        id1 = reorganization_planner.generate_plan_id()
        id2 = reorganization_planner.generate_plan_id()
        id3 = reorganization_planner.generate_plan_id()

        assert id1 != id2 != id3
        assert id1 == "REORG-0001"
        assert id2 == "REORG-0002"
        assert id3 == "REORG-0003"

    def test_id_counter_increments(self, reorganization_planner: ReorganizationPlanner):
        """Test that counter increments correctly"""
        assert reorganization_planner.plan_counter == 0

        _ = reorganization_planner.generate_plan_id()
        assert reorganization_planner.plan_counter == 1

        _ = reorganization_planner.generate_plan_id()
        assert reorganization_planner.plan_counter == 2

    def test_id_format(self, reorganization_planner: ReorganizationPlanner):
        """Test that ID format is correct"""
        id1 = reorganization_planner.generate_plan_id()

        assert id1.startswith("REORG-")
        assert len(id1) == 10  # "REORG-" (6 chars) + 4 digits = 10 total
        assert id1[6:].isdigit()


class TestCategoryInference:
    """Test category inference from filenames"""

    def test_infer_context_category(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test inferring context category"""
        files = ["activeContext.md", "systemPatterns.md", "context-overview.md"]

        categories = reorganization_planner.infer_categories(files)

        assert "context" in categories
        assert len(categories["context"]) == 3

    def test_infer_technical_category(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test inferring technical category"""
        files = ["techContext.md", "architecture.md", "design-patterns.md"]

        categories = reorganization_planner.infer_categories(files)

        assert "technical" in categories
        # design-patterns will be in planning category (contains "design")
        # techContext and architecture should be in technical
        assert len(categories["technical"]) == 2

    def test_infer_progress_category(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test inferring progress category"""
        files = ["progress.md", "status.md", "changelog.md"]

        categories = reorganization_planner.infer_categories(files)

        assert "progress" in categories
        assert len(categories["progress"]) == 3

    def test_infer_planning_category(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test inferring planning category"""
        files = ["projectBrief.md", "roadmap.md", "plan-2024.md"]

        categories = reorganization_planner.infer_categories(files)

        assert "planning" in categories
        assert len(categories["planning"]) == 3

    def test_infer_reference_category(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test inferring reference category"""
        files = ["api.md", "reference.md", "docs.md"]

        categories = reorganization_planner.infer_categories(files)

        assert "reference" in categories
        assert len(categories["reference"]) == 3

    def test_infer_uncategorized(self, reorganization_planner: ReorganizationPlanner):
        """Test uncategorized files"""
        files = ["random.md", "misc.md", "other.md"]

        categories = reorganization_planner.infer_categories(files)

        assert "uncategorized" in categories
        assert len(categories["uncategorized"]) == 3

    def test_removes_empty_categories(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test that empty categories are removed"""
        files = ["activeContext.md"]

        categories = reorganization_planner.infer_categories(files)

        # Only context category should be present
        assert "context" in categories
        # Other categories shouldn't exist if empty
        assert len(categories) == 1


class TestNeedsReorganization:
    """Test reorganization need detection"""

    def test_needs_reorg_dependency_depth(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test detecting need for reorganization based on dependency depth"""
        structure = MemoryBankStructureData(dependency_depth=7)

        needs_reorg, reasons = reorganization_planner.needs_reorganization(
            structure, "dependency_depth"
        )

        assert needs_reorg is True
        assert len(reasons) > 0
        assert "Dependency depth" in reasons[0]

    def test_no_reorg_needed_dependency_depth(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test no reorganization needed for acceptable dependency depth"""
        structure = MemoryBankStructureData(dependency_depth=3)

        needs_reorg, reasons = reorganization_planner.needs_reorganization(
            structure, "dependency_depth"
        )

        assert needs_reorg is False
        assert len(reasons) == 0

    def test_needs_reorg_category_based_flat(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test detecting need for categorization in flat structure"""
        structure = MemoryBankStructureData(
            organization="flat", total_files=10, categories={}
        )

        needs_reorg, reasons = reorganization_planner.needs_reorganization(
            structure, "category_based"
        )

        assert needs_reorg is True
        assert any("Flat structure" in r for r in reasons)

    def test_needs_reorg_uncategorized_files(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test detecting need for categorization with uncategorized files"""
        structure = MemoryBankStructureData(
            organization="category_based",
            categories={
                "uncategorized": ["file1.md", "file2.md", "file3.md", "file4.md"],
            },
        )

        needs_reorg, reasons = reorganization_planner.needs_reorganization(
            structure, "category_based"
        )

        assert needs_reorg is True
        assert any("lack clear categorization" in r for r in reasons)

    def test_needs_reorg_high_complexity(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test detecting need for reorganization based on complexity"""
        structure = MemoryBankStructureData(complexity_score=0.85, orphaned_files=[])

        needs_reorg, reasons = reorganization_planner.needs_reorganization(
            structure, "complexity"
        )

        assert needs_reorg is True
        assert any("complexity" in r.lower() for r in reasons)

    def test_needs_reorg_orphaned_files(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test detecting need for reorganization with orphaned files"""
        structure = MemoryBankStructureData(
            complexity_score=0.3,
            orphaned_files=["file1.md", "file2.md", "file3.md"],
        )

        needs_reorg, reasons = reorganization_planner.needs_reorganization(
            structure, "complexity"
        )

        assert needs_reorg is True
        assert any("orphaned" in r.lower() for r in reasons)


class TestOptimizeDependencyOrder:
    """Test dependency order optimization"""

    def test_optimize_dependency_order_basic(
        self,
        reorganization_planner: ReorganizationPlanner,
        sample_dependency_graph: DependencyGraphInput,
    ):
        """Test basic dependency order optimization"""
        structure = MemoryBankStructureData(
            files=[
                "activeContext.md",
                "projectBrief.md",
                "progress.md",
                "techContext.md",
            ]
        )

        order = reorganization_planner.optimize_dependency_order(
            structure, sample_dependency_graph
        )

        # projectBrief.md should come first (no dependencies)
        assert order[0] == "projectBrief.md"
        # Other files can come after
        assert len(order) == 4

    def test_optimize_dependency_order_empty_graph(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test optimization with empty dependency graph"""
        structure = MemoryBankStructureData(files=["file1.md", "file2.md", "file3.md"])
        empty_graph = DependencyGraphInput(dependencies={})

        order = reorganization_planner.optimize_dependency_order(structure, empty_graph)

        # Should return original files if no graph
        assert len(order) == 3

    def test_optimize_dependency_order_deterministic(
        self,
        reorganization_planner: ReorganizationPlanner,
        sample_dependency_graph: DependencyGraphInput,
    ):
        """Test that optimization produces deterministic results"""
        structure = MemoryBankStructureData(
            files=[
                "activeContext.md",
                "projectBrief.md",
                "progress.md",
                "techContext.md",
            ]
        )

        order1 = reorganization_planner.optimize_dependency_order(
            structure, sample_dependency_graph
        )
        order2 = reorganization_planner.optimize_dependency_order(
            structure, sample_dependency_graph
        )

        assert order1 == order2


class TestProposedStructures:
    """Test proposed structure generation"""

    def test_propose_category_structure(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test proposing category-based structure"""
        current = MemoryBankStructureData(
            organization="category_based",
            categories={
                "context": ["activeContext.md", "systemPatterns.md"],
                "technical": ["techContext.md"],
                "uncategorized": ["random.md", "misc.md"],
            },
        )

        proposed = reorganization_planner.propose_category_structure(current)

        # Should have categories from current structure
        assert "context" in proposed
        assert "technical" in proposed
        # Uncategorized should be assigned to default category
        assert len(proposed["context"]) >= 2

    def test_propose_simplified_structure(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test proposing simplified structure"""
        current = MemoryBankStructureData(
            files=[
                "memorybankinstructions.md",
                "projectBrief.md",
                "activeContext.md",
                "progress.md",
                "techContext.md",
            ]
        )

        simplified = reorganization_planner.propose_simplified_structure(current)

        # Should have three main categories
        assert "core" in simplified
        assert "context" in simplified
        assert "reference" in simplified
        # Instructions and brief should be in core
        assert any("instruction" in f.lower() for f in simplified["core"])


class TestActionGeneration:
    """Test reorganization action generation"""

    @pytest.mark.asyncio
    async def test_generate_actions_category_based(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test generating actions for category-based reorganization"""
        current = MemoryBankStructureData(files=["file1.md", "file2.md"])
        proposed = MemoryBankStructureData(
            organization="category_based",
            categories={
                "context": ["file1.md"],
                "technical": ["file2.md"],
            },
        )

        actions = await reorganization_planner.generate_actions(
            current, proposed, "category_based"
        )

        # Should create category directories and move files
        create_actions = [a for a in actions if a.action_type == "create_category"]
        move_actions = [a for a in actions if a.action_type == "move"]

        assert len(create_actions) == 2  # Two categories
        assert len(move_actions) <= 2  # May move files

    @pytest.mark.asyncio
    async def test_generate_actions_dependency_depth(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test generating actions for dependency depth optimization"""
        current = MemoryBankStructureData(files=["file1.md", "file2.md"])
        proposed = MemoryBankStructureData(
            organization="dependency_optimized",
            dependency_order=["file1.md", "file2.md"],
        )

        actions = await reorganization_planner.generate_actions(
            current, proposed, "dependency_depth"
        )

        # Should generate reorder action
        reorder_actions = [a for a in actions if a.action_type == "reorder"]
        assert len(reorder_actions) == 1

    @pytest.mark.asyncio
    async def test_generate_actions_complexity(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test generating actions for complexity reduction"""
        current = MemoryBankStructureData(files=["file1.md", "file2.md"])
        proposed = MemoryBankStructureData(
            organization="simplified",
            categories={
                "core": ["file1.md"],
                "context": ["file2.md"],
            },
        )

        actions = await reorganization_planner.generate_actions(
            current, proposed, "complexity"
        )

        # Should create simplified categories and move files
        create_actions = [a for a in actions if a.action_type == "create_category"]
        assert len(create_actions) >= 2


class TestImpactCalculation:
    """Test impact calculation"""

    def test_calculate_impact_basic(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test basic impact calculation"""
        current = MemoryBankStructureData(total_files=5)
        proposed = MemoryBankStructureData(organization="category_based")
        actions = [
            ReorganizationActionModel(
                action_type="move",
                source="file1.md",
                target="context/file1.md",
                reason="test",
                dependencies_affected=[],
            ),
            ReorganizationActionModel(
                action_type="move",
                source="file2.md",
                target="context/file2.md",
                reason="test",
                dependencies_affected=[],
            ),
            ReorganizationActionModel(
                action_type="create_category",
                source="",
                target="context",
                reason="test",
                dependencies_affected=[],
            ),
        ]

        impact = reorganization_planner.calculate_impact(current, proposed, actions)

        assert impact.files_moved == 2
        assert impact.categories_created == 1
        assert isinstance(impact.dependency_depth_reduction, float)
        assert isinstance(impact.complexity_reduction, float)

    def test_calculate_impact_effort_estimation(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test effort estimation based on action count"""
        current = MemoryBankStructureData()
        proposed = MemoryBankStructureData()

        # Few actions -> low effort
        few_actions = [
            ReorganizationActionModel(
                action_type="move",
                source="file1.md",
                target="context/file1.md",
                reason="test",
                dependencies_affected=[],
            )
        ]
        impact_low = reorganization_planner.calculate_impact(
            current, proposed, few_actions
        )
        assert impact_low.estimated_effort == "low"

        # Many actions -> medium effort
        many_actions = [
            ReorganizationActionModel(
                action_type="move",
                source=f"file{i}.md",
                target=f"context/file{i}.md",
                reason="test",
                dependencies_affected=[],
            )
            for i in range(15)
        ]
        impact_medium = reorganization_planner.calculate_impact(
            current, proposed, many_actions
        )
        assert impact_medium.estimated_effort == "medium"


class TestRiskIdentification:
    """Test risk identification"""

    def test_identify_risks_many_moves(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test identifying risks with many file moves"""
        actions = [
            ReorganizationActionModel(
                action_type="move",
                source=f"file{i}.md",
                target=f"context/file{i}.md",
                reason="test",
                dependencies_affected=[],
            )
            for i in range(8)
        ]
        current = MemoryBankStructureData(dependency_depth=2)

        risks = reorganization_planner.identify_risks(actions, current)

        assert len(risks) > 0
        assert any("link" in r.lower() for r in risks)

    def test_identify_risks_large_scale(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test identifying risks for large-scale reorganization"""
        actions = [
            ReorganizationActionModel(
                action_type="move",
                source=f"file{i}.md",
                target=f"context/file{i}.md",
                reason="test",
                dependencies_affected=[],
            )
            for i in range(15)
        ]
        current = MemoryBankStructureData(dependency_depth=2)

        risks = reorganization_planner.identify_risks(actions, current)

        assert any("Large-scale" in r for r in risks)

    def test_identify_risks_complex_dependencies(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test identifying risks with complex dependencies"""
        actions = [
            ReorganizationActionModel(
                action_type="move",
                source="file1.md",
                target="context/file1.md",
                reason="test",
                dependencies_affected=[],
            )
        ]
        current = MemoryBankStructureData(dependency_depth=5)

        risks = reorganization_planner.identify_risks(actions, current)

        assert any("dependencies" in r.lower() for r in risks)

    def test_identify_low_risk(self, reorganization_planner: ReorganizationPlanner):
        """Test identifying low risk scenarios"""
        actions = [
            ReorganizationActionModel(
                action_type="move",
                source="file1.md",
                target="context/file1.md",
                reason="test",
                dependencies_affected=[],
            )
        ]
        current = MemoryBankStructureData(dependency_depth=2)

        risks = reorganization_planner.identify_risks(actions, current)

        assert any("Low risk" in r for r in risks)


class TestBenefitIdentification:
    """Test benefit identification"""

    def test_identify_benefits_category_based(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test identifying benefits of category-based organization"""
        proposed = MemoryBankStructureData(organization="category_based")
        current = MemoryBankStructureData(organization="flat")

        benefits = reorganization_planner.identify_benefits(proposed, current)

        assert len(benefits) > 0
        assert any("categorization" in b.lower() for b in benefits)
        assert any("discoverability" in b.lower() for b in benefits)

    def test_identify_benefits_dependency_optimized(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test identifying benefits of dependency optimization"""
        proposed = MemoryBankStructureData(organization="dependency_optimized")
        current = MemoryBankStructureData(organization="flat")

        benefits = reorganization_planner.identify_benefits(proposed, current)

        assert any("dependency" in b.lower() for b in benefits)
        assert any("depth" in b.lower() or "flow" in b.lower() for b in benefits)

    def test_identify_benefits_simplified(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test identifying benefits of simplified structure"""
        proposed = MemoryBankStructureData(organization="simplified")
        current = MemoryBankStructureData(organization="complex")

        benefits = reorganization_planner.identify_benefits(proposed, current)

        assert any(
            "simplified" in b.lower() or "simpler" in b.lower() for b in benefits
        )
        assert any(
            "cognitive" in b.lower() or "navigation" in b.lower() for b in benefits
        )

    def test_always_includes_general_benefit(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test that general benefit is always included"""
        proposed = MemoryBankStructureData(organization="unknown")
        current = MemoryBankStructureData(organization="flat")

        benefits = reorganization_planner.identify_benefits(proposed, current)

        assert any(
            "overall" in b.lower() and "organization" in b.lower() for b in benefits
        )


class TestCreateReorganizationPlan:
    """Test complete reorganization plan creation"""

    @pytest.mark.asyncio
    async def test_create_plan_success(
        self,
        reorganization_planner: ReorganizationPlanner,
        tmp_path: Path,
        sample_structure_data: MemoryBankStructureData,
        sample_dependency_graph: DependencyGraphInput,
    ):
        """Test creating a successful reorganization plan"""
        # Create test files
        _ = (tmp_path / "file1.md").write_text("# File 1")
        _ = (tmp_path / "file2.md").write_text("# File 2")

        plan = await reorganization_planner.create_reorganization_plan(
            optimize_for="dependency_depth",
            structure_data=sample_structure_data,
            dependency_graph=sample_dependency_graph,
        )

        assert plan is not None
        assert plan.plan_id.startswith("REORG-")
        assert plan.optimization_goal == "dependency_depth"
        assert plan.current_structure
        assert plan.proposed_structure
        assert plan.actions
        assert plan.estimated_impact
        assert plan.risks
        assert plan.benefits

    @pytest.mark.asyncio
    async def test_create_plan_no_reorg_needed(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test that no plan is created when reorganization not needed"""
        structure_data = MemoryBankStructureData(
            organization="flat",
            dependency_depth=2,
            orphaned_files=[],
        )
        dependency_graph = DependencyGraphInput(dependencies={})

        plan = await reorganization_planner.create_reorganization_plan(
            optimize_for="dependency_depth",
            structure_data=structure_data,
            dependency_graph=dependency_graph,
        )

        assert plan is None

    @pytest.mark.asyncio
    async def test_create_plan_category_based(
        self,
        reorganization_planner: ReorganizationPlanner,
        tmp_path: Path,
    ):
        """Test creating category-based reorganization plan"""
        # Create test files
        for i in range(10):
            _ = (tmp_path / f"file{i}.md").write_text(f"# File {i}")

        structure_data = MemoryBankStructureData(
            organization="flat",
            total_files=10,
            files=[f"file{i}.md" for i in range(10)],
        )
        dependency_graph = DependencyGraphInput(dependencies={})

        plan = await reorganization_planner.create_reorganization_plan(
            optimize_for="category_based",
            structure_data=structure_data,
            dependency_graph=dependency_graph,
        )

        if plan:  # May be None if structure is acceptable
            assert plan.optimization_goal == "category_based"
            assert len(plan.actions) > 0

    @pytest.mark.asyncio
    async def test_create_plan_complexity(
        self,
        reorganization_planner: ReorganizationPlanner,
        tmp_path: Path,
        sample_structure_data: MemoryBankStructureData,
        sample_dependency_graph: DependencyGraphInput,
    ):
        """Test creating complexity reduction plan"""
        _ = (tmp_path / "file1.md").write_text("# File 1")

        plan = await reorganization_planner.create_reorganization_plan(
            optimize_for="complexity",
            structure_data=sample_structure_data,
            dependency_graph=sample_dependency_graph,
        )

        if plan:
            assert plan.optimization_goal == "complexity"

    @pytest.mark.asyncio
    async def test_create_plan_missing_data(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test that plan creation fails gracefully with missing data"""
        plan = await reorganization_planner.create_reorganization_plan(
            optimize_for="dependency_depth", structure_data=None, dependency_graph=None
        )

        assert plan is None


class TestPreviewReorganization:
    """Test reorganization preview"""

    @pytest.mark.asyncio
    async def test_preview_with_details(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test preview with detailed information"""
        plan = ReorganizationPlanModel(
            plan_id="REORG-0001",
            optimization_goal="category_based",
            current_structure=MemoryBankStructureData(organization="flat"),
            proposed_structure=MemoryBankStructureData(organization="category_based"),
            actions=[
                ReorganizationActionModel(
                    action_type="move",
                    source="file1.md",
                    target="context/file1.md",
                    reason="test",
                    dependencies_affected=[],
                ),
                ReorganizationActionModel(
                    action_type="create_category",
                    source="",
                    target="context",
                    reason="create context category",
                    dependencies_affected=[],
                ),
            ],
            estimated_impact=ReorganizationImpactModel(
                files_moved=1,
                categories_created=1,
                dependency_depth_reduction=0.0,
                complexity_reduction=0.0,
                maintainability_improvement=0.0,
                navigation_improvement=0.0,
                estimated_effort="low",
            ),
            risks=["Low risk"],
            benefits=["Improved organization"],
        )

        preview = await reorganization_planner.preview_reorganization(
            plan, show_details=True
        )

        assert preview.plan_id == "REORG-0001"
        assert preview.optimization_goal == "category_based"
        assert preview.actions_count == 2
        assert len(preview.actions) == 2
        assert preview.structure_comparison is not None

    @pytest.mark.asyncio
    async def test_preview_without_details(
        self, reorganization_planner: ReorganizationPlanner
    ):
        """Test preview without detailed information"""
        plan = ReorganizationPlanModel(
            plan_id="REORG-0001",
            optimization_goal="dependency_depth",
            current_structure=MemoryBankStructureData(),
            proposed_structure=MemoryBankStructureData(),
            actions=[],
            estimated_impact=ReorganizationImpactModel(
                files_moved=0,
                categories_created=0,
                dependency_depth_reduction=0.0,
                complexity_reduction=0.0,
                maintainability_improvement=0.0,
                navigation_improvement=0.0,
                estimated_effort="low",
            ),
            risks=[],
            benefits=[],
        )

        preview = await reorganization_planner.preview_reorganization(
            plan, show_details=False
        )

        assert preview.plan_id == "REORG-0001"
        assert preview.optimization_goal == "dependency_depth"
        assert preview.actions == []
        assert preview.structure_comparison is None


class TestReorganizationPlanModel:
    """Test ReorganizationPlanModel."""

    def test_model_dump_json(self):
        plan = ReorganizationPlanModel(
            plan_id="REORG-0001",
            optimization_goal="category_based",
            current_structure=MemoryBankStructureData(organization="flat"),
            proposed_structure=MemoryBankStructureData(organization="category_based"),
            actions=[
                ReorganizationActionModel(
                    action_type="move",
                    source="file1.md",
                    target="context/file1.md",
                    reason="test",
                    dependencies_affected=["dep1"],
                ),
                ReorganizationActionModel(
                    action_type="create_category",
                    source="",
                    target="context",
                    reason="create context",
                    dependencies_affected=[],
                ),
            ],
            estimated_impact=ReorganizationImpactModel(
                files_moved=1,
                categories_created=1,
                dependency_depth_reduction=0.0,
                complexity_reduction=0.0,
                maintainability_improvement=0.0,
                navigation_improvement=0.0,
                estimated_effort="low",
            ),
            risks=["Low risk"],
            benefits=["Improved organization"],
            preserve_history=True,
        )

        dumped = plan.model_dump(mode="json")
        assert dumped["plan_id"] == "REORG-0001"
        assert dumped["optimization_goal"] == "category_based"
        assert dumped["current_structure"]["organization"] == "flat"
        assert dumped["proposed_structure"]["organization"] == "category_based"
        assert isinstance(dumped["actions"], list)
        assert dumped["estimated_impact"]["files_moved"] == 1


class TestHelperMethods:
    """Test helper methods"""

    @pytest.mark.asyncio
    async def test_get_all_markdown_files(
        self, reorganization_planner: ReorganizationPlanner, tmp_path: Path
    ):
        """Test getting all markdown files"""
        # Create test files
        _ = (tmp_path / "file1.md").write_text("# File 1")
        _ = (tmp_path / "file2.md").write_text("# File 2")
        _ = (tmp_path / "file.txt").write_text("Not markdown")

        files = await reorganization_planner.get_all_markdown_files()

        # Should only return .md files
        assert len(files) == 2
        assert all(f.endswith(".md") for f in files)

    @pytest.mark.asyncio
    async def test_analyze_current_structure(
        self,
        reorganization_planner: ReorganizationPlanner,
        tmp_path: Path,
        sample_structure_data: MemoryBankStructureData,
        sample_dependency_graph: DependencyGraphInput,
    ):
        """Test analyzing current structure"""
        # Create test files
        _ = (tmp_path / "file1.md").write_text("# File 1")
        _ = (tmp_path / "file2.md").write_text("# File 2")

        structure = await reorganization_planner.analyze_current_structure(
            sample_structure_data, sample_dependency_graph
        )

        assert isinstance(structure.total_files, int)
        assert isinstance(structure.files, list)
        assert isinstance(structure.organization, str)
        assert isinstance(structure.categories, dict)
        assert isinstance(structure.dependency_depth, int)

    @pytest.mark.asyncio
    async def test_generate_proposed_structure_dependency(
        self,
        reorganization_planner: ReorganizationPlanner,
        sample_dependency_graph: DependencyGraphInput,
    ):
        """Test generating proposed structure for dependency optimization"""
        current = MemoryBankStructureData(files=["file1.md", "file2.md"])

        proposed = await reorganization_planner.generate_proposed_structure(
            current, "dependency_depth", sample_dependency_graph
        )

        assert proposed.organization == "dependency_optimized"
        assert proposed.dependency_order is not None

    @pytest.mark.asyncio
    async def test_generate_proposed_structure_category(
        self,
        reorganization_planner: ReorganizationPlanner,
        sample_dependency_graph: DependencyGraphInput,
    ):
        """Test generating proposed structure for category-based organization"""
        current = MemoryBankStructureData(
            organization="category_based",
            categories={
                "context": ["activeContext.md"],
                "technical": ["techContext.md"],
            },
        )

        proposed = await reorganization_planner.generate_proposed_structure(
            current, "category_based", sample_dependency_graph
        )

        assert proposed.organization == "category_based"
        assert isinstance(proposed.categories, dict)

    @pytest.mark.asyncio
    async def test_generate_proposed_structure_complexity(
        self,
        reorganization_planner: ReorganizationPlanner,
        sample_dependency_graph: DependencyGraphInput,
    ):
        """Test generating proposed structure for complexity reduction"""
        current = MemoryBankStructureData(
            files=[
                "memorybankinstructions.md",
                "projectBrief.md",
                "activeContext.md",
            ]
        )

        proposed = await reorganization_planner.generate_proposed_structure(
            current, "complexity", sample_dependency_graph
        )

        assert proposed["organization"] == "simplified"
        assert "categories" in proposed
