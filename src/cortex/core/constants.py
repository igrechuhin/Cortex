"""Named constants for MCP Memory Bank.

This module centralizes all configuration constants, thresholds, and magic
numbers used throughout the codebase. Each constant is documented with its
purpose and valid range.

All constants are extracted from production code to improve maintainability
and reduce magic numbers. When modifying these values, consider the impact
on existing behavior and run the full test suite.
"""

from enum import StrEnum

# =============================================================================
# File Size Limits
# =============================================================================

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB - Maximum file size for processing
# Logical lines only: blanks, comments, and docstrings excluded (see
# .cortex/synapse/scripts/python/check_file_sizes.py). Same limit as CI.
MAX_FILE_LINES = 400

# MCP tool input limits (security: prevent resource exhaustion)
MAX_MANAGE_FILE_CONTENT_BYTES = MAX_FILE_SIZE_BYTES  # Same as processing limit
MAX_TASK_DESCRIPTION_CHARS = 50_000  # Max chars for load_context task_description
MAX_SECTIONS_LIST_SIZE = 100  # Max sections list length for manage_file
# Logical lines in the function body: blanks, comments, and docstrings
# excluded (see .cortex/synapse/scripts/python/check_function_lengths.py).
MAX_FUNCTION_LINES = 30

# Filenames excluded from file-size check (must match CI and local quality gate)
FILE_SIZE_EXCLUDED_FILENAMES: tuple[str, ...] = ("models.py",)  # Pydantic schema-heavy

# Maps file extension → synapse script language subdirectory.
# Used by file_language_router to dispatch quality checks per extension.
# Add a new entry here to enable quality checks for a new language.
EXTENSION_SCRIPT_MAP: dict[str, str] = {
    ".py": "python",
    ".swift": "swift",
}

# Paths excluded from function-length check (MCP dispatchers; used by pre_commit + scripts)
FUNCTION_LENGTH_EXCLUDED_PATHS: tuple[str, ...] = (
    "src/cortex/tools/plans/plan.py",
    "src/cortex/tools/plans/plan_dispatcher.py",
    "src/cortex/tools/plans/roadmap_dispatcher.py",
    "src/cortex/tools/session/sequential_thinking.py",
    "src/cortex/tools/execution/pre_commit_pipeline.py",
)

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
# MCP Connection Stability
# =============================================================================

MCP_TOOL_TIMEOUT_SECONDS = 300  # Maximum time for MCP tool execution (5 minutes)
MCP_CONNECTION_TIMEOUT_SECONDS = 30  # Timeout for stdio connection operations
MCP_ROOTS_LIST_TIMEOUT_SECONDS = 5  # Timeout for roots/list request (fallback if slow)
MCP_MAX_CONCURRENT_TOOLS = 5  # Maximum concurrent MCP tool executions
MCP_MAX_CONCURRENT_RESOURCES = (
    10  # Max concurrent resource reads (Phase 69: avoid queueing behind tools)
)
MCP_CONNECTION_RETRY_ATTEMPTS = (
    2  # Initial try + 1 retry for transient connection failures
)
MCP_CONNECTION_RETRY_DELAY_SECONDS = (
    0.5  # Delay before retry (keeps tests fast, still backs off)
)
MCP_HEALTH_CHECK_INTERVAL_SECONDS = 60  # Interval for connection health checks
MCP_RESOURCE_CACHE_TTL_SECONDS = (
    30  # TTL for cached MCP resource responses (drain queue faster)
)
MCP_USAGE_CONTEXT_INIT_LOCK_TIMEOUT_SECONDS = (
    25  # Timeout for usage context init lock acquisition (prevents indefinite hangs)
)

# MCP Tool Timeout Categories (in seconds)
MCP_TOOL_TIMEOUT_FAST = 60.0  # Fast operations: health checks, simple queries
MCP_TOOL_TIMEOUT_MEDIUM = 120.0  # Medium operations: file reads, single validations
MCP_TOOL_TIMEOUT_COMPLEX = 300.0  # Complex operations: analysis, multi-file ops
MCP_TOOL_TIMEOUT_VERY_COMPLEX = (
    960.0  # Very complex: full tests (~15min), large refactors
)
MCP_TOOL_TIMEOUT_EXTERNAL = 120.0  # External operations: network, git sync
MCP_TOOL_TIMEOUT_QUALITY_FIXES = (
    60.0  # Quality auto-fix tools (e.g. fix_quality_issues)
)

# Progress reporting (Phase 46)
PROGRESS_REPORT_INTERVAL_SECONDS = 10  # Report progress every N seconds
PROGRESS_REPORT_INTERVAL_LONG_RUNNING_SECONDS = (
    5  # Shorter interval for tools with timeout >= 300s to avoid client idle timeout
)
PROGRESS_REPORT_INTERVAL_VERY_FREQUENT_SECONDS = 2  # Very frequent interval for tools prone to connection closed errors (e.g. execute_pre_commit_checks)
PROGRESS_THRESHOLD_TIMEOUT_SECONDS = (
    120.0  # Enable progress for tools with timeout >= this
)
# Heartbeat during long markdown lint runs to avoid client idle timeout (-32000).
# 2s matches PROGRESS_REPORT_INTERVAL_VERY_FREQUENT_SECONDS to reduce connection closed errors.
MARKDOWN_LINT_PROGRESS_HEARTBEAT_SECONDS = 2
# Batch size for markdownlint invocations; reduces subprocess count and total duration.
MARKDOWN_LINT_BATCH_SIZE = 25

# =============================================================================
# Performance Thresholds
# =============================================================================

RATE_LIMIT_OPS_PER_SECOND = 100  # Rate limit for file operations
GIT_RATE_LIMIT_OPS_PER_SECOND = 10  # Rate limit for git operations (Phase 9.4)
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
HEALTH_SCORE_WARNING = 50  # D grade minimum (50-59); below is F (0-49)

# Structure health checker grade boundaries (StructureHealthChecker)
HEALTH_GRADE_B_MIN = 75  # B grade: 75-89
HEALTH_GRADE_C_MIN = 60  # C grade: 60-74
HEALTH_GRADE_D_MIN = 50  # D grade: 50-59; below 50 is F
HEALTH_INITIAL_SCORE = 100  # Starting score before deductions
HEALTH_PENALTY_PER_MISSING_DIR = 15  # Deduction per missing required directory
HEALTH_PENALTY_BROKEN_SYMLINK = 10  # Deduction per broken Cursor symlink
HEALTH_PENALTY_NO_CONFIG = 10  # Deduction when config file missing
HEALTH_PENALTY_NO_MEMORY_BANK_FILES = 5  # Deduction when no .md files in memory_bank

# =============================================================================
# Quality Metrics Scoring (Freshness, Structure, Token Efficiency)
# =============================================================================

# Freshness score by age tiers (days since last modification)
QUALITY_FRESHNESS_DAYS_RECENT = 7  # ≤7 days → 100 score
QUALITY_FRESHNESS_DAYS_OLD = 90  # 31-90 days → 60 score (8-30 days → 80)
QUALITY_FRESHNESS_DAYS_VERY_OLD = 180  # 91-180 days → 40; >180 → 20
QUALITY_FRESHNESS_SCORE_RECENT = 100.0
QUALITY_FRESHNESS_SCORE_WITHIN_ORPHAN_DAYS = 80.0  # Within ORPHAN_FILE_THRESHOLD_DAYS
QUALITY_FRESHNESS_SCORE_OLD = 60.0  # 31-90 days
QUALITY_FRESHNESS_SCORE_VERY_OLD = 40.0  # 91-180 days
QUALITY_FRESHNESS_SCORE_STALE = 20.0  # >180 days
QUALITY_FRESHNESS_SCORE_UNKNOWN = 50.0  # When last_modified is missing or parse fails

# Structure score penalties (heading hierarchy validation)
QUALITY_STRUCTURE_INITIAL_SCORE = 100.0
QUALITY_STRUCTURE_PENALTY_SKIP_LEVEL = 10  # Per heading level skip (e.g. ## to ####)
QUALITY_STRUCTURE_PENALTY_DEEP_HEADING = 5  # Per heading level > 4
QUALITY_STRUCTURE_MAX_HEADING_LEVEL = 4  # Recommended max heading depth

# Token efficiency score bands (total context tokens)
QUALITY_TOKEN_OPTIMAL_MIN = 20_000  # Optimal range start
QUALITY_TOKEN_OPTIMAL_MAX = 80_000  # Optimal range end
QUALITY_TOKEN_EFFICIENCY_FLOOR = 50.0  # Minimum score for low/high token count
QUALITY_TOKEN_EFFICIENCY_PENALTY_PER_1000 = 2  # Excess tokens penalty rate
QUALITY_TOKEN_EFFICIENCY_MAX_PENALTY = 50  # Cap on excess-token penalty

# =============================================================================
# Insight Generation Thresholds
# =============================================================================

INSIGHT_COMPLEXITY_GOOD_THRESHOLD = 80  # No complexity insight if score >= 80
INSIGHT_COMPLEXITY_SEVERITY_HIGH_THRESHOLD = 60  # "high" severity if score < 60
INSIGHT_TOKEN_SAVINGS_PER_COMPLEXITY_POINT = 50  # Estimated savings per point below 100
INSIGHT_TOKEN_SAVINGS_PER_ORPHAN = 100  # Estimated savings per orphaned file
INSIGHT_TOKEN_SAVINGS_PER_EXCESSIVE_DEP = (
    400  # Estimated savings per excessive dependency
)
INSIGHT_MAX_DEPENDENCY_DEPTH_RECOMMENDED = 5  # Recommended max dependency chain depth
INSIGHT_AVG_FILE_SIZE_RECOMMENDED_KB = 15  # Recommended average file size (KB)
INSIGHT_AVG_SIZE_THRESHOLD_KB = 20  # Trigger "large average size" insight above this
INSIGHT_TOKEN_SAVINGS_PER_KB_OVER_AVG = 100  # Estimated savings per KB over recommended

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
# Memory Bank File Names
# =============================================================================


class MemoryBankFile(StrEnum):
    """Enumeration of memory bank file names.

    Use this enum instead of hardcoded strings throughout the codebase
    to ensure consistency and enable refactoring.
    """

    PROJECT_BRIEF = "projectBrief.md"
    PRODUCT_CONTEXT = "productContext.md"
    ACTIVE_CONTEXT = "activeContext.md"
    SYSTEM_PATTERNS = "systemPatterns.md"
    TECH_CONTEXT = "techContext.md"
    PROGRESS = "progress.md"
    ROADMAP = "roadmap.md"


# =============================================================================
# Validation Rules
# =============================================================================

MIN_SECTION_LENGTH_CHARS = 50  # Minimum characters for section to be valid
MAX_SECTION_LENGTH_CHARS = 50_000  # Maximum characters per section
REQUIRED_SECTIONS_CORE: list[str] = [
    MemoryBankFile.PROJECT_BRIEF,
    MemoryBankFile.PRODUCT_CONTEXT,
    MemoryBankFile.SYSTEM_PATTERNS,
    MemoryBankFile.TECH_CONTEXT,
    MemoryBankFile.ACTIVE_CONTEXT,
    MemoryBankFile.PROGRESS,
]  # Core memory bank files that must exist
