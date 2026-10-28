"""Behavioral regression tests for canonical manage_file reads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ContextManager, Literal, TypedDict, Unpack, cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.files.crud_operations import manage_file
from cortex.tools.files.section_helpers import (
    extract_content_sections as _real_extract_sections,
)
from tests.tools.canonical_read_test_support import (
    add_linked_worktree,
    build_canonical_main,
    commit_all,
    digest_of,
    snapshot_tree,
)

JsonDict = dict[str, object]


class _ManageArgs(TypedDict, total=False):
    operation: Literal["read", "write", "metadata", "rollback"]
    file_name: str
    content: str
    include_metadata: bool
    version: int
    source: str


async def _manage_json(**kwargs: Unpack[_ManageArgs]) -> JsonDict:
    result = await manage_file(**kwargs)
    return cast(JsonDict, json.loads(result))


@pytest.fixture(name="worktree_setup")
def worktree_setup_fixture(tmp_path: Path) -> dict[str, Path]:
    main = tmp_path / "main"
    build_canonical_main(main)
    worktree = tmp_path / "wt"
    add_linked_worktree(main, worktree)
    # Canonical records the approved conclusion after the worktree diverged.
    _ = (main / ".cortex" / "memory-bank" / "activeContext.md").write_text(
        (
            "# Active Context\n\n## Completed Work (2026-10-24)\n\n"
            "- **Validated conclusion** - COMPLETE. See "
            "[approved-report](../reviews/approved-report.md).\n"
        ),
        encoding="utf-8",
    )
    _ = (main / ".cortex" / "reviews" / "later-report.md").write_text(
        "# Later Report\n\nNewer validated conclusion.\n", encoding="utf-8"
    )
    _ = commit_all(main, "approved conclusion")
    return {"main": main, "worktree": worktree}


def _patched_root(worktree: Path) -> ContextManager[object]:
    return patch(
        "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
        new=AsyncMock(return_value=worktree),
    )


def _provenance(result: JsonDict) -> JsonDict:
    return cast(JsonDict, result["provenance"])


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_stale_local_conclusion_reads_canonical(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]

    with _patched_root(worktree):
        result = await _manage_json(
            operation="read", file_name="activeContext.md", source="canonical"
        )

    assert result["status"] == "success"
    assert "Validated conclusion" in str(result["content"])
    provenance = _provenance(result)
    assert provenance["source"] == "canonical"
    assert Path(str(provenance["root"])) == main.resolve()
    assert provenance["relation"] == "linked_worktree"
    assert provenance["local_state"] == "diverged"
    assert provenance["content_sha256"] == digest_of(
        main / ".cortex" / "memory-bank" / "activeContext.md"
    )


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_artifact_result_reference_is_readable(
    worktree_setup: dict[str, Path],
) -> None:
    worktree = worktree_setup["worktree"]

    with _patched_root(worktree):
        shared = await _manage_json(
            operation="read",
            file_name=".cortex/reviews/approved-report.md",
            source="canonical",
        )
        later = await _manage_json(
            operation="read",
            file_name=".cortex/reviews/later-report.md",
            source="canonical",
        )

    assert shared["status"] == "success"
    assert "Validated conclusion." in str(shared["content"])
    assert _provenance(shared)["local_state"] == "identical"
    assert later["status"] == "success"
    assert "Newer validated conclusion." in str(later["content"])
    assert _provenance(later)["local_state"] == "missing"


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_default_local_read_unchanged(
    worktree_setup: dict[str, Path],
) -> None:
    worktree = worktree_setup["worktree"]

    with _patched_root(worktree):
        result = await _manage_json(operation="read", file_name="activeContext.md")

    assert result["status"] == "success"
    assert "provenance" not in result
    assert "Validated conclusion" not in str(result["content"])


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_non_read_operations_reject_canonical_source(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]
    main_before = snapshot_tree(main)
    worktree_before = snapshot_tree(worktree)

    with _patched_root(worktree):
        write = await _manage_json(
            operation="write",
            file_name="activeContext.md",
            content="overwritten",
            source="canonical",
        )
        metadata = await _manage_json(
            operation="metadata",
            file_name="activeContext.md",
            source="canonical",
        )
        rollback = await _manage_json(
            operation="rollback",
            file_name="activeContext.md",
            version=1,
            source="canonical",
        )

    for outcome in (write, metadata, rollback):
        assert outcome["status"] == "error"
    assert "only supports operation='read'" in str(write["error"])
    assert snapshot_tree(main) == main_before
    assert snapshot_tree(worktree) == worktree_before


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_invalid_canonical_read_flags_rejected(
    worktree_setup: dict[str, Path],
) -> None:
    worktree = worktree_setup["worktree"]

    with _patched_root(worktree):
        meta_flag = await _manage_json(
            operation="read",
            file_name="activeContext.md",
            include_metadata=True,
            source="canonical",
        )
        invalid = await _manage_json(
            operation="read", file_name="activeContext.md", source="cloud"
        )

    assert meta_flag["status"] == "error"
    assert "include_metadata is not supported" in str(meta_flag["error"])
    assert invalid["status"] == "error"
    assert "Invalid source" in str(invalid["error"])


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
        _ = await _manage_json(
            operation="read", file_name="activeContext.md", source="canonical"
        )
        _ = await _manage_json(
            operation="read",
            file_name=".cortex/reviews/approved-report.md",
            source="canonical",
        )

    # AI: No wiki bootstrap, no manager directories, no lock files — the
    # canonical root must be byte-identical after cross-root reads.
    assert snapshot_tree(main) == main_before
    assert snapshot_tree(worktree) == worktree_before


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_traversal_paths_rejected(
    worktree_setup: dict[str, Path],
) -> None:
    worktree = worktree_setup["worktree"]

    with _patched_root(worktree):
        artifact_escape = await _manage_json(
            operation="read",
            file_name=".cortex/reviews/../../secret.md",
            source="canonical",
        )
        memory_escape = await _manage_json(
            operation="read",
            file_name="../../etc/passwd",
            source="canonical",
        )
        wrong_dir = await _manage_json(
            operation="read",
            file_name=".cortex/plans/shared-base.md",
            source="canonical",
        )

    for outcome in (artifact_escape, memory_escape, wrong_dir):
        assert outcome["status"] == "error"
        assert "traversal_escape" in str(outcome["error"])


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_local_memory_bank_symlink_reported_unsafe(
    worktree_setup: dict[str, Path],
) -> None:
    worktree = worktree_setup["worktree"]
    outside = worktree.parent / "outside-memory-bank"
    _ = outside.mkdir()
    _ = (outside / "activeContext.md").write_text(
        "outside conclusions\n", encoding="utf-8"
    )
    local_memory_bank = worktree / ".cortex" / "memory-bank"
    for entry in local_memory_bank.iterdir():
        _ = entry.unlink()
    _ = local_memory_bank.rmdir()
    _ = local_memory_bank.symlink_to(outside, target_is_directory=True)

    with _patched_root(worktree):
        result = await _manage_json(
            operation="read", file_name="activeContext.md", source="canonical"
        )

    assert result["status"] == "success"
    provenance = _provenance(result)
    # AI: The symlinked local memory-bank must not be read; the counterpart
    # is reported unsafe rather than mislabeled missing or identical.
    assert provenance["local_state"] == "unsafe"
    assert provenance["local_content_sha256"] is None
    assert "Validated conclusion" in str(result["content"])


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_mutation_during_assembly_fails_closed(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]
    target = main / ".cortex" / "memory-bank" / "activeContext.md"

    def mutate_then_extract(
        content_str: str, sections: list[str] | None
    ) -> tuple[str, str | None]:
        _ = target.write_text("# mutated during assembly\n", encoding="utf-8")
        return _real_extract_sections(content_str, sections)

    with (
        _patched_root(worktree),
        patch(
            "cortex.tools.files.section_helpers.extract_content_sections",
            side_effect=mutate_then_extract,
        ),
    ):
        result = await _manage_json(
            operation="read", file_name="activeContext.md", source="canonical"
        )

    assert result["status"] == "error"
    assert "revision_changed_during_read" in str(result["error"])


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_non_git_local_root_fails_closed(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    _ = plain.mkdir()

    with _patched_root(plain):
        result = await _manage_json(
            operation="read", file_name="activeContext.md", source="canonical"
        )

    assert result["status"] == "error"
    assert "not_a_git_checkout" in str(result["error"])


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_local_cortex_ancestor_symlink_reported_unsafe(
    worktree_setup: dict[str, Path],
) -> None:
    worktree = worktree_setup["worktree"]
    outside_root = worktree.parent / "outside-root"
    _ = (outside_root / ".cortex" / "memory-bank").mkdir(parents=True)
    _ = (outside_root / ".cortex" / "memory-bank" / "activeContext.md").write_text(
        "outside conclusions\n", encoding="utf-8"
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
        result = await _manage_json(
            operation="read", file_name="activeContext.md", source="canonical"
        )

    assert result["status"] == "success"
    provenance = _provenance(result)
    # AI: The symlinked .cortex ancestor must not redirect freshness
    # hashing outside the bound local root; report unsafe instead.
    assert provenance["local_state"] == "unsafe"
    assert provenance["local_content_sha256"] is None


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_canonical_read_then_local_write_stays_local(
    worktree_setup: dict[str, Path],
) -> None:
    main = worktree_setup["main"]
    worktree = worktree_setup["worktree"]
    main_before = snapshot_tree(main)

    with _patched_root(worktree):
        read = await _manage_json(
            operation="read", file_name="activeContext.md", source="canonical"
        )
        write = await _manage_json(
            operation="write",
            file_name="activeContext.md",
            content=(
                "# Active Context\n\n"
                "## Current Focus\n\nLocal worktree update.\n\n"
                "## Recent Changes\n\n- Local write after canonical read.\n\n"
                "## Next Steps\n\n- Continue.\n"
            ),
        )

    assert read["status"] == "success"
    assert write["status"] == "success"
    local_file = worktree / ".cortex" / "memory-bank" / "activeContext.md"
    persisted = local_file.read_text(encoding="utf-8")
    # AI: The write pipeline may add metadata markers (e.g. memory_type);
    # assert the persisted required structure rather than exact bytes.
    assert "## Current Focus" in persisted
    assert "Local worktree update." in persisted
    assert "## Recent Changes" in persisted
    assert "## Next Steps" in persisted
    assert snapshot_tree(main) == main_before
