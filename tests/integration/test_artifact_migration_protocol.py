"""Exercise artifact relocation and retrieval through a real stdio MCP server."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import (
    Implementation,
    ListRootsResult,
    Root,
    TextContent,
    TextResourceContents,
)
from pydantic import AnyUrl, FileUrl

_EXTERNAL_RULE_CONTENT = (
    b"# Shared rules\n\nUnmodified rules from the shared code tree.\n"
)
_GENERATED_CONTENT = (
    b"# Generated framework\n\nGenerated payload must stay unchanged.\n"
)


async def _manage(session: ClientSession, **arguments: object) -> dict[str, object]:
    result = await session.call_tool("manage_file", arguments)
    assert not result.isError, result
    text = "\n".join(
        item.text for item in result.content if isinstance(item, TextContent)
    )
    data = cast(dict[str, object], json.loads(text))
    assert data.get("status") == "success", data
    return data


def _prepare_core_files(bank: Path) -> None:
    bank.mkdir(parents=True)
    for name in (
        "projectBrief.md",
        "productContext.md",
        "systemPatterns.md",
        "techContext.md",
        "progress.md",
        "roadmap.md",
    ):
        _ = (bank / name).write_text(
            f"# {Path(name).stem}\n\n## Status\n\nProtocol fixture context.\n"
        )
    _ = (bank / "activeContext.md").write_text(
        "# Active Context\n\n## Current Work\n\n"
        + "[Legacy review](reviews/review-protocol-0.md)\n"
        + "[Legacy analysis](analyses/analyse-protocol-0.md)\n"
    )


def _prepare_external_rule_tree(root: Path) -> None:
    target = root.parent / (root.name + "-shared-code")
    target.mkdir()
    _ = (target / "rule.md").write_bytes(_EXTERNAL_RULE_CONTENT)
    (root / ".cortex/rules").symlink_to(target, target_is_directory=True)


def _prepare_generated_trees(root: Path) -> None:
    for relative in ("Build", "MachineOutput"):
        framework = root / relative / "ArgumentParser.framework"
        headers = framework / "Versions/A/Headers"
        headers.mkdir(parents=True)
        _ = (headers / "guide.md").write_bytes(_GENERATED_CONTENT)
        (framework / "Headers").symlink_to(
            "Versions/A/Headers", target_is_directory=True
        )
    _ = (root / ".gitignore").write_text(
        "/Build/\n/MachineOutput/\n/.cortex/reviews/\n/.cortex/wiki/\n"
    )
    _ = subprocess.run(
        ["git", "init", "-q", str(root)], check=True, capture_output=True
    )


def _assert_generated_trees(root: Path) -> None:
    for relative in ("Build", "MachineOutput"):
        pointer = root / relative / "ArgumentParser.framework/Headers"
        assert pointer.is_symlink()
        assert (pointer / "guide.md").read_bytes() == _GENERATED_CONTENT


def _prepare_workspace(root: Path) -> dict[str, bytes]:
    bank = root / ".cortex" / "memory-bank"
    _prepare_core_files(bank)
    _prepare_external_rule_tree(root)
    _prepare_generated_trees(root)
    reports: dict[str, bytes] = {}
    for folder, count in (("reviews", 13), ("analyses", 4), ("queries", 1)):
        target = bank / folder
        target.mkdir()
        for number in range(count):
            name = f"{folder[:-1]}-protocol-{number}.md"
            body = f"# Protocol {folder} {number}\n\nprotocolmigrationneedle evidence.\n".encode()
            _ = (target / name).write_bytes(body)
            reports[f"{folder}/{name}"] = body
    wiki = root / ".cortex" / "wiki"
    (wiki / "analyses").mkdir(parents=True)
    _ = (wiki / "index.md").write_text(
        "# Wiki\n\n| Page | Title | Category | Summary | Sources |\n| --- | --- | --- | --- | --- |\n"
    )
    _ = (wiki / "analyses" / "preserved.md").write_bytes(
        b"# Existing mirror\n\nNever replace this copy.\n"
    )
    return reports


async def _migrate_protocol(
    session: ClientSession, root: Path, reports: dict[str, bytes]
) -> object:
    preview = await _manage(session, operation="migrate_artifacts")
    digest = preview["preview_digest"]
    assert preview["project_root"] == str(root.resolve())
    assert preview["migration_count"] == 18
    for relative, expected in reports.items():
        assert (root / ".cortex/memory-bank" / relative).read_bytes() == expected
    applied = await _manage(
        session,
        operation="migrate_artifacts",
        content=json.dumps({"apply": True, "expected_preview_digest": digest}),
    )
    assert applied["apply"] is True and applied["migration_count"] == 18
    for relative, expected in reports.items():
        assert (root / ".cortex" / relative).read_bytes() == expected
    assert (
        root / ".cortex/wiki/analyses/preserved.md"
    ).read_bytes() == b"# Existing mirror\n\nNever replace this copy.\n"
    assert (
        "../reviews/review-protocol-0.md"
        in (root / ".cortex/memory-bank/activeContext.md").read_text()
    )
    assert (
        "../analyses/analyse-protocol-0.md"
        in (root / ".cortex/memory-bank/activeContext.md").read_text()
    )
    return digest


async def _context_text(session: ClientSession) -> str:
    resource = await session.read_resource(AnyUrl("cortex://context"))
    return "\n".join(
        part.text
        for part in resource.contents
        if isinstance(part, TextResourceContents)
    )


async def _retrieve_protocol(session: ClientSession) -> None:
    found = await _manage(
        session,
        operation="search",
        content=json.dumps({"query": "protocolmigrationneedle", "top_k": 30}),
    )
    assert found["count"] == 18
    assert "memory-bank/reviews" not in json.dumps(found["results"])
    context = await _context_text(session)
    assert "recent_artifacts" in context and "protocol-" in context


async def _file_protocol(session: ClientSession, root: Path) -> None:
    for artifact_type, folder in (
        ("review_report", "reviews"),
        ("session_analysis", "analyses"),
        ("query_result", "queries"),
    ):
        filed = await _manage(
            session,
            operation="file_artifact",
            artifact_type=artifact_type,
            title=f"Protocol fresh {folder}",
            content=f"# New {folder}\n\nprotocolfilingneedle.\n",
        )
        assert Path(str(filed["path"])).parent == root / ".cortex" / folder
        assert not (root / ".cortex/memory-bank" / folder).exists()
    assert "Protocol fresh" in await _context_text(session)


async def _reject_unsafe_requests(session: ClientSession) -> None:
    for request in ({"apply": "true"}, {"source": "../../escape"}, {"apply": True}):
        result = await session.call_tool(
            "manage_file",
            {"operation": "migrate_artifacts", "content": json.dumps(request)},
        )
        text = "\n".join(
            item.text for item in result.content if isinstance(item, TextContent)
        )
        assert json.loads(text)["status"] == "error", text


async def _exercise_protocol(
    session: ClientSession, root: Path, reports: dict[str, bytes]
) -> dict[str, object]:
    initialized = await session.initialize()
    assert initialized.protocolVersion
    inventory = await session.list_tools()
    manage = next(tool for tool in inventory.tools if tool.name == "manage_file")
    assert "migrate_artifacts" in json.dumps(manage.inputSchema)
    assert "patch_document" in json.dumps(manage.inputSchema)
    await _reject_unsafe_requests(session)
    digest = await _migrate_protocol(session, root, reports)
    await _retrieve_protocol(session)
    await _file_protocol(session, root)
    replay = await _manage(
        session,
        operation="migrate_artifacts",
        content=json.dumps({"apply": True, "expected_preview_digest": digest}),
    )
    assert replay["replayed"] is True
    assert (root / ".cortex/rules").is_symlink()
    assert (root / ".cortex/rules/rule.md").read_bytes() == _EXTERNAL_RULE_CONTENT
    _assert_generated_trees(root)
    await _patch_document_protocol(session, root)
    return {
        "protocol": initialized.protocolVersion,
        "tools": len(inventory.tools),
        "migrated_reports": len(reports),
        "preview_digest": digest,
        "replayed": replay["replayed"],
        "excluded_rule_tree_preserved": True,
        "excluded_generated_trees_preserved": True,
    }


def _server_parameters(root: Path, launch_mode: str) -> StdioServerParameters:
    checkout = Path(__file__).resolve().parents[2]
    environment = {**os.environ, "CORTEX_USE_FALLBACK_ROOT": "0"}
    if launch_mode == "packaged":
        environment["PYTHONPATH"] = ""
        return StdioServerParameters(
            command="uvx",
            args=[
                "--refresh-package",
                "cortex",
                "--from",
                str(checkout),
                "cortex",
            ],
            cwd=root,
            env=environment,
        )
    environment["PYTHONPATH"] = str(checkout / "src")
    return StdioServerParameters(
        command=str(Path(sys.executable).parent / "cortex"),
        args=[],
        cwd=root,
        env=environment,
    )


@pytest.mark.integration
@pytest.mark.timeout(120)
@pytest.mark.parametrize("launch_mode", ["editable", "packaged"])
async def test_artifact_migration_stdio_protocol(
    tmp_path: Path, launch_mode: str
) -> None:
    """Preview/apply, search, context and filing share canonical real-server behavior."""
    reports = _prepare_workspace(tmp_path)

    async def roots(context: object) -> ListRootsResult:
        return ListRootsResult(
            roots=[
                Root(
                    uri=FileUrl(tmp_path.resolve().as_uri()),
                    name="isolated-artifact-smoke",
                )
            ]
        )

    parameters = _server_parameters(tmp_path, launch_mode)
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(
            reader,
            writer,
            client_info=Implementation(name="cortex-artifact-smoke", version="1"),
            list_roots_callback=roots,
        ) as session:
            evidence = await _exercise_protocol(session, tmp_path, reports)
            print(json.dumps({"launch_mode": launch_mode, **evidence}))


def _patch_protocol_fixture(root: Path) -> tuple[Path, bytes, dict[str, object]]:
    target = root / ".cortex/plans/archive/canceled-protocol.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    before = b"---\r\nstatus: DONE\r\n---\r\n# Canceled (DONE)\r\n- [ ] old step\r\n"
    _ = target.write_bytes(before)
    target.chmod(0o640)
    payload: dict[str, object] = {
        "expected_sha256": hashlib.sha256(before).hexdigest(),
        "replacements": [
            {"old": "- [ ] old step", "new": "- [x] old step", "count": 1}
        ],
    }
    return target, before, payload


async def _patch_document_protocol(session: ClientSession, root: Path) -> None:
    target, before, payload = _patch_protocol_fixture(root)
    arguments = {
        "operation": "patch_document",
        "file_name": target.relative_to(root).as_posix(),
    }
    context = root / ".cortex/memory-bank/activeContext.md"
    unchanged_context = context.read_bytes()
    preview = await _manage(
        session, **arguments, content=json.dumps({**payload, "dry_run": True})
    )
    assert preview["project_root"] == str(root.resolve())
    assert preview["mutation_performed"] is False
    assert target.read_bytes() == before
    applied = await _manage(session, **arguments, content=json.dumps(payload))
    after = before.replace(b"- [ ] old step", b"- [x] old step")
    assert applied["mutation_performed"] is True
    assert applied["before_sha256"] == hashlib.sha256(before).hexdigest()
    assert applied["after_sha256"] == hashlib.sha256(after).hexdigest()
    assert target.read_bytes() == after
    assert target.stat().st_mode & 0o777 == 0o640
    stale = await session.call_tool(
        "manage_file", {**arguments, "content": json.dumps(payload)}
    )
    text = "\n".join(
        item.text for item in stale.content if isinstance(item, TextContent)
    )
    assert json.loads(text)["status"] == "error"
    assert target.read_bytes() == after
    assert context.read_bytes() == unchanged_context
