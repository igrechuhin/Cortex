"""Session health calculation and MCP health check for session_start.

Extracted from session_start_tools to keep file size under 400 lines.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cortex.core.constants import (
    CONTEXT_OCCUPANCY_CRITICAL_PERCENT,
    CONTEXT_OCCUPANCY_WARN_PERCENT,
    DEFAULT_CONTEXT_WINDOW_TOKENS,
    DEFAULT_SESSION_SPEND_BUDGET,
    MemoryBankFile,
)
from cortex.core.metadata_index import MetadataIndex
from cortex.managers.types import ManagersDict
from cortex.managers.utils import get_manager
from cortex.tools.session.connection_health import health_check
from cortex.tools.session.connection_models import MCPHealthCheckResponse
from cortex.tools.session.context_usage_store import read_context_usage
from cortex.tools.session.models import (
    ContextOccupancyStatus,
    ContextOccupancySummary,
    SessionHealthSummary,
    SessionSpendStatus,
    SessionSpendSummary,
    TokenBudgetStatus,
)

logger = logging.getLogger(__name__)

_REQUIRED_FILES = [
    MemoryBankFile.PROJECT_BRIEF,
    MemoryBankFile.ACTIVE_CONTEXT,
    MemoryBankFile.ROADMAP,
    MemoryBankFile.PROGRESS,
    MemoryBankFile.SYSTEM_PATTERNS,
    MemoryBankFile.TECH_CONTEXT,
    MemoryBankFile.PRODUCT_CONTEXT,
]


def determine_token_budget_status(
    total_tokens: int, default_budget: int = 80000
) -> TokenBudgetStatus:
    """Determine token budget status from usage."""
    token_usage_percent = (
        (total_tokens / default_budget * 100) if default_budget > 0 else 0
    )
    if token_usage_percent >= 100:
        return TokenBudgetStatus.OVER_BUDGET
    if token_usage_percent >= 85:
        return TokenBudgetStatus.WARNING
    return TokenBudgetStatus.HEALTHY


def determine_spend_status(
    cumulative_tokens: int, budget: int = DEFAULT_SESSION_SPEND_BUDGET
) -> SessionSpendStatus:
    """Determine runtime spend status from accumulated tool-output tokens.

    Mirrors `determine_token_budget_status()` but for the runtime spend
    tracker (`core.session_logger.record_spend_tokens`) instead of static
    memory-bank file size.
    """
    spend_percent = (cumulative_tokens / budget * 100) if budget > 0 else 0
    if spend_percent >= 100:
        return SessionSpendStatus.OVER_BUDGET
    if spend_percent >= 85:
        return SessionSpendStatus.WARNING
    return SessionSpendStatus.HEALTHY


def determine_occupancy_status(
    used_tokens: int, limit_tokens: int
) -> ContextOccupancyStatus:
    """Determine live context-window occupancy from a harness snapshot.

    Mirrors `determine_spend_status()` but for harness-reported context
    occupancy (`tools/session.context_usage_store`) instead of
    Cortex-recorded tool-output tokens. A non-positive limit is schema
    drift, not an occupancy reading, so it renders UNAVAILABLE.
    """
    if limit_tokens <= 0:
        return ContextOccupancyStatus.UNAVAILABLE
    occupancy_percent = used_tokens / limit_tokens * 100
    if occupancy_percent >= CONTEXT_OCCUPANCY_CRITICAL_PERCENT:
        return ContextOccupancyStatus.CRITICAL
    if occupancy_percent >= CONTEXT_OCCUPANCY_WARN_PERCENT:
        return ContextOccupancyStatus.WARNING
    return ContextOccupancyStatus.HEALTHY


def _unavailable_occupancy_summary() -> ContextOccupancySummary:
    """UNAVAILABLE summary for a missing or stale snapshot (never an estimate)."""
    return ContextOccupancySummary(
        used_tokens=0,
        limit_tokens=DEFAULT_CONTEXT_WINDOW_TOKENS,
        as_of=0.0,
        occupancy_status=ContextOccupancyStatus.UNAVAILABLE,
    )


async def _calculate_occupancy_summary(
    project_root: Path,
) -> ContextOccupancySummary:
    """Build the occupancy summary from this session's bound snapshot."""
    from cortex.core.session_logger import get_session_log_path, read_session_log

    session_log = read_session_log(get_session_log_path(project_root))
    # AI: the SessionStart hook capture is the only trusted binding between
    # this MCP session and a harness window. Without it — or when the bound
    # window has no fresh snapshot — occupancy is UNAVAILABLE rather than
    # attributed to whichever session wrote to disk last.
    expected = session_log.host_session_id if session_log else None
    snapshot = await read_context_usage(project_root, expected)
    if snapshot is None:
        return _unavailable_occupancy_summary()
    return ContextOccupancySummary(
        used_tokens=snapshot.used_tokens,
        limit_tokens=snapshot.limit_tokens,
        as_of=snapshot.as_of,
        host_session_id=snapshot.session_id,
        occupancy_status=determine_occupancy_status(
            snapshot.used_tokens, snapshot.limit_tokens
        ),
    )


def _calculate_spend_summary(project_root: Path) -> SessionSpendSummary:
    """Read the current session's cumulative runtime spend from its log."""
    from cortex.core.session_logger import get_session_log_path, read_session_log

    session_log = read_session_log(get_session_log_path(project_root))
    cumulative = session_log.cumulative_spend_tokens if session_log else 0
    return SessionSpendSummary(
        cumulative_tokens=cumulative,
        budget=DEFAULT_SESSION_SPEND_BUDGET,
        spend_status=determine_spend_status(cumulative, DEFAULT_SESSION_SPEND_BUDGET),
    )


async def _count_file_tokens(metadata_index: MetadataIndex, file_name: str) -> int:
    """Get token count for a file from metadata."""
    metadata = await metadata_index.get_file_metadata(file_name)
    if metadata is not None:
        return metadata.token_count
    return 0


async def _check_file_and_count_tokens(
    metadata_index: MetadataIndex,
    memory_bank_dir: Path,
    file_name: str,
) -> tuple[bool, int]:
    """Check if file exists and get its token count."""
    file_path = memory_bank_dir / file_name
    if file_path.exists():
        return True, await _count_file_tokens(metadata_index, file_name)
    return False, 0


async def calculate_health_summary(
    managers: ManagersDict,
    project_root: Path,
) -> SessionHealthSummary:
    """Calculate health summary for session start."""
    from cortex.core.file_system import FileSystemManager

    fs_manager: FileSystemManager = await get_manager(managers, "fs", FileSystemManager)
    metadata_index: MetadataIndex = await get_manager(managers, "index", MetadataIndex)

    file_count = 0
    total_tokens = 0
    missing_files: list[str] = []

    for file_name in _REQUIRED_FILES:
        exists, tokens = await _check_file_and_count_tokens(
            metadata_index, fs_manager.memory_bank_dir, file_name
        )
        if exists:
            file_count += 1
            total_tokens += tokens
        else:
            missing_files.append(file_name)

    return SessionHealthSummary(
        file_count=file_count,
        total_tokens=total_tokens,
        token_budget_status=determine_token_budget_status(total_tokens),
        missing_files=missing_files,
        has_errors=len(missing_files) > 0,
        spend=_calculate_spend_summary(project_root),
        context_occupancy=await _calculate_occupancy_summary(project_root),
    )


def parse_mcp_health(health_json: str) -> tuple[bool, str | None]:
    """Parse health_check JSON; return (healthy, message)."""
    import json

    from pydantic import ValidationError

    try:
        data = MCPHealthCheckResponse.model_validate_json(health_json)
        if data.status != "success":
            return False, data.error or "MCP health check failed"
        if data.health is None:
            return False, "MCP health check response invalid"
        if data.health.healthy:
            return True, None
        return False, "MCP connection unhealthy"
    except (json.JSONDecodeError, TypeError, ValidationError):
        return False, "MCP health check response invalid"


async def get_mcp_health_status() -> tuple[bool, str | None]:
    """Run MCP health check; return (healthy, message)."""
    try:
        health_json = await health_check()
        return parse_mcp_health(health_json)
    except Exception as e:
        logger.debug("MCP health check failed: %s", e)
        return False, str(e) or "MCP health check failed"
