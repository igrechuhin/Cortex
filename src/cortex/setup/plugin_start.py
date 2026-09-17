"""Native startup hook: reuse session orientation before host MCP is connected."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import cast

from fastmcp.exceptions import ToolError

from cortex.core.usage_context import set_current_project_root
from cortex.tools.session.plugin_lifecycle import run_plugin_hook


def startup_payload(raw: str, host: str, working_directory: Path) -> dict[str, object]:
    """Validate native input before selecting any workspace or loading managers."""
    if len(raw) > 65536:
        raise ValueError("Hook input exceeds 64 KiB")
    value: object = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    value = cast(dict[str, object], value)
    if value.get("hook_event_name") != "SessionStart":
        raise ValueError("Expected a SessionStart event")
    cwd = value.get("cwd")
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        raise ValueError("Hook cwd must be absolute")
    if Path(cwd).resolve(strict=True) != working_directory.resolve():
        raise ValueError("Hook cwd must match the command working directory")
    return {
        "host": host,
        "event": "SessionStart",
        "cwd": cwd,
        "session_id": value.get("session_id"),
        "source": value.get("source"),
    }


async def startup(raw: str, host: str, working_directory: Path) -> str:
    """Run the existing bounded operation without launching another MCP server."""
    payload = startup_payload(raw, host, working_directory)
    set_current_project_root(working_directory.resolve())
    return await run_plugin_hook(payload, None)


def main() -> None:
    try:
        if len(sys.argv) != 2:
            raise ValueError("Expected host argument: claude or codex")
        result = asyncio.run(startup(sys.stdin.read(65537), sys.argv[1], Path.cwd()))
        print(result)
    except (ValueError, OSError, ToolError) as error:
        print(
            f"Cortex startup failed: {error}. Run session() explicitly.",
            file=sys.stderr,
        )
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
