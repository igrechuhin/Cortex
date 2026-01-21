"""MCP tool failure detection and protocol enforcement.

This module provides automatic detection and handling of MCP tool failures
during commit procedure execution, ensuring agents cannot bypass the protocol
by using workarounds or fallbacks.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from cortex.core.exceptions import MemoryBankError
from cortex.core.path_resolver import CortexResourceType, get_cortex_path

logger = logging.getLogger(__name__)


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
                if (project_root / ".cortex").exists():
                    break
                project_root = project_root.parent
            else:
                raise ValueError("Could not find .cortex directory")

        self.project_root: Path = Path(project_root).resolve()
        self.plans_dir: Path = get_cortex_path(
            self.project_root, CortexResourceType.PLANS
        )

    def _check_json_error(
        self, error: Exception, error_str: str, tool_name: str, step_name: str
    ) -> bool:
        """Check for JSON parsing errors."""
        if isinstance(error, json.JSONDecodeError):
            logger.error(
                f"Detected JSON parsing error in {tool_name} during {step_name}: {error}"
            )
            return True
        if isinstance(error, ValueError):
            json_keywords = [
                "json",
                "decode",
                "parse",
                "malformed",
                "invalid",
                "encoding",
            ]
            if any(kw in error_str for kw in json_keywords):
                logger.error(
                    f"Detected JSON-related ValueError in {tool_name} during {step_name}: {error}"
                )
                return True
        return False

    def _check_connection_error(
        self, error: Exception, error_str: str, tool_name: str, step_name: str
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
                logger.error(
                    f"Detected connection error in {tool_name} during {step_name}: {error}"
                )
                return True
        return False

    def _check_type_attribute_key_error(
        self, error: Exception, error_str: str, tool_name: str, step_name: str
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
            logger.error(
                f"Detected unexpected behavior in {tool_name} during {step_name}: {error}"
            )
            return True
        return False

    def _check_runtime_error(
        self, error: Exception, error_str: str, tool_name: str, step_name: str
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
            logger.error(
                f"Detected runtime error in {tool_name} during {step_name}: {error}"
            )
            return True
        return False

    def _check_unexpected_behavior(
        self, error: Exception, error_str: str, tool_name: str, step_name: str
    ) -> bool:
        """Check for unexpected behavior errors."""
        if self._check_type_attribute_key_error(error, error_str, tool_name, step_name):
            return True
        return self._check_runtime_error(error, error_str, tool_name, step_name)

    def detect_failure(self, error: Exception, tool_name: str, step_name: str) -> bool:
        """Detect if error is an MCP tool failure.

        Distinguishes between actual tool failures and expected errors.
        """
        error_str = str(error).lower()
        if self._check_json_error(error, error_str, tool_name, step_name):
            return True
        if self._check_connection_error(error, error_str, tool_name, step_name):
            return True
        if self._check_unexpected_behavior(error, error_str, tool_name, step_name):
            return True
        if "fastmcp" in error_str or "mcp error" in error_str:
            logger.error(
                f"Detected MCP protocol error in {tool_name} during {step_name}: {error}"
            )
            return True
        return False

    def _generate_plan_content(
        self, tool_name: str, error: Exception, step_name: str
    ) -> str:
        """Generate investigation plan content."""
        error_type = type(error).__name__
        error_message = str(error)
        today = datetime.now().strftime("%Y-%m-%d")
        cause = (
            f"\n\n**Caused by**: {type(error.__cause__).__name__}: {error.__cause__}"
            if error.__cause__
            else ""
        )
        return f"""# Phase: Investigate {tool_name} MCP Tool Failure

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

1. **Investigate**: Analyze error, check tool implementation, verify MCP protocol compliance
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

Auto-generated on MCP tool failure. Tool: {tool_name}, Error: {error_type}: {error_message}
"""

    def create_investigation_plan(
        self, tool_name: str, error: Exception, step_name: str
    ) -> Path:
        """Create investigation plan for tool failure."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        plan_filename = f"phase-investigate-{tool_name}-failure-{timestamp}.md"
        plan_path = self.plans_dir / plan_filename
        plan_content = self._generate_plan_content(tool_name, error, step_name)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        _ = plan_path.write_text(plan_content, encoding="utf-8")
        logger.info(f"Created investigation plan: {plan_path}")
        return plan_path

    def add_to_roadmap(self, plan_path: Path, tool_name: str, error: Exception) -> None:
        """Add investigation plan to roadmap as blocker.

        Args:
            plan_path: Path to investigation plan file
            tool_name: Name of the tool that failed
            error: Exception that occurred
        """
        # Note: This method should use manage_file() MCP tool, but since we're
        # in a failure handler, we use standard file tools as fallback
        # The commit procedure will use MCP tools, but failure handling needs
        # to work even when MCP tools are broken
        roadmap_path = (
            get_cortex_path(self.project_root, CortexResourceType.MEMORY_BANK)
            / "roadmap.md"
        )

        if not roadmap_path.exists():
            logger.warning(f"Roadmap file not found: {roadmap_path}")
            return

        # Read roadmap
        roadmap_content = roadmap_path.read_text(encoding="utf-8")

        # Find "Blockers (ASAP Priority)" section
        blockers_section = "## Blockers (ASAP Priority)"
        if blockers_section not in roadmap_content:
            # Add section if it doesn't exist
            roadmap_content += f"\n\n{blockers_section}\n\n"

        # Create relative path from memory-bank to plan
        try:
            relative_plan_path = plan_path.relative_to(self.project_root)
        except ValueError:
            # If paths don't share common root, use absolute path
            relative_plan_path = plan_path

        # Add plan entry
        plan_entry = f"- [Phase: Investigate {tool_name} MCP Tool Failure]({relative_plan_path}) - ASAP (PLANNING) - Investigate and fix MCP tool failure that occurred during commit procedure - Tool: `{tool_name}`, Error: {type(error).__name__} - Impact: Commit procedure blocked - Target completion: {datetime.now().strftime('%Y-%m-%d')}\n"

        # Insert after blockers section header
        insert_pos = roadmap_content.find(blockers_section) + len(blockers_section)
        roadmap_content = (
            roadmap_content[:insert_pos]
            + "\n"
            + plan_entry
            + roadmap_content[insert_pos:]
        )

        # Write updated roadmap
        _ = roadmap_path.write_text(roadmap_content, encoding="utf-8")
        logger.info(f"Added investigation plan to roadmap: {plan_path}")

    def handle_failure(self, tool_name: str, error: Exception, step_name: str) -> None:
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

        Raises:
            MCPToolFailure: Always raises to stop commit procedure
        """
        # Create investigation plan
        plan_path = self.create_investigation_plan(tool_name, error, step_name)

        # Add to roadmap
        try:
            self.add_to_roadmap(plan_path, tool_name, error)
        except Exception as roadmap_error:
            logger.error(
                f"Failed to add plan to roadmap: {roadmap_error}. Plan created at: {plan_path}"
            )

        # Generate user notification (for logging, not returned since we raise)
        user_notification = self._generate_user_notification(
            tool_name, error, step_name, plan_path
        )
        logger.error(f"MCP tool failure notification: {user_notification}")

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

**Fix Recommendation**: **FIX-ASAP** priority - Tool must be fixed before commit can proceed

**Investigation Plan**: {relative_plan_path}

**Next Steps**:
1. Review the investigation plan
2. Investigate and fix the tool failure
3. Verify the fix works via MCP protocol
4. Re-run commit procedure after fix

**Protocol**: Commit procedure stopped immediately per MCP Tool Failure protocol. No workarounds or fallbacks allowed."""

        return notification
