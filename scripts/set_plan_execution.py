"""Call this checkout's guarded owner correction through a fresh MCP SDK session."""

import argparse
import asyncio
import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Literal

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, Implementation, ListRootsResult, Root, TextContent
from pydantic import BaseModel, ConfigDict, Field, FileUrl, ValidationError


class ExecutionResponse(BaseModel):
    """Validate the narrow wire contract without deriving authority from prose."""

    model_config = ConfigDict(strict=True)

    status: Literal["success", "error"]
    operation: Literal["set_execution"]
    project_root: str
    target: str | None = Field(
        pattern=r"^\.cortex/plans/[A-Za-z0-9][A-Za-z0-9._-]*\.md$"
    )
    mutation_performed: bool
    code: Literal["STALE_BASE", "POLICY_BLOCKED"] | None = None
    error: str | None = None
    before_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    after_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    dry_run: bool | None = None


def _server_parameters(checkout: Path, root: Path) -> StdioServerParameters:
    return StdioServerParameters(
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


def _payload(args: argparse.Namespace) -> dict[str, str | bool]:
    return {
        "expected_sha256": args.expected_sha256,
        "execution": args.execution,
        "reason": args.reason,
        "dry_run": not args.apply,
    }


def _validate_response(response: CallToolResult, root: Path) -> None:
    text = "\n".join(
        item.text for item in response.content if isinstance(item, TextContent)
    )
    print(text)
    try:
        result = ExecutionResponse.model_validate_json(text)
    except ValidationError as exc:
        raise RuntimeError(
            "Uncertain backend response; read back before any retry"
        ) from exc
    if result.project_root != str(root):
        raise RuntimeError(
            "Backend resolved a root other than the sole advertised root; "
            + "read back before any retry"
        )
    if result.status == "error":
        if (
            result.code is not None
            and result.mutation_performed is False
            and not response.isError
            and result.error
            and result.after_sha256 is None
            and (result.target is None) == (result.before_sha256 is None)
            and (result.code != "STALE_BASE" or result.target is not None)
        ):
            raise RuntimeError(f"{result.code}: {result.error}; no automatic retry")
        raise RuntimeError(
            f"Uncertain correction: {result.error}; read back before any retry"
        )
    _validate_success(result, response.isError)


def _validate_success(result: ExecutionResponse, is_error: bool | None) -> None:
    if (
        is_error
        or result.code is not None
        or result.error is not None
        or result.target is None
        or result.before_sha256 is None
        or result.after_sha256 is None
        or result.dry_run is None
        or result.mutation_performed
        != (not result.dry_run and result.before_sha256 != result.after_sha256)
    ):
        raise RuntimeError("Uncertain success response; read back before any retry")


async def call(args: argparse.Namespace) -> None:
    checkout = Path(__file__).resolve().parents[1]
    root = Path(args.root).absolute()
    if not root.is_dir() or root != root.resolve():
        raise ValueError("Root must be an existing directory without symlink ancestry")

    async def roots(context: object) -> ListRootsResult:
        return ListRootsResult(roots=[Root(uri=FileUrl(root.as_uri()), name=root.name)])

    parameters = _server_parameters(checkout, root)
    payload = _payload(args)
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
            _validate_response(response, root)


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
