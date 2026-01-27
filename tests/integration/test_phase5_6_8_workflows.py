"""
Integration tests for Phase 5, 6, and 8 workflows in MCP Memory Bank.

These tests verify end-to-end workflows across self-evolution (Phase 5),
shared rules (Phase 6), and project structure (Phase 8) modules.
"""

from datetime import datetime
from pathlib import Path

import pytest

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.insight_types import InsightDict
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.refactoring.consolidation_detector import ConsolidationDetector
from cortex.refactoring.refactoring_engine import RefactoringEngine
from cortex.refactoring.reorganization_planner import ReorganizationPlanner
from cortex.refactoring.split_recommender import SplitRecommender
from cortex.rules.context_detector import ContextDetector
from cortex.rules.synapse_manager import SynapseManager
from cortex.structure.structure_manager import StructureManager
from cortex.structure.template_manager import TemplateManager

# ============================================================================
# Phase 5.1-5.2 Integration: Pattern Analysis + Refactoring
# ============================================================================


@pytest.mark.integration
class TestPhase5Integration:
    """Test integration between Phase 5.1 (analysis) and 5.2 (refactoring)."""

    async def test_pattern_analysis_feeds_refactoring_suggestions(
        self, temp_project_root: Path
    ):
        """Test that pattern analysis results drive refactoring suggestions."""
        # Arrange
        fs = FileSystemManager(temp_project_root)
        metadata = MetadataIndex(temp_project_root)
        dep_graph = DependencyGraph()

        pattern_analyzer = PatternAnalyzer(temp_project_root)
        memory_bank_path = temp_project_root / ".cortex" / "memory-bank"
        memory_bank_path.mkdir(parents=True, exist_ok=True)
        structure_analyzer = StructureAnalyzer(
            temp_project_root, dep_graph, fs, metadata
        )
        insight_engine = InsightEngine(pattern_analyzer, structure_analyzer)
        refactoring_engine = RefactoringEngine(memory_bank_path)

        # Create large file (>50KB to trigger large file detection)
        # Each section is ~500 bytes, need 100+ sections to exceed 50KB
        section_content = (
            "## Section\n\n" + ("This is content for the section. " * 20) + "\n\n"
        )
        large_content = "# Large File\n\n" + (section_content * 200)
        file_path = memory_bank_path / "large_file.md"
        _ = await fs.write_file(file_path, large_content)

        # Record access patterns
        await pattern_analyzer.record_access("large_file.md")
        await pattern_analyzer.record_access("large_file.md")

        # Act: Analyze and generate insights
        insights_result = await insight_engine.generate_insights(min_impact_score=0.1)
        pydantic_insights: list[InsightDict] = insights_result.insights
        insights_list: list[ModelDict] = [
            insight.model_dump(mode="json") for insight in pydantic_insights
        ]

        # Generate refactoring suggestions from insights
        structure_data: ModelDict = {
            "large_file.md": {"size": len(large_content), "sections": 100}
        }
        suggestions = await refactoring_engine.generate_suggestions(
            insights=insights_list,
            structure_data=structure_data,
        )

        # Assert
        assert len(insights_list) > 0
        assert len(suggestions) > 0
        # Should suggest splitting the large file
        assert any(s.refactoring_type.value == "split" for s in suggestions)

    async def test_consolidation_detection_workflow(self, temp_project_root: Path):
        """Test end-to-end consolidation detection workflow."""
        # Arrange
        fs = FileSystemManager(temp_project_root)
        memory_bank_path = temp_project_root / "memory-bank"
        memory_bank_path.mkdir(parents=True, exist_ok=True)
        consolidation_detector = ConsolidationDetector(
            memory_bank_path, min_similarity=0.7
        )

        # Create files with substantial duplicate content (>70% similarity)
        # Make shared content large enough to dominate similarity calculation
        shared_content = (
            """
## Authentication

This section describes authentication mechanisms in detail.
OAuth2 is used for user authentication. The OAuth2 flow involves
multiple steps including authorization request, token exchange,
and resource access. This is a comprehensive authentication guide
that covers all aspects of OAuth2 implementation including security
considerations, token management, and refresh token handling.
"""
            * 5
        )  # Repeat to increase size and similarity

        api_docs_path = memory_bank_path / "api_docs.md"
        _ = await fs.write_file(
            api_docs_path,
            (
                f"# API Documentation\n{shared_content}\n## Endpoints\n"
                "Brief endpoint description.\n"
            ),
        )
        auth_guide_path = memory_bank_path / "auth_guide.md"
        _ = await fs.write_file(
            auth_guide_path,
            (
                f"# Authentication Guide\n{shared_content}\n## Setup\n"
                "Brief setup instructions.\n"
            ),
        )

        # Act: Detect consolidation opportunities
        opportunities = await consolidation_detector.detect_opportunities(
            files=["api_docs.md", "auth_guide.md"]
        )

        # Assert
        assert len(opportunities) > 0
        assert opportunities[0].affected_files == ["api_docs.md", "auth_guide.md"]
        assert opportunities[0].token_savings > 0

    async def test_split_recommendation_workflow(self, temp_project_root: Path):
        """Test end-to-end file splitting recommendation workflow."""
        # Arrange
        fs = FileSystemManager(temp_project_root)
        memory_bank_path = temp_project_root / "memory-bank"
        memory_bank_path.mkdir(parents=True, exist_ok=True)
        split_recommender = SplitRecommender(
            memory_bank_path, max_file_size=1000, max_sections=10
        )

        # Create large file with multiple sections (>10 sections and >1000 tokens)
        # Each section has substantial content to exceed token threshold
        sections: list[str] = []
        for i in range(15):  # >10 sections
            section_content = (
                f"""## Section {i + 1}
Large section about topic {i + 1} with detailed content.
"""
                + ("Detailed content line with substantial information. " * 30)
                + "\n"
            )
            sections.append(section_content)

        large_content = "# Main Document\n\n" + "\n".join(sections)

        file_path = memory_bank_path / "design.md"
        _ = await fs.write_file(file_path, large_content)

        # Act: Suggest splits
        recommendations = await split_recommender.suggest_file_splits(
            files=["design.md"]
        )

        # Assert
        assert len(recommendations) > 0
        rec = recommendations[0]
        assert rec.file_path == "design.md"
        assert rec.split_strategy in [
            "by_size",
            "by_sections",
            "by_topics",
            "by_dependencies",
        ]
        assert len(rec.split_points) > 0

    async def test_reorganization_planning_workflow(self, temp_project_root: Path):
        """Test end-to-end reorganization planning workflow."""
        # Arrange
        fs = FileSystemManager(temp_project_root)
        memory_bank_path = temp_project_root / "memory-bank"
        memory_bank_path.mkdir(parents=True, exist_ok=True)
        reorganization_planner = ReorganizationPlanner(memory_bank_path)

        # Create files in various categories
        # Need >3 uncategorized files to trigger category_based reorganization
        _ = await fs.write_file(
            memory_bank_path / "api_endpoints.md", "# API Endpoints\n"
        )
        _ = await fs.write_file(
            memory_bank_path / "api_auth.md", "# API Authentication\n"
        )
        _ = await fs.write_file(
            memory_bank_path / "db_schema.md", "# Database Schema\n"
        )
        _ = await fs.write_file(
            memory_bank_path / "db_migrations.md", "# Database Migrations\n"
        )
        _ = await fs.write_file(
            memory_bank_path / "uncategorized1.md", "# Uncategorized File 1\n"
        )
        _ = await fs.write_file(
            memory_bank_path / "uncategorized2.md", "# Uncategorized File 2\n"
        )
        _ = await fs.write_file(
            memory_bank_path / "uncategorized3.md", "# Uncategorized File 3\n"
        )
        _ = await fs.write_file(
            memory_bank_path / "uncategorized4.md", "# Uncategorized File 4\n"
        )

        # Provide structure data and dependency graph (required for plan creation)
        structure_data: ModelDict = {
            "organization": {"type": "flat"},
            "complexity_metrics": {"max_dependency_depth": 1},
            "anti_patterns": {"orphaned_files": []},
        }
        dependency_graph: ModelDict = {
            "dependencies": {},
        }

        # Act: Create reorganization plan
        plan = await reorganization_planner.create_reorganization_plan(
            optimize_for="category_based",
            structure_data=structure_data,
            dependency_graph=dependency_graph,
        )

        # Assert
        assert plan is not None
        assert len(plan.actions) > 0
        # Should suggest organizing by category
        assert any(a.action_type == "create_category" for a in plan.actions)


# ============================================================================
# Phase 6 Integration: Shared Rules with Context Detection
# ============================================================================


@pytest.mark.integration
class TestPhase6Integration:
    """Test integration of shared rules with context detection."""

    async def test_context_detection_drives_rule_selection(
        self, temp_project_root: Path, tmp_path: Path
    ):
        """Test that context detection influences rule selection."""
        # Arrange
        context_detector = ContextDetector()

        # Act: Detect context from task descriptions
        python_context = context_detector.detect_context(
            "Fix authentication bug in Django REST API",
            [Path("test.py"), Path("test.pyc")],
        )

        swift_context = context_detector.detect_context(
            "Add SwiftUI view for user profile", [Path("test.swift")]
        )

        # Assert
        languages_python: list[str] = list(python_context.detected_languages)
        frameworks_python: list[str] = list(python_context.detected_frameworks)
        assert "python" in languages_python
        assert "django" in frameworks_python
        assert python_context.task_type is not None

        languages_swift: list[str] = list(swift_context.detected_languages)
        frameworks_swift: list[str] = list(swift_context.detected_frameworks)
        assert "swift" in languages_swift
        assert "swiftui" in frameworks_swift
        assert swift_context.task_type is not None

    async def test_shared_rules_integration_workflow(
        self, temp_project_root: Path, tmp_path: Path
    ):
        """Test end-to-end shared rules workflow with context detection."""
        # Arrange
        # Use .shared-rules as synapse folder to match test setup
        synapse_manager = SynapseManager(
            temp_project_root, synapse_folder=".shared-rules"
        )
        context_detector = ContextDetector()

        # Create mock shared rules structure
        shared_rules_dir = temp_project_root / ".shared-rules"
        shared_rules_dir.mkdir(exist_ok=True)

        # Create rules subdirectory (SynapseManager expects rules/ subdirectory)
        rules_dir = shared_rules_dir / "rules"
        rules_dir.mkdir(exist_ok=True)

        # Create manifest
        manifest = {
            "version": "1.0.0",
            "categories": {
                "python": {
                    "rules": [
                        {
                            "file": "style-guide.md",
                            "priority": 100,
                            "keywords": ["python"],
                        }
                    ]
                },
                "generic": {
                    "rules": [
                        {
                            "file": "security.md",
                            "priority": 100,
                            "keywords": ["security"],
                        }
                    ]
                },
            },
        }

        import json

        _ = (rules_dir / "rules-manifest.json").write_text(json.dumps(manifest))

        # Create rule files
        python_dir = rules_dir / "python"
        python_dir.mkdir(exist_ok=True)
        _ = (python_dir / "style-guide.md").write_text(
            "# Python Style Guide\nUse PEP 8"
        )

        generic_dir = rules_dir / "generic"
        generic_dir.mkdir(exist_ok=True)
        _ = (generic_dir / "security.md").write_text("# Security\nValidate all inputs")

        # Act: Load manifest
        loaded = await synapse_manager.load_rules_manifest()

        # Detect context
        context = context_detector.detect_context(
            "Fix Python authentication", [Path("test.py")]
        )

        # Assert
        assert loaded is not None
        languages: list[str] = list(context.detected_languages)
        assert "python" in languages


# ============================================================================
# Phase 8 Integration: Structure Management + Templates
# ============================================================================


@pytest.mark.integration
class TestPhase8Integration:
    """Test integration of structure management with template system."""

    async def test_structure_setup_with_templates(self, temp_project_root: Path):
        """Test setting up project structure with template generation."""
        # Arrange
        structure_manager = StructureManager(temp_project_root)
        template_manager = TemplateManager(temp_project_root)

        # Act: Setup structure
        result = await structure_manager.create_structure(force=False)

        # Generate templates separately
        plans_dir = structure_manager.get_path("plans")
        _ = template_manager.create_plan_templates(plans_dir)

        # Assert: Structure created
        assert "created_directories" in result
        assert "created_files" in result

        memory_bank_dir = structure_manager.get_path("memory_bank")
        assert memory_bank_dir.exists()
        assert (structure_manager.get_path("rules") / "local").exists()
        assert structure_manager.get_path("plans").exists()

        # Templates created
        plans_templates = structure_manager.get_path("plans") / "templates"
        assert plans_templates.exists()
        assert (plans_templates / "feature.md").exists()

    async def test_structure_migration_workflow(self, temp_project_root: Path):
        """Test migrating from legacy structure to standardized layout."""
        # Arrange
        # Remove .cortex directory if it exists (from fixture) to allow detection
        cortex_dir = temp_project_root / ".cortex"
        if cortex_dir.exists():
            import shutil

            shutil.rmtree(cortex_dir)

        structure_manager = StructureManager(temp_project_root)

        # Create legacy structure (scattered files)
        # Use standard knowledge file names to ensure they're migrated
        # Create projectBrief.md in root to trigger scattered-files detection
        fs = FileSystemManager(temp_project_root)
        _ = await fs.write_file(
            temp_project_root / "projectBrief.md", "# Project Brief\n"
        )
        _ = await fs.write_file(
            temp_project_root / "activeContext.md", "# Active Context\n"
        )
        _ = await fs.write_file(temp_project_root / "progress.md", "# Progress\n")

        # Act: Detect migration need
        detected_type = structure_manager.detect_legacy_structure()

        # Migrate if needed
        result: ModelDict | None = None
        if detected_type:
            result = await structure_manager.migrate_legacy_structure(
                detected_type, backup=False
            )

        # Assert
        assert detected_type in ["scattered-files", "cursor-default"]

        if result:
            assert result.get("success") is True
            files_migrated = result.get("files_migrated", 0)
            files_migrated_int = (
                int(files_migrated) if isinstance(files_migrated, (int, float)) else 0
            )
            assert files_migrated_int >= 2

    async def test_structure_health_monitoring(self, temp_project_root: Path):
        """Test structure health check and recommendations."""
        # Arrange
        structure_manager = StructureManager(temp_project_root)

        # Setup structure first
        _ = await structure_manager.create_structure(force=False)

        # Act: Check health
        health = structure_manager.check_structure_health()

        # Assert
        assert "score" in health
        assert "status" in health
        assert "checks" in health
        score = health.get("score", 0)
        score_int = int(score) if isinstance(score, (int, float)) else 0
        assert score_int >= 0
        assert score_int <= 100

    async def test_template_generation_workflow(self, temp_project_root: Path):
        """Test generating customized templates based on project info."""
        # Arrange
        template_manager = TemplateManager(temp_project_root)

        # Act: Generate plan template
        feature_plan = template_manager.generate_plan(
            "feature.md",
            plan_name="User Authentication",
            variables={
                "feature_name": "User Authentication",
                "description": "Add OAuth2 authentication",
            },
        )

        # Generate rule template
        coding_standards = template_manager.generate_rule(
            "coding-standards.md", variables={"language": "Python"}
        )

        # Assert
        assert "User Authentication" in feature_plan
        assert (
            "2025-12-24" in feature_plan
            or datetime.now().strftime("%Y-%m-%d") in feature_plan
        )
        assert "Python" in coding_standards
        assert len(feature_plan) > 100
        assert len(coding_standards) > 100


# ============================================================================
# Cross-Phase Integration: Complete Workflow
# ============================================================================


@pytest.mark.integration
class TestCompleteWorkflow:
    """Test complete end-to-end workflows across all phases."""

    async def test_full_analysis_to_refactoring_workflow(self, temp_project_root: Path):
        """Test complete workflow from analysis to refactoring suggestion."""
        # Arrange: Setup all required components
        fs = FileSystemManager(temp_project_root)
        metadata = MetadataIndex(temp_project_root)
        dep_graph = DependencyGraph()

        pattern_analyzer = PatternAnalyzer(temp_project_root)
        memory_bank_path = temp_project_root / ".cortex" / "memory-bank"
        memory_bank_path.mkdir(parents=True, exist_ok=True)
        structure_analyzer = StructureAnalyzer(
            temp_project_root, dep_graph, fs, metadata
        )
        insight_engine = InsightEngine(pattern_analyzer, structure_analyzer)
        refactoring_engine = RefactoringEngine(memory_bank_path)
        consolidation_detector = ConsolidationDetector(
            memory_bank_path, min_similarity=0.6
        )

        # Load metadata to index files
        _ = await metadata.load()

        # Create test files with issues
        # Large file (>50KB to trigger large file detection)
        section_content = (
            "## Section\n\n" + ("This is content for the section. " * 30) + "\n\n"
        )
        large_content = "# Large\n\n" + (section_content * 200)
        large_path = memory_bank_path / "large.md"
        _ = await fs.write_file(large_path, large_content)

        # Duplicate content (substantial to meet similarity threshold)
        shared = (
            """
## Common Section

This is shared content that appears in both documents.
The content needs to be substantial enough to meet the similarity threshold.
This section contains detailed information that is duplicated across files.
"""
            * 5
        )  # Repeat to increase similarity
        doc1_path = memory_bank_path / "doc1.md"
        _ = await fs.write_file(
            doc1_path, f"# Doc 1\n{shared}\n## Unique 1\nUnique content for doc 1.\n"
        )
        doc2_path = memory_bank_path / "doc2.md"
        _ = await fs.write_file(
            doc2_path, f"# Doc 2\n{shared}\n## Unique 2\nUnique content for doc 2.\n"
        )

        # Record usage
        await pattern_analyzer.record_access("large.md")
        await pattern_analyzer.record_access("doc1.md")
        await pattern_analyzer.record_access("doc2.md")

        # Analyze structure first to populate metadata
        _ = await metadata.load()
        _ = await structure_analyzer.analyze_file_organization()
        await metadata.save()

        # Act: Complete workflow
        # 1. Generate insights
        insights_result = await insight_engine.generate_insights(min_impact_score=0.1)
        pydantic_insights: list[InsightDict] = insights_result.insights
        insights_list: list[ModelDict] = [
            insight.model_dump(mode="json") for insight in pydantic_insights
        ]

        # 2. Detect consolidation opportunities
        consolidation_ops = await consolidation_detector.detect_opportunities(
            files=["doc1.md", "doc2.md"]
        )

        # 3. Generate refactoring suggestions
        structure_data: ModelDict = {
            "large.md": {"size": len(large_content), "sections": 50}
        }
        suggestions = await refactoring_engine.generate_suggestions(
            insights=insights_list,
            structure_data=structure_data,
        )

        # Assert: Complete workflow produces actionable results
        assert len(insights_list) > 0
        assert len(consolidation_ops) > 0
        assert len(suggestions) > 0

        # Should have split suggestion for large file
        split_suggestions = [
            s for s in suggestions if s.refactoring_type.value == "split"
        ]
        assert len(split_suggestions) > 0

        # Should have consolidation opportunity
        assert consolidation_ops[0].opportunity_type in [
            "exact_duplicate",
            "similar_content",
            "shared_section",
        ]

    async def test_structure_setup_to_content_creation_workflow(
        self, temp_project_root: Path
    ):
        """Test workflow from structure setup to content creation with templates."""
        # Arrange
        structure_manager = StructureManager(temp_project_root)
        template_manager = TemplateManager(temp_project_root)

        # Act: Complete workflow
        # 1. Setup structure
        setup_result = await structure_manager.create_structure(force=False)

        # 2. Generate initial files
        project_info: ModelDict = {
            "name": "Test Project",
            "type": "library",
            "languages": ["Python"],
            "frameworks": ["FastAPI"],
        }
        knowledge_dir = temp_project_root / ".memory-bank" / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        templates = template_manager.PLAN_TEMPLATES
        initial_files = template_manager.generate_initial_files(
            knowledge_dir, project_info, templates
        )

        # 3. Create a feature plan
        feature_plan = template_manager.generate_plan(
            "feature.md",
            plan_name="API Endpoints",
            variables={
                "feature_name": "API Endpoints",
                "description": "REST API endpoints",
            },
        )

        # Write plan to structure
        plans_dir = temp_project_root / ".memory-bank" / "plans" / "active"
        plans_dir.mkdir(parents=True, exist_ok=True)
        _ = (plans_dir / "api-endpoints.md").write_text(feature_plan)

        # Assert: Complete workflow creates organized structure with content
        assert "created_directories" in setup_result or "skipped" in setup_result
        assert len(initial_files) > 0
        assert "API Endpoints" in feature_plan

        # Verify structure
        memory_bank = temp_project_root / ".memory-bank"
        assert (memory_bank / "knowledge").exists()
        assert (memory_bank / "plans" / "active" / "api-endpoints.md").exists()
