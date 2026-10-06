"""Tests for manage_file file_artifact operation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.artifacts.artifact_types import ArtifactType, get_artifact_directory
from cortex.tools.files.artifact_operations import file_artifact
from cortex.tools.files.operation_helpers import validate_manage_file_operation
from cortex.wiki.categories import WikiCategoryDir
from cortex.wiki.layout import ensure_default_wiki_layout
from cortex.wiki.wiki_root_files import WikiRootDocument


def _read_json(result: str) -> dict[str, object]:
    return json.loads(result)


async def test_file_artifact_writes_review_report(tmp_path: Path) -> None:
    memory_bank_dir = tmp_path / ".cortex" / "memory-bank"
    memory_bank_dir.mkdir(parents=True, exist_ok=True)
    _ = (memory_bank_dir / "activeContext.md").write_text(
        "# Active Context\n\n## Completed Work (2026-04-07)\n\n",
        encoding="utf-8",
    )

    result = _read_json(
        await file_artifact(
            project_root=tmp_path,
            artifact_type="review_report",
            title="Auth Review",
            content="review content",
            tags=["security"],
        )
    )

    assert result["status"] == "success"
    output_path = Path(str(result["path"]))
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "review content"
    assert output_path.parent == tmp_path / ".cortex" / "reviews"
    assert output_path.name.startswith("review-auth-review-")
    active_context = (memory_bank_dir / "activeContext.md").read_text(encoding="utf-8")
    assert "[Auth Review](../reviews/" in active_context
    assert not (memory_bank_dir / "reviews").exists()


async def test_file_artifact_invalidates_context_resource_cache(tmp_path: Path) -> None:
    memory_bank_dir = tmp_path / ".cortex" / "memory-bank"
    memory_bank_dir.mkdir(parents=True)
    _ = (memory_bank_dir / "activeContext.md").write_text(
        "# Active Context\n\n## Completed Work (2026-04-07)\n\n",
        encoding="utf-8",
    )
    with patch(
        "cortex.tools.optimization.handlers.invalidate_context_resource_cache"
    ) as inv:
        result = _read_json(
            await file_artifact(
                project_root=tmp_path,
                artifact_type="review_report",
                title="Cache Test",
                content="body",
                tags=None,
            )
        )
    assert result["status"] == "success"
    inv.assert_called_once()


async def test_file_artifact_dedupes_duplicate_titles(tmp_path: Path) -> None:
    memory_bank_dir = tmp_path / ".cortex" / "memory-bank"
    memory_bank_dir.mkdir(parents=True, exist_ok=True)
    _ = (memory_bank_dir / "activeContext.md").write_text(
        "# Active Context\n\n## Completed Work (2026-04-07)\n\n",
        encoding="utf-8",
    )

    first = _read_json(
        await file_artifact(
            project_root=tmp_path,
            artifact_type="session_analysis",
            title="Weekly Session",
            content="one",
            tags=None,
        )
    )
    second = _read_json(
        await file_artifact(
            project_root=tmp_path,
            artifact_type="session_analysis",
            title="Weekly Session",
            content="two",
            tags=None,
        )
    )

    _assert_duplicate_analysis_paths(
        tmp_path, Path(str(first["path"])), Path(str(second["path"]))
    )


def _assert_duplicate_analysis_paths(
    project_root: Path, first_path: Path, second_path: Path
) -> None:
    assert first_path != second_path
    assert second_path.stem.endswith("-2")
    assert first_path.parent == project_root / ".cortex" / "analyses"
    assert first_path.read_text(encoding="utf-8") == "one"
    assert second_path.read_text(encoding="utf-8") == "two"
    active_path = project_root / ".cortex" / "memory-bank" / "activeContext.md"
    active = active_path.read_text(encoding="utf-8")
    assert f"(../analyses/{first_path.name})" in active
    assert f"(../analyses/{second_path.name})" in active


def _wiki_project_with_memory_bank(tmp_path: Path) -> tuple[Path, Path]:
    _ = (tmp_path / ".cortex").mkdir()
    _ = ensure_default_wiki_layout(tmp_path)
    wiki_root = get_cortex_path(tmp_path, CortexResourceType.WIKI)
    memory_bank_dir = tmp_path / ".cortex" / "memory-bank"
    memory_bank_dir.mkdir(parents=True, exist_ok=True)
    _ = (memory_bank_dir / "activeContext.md").write_text(
        "# Active Context\n\n## Completed Work (2026-04-07)\n\n",
        encoding="utf-8",
    )
    return wiki_root, memory_bank_dir


async def test_file_artifact_references_review_report_from_wiki(tmp_path: Path) -> None:
    wiki_root, _memory_bank_dir = _wiki_project_with_memory_bank(tmp_path)
    review = _read_json(
        await file_artifact(
            project_root=tmp_path,
            artifact_type="review_report",
            title="Auth Review",
            content="# Findings\n\nToken refresh is missing.\n",
            tags=["security"],
        )
    )
    assert review["status"] == "success"
    wiki_pages = list(
        (wiki_root / WikiCategoryDir.ANALYSES.value).glob("review-auth-review-*.md")
    )
    assert len(wiki_pages) == 1
    wiki_text = wiki_pages[0].read_text(encoding="utf-8")
    assert wiki_text.startswith("---\n")
    cat = WikiCategoryDir.ANALYSES.value
    assert f'category: "{cat}"' in wiki_text or f"category: {cat}" in wiki_text
    assert "Token refresh is missing" not in wiki_text
    canonical = Path(str(review["path"]))
    assert f"](../../reviews/{canonical.name})" in wiki_text
    index = (wiki_root / WikiRootDocument.INDEX.value).read_text(encoding="utf-8")
    assert f"{WikiCategoryDir.ANALYSES.value}/" in index and "Auth Review" in index


async def test_file_artifact_references_session_analysis_from_wiki(
    tmp_path: Path,
) -> None:
    wiki_root, _memory_bank_dir = _wiki_project_with_memory_bank(tmp_path)
    analysis = _read_json(
        await file_artifact(
            project_root=tmp_path,
            artifact_type="session_analysis",
            title="Session Wrap",
            content="## Summary\n\nWe fixed ingest routing.\n",
            tags=None,
        )
    )
    assert analysis["status"] == "success"
    wiki_analysis = list(
        (wiki_root / WikiCategoryDir.ANALYSES.value).glob("analysis-session-wrap-*.md")
    )
    assert len(wiki_analysis) == 1
    canonical = Path(str(analysis["path"]))
    wiki_text = wiki_analysis[0].read_text(encoding="utf-8")
    assert "We fixed ingest routing" not in wiki_text
    assert f"](../../analyses/{canonical.name})" in wiki_text


def test_validate_manage_file_operation_file_artifact_no_filename() -> None:
    parsed_op, error = validate_manage_file_operation(
        operation="file_artifact",
        file_name=None,
    )

    assert error is None
    assert parsed_op is not None
    assert parsed_op.value == "file_artifact"


@pytest.mark.parametrize("artifact_type", list(ArtifactType))
async def test_file_artifact_routes_and_dedupes_every_type(
    tmp_path: Path, artifact_type: ArtifactType
) -> None:
    memory_bank = tmp_path / ".cortex" / "memory-bank"
    memory_bank.mkdir(parents=True)
    active_path = memory_bank / "activeContext.md"
    _ = active_path.write_text("# Active Context\n\n", encoding="utf-8")
    results = [
        _read_json(
            await file_artifact(tmp_path, artifact_type, "../Same Title!", body, None)
        )
        for body in ("first", "second")
    ]
    assert all(result["status"] == "success" for result in results)
    paths = [Path(str(result["path"])) for result in results]
    assert all(
        path.parent == get_artifact_directory(tmp_path, artifact_type) for path in paths
    )
    assert paths[1].stem == f"{paths[0].stem}-2"
    assert [path.read_text(encoding="utf-8") for path in paths] == ["first", "second"]
    active = active_path.read_text(encoding="utf-8")
    for path in paths:
        link = (
            f"findings/{path.name}"
            if artifact_type == ArtifactType.ARCHITECTURAL_FINDING
            else f"../{path.parent.name}/{path.name}"
        )
        assert f"]({link})" in active
    assert not (tmp_path / ".cortex" / "wiki").exists()
    for folder in ("reviews", "analyses", "queries"):
        assert not (memory_bank / folder).exists()


@pytest.mark.parametrize(
    "artifact_type", [ArtifactType.QUERY_RESULT, ArtifactType.ARCHITECTURAL_FINDING]
)
async def test_file_artifact_does_not_mirror_queries_or_findings(
    tmp_path: Path, artifact_type: ArtifactType
) -> None:
    wiki_root, _memory_bank = _wiki_project_with_memory_bank(tmp_path)
    pages_before = set(wiki_root.rglob("*.md"))
    index_path = wiki_root / WikiRootDocument.INDEX.value
    index_before = index_path.read_text(encoding="utf-8")
    result = _read_json(
        await file_artifact(tmp_path, artifact_type, "No Mirror", "body", None)
    )
    assert result["status"] == "success"
    assert set(wiki_root.rglob("*.md")) == pages_before
    assert index_path.read_text(encoding="utf-8") == index_before


@pytest.mark.parametrize(
    "artifact_type", [ArtifactType.REVIEW_REPORT, ArtifactType.SESSION_ANALYSIS]
)
async def test_file_artifact_preserves_wiki_duplicate_naming(
    tmp_path: Path, artifact_type: ArtifactType
) -> None:
    wiki_root, _memory_bank = _wiki_project_with_memory_bank(tmp_path)
    for body in ("first", "second"):
        result = _read_json(
            await file_artifact(tmp_path, artifact_type, "Mirror", body, ["tag"])
        )
        assert result["status"] == "success"
    canonical = sorted(get_artifact_directory(tmp_path, artifact_type).glob("*.md"))
    mirrors = sorted((wiki_root / WikiCategoryDir.ANALYSES.value).glob("*-mirror-*.md"))
    assert {path.name for path in mirrors} == {path.name for path in canonical}
    assert len(mirrors) == 2
    for path in mirrors:
        assert "tags:\n" in path.read_text(encoding="utf-8")
    index = (wiki_root / WikiRootDocument.INDEX.value).read_text(encoding="utf-8")
    for path in mirrors:
        assert f"analyses/{path.name}" in index


async def test_file_artifact_preserves_mirror_failure_semantics(tmp_path: Path) -> None:
    _ = _wiki_project_with_memory_bank(tmp_path)
    with patch(
        "cortex.wiki.artifact_mirror.mirror_file_artifact_to_wiki_if_enabled",
        side_effect=OSError("mirror failure"),
    ):
        with pytest.raises(OSError, match="mirror failure"):
            _ = await file_artifact(
                tmp_path, ArtifactType.REVIEW_REPORT, "Mirror Failure", "body", None
            )
    paths = list(
        get_artifact_directory(tmp_path, ArtifactType.REVIEW_REPORT).glob("*.md")
    )
    assert len(paths) == 1
    assert paths[0].read_text(encoding="utf-8") == "body"


async def test_file_artifact_preserves_cross_reference_failure_semantics(
    tmp_path: Path,
) -> None:
    wiki_root, memory_bank = _wiki_project_with_memory_bank(tmp_path)
    (memory_bank / "activeContext.md").unlink()
    result = _read_json(
        await file_artifact(
            tmp_path,
            ArtifactType.REVIEW_REPORT,
            "Cross Reference Failure",
            "body",
            None,
        )
    )
    assert result["status"] == "error"
    paths = list(
        get_artifact_directory(tmp_path, ArtifactType.REVIEW_REPORT).glob("*.md")
    )
    assert len(paths) == 1
    assert paths[0].read_text(encoding="utf-8") == "body"
    assert (wiki_root / "analyses" / paths[0].name).exists()


@pytest.mark.parametrize("artifact_type", list(ArtifactType))
@pytest.mark.parametrize("symlink_cortex_root", [False, True])
async def test_file_artifact_rejects_symlinked_artifact_roots(
    tmp_path: Path, artifact_type: ArtifactType, symlink_cortex_root: bool
) -> None:
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    cortex = project / ".cortex"
    if symlink_cortex_root:
        cortex.symlink_to(outside, target_is_directory=True)
    else:
        directory = get_artifact_directory(project, artifact_type)
        directory.parent.mkdir(parents=True)
        directory.symlink_to(outside, target_is_directory=True)
    result = _read_json(
        await file_artifact(project, artifact_type, "Unsafe", "body", None)
    )
    assert result["status"] == "error"
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    "relative_path",
    [
        "memory-bank",
        "memory-bank/activeContext.md",
        "wiki",
        "wiki/analyses",
        f"wiki/{WikiRootDocument.INDEX.value}",
        f"wiki/{WikiRootDocument.INDEX.value}.tmp",
    ],
)
async def test_file_artifact_rejects_symlinked_side_outputs_before_filing(
    tmp_path: Path, relative_path: str
) -> None:
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    sentinel = outside / "sentinel.md"
    _ = sentinel.write_text("unchanged", encoding="utf-8")
    link = project / ".cortex" / relative_path
    link.parent.mkdir(parents=True)
    target = sentinel if ".md" in link.name else outside
    link.symlink_to(target, target_is_directory=target.is_dir())
    result = _read_json(
        await file_artifact(project, ArtifactType.REVIEW_REPORT, "Unsafe", "body", None)
    )
    assert result["status"] == "error"
    assert not (project / ".cortex" / "reviews").exists()
    assert list(outside.iterdir()) == [sentinel]
    assert sentinel.read_text(encoding="utf-8") == "unchanged"


async def test_file_artifact_rejects_dangling_collision_symlink(tmp_path: Path) -> None:
    _ = _wiki_project_with_memory_bank(tmp_path)
    first = _read_json(
        await file_artifact(
            tmp_path, ArtifactType.REVIEW_REPORT, "Collision", "first", None
        )
    )
    assert first["status"] == "success"
    first_path = Path(str(first["path"]))
    outside = tmp_path / "outside.md"
    collision = first_path.with_name(f"{first_path.stem}-2.md")
    collision.symlink_to(outside)
    result = _read_json(
        await file_artifact(
            tmp_path, ArtifactType.REVIEW_REPORT, "Collision", "second", None
        )
    )
    assert result["status"] == "error"
    assert not outside.exists()
    assert first_path.read_text(encoding="utf-8") == "first"
