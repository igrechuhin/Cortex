"""Project access exercises only temporary files, snapshots and harmless jobs."""

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.tools.files.operation_helpers import (
    FileOperation,
    validate_manage_file_operation,
)
from cortex.tools.files.project_access.handler import handle_project_access
from cortex.tools.files.project_access.models import Request
from cortex.tools.files.project_access.paths import read_bytes
from cortex.tools.files.project_access.policy import HASH_ENV, POLICY_ENV
from cortex.tools.files.project_access.sqlite_read import configure_readonly
from tests.helpers.project_access_fixtures import AccessFixture, approve, call


@pytest.mark.asyncio
async def test_project_access_disabled_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(POLICY_ENV, raising=False)
    monkeypatch.delenv(HASH_ENV, raising=False)
    result = json.loads(await handle_project_access(tmp_path, '{"action":"discover"}'))
    assert result["status"] == "error"
    assert "disabled" in result["error"]
    assert validate_manage_file_operation("project_access", None) == (
        FileOperation.PROJECT_ACCESS,
        None,
    )


@pytest.mark.asyncio
async def test_project_access_exact_file_pagination(
    access_fixture: AccessFixture,
) -> None:
    first = await call(access_fixture, action="read", path="contract.md", length=5)
    assert first.result.text == "Full "
    assert first.result.next_offset == 5
    rest = await call(access_fixture, action="read", path="contract.md", offset=5)
    assert first.result.text + rest.result.text == "Full original contract: αβγ\n"
    discovery = await call(access_fixture, action="discover")
    assert discovery.result.files == ["contract.md"]


@pytest.mark.parametrize(
    "path",
    [
        "../contract.md",
        "/etc/passwd",
        "a/../../contract.md",
        "a//b",
        "./contract.md",
        "a\\b",
        ".env",
        "credentials.json",
        "key.pem",
        "a\x00b",
    ],
)
@pytest.mark.asyncio
async def test_project_access_path_denials(
    access_fixture: AccessFixture, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    access_fixture.policy.files = [path]
    approve(access_fixture, monkeypatch)
    assert (await call(access_fixture, action="read", path=path)).status == "error"


@pytest.mark.parametrize("kind", ["file", "directory", "hardlink", "fifo"])
@pytest.mark.asyncio
async def test_project_access_alias_and_special_file_denials(
    access_fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    root = access_fixture.root
    name = "alias.md"
    if kind == "file":
        (root / name).symlink_to(root / "contract.md")
    elif kind == "directory":
        (root / "alias").symlink_to(root, target_is_directory=True)
        name = "alias/contract.md"
    elif kind == "hardlink":
        os.link(root / "contract.md", root / name)
    else:
        os.mkfifo(root / name)
    access_fixture.policy.files = [name]
    approve(access_fixture, monkeypatch)
    assert (await call(access_fixture, action="read", path=name)).status == "error"


@pytest.mark.asyncio
async def test_project_access_secret_content_and_unapproved_file(
    access_fixture: AccessFixture,
) -> None:
    _ = (access_fixture.root / "contract.md").write_text("api_" + "key = fixture-value")
    result = await call(access_fixture, action="read", path="contract.md", length=1)
    assert result.status == "error"
    assert "fixture-value" not in result.model_dump_json()
    assert (
        await call(access_fixture, action="read", path="prepare.py")
    ).status == "error"


@pytest.mark.parametrize("mutation", ["root", "hash", "disabled", "inside", "symlink"])
@pytest.mark.asyncio
async def test_project_access_approval_boundary(
    access_fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    if mutation == "root":
        access_fixture.policy.project_root = str(access_fixture.root.parent)
    elif mutation == "disabled":
        access_fixture.policy.enabled = False
    elif mutation == "inside":
        access_fixture.policy_path = access_fixture.root / "approval.json"
    elif mutation == "symlink":
        alias = access_fixture.policy_path.parent / "alias.json"
        alias.symlink_to(access_fixture.policy_path)
        monkeypatch.setenv(POLICY_ENV, str(alias))
        assert (await call(access_fixture, action="discover")).status == "error"
        return
    approve(access_fixture, monkeypatch)
    if mutation == "hash":
        _ = access_fixture.policy_path.write_text("{}")
    assert (await call(access_fixture, action="discover")).status == "error"


@pytest.mark.asyncio
async def test_project_access_sqlite_exact_results_and_no_injection(
    access_fixture: AccessFixture,
) -> None:
    before = (access_fixture.root / "profiles.sqlite").read_bytes()
    result = await call(
        access_fixture, action="query", dataset="profiles", filters={"figi": "FIGI1"}
    )
    assert result.result.rows == [["FIGI1", "Full original profile"]]
    assert result.result.source_sha256 == hashlib.sha256(before).hexdigest()
    injected = await call(
        access_fixture,
        action="query",
        dataset="profiles",
        filters={"figi": "' OR 1=1; DROP TABLE profiles;--"},
    )
    assert injected.result.rows == []
    assert (access_fixture.root / "profiles.sqlite").read_bytes() == before


@pytest.mark.parametrize(
    "input_fields",
    [
        {"sql": "SELECT * FROM profiles"},
        {"table": "profiles"},
        {"limit": 201},
        {"limit": "1"},
        {"offset": 10001},
        {"filters": {"internal": "excluded"}},
        {"filters": {"figi": "x" * 513}},
        {"filters": {"figi": True}},
        {"filters": {"figi": float("inf")}},
        {"filters": {"figi": 2**63}},
        {"dataset": "unapproved"},
    ],
)
@pytest.mark.asyncio
async def test_project_access_query_input_denials(
    access_fixture: AccessFixture, input_fields: dict[str, object]
) -> None:
    arguments: dict[str, object] = {
        "action": "query",
        "dataset": "profiles",
        **input_fields,
    }
    assert (await call(access_fixture, **arguments)).status == "error"


@pytest.mark.parametrize(
    "kind", ["wal", "journal", "view", "identifier", "oversize", "binary"]
)
@pytest.mark.asyncio
async def test_project_access_sqlite_unsafe_sources(
    access_fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    root = access_fixture.root
    if kind in {"wal", "journal"}:
        _ = (root / ("profiles.sqlite-" + kind)).write_text("active")
    elif kind == "identifier":
        access_fixture.policy.datasets["profiles"].table = (
            "profiles; DROP TABLE profiles"
        )
        approve(access_fixture, monkeypatch)
    else:
        with sqlite3.connect(root / "profiles.sqlite") as db:
            if kind == "view":
                _ = db.execute("CREATE VIEW exported AS SELECT * FROM profiles")
                access_fixture.policy.datasets["profiles"].table = "exported"
                approve(access_fixture, monkeypatch)
            elif kind == "oversize":
                _ = db.execute("UPDATE profiles SET profile = ?", ("x" * 140000,))
            else:
                _ = db.execute("UPDATE profiles SET profile = ?", (b"bytes",))
    assert (
        await call(access_fixture, action="query", dataset="profiles")
    ).status == "error"


def test_project_access_sqlite_authorizer_blocks_writes(
    access_fixture: AccessFixture,
) -> None:
    dataset = access_fixture.policy.datasets["profiles"]
    with sqlite3.connect(":memory:") as db:
        _ = db.execute("CREATE TABLE profiles(figi TEXT, profile TEXT)")
        configure_readonly(db, dataset)
        for sql in (
            "DELETE FROM profiles",
            "ATTACH ':memory:' AS other",
            "SELECT sqlite_version()",
        ):
            with pytest.raises(sqlite3.DatabaseError):
                _ = db.execute(sql)


def test_project_access_request_rejects_unrecognized_actions() -> None:
    with pytest.raises(ValueError):
        _ = Request.model_validate_json('{"action":"execute","command":"forbidden"}')


@pytest.mark.asyncio
async def test_project_access_snapshot_rechecks_sidecars(
    access_fixture: AccessFixture,
) -> None:
    def copy_then_activate(root: Path, path: str, maximum: int) -> bytes:
        data = read_bytes(root, path, maximum)
        _ = (root / (path + "-wal")).write_text("fixture activity")
        return data

    with patch(
        "cortex.tools.files.project_access.sqlite_read.read_bytes",
        side_effect=copy_then_activate,
    ):
        assert (
            await call(access_fixture, action="query", dataset="profiles")
        ).status == "error"
