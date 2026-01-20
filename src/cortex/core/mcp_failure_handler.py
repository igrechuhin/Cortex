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

    def detect_failure(self, error: Exception, tool_name: str, step_name: str) -> bool:
        """Detect if error is an MCP tool failure.

        This method distinguishes between actual tool failures (JSON parsing,
        connection errors, unexpected behavior) and expected errors (validation
        failures, business logic errors).

        Args:
            error: Exception that occurred
            tool_name: Name of the tool that failed
            step_name: Commit procedure step where failure occurred

        Returns:
            True if error is an MCP tool failure (not an expected error)
        """
        error_str = str(error).lower()

        # JSON parsing errors - always tool failures
        if isinstance(error, json.JSONDecodeError):
            logger.error(
                f"Detected JSON parsing error in {tool_name} during {step_name}: {error}"
            )
            return True

        # ValueError that indicates JSON/parsing issues
        if isinstance(error, ValueError):
            json_keywords = [
                "json",
                "decode",
                "parse",
                "malformed",
                "invalid",
                "encoding",
            ]
            if any(keyword in error_str for keyword in json_keywords):
                logger.error(
                    f"Detected JSON-related ValueError in {tool_name} during {step_name}: {error}"
                )
                return True

        # Connection errors (already handled by mcp_stability, but check for unexpected ones)
        if isinstance(error, (ConnectionError, BrokenPipeError, OSError)):
            # Distinguish between expected connection errors (handled by retry) and failures
            connection_keywords = [
                "connection closed",
                "connection reset",
                "broken pipe",
                "-32000",  # MCP protocol error code
                "stdio",
                "resource",
                "broken resource",
            ]
            if any(keyword in error_str for keyword in connection_keywords):
                # If connection error occurred after retries exhausted, it's a failure
                logger.error(
                    f"Detected connection error in {tool_name} during {step_name}: {error}"
                )
                return True

        # Unexpected behavior (wrong return type, missing fields, etc.)
        if isinstance(error, (TypeError, AttributeError, KeyError)):
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
            if any(keyword in error_str for keyword in unexpected_keywords):
                logger.error(
                    f"Detected unexpected behavior in {tool_name} during {step_name}: {error}"
                )
                return True

        # Runtime errors that indicate tool failure (not business logic errors)
        if isinstance(error, RuntimeError):
            tool_failure_keywords = [
                "mcp",
                "tool",
                "protocol",
                "serialization",
                "deserialization",
                "double-encoding",
                "json string instead of dict",
            ]
            if any(keyword in error_str for keyword in tool_failure_keywords):
                logger.error(
                    f"Detected runtime error in {tool_name} during {step_name}: {error}"
                )
                return True

        # Check for FastMCP-specific errors
        if "fastmcp" in error_str or "mcp error" in error_str:
            logger.error(
                f"Detected MCP protocol error in {tool_name} during {step_name}: {error}"
            )
            return True

        # Not a tool failure - likely an expected error (validation failure, etc.)
        return False

    def create_investigation_plan(
        self, tool_name: str, error: Exception, step_name: str
    ) -> Path:
        """Create investigation plan for tool failure.

        Args:
            tool_name: Name of the tool that failed
            error: Exception that occurred
            step_name: Commit procedure step where failure occurred

        Returns:
            Path to created investigation plan file
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        plan_filename = f"phase-investigate-{tool_name}-failure-{timestamp}.md"
        plan_path = self.plans_dir / plan_filename

        # Generate plan content
        error_type = type(error).__name__
        error_message = str(error)
        error_traceback = ""
        if error.__cause__:
            error_traceback = f"\n\n**Caused by**: {type(error.__cause__).__name__}: {error.__cause__}"

        plan_content = f"""# Phase: Investigate {tool_name} MCP Tool Failure

**Status**: PLANNING
**Priority**: ASAP (Blocker)
**Created**: {datetime.now().strftime("%Y-%m-%d")}
**Target Completion**: {datetime.now().strftime("%Y-%m-%d")}

## Goal

Investigate and fix MCP tool failure that occurred during commit procedure execution.

## Context

**Problem**: The `{tool_name}` MCP tool failed during commit procedure step: **{step_name}**

**Error Details**:
- **Error Type**: `{error_type}`
- **Error Message**: `{error_message}`{error_traceback}

**Failure Type**: MCP Tool Failure (JSON parsing, connection error, or unexpected behavior)

**Impact**:
- Commit procedure was blocked at step: {step_name}
- Tool must be fixed before commit can proceed
- This is a blocker that prevents all commits

## Requirements

### Functional Requirements

1. **Investigate Root Cause**:
   - Analyze error type and message
   - Check tool implementation for issues
   - Verify MCP protocol compliance
   - Check for connection issues

2. **Fix Tool Failure**:
   - Resolve root cause
   - Ensure tool works correctly via MCP protocol
   - Add error handling if needed
   - Add validation if needed

3. **Verify Fix**:
   - Test tool via MCP protocol
   - Verify commit procedure can proceed
   - Ensure no regressions

### Technical Requirements

1. **Error Analysis**:
   - Determine if error is JSON parsing, connection, or unexpected behavior
   - Check tool return type matches MCP protocol expectations
   - Verify error handling is correct

2. **Tool Fix**:
   - Fix root cause of failure
   - Ensure proper error handling
   - Add validation if needed

3. **Testing**:
   - Add tests for failure scenarios
   - Verify tool works in commit procedure
   - Ensure no regressions

## Approach

1. **Investigate**:
   - Analyze error details
   - Check tool implementation
   - Review MCP protocol requirements
   - Check related tools for similar issues

2. **Fix**:
   - Implement fix for root cause
   - Add error handling
   - Add validation
   - Update tests

3. **Verify**:
   - Test tool via MCP protocol
   - Test in commit procedure
   - Verify no regressions

## Implementation Steps

1. **Analyze Error**:
   - Review error type and message
   - Check tool implementation
   - Identify root cause

2. **Implement Fix**:
   - Fix root cause
   - Add error handling
   - Add validation

3. **Add Tests**:
   - Test failure scenarios
   - Test fix
   - Verify no regressions

4. **Verify**:
   - Test tool via MCP protocol
   - Test in commit procedure
   - Verify fix works

## Success Criteria

- ✅ Root cause identified and documented
- ✅ Tool failure fixed
- ✅ Tool works correctly via MCP protocol
- ✅ Commit procedure can proceed
- ✅ Tests added for failure scenarios
- ✅ No regressions introduced

## Dependencies

- None (this is a blocker that must be fixed first)

## Risks & Mitigation

- **Risk**: Fix might not address root cause
  - **Mitigation**: Thorough investigation and testing
- **Risk**: Fix might introduce regressions
  - **Mitigation**: Comprehensive testing before and after fix

## Notes

- This investigation plan was automatically generated when MCP tool failure was detected
- Tool failure occurred during commit procedure step: {step_name}
- Tool name: {tool_name}
- Error: {error_type}: {error_message}
"""

        # Write plan file (use standard file tools as fallback for plan creation)
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
