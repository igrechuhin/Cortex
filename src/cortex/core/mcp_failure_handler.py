"""MCP tool failure detection and protocol enforcement.

This module provides automatic detection and handling of MCP tool failures
during commit procedure execution, ensuring agents cannot bypass the protocol
by using workarounds or fallbacks.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from cortex.core.context_logging import MCPContext, log_client
from cortex.core.exceptions import MemoryBankError
from cortex.core.path_resolver import CortexResourceType, get_cortex_path

logger = logging.getLogger(__name__)

_PLAN_TEMPLATE = """# Phase: Investigate {tool_name} MCP Tool Failure

**Status**: PLANNING
**Priority**: ASAP (Blocker)
**Created**: {today}
**Target Completion**: {today}

## Goal

Investigate and fix MCP tool failure that occurred during commit procedure execution.

## Context

**Problem**: The `{tool_name}` MCP tool failed during step: **{step_name}**

**Error Details**:
- **Error Type**: `{error_type}`
- **Error Message**: `{error_message}`{cause}

**Impact**: Commit procedure blocked at step: {step_name}. This is a blocker.

## Requirements

1. **Investigate**: Analyze error, check tool implementation, verify MCP
   protocol compliance
2. **Fix**: Resolve root cause, ensure tool works via MCP protocol
3. **Verify**: Test tool, verify commit procedure proceeds, ensure no regressions

## Implementation Steps

1. Analyze error type and message, check tool implementation
2. Fix root cause, add error handling/validation
3. Add tests for failure scenarios, verify fix works

## Success Criteria

- Root cause identified and fixed
- Tool works correctly via MCP protocol
- Commit procedure can proceed, no regressions

## Notes

Auto-generated on MCP tool failure. Tool: {tool_name}, Error:
{error_type}: {error_message}
"""


def _format_error_cause(error: Exception) -> str:
    """Format error cause string for plan template."""
    if error.__cause__:
        return f"\n\n**Caused by**: {type(error.__cause__).__name__}: {error.__cause__}"
    return ""


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
            tool_name: Name of the tool that failed
            error: Original exception that occurred
            step_name: Commit procedure step where failure occurred
            message: Optional custom error message
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
            message: Description of the violation
        """
        super().__init__(f"Protocol violation: {message}")


class MCPToolFailureHandler:
    """Handles MCP tool failures and enforces protocol.

    This class provides automatic detection and handling of MCP tool failures,
    ensuring that commit procedures stop immediately when tools fail and
    investigation plans are created automatically.
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize failure handler.

        Args:
            project_root: Root directory of the project (auto-detected if None)
        """
        if project_root is None:
            # Auto-detect project root by finding .cortex directory
            project_root = Path.cwd()
            while project_root != project_root.parent:
                if get_cortex_path(
                    project_root, CortexResourceType.CORTEX_DIR
                ).exists():
                    break
                project_root = project_root.parent
            else:
                raise ValueError("Could not find .cortex directory")

        self.project_root: Path = Path(project_root).resolve()
        self.plans_dir: Path = get_cortex_path(
            self.project_root, CortexResourceType.PLANS
        )

    async def _check_json_error(
        self,
        error: Exception,
        error_str: str,
        tool_name: str,
        step_name: str,
        ctx: MCPContext | None = None,
    ) -> bool:
        """Check for JSON parsing errors."""
        if isinstance(error, json.JSONDecodeError):
            await self._log_json_error(
                ctx, tool_name, step_name, error, "JSON parsing error"
            )
            return True
        if isinstance(error, ValueError) and self._is_json_value_error(error_str):
            await self._log_json_error(
                ctx, tool_name, step_name, error, "JSON-related ValueError"
            )
            return True
        return False

    def _is_json_value_error(self, error_str: str) -> bool:
        """Check if ValueError is JSON-related."""
        json_keywords = ["json", "decode", "parse", "malformed", "invalid", "encoding"]
        return any(kw in error_str for kw in json_keywords)

    async def _log_json_error(
        self,
        ctx: MCPContext | None,
        tool_name: str,
        step_name: str,
        error: Exception,
        error_type: str,
    ) -> None:
        """Log JSON error to client and server."""
        msg = f"Detected {error_type} in {tool_name} during {step_name}: {error}"
        await log_client(ctx, "error", msg)
        logger.debug(f"{error_type} details: {error}")  # Server-side detail

    async def _check_connection_error(
        self,
        error: Exception,
        error_str: str,
        tool_name: str,
        step_name: str,
        ctx: MCPContext | None = None,
    ) -> bool:
        """Check for connection-related errors."""
        if isinstance(error, (ConnectionError, BrokenPipeError, OSError)):
            connection_keywords = [
                "connection closed",
                "connection reset",
                "broken pipe",
                "-32000",
                "stdio",
                "resource",
                "broken resource",
            ]
            if any(kw in error_str for kw in connection_keywords):
                msg = (
                    f"Detected connection error in {tool_name} during "
                    + f"{step_name}: {error}"
                )
                await log_client(ctx, "error", msg)
                logger.debug(f"Connection error details: {error}")  # Server-side detail
                return True
        return False

    async def _check_type_attribute_key_error(
        self,
        error: Exception,
        error_str: str,
        tool_name: str,
        step_name: str,
        ctx: MCPContext | None = None,
    ) -> bool:
        """Check for TypeError, AttributeError, or KeyError with unexpected behavior."""
        if not isinstance(error, (TypeError, AttributeError, KeyError)):
            return False
        unexpected_keywords = [
            "unexpected",
            "missing",
            "invalid",
            "wrong type",
            "not found",
            "cannot access",
            "has no attribute",
            "keyerror",
        ]
        if any(kw in error_str for kw in unexpected_keywords):
            msg = (
                f"Detected unexpected behavior in {tool_name} during "
                + f"{step_name}: {error}"
            )
            await log_client(ctx, "error", msg)
            logger.debug(f"Unexpected behavior details: {error}")  # Server-side detail
            return True
        return False

    async def _check_runtime_error(
        self,
        error: Exception,
        error_str: str,
        tool_name: str,
        step_name: str,
        ctx: MCPContext | None = None,
    ) -> bool:
        """Check for RuntimeError with tool-related keywords."""
        if not isinstance(error, RuntimeError):
            return False
        tool_keywords = [
            "mcp",
            "tool",
            "protocol",
            "serialization",
            "deserialization",
            "double-encoding",
            "json string instead of dict",
        ]
        if any(kw in error_str for kw in tool_keywords):
            msg = f"Detected runtime error in {tool_name} during {step_name}: {error}"
            await log_client(ctx, "error", msg)
            logger.debug(f"Runtime error details: {error}")  # Server-side detail
            return True
        return False

    async def _check_unexpected_behavior(
        self,
        error: Exception,
        error_str: str,
        tool_name: str,
        step_name: str,
        ctx: MCPContext | None = None,
    ) -> bool:
        """Check for unexpected behavior errors."""
        if await self._check_type_attribute_key_error(
            error, error_str, tool_name, step_name, ctx
        ):
            return True
        return await self._check_runtime_error(
            error, error_str, tool_name, step_name, ctx
        )

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
        error_str = str(error).lower()
        if await self._check_json_error(error, error_str, tool_name, step_name, ctx):
            return True
        if await self._check_connection_error(
            error, error_str, tool_name, step_name, ctx
        ):
            return True
        if await self._check_unexpected_behavior(
            error, error_str, tool_name, step_name, ctx
        ):
            return True
        if "fastmcp" in error_str or "mcp error" in error_str:
            msg = (
                f"Detected MCP protocol error in {tool_name} during "
                + f"{step_name}: {error}"
            )
            await log_client(ctx, "error", msg)
            logger.debug(f"MCP protocol error details: {error}")  # Server-side detail
            return True
        return False

    def _generate_plan_content(
        self, tool_name: str, error: Exception, step_name: str
    ) -> str:
        """Generate investigation plan content."""
        error_type = type(error).__name__
        error_message = str(error)
        today = datetime.now().strftime("%Y-%m-%d")
        cause = _format_error_cause(error)
        return _PLAN_TEMPLATE.format(
            tool_name=tool_name,
            step_name=step_name,
            today=today,
            error_type=error_type,
            error_message=error_message,
            cause=cause,
        )

    async def create_investigation_plan(
        self,
        tool_name: str,
        error: Exception,
        step_name: str,
        ctx: MCPContext | None = None,
    ) -> Path:
        """Create investigation plan for tool failure."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        plan_filename = f"phase-investigate-{tool_name}-failure-{timestamp}.md"
        plan_path = self.plans_dir / plan_filename
        plan_content = self._generate_plan_content(tool_name, error, step_name)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        _ = plan_path.write_text(plan_content, encoding="utf-8")
        await log_client(
            ctx,
            "info",
            f"Created investigation plan: {plan_path.relative_to(self.project_root) if plan_path.is_relative_to(self.project_root) else plan_path}",
        )
        logger.debug(f"Investigation plan details: {plan_path}")  # Server-side detail
        return plan_path

    async def add_to_roadmap(
        self,
        plan_path: Path,
        tool_name: str,
        error: Exception,
        ctx: MCPContext | None = None,
    ) -> None:
        """Add investigation plan to roadmap as blocker.

        Args:
            plan_path: Path to investigation plan file
            tool_name: Name of the tool that failed
            error: Exception that occurred
            ctx: Optional MCP context for client-visible logging
        """
        roadmap_path = self._get_roadmap_path()
        if not roadmap_path:
            await log_client(
                ctx,
                "warning",
                f"Roadmap file not found; investigation plan created at: {plan_path.relative_to(self.project_root) if plan_path.is_relative_to(self.project_root) else plan_path}",
            )
            return

        roadmap_content = roadmap_path.read_text(encoding="utf-8")
        roadmap_content = self._ensure_blockers_section(roadmap_content)
        relative_plan_path = self._get_relative_plan_path(plan_path)
        plan_entry = self._create_plan_entry(tool_name, relative_plan_path, error)
        roadmap_content = self._insert_plan_entry(roadmap_content, plan_entry)

        _ = roadmap_path.write_text(roadmap_content, encoding="utf-8")
        await log_client(
            ctx,
            "info",
            f"Added investigation plan to roadmap: {relative_plan_path}",
        )
        logger.debug(f"Roadmap update details: {plan_path}")  # Server-side detail

    def _get_roadmap_path(self) -> Path | None:
        """Get roadmap file path.

        Returns:
            Path to roadmap file, or None if not found
        """
        roadmap_path = (
            get_cortex_path(self.project_root, CortexResourceType.MEMORY_BANK)
            / "roadmap.md"
        )
        if not roadmap_path.exists():
            # Server-side logging only (file system issue)
            logger.warning(f"Roadmap file not found: {roadmap_path}")
            return None
        return roadmap_path

    def _ensure_blockers_section(self, content: str) -> str:
        """Ensure blockers section exists in roadmap.

        Args:
            content: Current roadmap content

        Returns:
            Updated roadmap content with blockers section
        """
        blockers_section = "## Blockers (ASAP Priority)"
        if blockers_section not in content:
            content += f"\n\n{blockers_section}\n\n"
        return content

    def _get_relative_plan_path(self, plan_path: Path) -> Path:
        """Get relative path from project root to plan.

        Args:
            plan_path: Absolute path to plan file

        Returns:
            Relative path, or absolute path if not relative
        """
        try:
            return plan_path.relative_to(self.project_root)
        except ValueError:
            return plan_path

    def _create_plan_entry(
        self, tool_name: str, relative_plan_path: Path, error: Exception
    ) -> str:
        """Create plan entry text for roadmap.

        Args:
            tool_name: Name of the tool that failed
            relative_plan_path: Relative path to plan file
            error: Exception that occurred

        Returns:
            Formatted plan entry text
        """
        return (
            f"- [Phase: Investigate {tool_name} MCP Tool Failure]"
            f"({relative_plan_path}) - ASAP (PLANNING) - Investigate and "
            f"fix MCP tool failure that occurred during commit procedure - "
            f"Tool: `{tool_name}`, Error: {type(error).__name__} - Impact: "
            f"Commit procedure blocked - Target completion: "
            f"{datetime.now().strftime('%Y-%m-%d')}\n"
        )

    def _insert_plan_entry(self, content: str, plan_entry: str) -> str:
        """Insert plan entry into roadmap content.

        Args:
            content: Current roadmap content
            plan_entry: Plan entry text to insert

        Returns:
            Updated roadmap content with plan entry inserted.

        Deduplicates entries that reference the same investigation plan path
        to avoid accumulating many identical blockers for the same plan.
        """
        blockers_section = "## Blockers (ASAP Priority)"

        # Extract the plan path fragment from the markdown link, if present.
        # Example entry:
        # - [Phase: Investigate foo MCP Tool Failure](.cortex/plans/phase-investigate-foo-failure-20260217-123456.md) - ASAP ...
        link_start = plan_entry.find("](")
        link_end = plan_entry.find(")", link_start + 2) if link_start != -1 else -1
        if link_start != -1 and link_end != -1:
            plan_path_fragment = plan_entry[link_start + 2 : link_end].strip()
            if plan_path_fragment:
                # If any existing blocker line already references this plan path,
                # treat the new entry as a duplicate and skip insertion.
                for line in content.split("\n"):
                    stripped = line.strip()
                    if (
                        stripped.startswith("- [Phase: Investigate ")
                        and plan_path_fragment in stripped
                    ):
                        return content

        # As an extra safety guard, avoid inserting an exact duplicate line.
        if plan_entry.strip() in content:
            return content

        insert_pos = content.find(blockers_section) + len(blockers_section)
        return content[:insert_pos] + "\n" + plan_entry + content[insert_pos:]

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
            tool_name: Name of the tool that failed
            error: Exception that occurred
            step_name: Commit procedure step where failure occurred
            ctx: Optional MCP context for client-visible logging

        Raises:
            MCPToolFailure: Always raises to stop commit procedure
        """
        # Create investigation plan
        plan_path = await self.create_investigation_plan(
            tool_name, error, step_name, ctx
        )

        # Add to roadmap
        try:
            await self.add_to_roadmap(plan_path, tool_name, error, ctx)
        except Exception as roadmap_error:
            msg = (
                f"Failed to add plan to roadmap: {roadmap_error}. "
                + f"Plan created at: {plan_path}"
            )
            await log_client(ctx, "error", msg)
            logger.debug(
                f"Roadmap error details: {roadmap_error}"
            )  # Server-side detail

        # Generate user notification (for logging, not returned since we raise)
        user_notification = self._generate_user_notification(
            tool_name, error, step_name, plan_path
        )
        await log_client(
            ctx, "error", f"MCP tool failure: {tool_name} failed during {step_name}"
        )
        logger.debug(f"User notification: {user_notification}")  # Server-side detail

        # Raise exception to stop commit procedure
        raise MCPToolFailure(tool_name, error, step_name)

    def _generate_user_notification(
        self, tool_name: str, error: Exception, step_name: str, plan_path: Path
    ) -> str:
        """Generate user notification for tool failure.

        Args:
            tool_name: Name of the tool that failed
            error: Exception that occurred
            step_name: Commit procedure step where failure occurred
            plan_path: Path to investigation plan

        Returns:
            User notification message
        """
        error_type = type(error).__name__
        error_message = str(error)

        # Create relative path for display
        try:
            relative_plan_path = plan_path.relative_to(self.project_root)
        except ValueError:
            relative_plan_path = plan_path

        notification = f"""## ⚠️ MCP Tool Failure Detected

**Tool**: `{tool_name}`
**Step**: {step_name}
**Error Type**: {error_type}
**Error Message**: {error_message}

**Impact**: Commit procedure was blocked at step: {step_name}

**Fix Recommendation**: **FIX-ASAP** priority - Tool must be fixed before
commit can proceed

**Investigation Plan**: {relative_plan_path}

**Next Steps**:
1. Review the investigation plan
2. Investigate and fix the tool failure
3. Verify the fix works via MCP protocol
4. Re-run commit procedure after fix

**Protocol**: Commit procedure stopped immediately per MCP Tool Failure
protocol. No workarounds or fallbacks allowed."""

        return notification
