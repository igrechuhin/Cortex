"""Real sole-root SDK preview/apply/stale and consumer-visibility evidence."""

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import cast

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Implementation, ListRootsResult, Root, TextContent
from pydantic import FileUrl

_TARGETS = ("activeContext.md", "progress.md")
_BODY = (
    "---\r\nstatus: DONE\r\n---\r\n# Memory Bank\r\n\r\n"
    "## 2026-10-02\r\n\r\n"
    "- **Fixture evidence** - COMPLETE. measured 2026-10-02 14:27Z; 21 entries.\r\n"
    "Unrelated Unicode: é; counts 34 and 43.\r\n"
).encode("utf-8")
_OLD = "measured 2026-10-02 14:27Z"
_NEW = "measured 2026-10-02T14:27Z"


def _server(root: Path) -> StdioServerParameters:
    checkout = Path(__file__).resolve().parents[2]
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"CORTEX_SESSION_ID", "CORTEX_PIPELINE_SESSION_ID"}
    }
    environment.update(
        CORTEX_USE_FALLBACK_ROOT="0",
        CORTEX_AUTO_RESTART="0",
        CORTEX_SKIP_SYNAPSE_UPDATE="1",
        PYTHONPATH=str(checkout / "src"),
    )
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "cortex.main"],
        cwd=root,
        env=environment,
    )


def _prepare(root: Path) -> dict[str, Path]:
    bank = root / ".cortex/memory-bank"
    bank.mkdir(parents=True)
    paths = {name: bank / name for name in _TARGETS}
    for target in paths.values():
        _ = target.write_bytes(_BODY)
        target.chmod(0o640)
    _ = (bank / "projectBrief.md").write_bytes(b"# Untouched\r\n")
    return paths


async def _call(
    session: ClientSession, relative: str, payload: dict[str, object]
) -> dict[str, object]:
    response = await session.call_tool(
        "manage_file",
        {
            "operation": "patch_document",
            "file_name": relative,
            "content": json.dumps(payload),
        },
    )
    text = "\n".join(
        item.text for item in response.content if isinstance(item, TextContent)
    )
    return cast(dict[str, object], json.loads(text))


async def _exercise_target(
    session: ClientSession, root: Path, target: Path
) -> dict[str, object]:
    payload: dict[str, object] = {
        "expected_sha256": hashlib.sha256(_BODY).hexdigest(),
        "replacements": [{"old": _OLD, "new": _NEW, "count": 1}],
    }
    relative = target.relative_to(root).as_posix()
    preview = await _call(session, relative, {**payload, "dry_run": True})
    assert preview["status"] == "success", preview
    assert preview["project_root"] == str(root)
    assert preview["mutation_performed"] is False
    assert target.read_bytes() == _BODY
    applied = await _call(session, relative, payload)
    after = _BODY.replace(_OLD.encode(), _NEW.encode())
    assert applied["status"] == "success", applied
    assert applied["mutation_performed"] is True
    assert (
        applied["after_sha256"]
        == preview["after_sha256"]
        == hashlib.sha256(after).hexdigest()
    )
    assert applied["before_sha256"] == payload["expected_sha256"]
    assert target.read_bytes() == after
    assert target.stat().st_mode & 0o777 == 0o640
    stale = await _call(session, relative, payload)
    assert stale["status"] == "error" and stale["mutation_performed"] is False, stale
    assert "Stale" in str(stale["error"])
    assert target.read_bytes() == after
    return {"target": relative, "preview": preview, "apply": applied, "stale": stale}


async def _exercise_protocol(
    session: ClientSession, root: Path, paths: dict[str, Path]
) -> None:
    initialized = await session.initialize()
    inventory = await session.list_tools()
    manage = next(tool for tool in inventory.tools if tool.name == "manage_file")
    assert "patch_document" in json.dumps(manage.inputSchema)
    assert "activeContext,progress" in (manage.description or "")
    receipts = [
        await _exercise_target(session, root, target) for target in paths.values()
    ]
    assert (
        root / ".cortex/memory-bank/projectBrief.md"
    ).read_bytes() == b"# Untouched\r\n"
    print(
        json.dumps(
            {
                "protocol": initialized.protocolVersion,
                "sole_root": str(root),
                "receipts": receipts,
            }
        )
    )


async def _exercise_consumer_refusals(
    session: ClientSession, root: Path, paths: dict[str, Path]
) -> None:
    payload: dict[str, object] = {
        "expected_sha256": hashlib.sha256(_BODY).hexdigest(),
        "replacements": [{"old": _OLD, "new": _NEW, "count": 1}],
    }
    target = ".cortex/memory-bank/progress.md"
    cases: list[tuple[str, dict[str, object]]] = [
        (str(paths["progress.md"]), payload),
        (".cortex/memory-bank/projectBrief.md", payload),
        (target, {**payload, "operator_authorized": True}),
        (target, {"content": "# Whole-file replacement"}),
        (
            target,
            {
                **payload,
                "replacements": [{"old": "COMPLETE", "new": "PENDING", "count": 1}],
            },
        ),
    ]
    for relative, request in cases:
        refused = await _call(session, relative, request)
        assert refused["status"] == "error", refused
        assert refused["mutation_performed"] is False
    assert all(target.read_bytes() == _BODY for target in paths.values())
    assert (
        root / ".cortex/memory-bank/projectBrief.md"
    ).read_bytes() == b"# Untouched\r\n"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_sole_root_sdk_entry_patch_protocol(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    paths = _prepare(root)

    async def roots(context: object) -> ListRootsResult:
        return ListRootsResult(
            roots=[Root(uri=FileUrl(root.as_uri()), name="entry-fixture")]
        )

    async with stdio_client(_server(root)) as (reader, writer):
        async with ClientSession(
            reader,
            writer,
            list_roots_callback=roots,
            client_info=Implementation(name="cortex-entry-smoke", version="1"),
        ) as session:
            await _exercise_protocol(session, root, paths)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_sdk_consumer_cannot_bypass_guarded_entry_patch(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    paths = _prepare(root)

    async def roots(context: object) -> ListRootsResult:
        return ListRootsResult(
            roots=[Root(uri=FileUrl(root.as_uri()), name="entry-fixture")]
        )

    async with stdio_client(_server(root)) as (reader, writer):
        async with ClientSession(
            reader,
            writer,
            list_roots_callback=roots,
            client_info=Implementation(name="cortex-entry-consumer", version="1"),
        ) as session:
            _ = await session.initialize()
            await _exercise_consumer_refusals(session, root, paths)
