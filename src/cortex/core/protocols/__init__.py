#!/usr/bin/env python3
"""Protocol definitions for MCP Memory Bank.

All protocols are re-exported from this module for convenience.
Import structure:
    from cortex.core.protocols import FileSystemProtocol

This works because __init__.py re-exports all protocols from submodules.
"""

# File system protocols
# Analysis protocols
from cortex.core.protocols.analysis import (
    PatternAnalyzerProtocol,
    StructureAnalyzerProtocol,
)
from cortex.core.protocols.file_system import (
    FileSystemProtocol,
    MetadataIndexProtocol,
)

# Linking protocols
from cortex.core.protocols.linking import (
    LinkParserProtocol,
    LinkValidatorProtocol,
    TransclusionEngineProtocol,
)

# Progressive loading and summarization protocols
from cortex.core.protocols.loading import (
    ProgressiveLoaderProtocol,
    SummarizationEngineProtocol,
)

# Optimization protocols
from cortex.core.protocols.optimization import (
    ContextOptimizerProtocol,
    RelevanceScorerProtocol,
)

# Refactoring protocols
from cortex.core.protocols.refactoring import (
    ConsolidationDetectorProtocol,
    RefactoringEngineProtocol,
    ReorganizationPlannerProtocol,
    SplitRecommenderProtocol,
)

# Refactoring execution protocols
from cortex.core.protocols.refactoring_execution import (
    ApprovalManagerProtocol,
    LearningEngineProtocol,
    RollbackManagerProtocol,
)

# Rules protocols
from cortex.core.protocols.rules import (
    RulesManagerProtocol,
)

# Token and dependency protocols
from cortex.core.protocols.token import (
    DependencyGraphProtocol,
    TokenCounterProtocol,
)

# Version management protocols
from cortex.core.protocols.versioning import (
    VersionManagerProtocol,
)

__all__ = [
    # File system
    "FileSystemProtocol",
    "MetadataIndexProtocol",
    # Token and dependency
    "TokenCounterProtocol",
    "DependencyGraphProtocol",
    # Linking
    "LinkParserProtocol",
    "TransclusionEngineProtocol",
    "LinkValidatorProtocol",
    # Versioning
    "VersionManagerProtocol",
    # Optimization
    "RelevanceScorerProtocol",
    "ContextOptimizerProtocol",
    "ProgressiveLoaderProtocol",
    "SummarizationEngineProtocol",
    # Analysis
    "PatternAnalyzerProtocol",
    "StructureAnalyzerProtocol",
    # Refactoring
    "RefactoringEngineProtocol",
    "ConsolidationDetectorProtocol",
    "SplitRecommenderProtocol",
    "ReorganizationPlannerProtocol",
    # Refactoring execution
    "ApprovalManagerProtocol",
    "RollbackManagerProtocol",
    "LearningEngineProtocol",
    # Rules
    "RulesManagerProtocol",
]
