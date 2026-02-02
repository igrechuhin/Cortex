"""Progress reporting for long-running MCP tools.

Provides ProgressReporter to report stage-based progress to MCP clients
when Context is available. Uses report_progress_safe for no-op when
ctx is None (e.g. in tests or non-request code).
"""

from cortex.core.context_logging import MCPContext, report_progress_safe

__all__ = ["ProgressReporter"]


class ProgressReporter:
    """Helper for reporting progress in MCP tools.

    Use in tool implementations that accept optional ctx. When ctx is
    present, progress is sent to the client; when ctx is None, reporting
    is a no-op.
    """

    def __init__(
        self,
        total_steps: int = 100,
        tool_name: str = "",
        ctx: MCPContext | None = None,
    ) -> None:
        """Initialize reporter.

        Args:
            total_steps: Number of logical steps (used to normalize progress).
            tool_name: Name of the tool (prefixed to messages when non-empty).
            ctx: MCP Context; when None, report methods are no-ops.
        """
        self._total_steps = max(1, total_steps)
        self._tool_name = tool_name
        self._ctx = ctx
        self._current_step = 0

    def _progress_pct(self, progress: int) -> int:
        """Normalize progress to 0-100 (step index or raw percentage)."""
        if progress <= self._total_steps:
            return min(100, int((progress / self._total_steps) * 100))
        return min(100, max(0, progress))

    async def start(self, message: str = "Starting...") -> None:
        """Report start (0%)."""
        await self.report(0, message)

    async def report(self, progress: int, message: str = "") -> None:
        """Report progress.

        Args:
            progress: Step number (0 to total_steps) or percentage (0-100).
            message: Optional status message.
        """
        pct = (
            self._progress_pct(progress)
            if progress <= self._total_steps
            else min(100, progress)
        )
        await report_progress_safe(self._ctx, float(pct), 100.0)
        self._current_step = progress

    async def step(self, message: str = "") -> None:
        """Report next step (increments current step and reports)."""
        self._current_step = min(self._current_step + 1, self._total_steps)
        await self.report(self._current_step, message)

    async def complete(self, message: str = "Complete") -> None:
        """Report completion (100%)."""
        await self.report(self._total_steps, message)
