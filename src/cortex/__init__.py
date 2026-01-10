"""MCP Memory Bank - Structured documentation system for AI assistants."""

# Core infrastructure (Phase 1)
from cortex.analysis.insight_engine import InsightEngine

# Analysis (Phase 5.1)
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex

# Linking (Phase 2)
from cortex.linking.link_parser import LinkParser
from cortex.linking.transclusion_engine import TransclusionEngine

# Managers
from cortex.managers.initialization import get_managers

# Optimization (Phase 4)
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.rules_manager import RulesManager

# Refactoring (Phase 5.2-5.4)
from cortex.refactoring.refactoring_engine import RefactoringEngine
from cortex.refactoring.refactoring_executor import RefactoringExecutor

# Rules (Phase 6)
from cortex.rules.shared_rules_manager import SharedRulesManager

# Structure (Phase 8)
from cortex.structure.structure_manager import StructureManager
from cortex.validation.quality_metrics import QualityMetrics

# Validation (Phase 3)
from cortex.validation.schema_validator import SchemaValidator

__version__ = "0.2.0"

__all__ = [
    # Analysis
    "InsightEngine",
    "PatternAnalyzer",
    # Core
    "FileSystemManager",
    "MetadataIndex",
    # Linking
    "LinkParser",
    "TransclusionEngine",
    # Managers
    "get_managers",
    # Optimization
    "ContextOptimizer",
    "QualityMetrics",
    "RulesManager",
    # Refactoring
    "RefactoringEngine",
    "RefactoringExecutor",
    # Rules
    "SharedRulesManager",
    # Structure
    "StructureManager",
    # Validation
    "SchemaValidator",
]
