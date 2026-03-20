"""MCP tool failure detection and protocol enforcement.

This module provides automatic detection and handling of MCP tool failures
during commit procedure execution, ensuring agents cannot bypass the protocol
by using workarounds or fallbacks.

Implementation is split across:
- ``mcp_failure_detection``  – error classification helpers
- ``mcp_failure_recovery``   – investigation-plan and roadmap helpers

This file re-exports the public API so existing imports keep working.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cortex.core.context_logging import MCPContext, log_client
from cortex.core.exceptions import MemoryBankError
from cortex.core.mcp_failure_detection import detect_failure as _detect_failure
from cortex.core.mcp_failure_recovery import (
    add_to_roadmap as _add_to_roadmap,
)
from cortex.core.mcp_failure_recovery import (
    create_investigation_plan as _create_investigation_plan,
)
from cortex.core.mcp_failure_recovery import (
    generate_user_notification as _generate_user_notification,
)
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.initialization import get_project_root

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------


class MCPToolFailure(MemoryBankError):
    """Raised when an MCP tool fails (JSON parsing, connection, unexpected behavior)."""

    def __init__(
        self,
        tool_name: str,
        error: Exception,
        step_name: str,
        message: str | None = None,
    ):
        """Initialize MCP tool failure exception.

        Args:
            tool_name: Name of the tool that failed.
            error: Original exception that occurred.
            step_name: Commit procedure step where failure occurred.
            message: Optional custom error message.
        """
        self.tool_name: str = tool_name
        self.error: Exception = error
        self.step_name: str = step_name
        error_msg = (
            message or f"MCP tool {tool_name} failed during {step_name}: {error}"
        )
        super().__init__(error_msg)


class ProtocolViolation(MemoryBankError):
    """Raised when commit procedure violates MCP tool failure protocol."""

    def __init__(self, message: str):
        """Initialize protocol violation exception.

        Args:
            message: Description of the violation.
        """
        super().__init__(f"Protocol violation: {message}")


# ------------------------------------------------------------------
# Handler (composes detection + recovery)
# ------------------------------------------------------------------


class MCPToolFailureHandler:
    """Handles MCP tool failures and enforces protocol.

    This class provides automatic detection and handling of MCP tool failures,
    ensuring that commit procedures stop immediately when tools fail and
    investigation plans are created automatically.
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize failure handler.

        Args:
            project_root: Root directory of the project (auto-detected if None).
        """
        if project_root is None:
            project_root = get_project_root(None)
            cortex_dir = get_cortex_path(project_root, CortexResourceType.CORTEX_DIR)
            if not cortex_dir.exists():
                raise ValueError(
                    f"Could not find .cortex directory at {cortex_dir}. Project root detected as: {project_root}"
                )

        self.project_root: Path = Path(project_root).resolve()
        self.plans_dir: Path = get_cortex_path(
            self.project_root, CortexResourceType.PLANS
        )

    # -- detection (delegates to mcp_failure_detection) ----------------

    async def detect_failure(
        self,
        error: Exception,
        tool_name: str,
        step_name: str,
        ctx: MCPContext | None = None,
    ) -> bool:
        """Detect if error is an MCP tool failure.

        Distinguishes between actual tool failures and expected errors.
        """
        return await _detect_failure(error, tool_name, step_name, ctx)

    # -- recovery (delegates to mcp_failure_recovery) ------------------

    async def create_investigation_plan(
        self,
        tool_name: str,
        error: Exception,
        step_name: str,
        ctx: MCPContext | None = None,
    ) -> Path:
        """Create investigation plan for tool failure."""
        return await _create_investigation_plan(
            self.plans_dir,
            self.project_root,
            tool_name,
            error,
            step_name,
            ctx,
        )

    async def add_to_roadmap(
        self,
        plan_path: Path,
        tool_name: str,
        error: Exception,
        ctx: MCPContext | None = None,
    ) -> None:
        """Add investigation plan to roadmap as blocker.

        Args:
            plan_path: Path to investigation plan file.
            tool_name: Name of the tool that failed.
            error: Exception that occurred.
            ctx: Optional MCP context for client-visible logging.
        """
        await _add_to_roadmap(self.project_root, plan_path, tool_name, error, ctx)

    # -- orchestration -------------------------------------------------

    async def handle_failure(
        self,
        tool_name: str,
        error: Exception,
        step_name: str,
        ctx: MCPContext | None = None,
    ) -> None:
        """Handle MCP tool failure according to protocol.

        This method:
        1. Creates investigation plan
        2. Adds plan to roadmap as blocker
        3. Generates user notification
        4. Raises exception to stop commit procedure

        Args:
            tool_name: Name of the tool that failed.
            error: Exception that occurred.
            step_name: Commit procedure step where failure occurred.
            ctx: Optional MCP context for client-visible logging.

        Raises:
            MCPToolFailure: Always raises to stop commit procedure.
        """
        plan_path = await self.create_investigation_plan(
            tool_name, error, step_name, ctx
        )

        try:
            await self.add_to_roadmap(plan_path, tool_name, error, ctx)
        except (OSError, MemoryBankError) as roadmap_error:
            msg = (
                f"Failed to add plan to roadmap: {roadmap_error}. "
                f"Plan created at: {plan_path}"
            )
            await log_client(ctx, "error", msg)
            logger.debug(f"Roadmap error details: {roadmap_error}")

        user_notification = _generate_user_notification(
            tool_name, error, step_name, plan_path, self.project_root
        )
        await log_client(
            ctx,
            "error",
            f"MCP tool failure: {tool_name} failed during {step_name}",
        )
        logger.debug(f"User notification: {user_notification}")

        raise MCPToolFailure(tool_name, error, step_name)
