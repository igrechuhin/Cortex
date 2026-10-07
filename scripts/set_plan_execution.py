"""Call this checkout's guarded owner correction through a fresh MCP SDK session."""

import argparse
import asyncio
import json
import os
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Implementation, ListRootsResult, Root, TextContent
from pydantic import FileUrl


async def call(args: argparse.Namespace) -> None:
    checkout = Path(__file__).resolve().parents[1]
    root = Path(args.root).absolute()
    if not root.is_dir() or root != root.resolve():
        raise ValueError("Root must be an existing directory without symlink ancestry")

    async def roots(context: object) -> ListRootsResult:
        return ListRootsResult(roots=[Root(uri=FileUrl(root.as_uri()), name=root.name)])

    parameters = StdioServerParameters(
        command=str(checkout / ".venv/bin/python"),
        args=["-m", "cortex.main"],
        cwd=str(root),
        env={
            **os.environ,
            "PYTHONPATH": str(checkout / "src"),
            "CORTEX_USE_FALLBACK_ROOT": "0",
            "CORTEX_AUTO_RESTART": "0",
            "CORTEX_MCP_TRANSPORT": "stdio",
            "CORTEX_SKIP_SYNAPSE_UPDATE": "1",
        },
    )
    payload = {
        "expected_sha256": args.expected_sha256,
        "execution": args.execution,
        "reason": args.reason,
        "dry_run": not args.apply,
    }
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(
            reader,
            writer,
            list_roots_callback=roots,
            client_info=Implementation(
                name="cortex-local-execution-correction", version="1"
            ),
            read_timeout_seconds=timedelta(seconds=120),
        ) as session:
            _ = await session.initialize()
            response = await session.call_tool(
                "plan",
                {
                    "operation": "set_execution",
                    "slug": args.slug,
                    "content": json.dumps(payload),
                },
            )
            text = "\n".join(
                item.text for item in response.content if isinstance(item, TextContent)
            )
            print(text)
            result = json.loads(text)
            if response.isError or result.get("status") != "success":
                raise RuntimeError("Guarded execution correction rejected")
            if result["project_root"] != str(root):
                raise RuntimeError(
                    "Backend resolved a root other than the sole advertised root"
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--root", required=True)
    _ = parser.add_argument("--slug", required=True)
    _ = parser.add_argument("--expected-sha256", required=True)
    _ = parser.add_argument("--execution", choices=("agent", "operator"), required=True)
    _ = parser.add_argument("--reason", required=True)
    _ = parser.add_argument(
        "--apply", action="store_true", help="Apply; default is dry-run"
    )
    asyncio.run(call(parser.parse_args()))
