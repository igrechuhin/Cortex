#!/usr/bin/env python3
"""Manager initialization and lifecycle management for MCP Memory Bank."""

import collections.abc
from pathlib import Path
from typing import cast

from cortex.analysis.insight_engine import InsightEngine

# Import Phase 5 modules (Self-Evolution)
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.core.dependency_graph import DependencyGraph

# Import all Phase 1 managers
from cortex.core.file_system import FileSystemManager
from cortex.core.file_watcher import FileWatcherManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.migration import MigrationManager
from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.guides.benefits import GUIDE as BENEFITS_GUIDE
from cortex.guides.setup import GUIDE as SETUP_GUIDE
from cortex.guides.structure import GUIDE as STRUCTURE_GUIDE
from cortex.guides.usage import GUIDE as USAGE_GUIDE

# Import Phase 2 modules (DRY Linking and Transclusion)
from cortex.linking.link_parser import LinkParser
from cortex.linking.link_validator import LinkValidator
from cortex.linking.transclusion_engine import TransclusionEngine
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.types import CoreManagersDict, ManagersDict
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.optimization.progressive_loader import ProgressiveLoader

# Import Phase 4 modules (Token Optimization)
from cortex.optimization.relevance_scorer import RelevanceScorer
from cortex.optimization.rules_manager import RulesManager
from cortex.optimization.summarization_engine import SummarizationEngine
from cortex.refactoring.adaptation_config import AdaptationConfig
from cortex.refactoring.approval_manager import ApprovalManager
from cortex.refactoring.consolidation_detector import ConsolidationDetector
from cortex.refactoring.learning_engine import LearningEngine

# Import Phase 5.2 modules (Refactoring Suggestions)
from cortex.refactoring.refactoring_engine import RefactoringEngine

# Import Phase 5.3-5.4 modules (Safe Execution and Learning)
from cortex.refactoring.refactoring_executor import RefactoringExecutor
from cortex.refactoring.reorganization_planner import ReorganizationPlanner
from cortex.refactoring.rollback_manager import RollbackManager
from cortex.refactoring.split_recommender import SplitRecommender

# Import Synapse manager
from cortex.rules.synapse_manager import SynapseManager
from cortex.templates.active_context import TEMPLATE as ACTIVE_CONTEXT_TEMPLATE

# Import templates and guides
from cortex.templates.memory_bank_instructions import (
    TEMPLATE as MEMORY_BANK_INSTRUCTIONS_TEMPLATE,
)
from cortex.templates.product_context import (
    TEMPLATE as PRODUCT_CONTEXT_TEMPLATE,
)
from cortex.templates.progress import TEMPLATE as PROGRESS_TEMPLATE
from cortex.templates.projectBrief import TEMPLATE as PROJECTBRIEF_TEMPLATE
from cortex.templates.system_patterns import (
    TEMPLATE as SYSTEM_PATTERNS_TEMPLATE,
)
from cortex.templates.tech_context import TEMPLATE as TECH_CONTEXT_TEMPLATE
from cortex.validation.duplication_detector import DuplicationDetector
from cortex.validation.quality_metrics import QualityMetrics
from cortex.validation.schema_validator import SchemaValidator
from cortex.validation.validation_config import ValidationConfig

# Templates dictionary for Memory Bank files
TEMPLATES = {
    "memorybankinstructions.md": MEMORY_BANK_INSTRUCTIONS_TEMPLATE,
    "projectBrief.md": PROJECTBRIEF_TEMPLATE,
    "productContext.md": PRODUCT_CONTEXT_TEMPLATE,
    "activeContext.md": ACTIVE_CONTEXT_TEMPLATE,
    "systemPatterns.md": SYSTEM_PATTERNS_TEMPLATE,
    "techContext.md": TECH_CONTEXT_TEMPLATE,
    "progress.md": PROGRESS_TEMPLATE,
}

# Guides dictionary for help content
GUIDES = {
    "setup": SETUP_GUIDE,
    "usage": USAGE_GUIDE,
    "benefits": BENEFITS_GUIDE,
    "structure": STRUCTURE_GUIDE,
}


def get_project_root(project_root: str | None = None) -> Path:
    """Get project root directory.

    When project_root is None, automatically detects the project root by walking
    up from the current working directory or script location to find a directory
    containing .cortex/. Prefers the .cortex/ closest to the starting point.

    Args:
        project_root: Optional project root path. If provided, returns resolved path.
                     If None, attempts to detect project root from .cortex/ directory.

    Returns:
        Resolved absolute path to project root
    """
    if project_root:
        return Path(project_root).resolve()

    # Try to detect project root by finding .cortex/ directory
    # Prefer script location over CWD to avoid finding wrong .cortex/ in home directory
    current = Path.cwd().resolve()

    # First, try from script location (more reliable for MCP server)
    # This helps when MCP server runs from a different directory
    try:
        import sys

        if sys.argv and sys.argv[0]:
            script_path = Path(sys.argv[0]).resolve()
            # Walk up from script location
            for path in [script_path.parent, *script_path.parent.parents]:
                cortex_dir = path / ".cortex"
                if cortex_dir.is_dir():
                    # Verify this .cortex/ has a memory-bank subdirectory
                    # (more specific check)
                    memory_bank_dir = cortex_dir / "memory-bank"
                    if memory_bank_dir.is_dir():
                        return path
    except Exception:
        pass  # Fall through to CWD check

    # Also try from current working directory
    for path in [current, *current.parents]:
        cortex_dir = path / ".cortex"
        if cortex_dir.is_dir():
            # Verify this .cortex/ has a memory-bank subdirectory (more specific check)
            memory_bank_dir = cortex_dir / "memory-bank"
            if memory_bank_dir.is_dir():
                return path

    # Fallback to current working directory if .cortex/ not found
    return current


async def get_managers(project_root: Path) -> ManagersDict:
    """Get or initialize managers for a project with lazy loading.

    Core managers (priority 1) are initialized immediately for reliability.
    Other managers are wrapped in LazyManager for on-demand initialization.

    Args:
        project_root: Project root directory

    Returns:
        ManagersDict model with manager instances (or LazyManager wrappers)
    """
    from cortex.core.manager_registry import ManagerRegistry

    registry = ManagerRegistry()
    managers_dict = await registry.get_managers(project_root)
    return ManagersDict.model_validate(managers_dict)


async def initialize_managers(project_root: Path) -> ManagersDict:
    """Initialize all managers with core managers eager and others lazy.

    Args:
        project_root: Project root directory

    Returns:
        ManagersDict model with manager instances and LazyManager wrappers
    """
    core_managers = await _init_core_managers(project_root)
    managers = ManagersDict(
        fs=core_managers.fs,
        index=core_managers.index,
        tokens=core_managers.tokens,
        graph=core_managers.graph,
        versions=core_managers.versions,
        migration=core_managers.migration,
        watcher=core_managers.watcher,
    )

    _add_linking_managers(managers, core_managers)
    _add_validation_managers(managers, project_root)
    _add_optimization_managers(managers, project_root, core_managers)
    _add_analysis_managers(managers, project_root, core_managers)
    _add_refactoring_managers(managers, project_root)
    _add_execution_managers(managers, project_root, core_managers)

    await _post_init_setup(project_root, managers)
    return managers


def _add_linking_managers(
    managers: ManagersDict, core_managers: CoreManagersDict
) -> None:
    """Add Phase 2 linking managers as lazy.

    Args:
        managers: Managers dictionary to update
        core_managers: Core managers dictionary
    """
    managers.link_parser = LazyManager(
        lambda: _create_link_parser(), name="link_parser"
    )
    managers.transclusion = LazyManager(
        lambda: _create_transclusion_engine(core_managers),
        name="transclusion",
    )
    managers.link_validator = LazyManager(
        lambda: _create_link_validator(core_managers),
        name="link_validator",
    )


def _add_validation_managers(managers: ManagersDict, project_root: Path) -> None:
    """Add Phase 3 validation managers as lazy.

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
    """
    managers.validation_config = LazyManager(
        lambda: _create_validation_config(project_root), name="validation_config"
    )
    managers.schema_validator = LazyManager(
        lambda: _create_schema_validator(project_root),
        name="schema_validator",
    )
    managers.duplication_detector = LazyManager(
        lambda: _create_duplication_detector(), name="duplication_detector"
    )
    managers.quality_metrics = LazyManager(
        lambda: _create_quality_metrics(managers), name="quality_metrics"
    )


def _make_synapse_factory(
    proj_root: Path, mgrs: ManagersDict
) -> collections.abc.Callable[[], collections.abc.Awaitable[SynapseManager]]:
    """Create factory function for SynapseManager.

    Args:
        proj_root: Project root directory
        mgrs: Managers dictionary

    Returns:
        Factory function that creates SynapseManager
    """

    async def factory() -> SynapseManager:
        return await _create_synapse_manager(proj_root, mgrs)

    return factory


def _add_optimization_managers(
    managers: ManagersDict,
    project_root: Path,
    core_managers: CoreManagersDict,
) -> None:
    """Add Phase 4 optimization managers as lazy.

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
        core_managers: Core managers dictionary
    """
    managers.optimization_config = LazyManager(
        lambda: _create_optimization_config(project_root), name="optimization_config"
    )
    managers.relevance_scorer = LazyManager(
        lambda: _create_relevance_scorer(core_managers, managers),
        name="relevance_scorer",
    )
    managers.context_optimizer = LazyManager(
        lambda: _create_context_optimizer(core_managers, managers),
        name="context_optimizer",
    )
    managers.progressive_loader = LazyManager(
        lambda: _create_progressive_loader(core_managers, managers),
        name="progressive_loader",
    )
    managers.summarization_engine = LazyManager(
        lambda: _create_summarization_engine(core_managers),
        name="summarization_engine",
    )
    managers.rules_manager = LazyManager(
        lambda: _create_rules_manager(project_root, core_managers, managers),
        name="rules_manager",
    )
    managers.synapse = LazyManager(
        _make_synapse_factory(project_root, managers), name="synapse"
    )


def _add_analysis_managers(
    managers: ManagersDict,
    project_root: Path,
    core_managers: CoreManagersDict,
) -> None:
    """Add Phase 5.1 analysis managers as lazy.

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
        core_managers: Core managers dictionary
    """
    managers.pattern_analyzer = LazyManager(
        lambda: _create_pattern_analyzer(project_root), name="pattern_analyzer"
    )
    managers.structure_analyzer = LazyManager(
        lambda: _create_structure_analyzer(project_root, core_managers),
        name="structure_analyzer",
    )
    managers.insight_engine = LazyManager(
        lambda: _create_insight_engine(managers), name="insight_engine"
    )


def _add_refactoring_managers(managers: ManagersDict, project_root: Path) -> None:
    """Add Phase 5.2 refactoring managers as lazy.

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
    """
    managers.refactoring_engine = LazyManager(
        lambda: _create_refactoring_engine(project_root, managers),
        name="refactoring_engine",
    )
    managers.consolidation_detector = LazyManager(
        lambda: _create_consolidation_detector(project_root),
        name="consolidation_detector",
    )
    managers.split_recommender = LazyManager(
        lambda: _create_split_recommender(project_root), name="split_recommender"
    )
    managers.reorganization_planner = LazyManager(
        lambda: _create_reorganization_planner(project_root),
        name="reorganization_planner",
    )


def _add_execution_managers(
    managers: ManagersDict,
    project_root: Path,
    core_managers: CoreManagersDict,
) -> None:
    """Add Phase 5.3-5.4 execution managers as lazy.

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
        core_managers: Core managers dictionary
    """
    managers.refactoring_executor = LazyManager(
        lambda: _create_refactoring_executor(project_root, core_managers, managers),
        name="refactoring_executor",
    )
    managers.approval_manager = LazyManager(
        lambda: _create_approval_manager(project_root),
        name="approval_manager",
    )
    managers.rollback_manager = LazyManager(
        lambda: _create_rollback_manager(project_root, core_managers),
        name="rollback_manager",
    )
    managers.learning_engine = LazyManager(
        lambda: _create_learning_engine(project_root, managers), name="learning_engine"
    )
    managers.adaptation_config = LazyManager(
        lambda: _create_adaptation_config(managers), name="adaptation_config"
    )


async def _init_core_managers(project_root: Path) -> CoreManagersDict:
    """Initialize core managers that are always needed (priority 1).

    Args:
        project_root: Project root directory

    Returns:
        Dictionary of initialized core managers
    """
    fs = FileSystemManager(project_root)
    index = MetadataIndex(project_root)
    tokens = TokenCounter()
    graph = DependencyGraph()
    versions = VersionManager(project_root)
    migration = MigrationManager(project_root)
    watcher = FileWatcherManager()

    from cortex.managers.types import CoreManagersDict

    return CoreManagersDict(
        fs=fs,
        index=index,
        tokens=tokens,
        graph=graph,
        versions=versions,
        migration=migration,
        watcher=watcher,
    )


# Factory functions for lazy manager creation


async def _create_link_parser() -> LinkParser:
    """Create LinkParser instance."""
    return LinkParser()


async def _create_transclusion_engine(
    core_managers: CoreManagersDict,
) -> TransclusionEngine:
    """Create TransclusionEngine instance."""
    fs_manager = core_managers.fs
    link_parser = LinkParser()
    return TransclusionEngine(
        file_system=fs_manager,
        link_parser=link_parser,
        max_depth=5,
        cache_enabled=True,
    )


async def _create_link_validator(core_managers: CoreManagersDict) -> LinkValidator:
    """Create LinkValidator instance."""
    fs_manager = core_managers.fs
    link_parser = LinkParser()
    return LinkValidator(file_system=fs_manager, link_parser=link_parser)


async def _create_optimization_config(project_root: Path) -> OptimizationConfig:
    """Create OptimizationConfig instance."""
    return OptimizationConfig(project_root)


async def _create_relevance_scorer(
    core_managers: CoreManagersDict, managers: ManagersDict
) -> RelevanceScorer:
    """Create RelevanceScorer instance."""
    from cortex.managers.manager_utils import get_manager

    dep_graph = core_managers.graph
    metadata_index = core_managers.index
    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    return RelevanceScorer(
        dependency_graph=dep_graph,
        metadata_index=metadata_index,
        **optimization_config.get_relevance_weights(),
    )


async def _create_context_optimizer(
    core_managers: CoreManagersDict, managers: ManagersDict
) -> ContextOptimizer:
    """Create ContextOptimizer instance."""
    from cortex.managers.manager_utils import get_manager

    token_counter = core_managers.tokens
    dep_graph = core_managers.graph
    relevance_scorer = await get_manager(managers, "relevance_scorer", RelevanceScorer)
    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    return ContextOptimizer(
        token_counter=token_counter,
        relevance_scorer=relevance_scorer,
        dependency_graph=dep_graph,
        mandatory_files=optimization_config.get_mandatory_files(),
    )


async def _create_progressive_loader(
    core_managers: CoreManagersDict, managers: ManagersDict
) -> ProgressiveLoader:
    """Create ProgressiveLoader instance."""
    from cortex.managers.manager_utils import get_manager

    fs_manager = core_managers.fs
    metadata_index = core_managers.index
    context_optimizer = await get_manager(
        managers, "context_optimizer", ContextOptimizer
    )

    return ProgressiveLoader(
        file_system=fs_manager,
        context_optimizer=context_optimizer,
        metadata_index=metadata_index,
    )


async def _create_summarization_engine(
    core_managers: CoreManagersDict,
) -> SummarizationEngine:
    """Create SummarizationEngine instance."""
    token_counter = core_managers.tokens
    metadata_index = core_managers.index

    return SummarizationEngine(
        token_counter=token_counter, metadata_index=metadata_index
    )


async def _create_rules_manager(
    project_root: Path, core_managers: CoreManagersDict, managers: ManagersDict
) -> RulesManager:
    """Create RulesManager instance."""
    from cortex.managers.manager_utils import get_manager

    fs_manager = core_managers.fs
    metadata_index = core_managers.index
    token_counter = core_managers.tokens
    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    return RulesManager(
        project_root=project_root,
        file_system=fs_manager,
        metadata_index=metadata_index,
        token_counter=token_counter,
        rules_folder=(
            optimization_config.get_rules_folder()
            if optimization_config.is_rules_enabled()
            else None
        ),
        reindex_interval_minutes=optimization_config.get_rules_reindex_interval(),
    )


async def _create_synapse_manager(
    project_root: Path, managers: ManagersDict
) -> SynapseManager:
    """Create SynapseManager instance."""
    from cortex.managers.manager_utils import get_manager

    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    synapse_folder = optimization_config.get_synapse_folder()

    return SynapseManager(
        project_root=project_root,
        synapse_folder=synapse_folder,
    )


async def _create_pattern_analyzer(project_root: Path) -> PatternAnalyzer:
    """Create PatternAnalyzer instance."""
    return PatternAnalyzer(project_root)


async def _create_structure_analyzer(
    project_root: Path, core_managers: CoreManagersDict
) -> StructureAnalyzer:
    """Create StructureAnalyzer instance."""
    dep_graph = core_managers.graph
    fs_manager = core_managers.fs
    metadata_index = core_managers.index

    return StructureAnalyzer(
        project_root=project_root,
        dependency_graph=dep_graph,
        file_system=fs_manager,
        metadata_index=metadata_index,
    )


async def _create_insight_engine(managers: ManagersDict) -> InsightEngine:
    """Create InsightEngine instance."""
    from cortex.managers.manager_utils import get_manager

    pattern_analyzer = await get_manager(managers, "pattern_analyzer", PatternAnalyzer)
    structure_analyzer = await get_manager(
        managers, "structure_analyzer", StructureAnalyzer
    )

    return InsightEngine(
        pattern_analyzer=pattern_analyzer, structure_analyzer=structure_analyzer
    )


async def _create_refactoring_engine(
    project_root: Path, managers: ManagersDict
) -> RefactoringEngine:
    """Create RefactoringEngine instance."""
    from cortex.managers.manager_utils import get_manager

    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

    return RefactoringEngine(
        memory_bank_path=memory_bank_path,
        min_confidence=cast(
            float,
            optimization_config.get("self_evolution.suggestions.min_confidence", 0.7),
        ),
        max_suggestions_per_run=cast(
            int,
            optimization_config.get(
                "self_evolution.suggestions.max_suggestions_per_run", 10
            ),
        ),
    )


async def _create_consolidation_detector(
    project_root: Path,
) -> ConsolidationDetector:
    """Create ConsolidationDetector instance."""
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    return ConsolidationDetector(
        memory_bank_path=memory_bank_path,
        min_similarity=0.80,
        min_section_length=100,
        target_reduction=0.30,
    )


async def _create_split_recommender(project_root: Path) -> SplitRecommender:
    """Create SplitRecommender instance."""
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    return SplitRecommender(
        memory_bank_path=memory_bank_path,
        max_file_size=5000,
        max_sections=10,
        min_section_independence=0.6,
    )


async def _create_reorganization_planner(
    project_root: Path,
) -> ReorganizationPlanner:
    """Create ReorganizationPlanner instance."""
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    return ReorganizationPlanner(
        memory_bank_path=memory_bank_path,
        max_dependency_depth=5,
        enable_categories=True,
    )


async def _create_refactoring_executor(
    project_root: Path, core_managers: CoreManagersDict, managers: ManagersDict
) -> RefactoringExecutor:
    """Create RefactoringExecutor instance."""
    from cortex.managers.manager_utils import get_manager

    fs_manager = core_managers.fs
    metadata_index = core_managers.index
    version_manager = core_managers.versions
    link_validator = await get_manager(managers, "link_validator", LinkValidator)
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

    return RefactoringExecutor(
        memory_bank_dir=memory_bank_path,
        fs_manager=fs_manager,
        version_manager=version_manager,
        link_validator=link_validator,
        metadata_index=metadata_index,
        config=None,
    )


async def _create_approval_manager(
    project_root: Path,
) -> ApprovalManager:
    """Create ApprovalManager instance."""
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

    return ApprovalManager(memory_bank_dir=memory_bank_path, config=None)


async def _create_rollback_manager(
    project_root: Path, core_managers: CoreManagersDict
) -> RollbackManager:
    """Create RollbackManager instance."""
    fs_manager = core_managers.fs
    version_manager = core_managers.versions
    metadata_index = core_managers.index
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

    return RollbackManager(
        memory_bank_dir=memory_bank_path,
        fs_manager=fs_manager,
        version_manager=version_manager,
        metadata_index=metadata_index,
        config=None,
    )


async def _create_learning_engine(
    project_root: Path, managers: ManagersDict
) -> LearningEngine:
    """Create LearningEngine instance."""
    from cortex.managers.manager_utils import get_manager

    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

    return LearningEngine(
        memory_bank_dir=memory_bank_path,
        config=cast(ModelDict, optimization_config.get("self_evolution.learning", {})),
    )


async def _create_validation_config(project_root: Path) -> ValidationConfig:
    """Create ValidationConfig instance."""
    return ValidationConfig(project_root)


async def _create_schema_validator(
    project_root: Path,
) -> SchemaValidator:
    """Create SchemaValidator instance."""

    return SchemaValidator(config_path=project_root / ".cortex" / "validation.json")


async def _create_duplication_detector() -> DuplicationDetector:
    """Create DuplicationDetector instance."""

    return DuplicationDetector()


async def _create_quality_metrics(managers: ManagersDict) -> QualityMetrics:
    """Create QualityMetrics instance."""
    from cortex.managers.manager_utils import get_manager

    schema_validator = await get_manager(managers, "schema_validator", SchemaValidator)
    metadata_index = managers.index
    return QualityMetrics(
        schema_validator=schema_validator, metadata_index=metadata_index
    )


async def _create_adaptation_config(managers: ManagersDict) -> AdaptationConfig:
    """Create AdaptationConfig instance."""
    # AdaptationConfig uses a dedicated schema (learning/feedback/etc.) and should
    # not be hydrated from OptimizationConfig's `self_evolution` section.
    return AdaptationConfig(base_config=None)


async def _post_init_setup(project_root: Path, managers: ManagersDict) -> None:
    """Perform post-initialization setup tasks for core managers.

    Args:
        project_root: Project root directory
        managers: Dictionary of manager instances and LazyManager wrappers
    """
    from cortex.managers.manager_utils import get_manager

    metadata_index = managers.index
    fs_manager = managers.fs

    # Load metadata index if it exists
    index_path = project_root / ".cortex" / "index.json"
    if index_path.exists():
        try:
            _ = await metadata_index.load()
        except Exception:
            # If load fails, metadata_index will auto-rebuild
            pass

    # Clean up stale locks
    await fs_manager.cleanup_locks()

    # Initialize rules manager if enabled (only if needed)
    # This will trigger lazy initialization if optimization_config is accessed
    try:
        optimization_config = await get_manager(
            managers, "optimization_config", OptimizationConfig
        )
        if optimization_config.is_rules_enabled():
            rules_manager = await get_manager(managers, "rules_manager", RulesManager)
            _ = await rules_manager.initialize()
    except Exception:
        # Don't fail if rules initialization fails
        pass


async def handle_file_change(file_path: Path, event_type: str) -> None:
    """Callback for file watcher to handle external file changes.

    This function is called when files are modified externally (outside MCP).
    It updates metadata and creates version snapshots if needed.

    Args:
        file_path: Path to changed file
        event_type: Type of change ('created', 'modified', 'deleted')
    """
    try:
        project_root = file_path.parent.parent  # memory-bank/file.md -> project_root
        mgrs = await get_managers(project_root)

        file_name = file_path.name
        metadata_index = mgrs.index
        fs_manager = mgrs.fs
        token_counter = mgrs.tokens

        if event_type == "deleted":
            await _handle_deleted_file(metadata_index, file_name, file_path)
        else:
            await _handle_modified_file(
                metadata_index, fs_manager, token_counter, file_name, file_path
            )
    except Exception:
        # Silently fail - don't disrupt file watcher
        pass


async def _handle_deleted_file(
    metadata_index: MetadataIndex, file_name: str, file_path: Path
) -> None:
    """Handle deleted file event."""
    await metadata_index.update_file_metadata(
        file_name=file_name,
        path=file_path,
        exists=False,
        size_bytes=0,
        token_count=0,
        content_hash="",
        sections=[],
        change_source="external",
    )


async def _handle_modified_file(
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
    file_name: str,
    file_path: Path,
) -> None:
    """Handle created or modified file event."""
    content, content_hash = await fs_manager.read_file(file_path)
    sections_raw = fs_manager.parse_sections(content)
    sections = [section.model_dump(mode="json") for section in sections_raw]
    token_count = token_counter.count_tokens(content)

    await metadata_index.update_file_metadata(
        file_name=file_name,
        path=file_path,
        exists=True,
        size_bytes=len(content.encode("utf-8")),
        token_count=token_count,
        content_hash=content_hash,
        sections=sections,
        change_source="external",
    )
