"""Behavioral regression tests for canonical plan reads from a worktree."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ContextManager, TypedDict, Unpack, cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.plans.crud_helpers import (
    extract_plan_title as _real_extract_plan_title,
)
from cortex.tools.plans.plan import plan
from tests.tools.canonical_read_test_support import (
    add_linked_worktree,
    build_canonical_main,
    commit_all,
    digest_of,
    snapshot_tree,
)

JsonDict = dict[str, object]


class _PlanArgs(TypedDict, total=False):
    operation: str
    title: str
    content: str
    slug: str
    include_archive: bool
    plan_title: str
    summary: str
    source: str


async def _plan_json(**kwargs: Unpack[_PlanArgs]) -> JsonDict:
    result = await plan(**kwargs)
    return cast(JsonDict, json.loads(result))


@pytest.fixture(name="worktree_setup")
def worktree_setup_fixture(tmp_path: Path) -> dict[str, Path]:
    main = tmp_path / "main"
    build_canonical_main(main)
    worktree = tmp_path / "wt"
    add_linked_worktree(main, worktree)
    # Canonical-only approved plan added after the worktree diverged.
    _ = (main / ".cortex" / "plans" / "approved-later.md").write_text(
        "---\ntitle: Approved later\nstatus: DONE\n---\n# Approved later\n",
        encoding="utf-8",
    )
    # Canonical updates an existing shared plan: local copy goes stale.
    _ = (main / ".cortex" / "plans" / "shared-base.md").write_text(
        "---\ntitle: Shared base\nstatus: DONE\n---\n# Shared base updated\n",
        encoding="utf-8",
    )
    _ = commit_all(main, "approved work")
    return {"main": main, "worktree": worktree}


def _patched_root(worktree: Path) -> ContextManager[object]:
    return patch(
        "cortex.tools.plans.crud.resolve_project_root_async",
        new=AsyncMock(return_value=worktree),
    )


def _provenance(result: JsonDict) -> JsonDict:
    return cast(JsonDict, result["provenance"])


def _plan_entries(result: JsonDict) -> list[JsonDict]:
    return cast(list[JsonDict], result["plans"])


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_missing_local_plan_reads_canonical(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]

    with _patched_root(worktree):
        result = await _plan_json(
            operation="get", slug="approved-later", source="canonical"
        )

    assert result["status"] == "success"
    assert "Approved later" in str(result["content"])
    provenance = _provenance(result)
    assert provenance["source"] == "canonical"
    assert Path(str(provenance["root"])) == main.resolve()
    assert provenance["relation"] == "linked_worktree"
    assert provenance["local_state"] == "missing"
    expected_digest = digest_of(main / ".cortex" / "plans" / "approved-later.md")
    assert provenance["content_sha256"] == expected_digest
    assert len(str(provenance["git_revision"])) == 40


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_stale_local_plan_reports_diverged(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]

    with _patched_root(worktree):
        result = await _plan_json(
            operation="get", slug="shared-base", source="canonical"
        )

    assert result["status"] == "success"
    assert "updated" in str(result["content"])
    provenance = _provenance(result)
    assert provenance["local_state"] == "diverged"
    assert provenance["local_content_sha256"] != provenance["content_sha256"]
    assert provenance["local_content_sha256"] == digest_of(
        worktree / ".cortex" / "plans" / "shared-base.md"
    )
    assert provenance["content_sha256"] == digest_of(
        main / ".cortex" / "plans" / "shared-base.md"
    )


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_canonical_list_reports_missing_and_stale(
    worktree_setup: dict[str, Path],
) -> None:
    worktree = worktree_setup["worktree"]

    with _patched_root(worktree):
        result = await _plan_json(
            operation="list", source="canonical", include_archive=True
        )

    assert result["status"] == "success"
    slugs = {entry["slug"] for entry in _plan_entries(result)}
    assert "approved-later" in slugs
    provenance = _provenance(result)
    assert provenance["local_missing"] == ["approved-later"]
    assert provenance["local_stale"] == ["shared-base"]


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_defaults_remain_local_without_provenance(
    worktree_setup: dict[str, Path],
) -> None:
    worktree = worktree_setup["worktree"]

    with _patched_root(worktree):
        local_list = await _plan_json(operation="list")
        local_get = await _plan_json(operation="get", slug="shared-base")

    assert local_list["status"] == "success"
    assert local_list["provenance"] is None
    assert {entry["slug"] for entry in _plan_entries(local_list)} == {"shared-base"}
    assert local_get["provenance"] is None
    assert "updated" not in str(local_get["content"])


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_write_operations_reject_canonical_source(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]
    main_before = snapshot_tree(main)
    worktree_before = snapshot_tree(worktree)

    with _patched_root(worktree):
        create = await _plan_json(
            operation="create",
            title="Cross root",
            content="# Cross root\n",
            source="canonical",
        )
        complete = await _plan_json(
            operation="complete",
            plan_title="Shared base",
            summary="s",
            source="canonical",
        )
        graph = await _plan_json(operation="graph", source="canonical")
        invalid = await _plan_json(operation="get", slug="x", source="cloud")

    assert create["status"] == "error"
    assert "only supports read operations" in str(create["message"])
    assert complete["status"] == "error"
    assert graph["status"] == "error"
    assert invalid["status"] == "error"
    assert snapshot_tree(main) == main_before
    assert snapshot_tree(worktree) == worktree_before


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_canonical_reads_write_nothing(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]
    main_before = snapshot_tree(main)
    worktree_before = snapshot_tree(worktree)

    with _patched_root(worktree):
        _ = await _plan_json(operation="get", slug="approved-later", source="canonical")
        _ = await _plan_json(operation="list", source="canonical")

    assert snapshot_tree(main) == main_before
    assert snapshot_tree(worktree) == worktree_before


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_crlf_canonical_bytes_digest_exact_bytes(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]
    crlf_path = main / ".cortex" / "plans" / "crlf-plan.md"
    _ = crlf_path.write_bytes(
        b"---\ntitle: CRLF\nstatus: DONE\n---\n# CRLF\r\n\r\nBody\r\n"
    )
    _ = commit_all(main, "crlf")

    with _patched_root(worktree):
        result = await _plan_json(operation="get", slug="crlf-plan", source="canonical")

    assert result["status"] == "success"
    assert "\r" not in str(result["content"])
    provenance = _provenance(result)
    assert provenance["content_sha256"] == digest_of(crlf_path)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_mutation_during_assembly_fails_closed(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]
    target = main / ".cortex" / "plans" / "approved-later.md"

    def mutate_then_build(
        slug: str, raw: str, relative_path: str, response_format: str
    ) -> object:
        from cortex.tools.plans.crud_helpers import (
            build_plan_result_from_text,
        )

        _ = target.write_text("# mutated during assembly\n", encoding="utf-8")
        return build_plan_result_from_text(slug, raw, relative_path, response_format)

    with (
        _patched_root(worktree),
        patch(
            "cortex.tools.plans.canonical_reads.build_plan_result_from_text",
            side_effect=mutate_then_build,
        ),
    ):
        result = await _plan_json(
            operation="get", slug="approved-later", source="canonical"
        )

    assert result["status"] == "error"
    assert "revision_changed_during_read" in str(result["error"])


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_head_revalidation_failure_fails_closed(
    worktree_setup: dict[str, Path],
) -> None:
    worktree = worktree_setup["worktree"]

    with (
        _patched_root(worktree),
        patch(
            "cortex.tools.plans.canonical_reads.revalidate_revision",
            return_value=False,
        ),
    ):
        result = await _plan_json(
            operation="get", slug="approved-later", source="canonical"
        )

    assert result["status"] == "error"
    assert "revision_changed_during_read" in str(result["error"])


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_non_git_local_root_fails_closed(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    _ = plain.mkdir()

    with _patched_root(plain):
        result = await _plan_json(operation="get", slug="anything", source="canonical")

    assert result["status"] == "error"
    assert "not_a_git_checkout" in str(result["error"])


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_traversal_slug_not_found(
    worktree_setup: dict[str, Path],
) -> None:
    worktree = worktree_setup["worktree"]

    with _patched_root(worktree):
        result = await _plan_json(
            operation="get", slug="../../etc/passwd", source="canonical"
        )

    assert result["status"] == "error"
    assert "not found in canonical root" in str(result["message"]).lower()


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_local_is_canonical_read_still_works(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]

    with _patched_root(main):
        result = await _plan_json(
            operation="get", slug="approved-later", source="canonical"
        )

    assert result["status"] == "success"
    provenance = _provenance(result)
    assert provenance["relation"] == "local_is_canonical"
    assert provenance["local_state"] == "identical"


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_legacy_create_plan_rejects_canonical_source(
    worktree_setup: dict[str, Path],
) -> None:
    from cortex.tools.plans.crud import create_plan

    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]
    main_before = snapshot_tree(main)
    worktree_before = snapshot_tree(worktree)

    with _patched_root(worktree):
        result_str = await create_plan(
            operation="create",
            title="Cross root",
            content="# Cross root\n",
            source="canonical",
        )

    result = cast(JsonDict, json.loads(result_str))
    assert result["status"] == "error"
    assert "only supports read operations" in str(result["message"])
    assert snapshot_tree(main) == main_before
    assert snapshot_tree(worktree) == worktree_before


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_list_membership_mutation_fails_closed(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]

    def add_plan_then_title(content: str) -> str | None:
        _ = (main / ".cortex" / "plans" / "injected-during-list.md").write_text(
            "# Injected during list\n", encoding="utf-8"
        )
        return _real_extract_plan_title(content)

    with (
        _patched_root(worktree),
        patch(
            "cortex.tools.plans.crud_helpers.extract_plan_title",
            side_effect=add_plan_then_title,
        ),
    ):
        result = await _plan_json(operation="list", source="canonical")

    assert result["status"] == "error"
    assert "revision_changed_during_read" in str(result["error"])


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_local_cortex_ancestor_symlink_plan_freshness_unsafe(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]
    outside_root = worktree.parent / "outside-root"
    _ = (outside_root / ".cortex" / "plans").mkdir(parents=True)
    _ = (outside_root / ".cortex" / "plans" / "shared-base.md").write_text(
        "---\ntitle: Shared base\nstatus: DONE\n---\n# Outside\n",
        encoding="utf-8",
    )
    real_cortex = worktree / ".cortex"
    for child in sorted(real_cortex.iterdir(), reverse=True):
        if child.is_dir():
            for entry in child.iterdir():
                _ = entry.unlink()
            _ = child.rmdir()
        else:
            _ = child.unlink()
    _ = real_cortex.rmdir()
    _ = real_cortex.symlink_to(outside_root / ".cortex", target_is_directory=True)

    with _patched_root(worktree):
        get = await _plan_json(operation="get", slug="shared-base", source="canonical")
        listed = await _plan_json(operation="list", source="canonical")

    # AI: The symlinked .cortex ancestor must not redirect plan freshness
    # hashing outside the bound local root; report unsafe instead.
    assert get["status"] == "success"
    assert _provenance(get)["local_state"] == "unsafe"
    assert _provenance(get)["local_content_sha256"] is None
    assert listed["status"] == "success"
    slugs = [str(entry["slug"]) for entry in _plan_entries(listed)]
    assert _provenance(listed)["local_unsafe"] == sorted(slugs)
    assert main.joinpath(".cortex", "plans").is_dir()


@pytest.mark.timeout(30)
def test_structurecanonical_identity_block_reports_mapping(
    worktree_setup: dict[str, Path],
) -> None:
    from cortex.tools.structure.main import canonical_identity_block

    main_block = canonical_identity_block(worktree_setup["main"])
    wt_block = canonical_identity_block(worktree_setup["worktree"])

    assert main_block["available"] is True
    assert main_block["relation"] == "local_is_canonical"
    assert len(str(main_block["git_revision"])) == 40
    assert wt_block["available"] is True
    assert wt_block["relation"] == "linked_worktree"
    assert wt_block["canonical_root"] == main_block["canonical_root"]


@pytest.mark.timeout(30)
def test_structurecanonical_identity_block_non_git_unavailable(
    tmp_path: Path,
) -> None:
    from cortex.tools.structure.main import canonical_identity_block

    block = canonical_identity_block(tmp_path)

    assert block["available"] is False
    assert block["failure"] == "not_a_git_checkout"
