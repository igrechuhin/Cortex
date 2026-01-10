"""Named constants for MCP Memory Bank.

This module centralizes all configuration constants, thresholds, and magic
numbers used throughout the codebase. Each constant is documented with its
purpose and valid range.

All constants are extracted from production code to improve maintainability
and reduce magic numbers. When modifying these values, consider the impact
on existing behavior and run the full test suite.
"""

# =============================================================================
# File Size Limits
# =============================================================================

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB - Maximum file size for processing
MAX_FILE_LINES = 400  # Maximum lines per file (maintainability rule)
MAX_FUNCTION_LINES = 30  # Maximum logical lines per function

# =============================================================================
# Token Budget Defaults
# =============================================================================

DEFAULT_TOKEN_BUDGET = 100_000  # Default context window budget
MAX_TOKEN_BUDGET = 200_000  # Maximum allowed token budget
TOKEN_RESERVE = 10_000  # Reserved tokens for system prompts
TOKENS_PER_SECTION_ESTIMATE = 500  # Estimated tokens per markdown section

# =============================================================================
# Similarity Thresholds
# =============================================================================

SIMILARITY_THRESHOLD_EXACT = 1.0  # Exact match threshold (100%)
SIMILARITY_THRESHOLD_DUPLICATE = 0.85  # Threshold for duplicate detection (85%)
SIMILARITY_THRESHOLD_SIMILAR = 0.70  # Threshold for similar content (70%)
SIMILARITY_THRESHOLD_RELATED = 0.50  # Threshold for related content (50%)

# =============================================================================
# Quality Score Weights
# =============================================================================

# Quality score is calculated as weighted sum of these components
# Total must equal 1.0 for normalized scoring
QUALITY_WEIGHT_COMPLETENESS = 0.25  # Weight for section completeness (25%)
QUALITY_WEIGHT_CONSISTENCY = 0.25  # Weight for consistency checks (25%)
QUALITY_WEIGHT_FRESHNESS = 0.15  # Weight for recent updates (15%)
QUALITY_WEIGHT_STRUCTURE = 0.20  # Weight for structural quality (20%)
QUALITY_WEIGHT_EFFICIENCY = 0.15  # Weight for token efficiency (15%)

# =============================================================================
# Relevance Scoring Weights
# =============================================================================

# Relevance score combines multiple factors with these weights
# Total must equal 1.0 for normalized scoring
RELEVANCE_WEIGHT_KEYWORD = 0.40  # Weight for keyword matches (40%)
RELEVANCE_WEIGHT_DEPENDENCY = 0.30  # Weight for dependency relevance (30%)
RELEVANCE_WEIGHT_RECENCY = 0.20  # Weight for recent modifications (20%)
RELEVANCE_WEIGHT_QUALITY = 0.10  # Weight for quality score (10%)

# =============================================================================
# Timing Constants
# =============================================================================

LOCK_TIMEOUT_SECONDS = 30  # Maximum time to wait for file lock
LOCK_POLL_INTERVAL_SECONDS = 0.1  # Interval between lock checks (100ms)
CACHE_TTL_SECONDS = 300  # Default cache TTL (5 minutes)
CACHE_MAX_SIZE = 100  # Maximum number of cached items (LRU)
REINDEX_INTERVAL_SECONDS = 60  # Interval for rule reindexing (1 minute)
GIT_OPERATION_TIMEOUT_SECONDS = 30  # Timeout for git operations

# =============================================================================
# Performance Thresholds
# =============================================================================

RATE_LIMIT_OPS_PER_SECOND = 100  # Rate limit for file operations
BATCH_SIZE_DEFAULT = 50  # Default batch size for bulk operations
MAX_CONCURRENT_OPERATIONS = 10  # Maximum concurrent async operations

# =============================================================================
# Dependency Analysis
# =============================================================================

MAX_DEPENDENCY_DEPTH = 10  # Maximum dependency chain depth to analyze
CIRCULAR_DEPENDENCY_LIMIT = 100  # Maximum cycles to report
ORPHAN_FILE_THRESHOLD_DAYS = 30  # Days without access to consider orphaned
MAX_TRANSCLUSION_DEPTH = 10  # Maximum nested transclusion depth

# =============================================================================
# Health Score Thresholds
# =============================================================================

# Health scores are on a 0-100 scale with letter grades
HEALTH_SCORE_EXCELLENT = 90  # A grade threshold (90-100)
HEALTH_SCORE_GOOD = 80  # B grade threshold (80-89)
HEALTH_SCORE_FAIR = 70  # C grade threshold (70-79)
HEALTH_SCORE_POOR = 60  # D grade threshold (60-69)
# Below POOR is F grade (0-59)

# =============================================================================
# Pattern Analysis
# =============================================================================

MIN_ACCESS_COUNT_FOR_PATTERN = 3  # Minimum accesses to establish pattern
CO_ACCESS_TIME_WINDOW_SECONDS = 300  # Time window for co-access detection (5 min)
ACCESS_LOG_MAX_ENTRIES = 10_000  # Maximum access log entries before cleanup

# =============================================================================
# Refactoring Thresholds
# =============================================================================

REFACTORING_MIN_CONFIDENCE = 0.7  # Minimum confidence for auto-suggest (70%)
CONSOLIDATION_MIN_SIMILARITY = 0.80  # Minimum similarity for consolidation (80%)
SPLIT_MIN_FILE_SIZE_LINES = 200  # Minimum lines to suggest split
SPLIT_TARGET_SECTION_LINES = 100  # Target lines per section after split

# =============================================================================
# Git and Version Control
# =============================================================================

MAX_SNAPSHOT_COUNT = 50  # Maximum version snapshots to retain per file
SNAPSHOT_CLEANUP_THRESHOLD = 100  # Clean up when snapshot count exceeds this
VERSION_HISTORY_MAX_ENTRIES = 100  # Maximum version history entries to return

# =============================================================================
# Validation Rules
# =============================================================================

MIN_SECTION_LENGTH_CHARS = 50  # Minimum characters for section to be valid
MAX_SECTION_LENGTH_CHARS = 50_000  # Maximum characters per section
REQUIRED_SECTIONS_CORE = [
    "projectBrief.md",
    "productContext.md",
    "systemPatterns.md",
    "techContext.md",
    "activeContext.md",
    "progress.md",
]  # Core memory bank files that must exist
