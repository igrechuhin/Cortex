"""Independent data-root approval uses synthetic sibling directories only."""

import json
import os
import sqlite3
from pathlib import Path

import pytest

from cortex.tools.files.project_access.models import DataRoot
from cortex.tools.files.project_access.paths import directory
from cortex.tools.files.project_access.policy import load_access
from tests.helpers.project_access_fixtures import AccessFixture, approve, call


@pytest.fixture
def data_fixture(
    access_fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch
) -> AccessFixture:
    root = access_fixture.root.parent / "data"
    root.mkdir()
    (root / "runs").mkdir()
    _ = (root / "contract.md").write_text("Synthetic data contract")
    with sqlite3.connect(root / "tiny.sqlite") as db:
        _ = db.execute("CREATE TABLE profiles(figi TEXT, profile TEXT)")
        _ = db.execute("INSERT INTO profiles VALUES ('fixture', 'complete fixture')")
    access_fixture.policy.data_root = DataRoot.model_validate_json(
        json.dumps(
            {
                "enabled": True,
                "root": str(root),
                "files": ["contract.md"],
                "datasets": {
                    "tiny": {
                        "path": "tiny.sqlite",
                        "table": "profiles",
                        "columns": ["figi", "profile"],
                    }
                },
                "output_bases": {"fixture": "runs"},
            }
        )
    )
    approve(access_fixture, monkeypatch)
    return access_fixture


@pytest.mark.asyncio
async def test_project_access_independent_data_reads(
    data_fixture: AccessFixture,
) -> None:
    project = await call(data_fixture, action="read", path="contract.md")
    data = await call(data_fixture, action="read", scope="data", path="contract.md")
    query = await call(
        data_fixture, action="query", scope="data", dataset="tiny", limit=1
    )
    assert project.result.text == "Full original contract: αβγ\n"
    assert data.result.text == "Synthetic data contract"
    assert query.result.rows == [["fixture", "complete fixture"]]
    assert (await call(data_fixture, action="query", dataset="tiny")).status == "error"
    assert (
        await call(data_fixture, action="query", scope="data", dataset="profiles")
    ).status == "error"


@pytest.mark.asyncio
async def test_project_access_data_root_requires_separate_opt_in(
    data_fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    grant = data_fixture.policy.data_root
    assert grant is not None
    grant.enabled = False
    approve(data_fixture, monkeypatch)
    assert (
        await call(data_fixture, action="read", scope="data", path="contract.md")
    ).status == "error"
    assert (
        await call(data_fixture, action="read", path="contract.md")
    ).status == "success"


@pytest.mark.parametrize(
    "kind", ["same", "parent", "child", "alias", "relative", "traversal", "policy"]
)
def test_project_access_rejects_data_root_widening(
    data_fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    grant = data_fixture.policy.data_root
    assert grant is not None
    if kind == "same":
        grant.root = str(data_fixture.root)
    elif kind in {"parent", "policy"}:
        grant.root = str(data_fixture.root.parent)
    elif kind == "child":
        grant.root = str(data_fixture.root / "artifacts")
    elif kind == "alias":
        alias = data_fixture.root.parent / "alias"
        alias.symlink_to(grant.root, target_is_directory=True)
        grant.root = str(alias)
    elif kind == "relative":
        grant.root = "data"
    else:
        grant.root += "/../data"
    approve(data_fixture, monkeypatch)
    with pytest.raises((ValueError, OSError)):
        _ = load_access(data_fixture.root)


@pytest.mark.parametrize(
    "kind", ["overlap", "parent", "duplicate", "nested", "symlink", "escape"]
)
def test_project_access_rejects_write_allowlist_escapes(
    data_fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    grant = data_fixture.policy.data_root
    assert grant is not None
    root = Path(grant.root)
    if kind == "overlap":
        grant.files = ["runs/input.md"]
    elif kind == "parent":
        grant.files = ["runs"]
    elif kind == "duplicate":
        grant.output_bases["other"] = "runs"
    elif kind == "nested":
        grant.output_bases["other"] = "runs/nested"
    elif kind == "symlink":
        (root / "runs").rmdir()
        (root / "runs").symlink_to(
            data_fixture.root / "artifacts", target_is_directory=True
        )
    else:
        grant.output_bases["fixture"] = "../project/artifacts"
    approve(data_fixture, monkeypatch)
    with pytest.raises((ValueError, OSError)):
        _ = load_access(data_fixture.root)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "directory_alias"])
@pytest.mark.asyncio
async def test_project_access_data_physical_alias_denials(
    data_fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    grant = data_fixture.policy.data_root
    assert grant is not None
    root = Path(grant.root)
    path = "alias.md"
    if kind == "symlink":
        (root / path).symlink_to(data_fixture.root / "contract.md")
    elif kind == "hardlink":
        os.link(root / "contract.md", root / path)
    elif kind == "fifo":
        os.mkfifo(root / path)
    else:
        (root / "alias").symlink_to(root, target_is_directory=True)
        path = "alias/contract.md"
    grant.files = [path]
    approve(data_fixture, monkeypatch)
    assert (
        await call(data_fixture, action="read", scope="data", path=path)
    ).status == "error"


@pytest.mark.asyncio
async def test_project_access_data_scope_never_dispatches_legacy_jobs(
    data_fixture: AccessFixture,
) -> None:
    result = await call(
        data_fixture,
        action="start",
        scope="data",
        job="prepare",
        parameters={"figi": "FIGI1"},
    )
    assert result.status == "error"
    assert list((data_fixture.root / "artifacts").iterdir()) == []


def test_project_access_policy_hardlink_is_not_approval(
    data_fixture: AccessFixture,
) -> None:
    os.link(
        data_fixture.policy_path, data_fixture.policy_path.parent / "policy-alias.json"
    )
    with pytest.raises(ValueError, match="regular file"):
        _ = load_access(data_fixture.root)


def test_project_access_absolute_ancestor_swap_is_refused(tmp_path: Path) -> None:
    parent = tmp_path.resolve() / "ancestor"
    root = parent / "root"
    root.mkdir(parents=True)
    _ = parent.rename(parent.with_name("original"))
    parent.symlink_to(parent.with_name("original"), target_is_directory=True)
    with pytest.raises(OSError):
        with directory(root):
            pass


def test_project_access_case_alias_root_is_refused(
    data_fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    alias = data_fixture.root.with_name(data_fixture.root.name.upper())
    if not alias.exists():
        pytest.skip(
            "Needs case-insensitive filesystem; ref: tradewing-scoped-data-root-adapters"
        )
    grant = data_fixture.policy.data_root
    assert grant is not None
    grant.root = str(alias)
    approve(data_fixture, monkeypatch)
    with pytest.raises(ValueError):
        _ = load_access(data_fixture.root)
