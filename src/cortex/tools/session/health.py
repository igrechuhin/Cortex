"""Session health calculation and MCP health check for session_start.

Extracted from session_start_tools to keep file size under 400 lines.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.metadata_index import MetadataIndex
from cortex.managers.types import ManagersDict
from cortex.managers.utils import get_manager
from cortex.tools.connection_health import check_mcp_connection_health
from cortex.tools.models import (
    MCPHealthCheckResponse,
    SessionHealthSummary,
)
from cortex.tools.session_models import TokenBudgetStatus

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
    )


def parse_mcp_health(health_json: str) -> tuple[bool, str | None]:
    """Parse check_mcp_connection_health JSON; return (healthy, message)."""
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
        health_json = await check_mcp_connection_health()
        return parse_mcp_health(health_json)
    except Exception as e:
        logger.debug("MCP health check failed: %s", e)
        return False, str(e) or "MCP health check failed"
