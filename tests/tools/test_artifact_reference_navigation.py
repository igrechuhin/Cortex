"""Canonical report navigation must not duplicate searchable report bodies."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from cortex.retrieval.memory_searcher import MemoryBankSearcher
from cortex.tools.artifacts.artifact_types import ArtifactType
from cortex.tools.context.l3_deep_search import build_l3
from cortex.tools.context.recent_artifacts_context import (
    build_recent_artifacts_markdown,
)
from cortex.tools.files.artifact_operations import file_artifact
from cortex.wiki.ingest_wiki import index_catalog_linked_page_paths
from cortex.wiki.layout import ensure_default_wiki_layout
from cortex.wiki.wiki_root_files import WikiRootDocument

_MARKER = "bodyonlyquartzmarker"


def _prepare_project(root: Path) -> Path:
    memory_bank = root / ".cortex" / "memory-bank"
    memory_bank.mkdir(parents=True)
    _ = (memory_bank / "activeContext.md").write_text(
        "# Active Context\n\n## Completed Work\n\n", encoding="utf-8"
    )
    _ = ensure_default_wiki_layout(root)
    return root / ".cortex" / "wiki"


def _report_link_target(page: Path) -> Path:
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", page.read_text(encoding="utf-8"))
    assert len(links) == 1
    assert not Path(links[0]).is_absolute()
    assert "\\" not in links[0]
    return (page.parent / links[0]).resolve(strict=True)


async def _file_report(root: Path, artifact_type: ArtifactType, body: str) -> Path:
    response = json.loads(
        await file_artifact(root, artifact_type, "Same Report", body, ["navigation"])
    )
    assert response["status"] == "success"
    path = Path(response["path"])
    assert path.read_text(encoding="utf-8") == body
    return path


def _assert_navigation(root: Path, wiki: Path, page: Path, canonical: Path) -> None:
    assert _report_link_target(page) == canonical.resolve()
    text = page.read_text(encoding="utf-8")
    metadata = yaml.safe_load(text.split("---", 2)[1])
    assert metadata["title"] == "Same Report"
    assert metadata["category"] == "analyses"
    assert metadata["tags"] == ["navigation"]
    assert str(metadata["last_updated"]) == datetime.now(UTC).date().isoformat()
    assert not any(line.startswith("# ") for line in text.splitlines())
    assert _MARKER not in text
    catalog = (wiki / WikiRootDocument.INDEX.value).read_text(encoding="utf-8")
    linked = index_catalog_linked_page_paths(catalog)
    assert page.relative_to(wiki).as_posix() in linked
    assert all((wiki / link).is_file() for link in linked)
    active = root / ".cortex" / "memory-bank" / "activeContext.md"
    targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", active.read_text(encoding="utf-8"))
    assert canonical.resolve() in {(active.parent / link).resolve() for link in targets}


@pytest.mark.parametrize(
    "artifact_type", [ArtifactType.REVIEW_REPORT, ArtifactType.SESSION_ANALYSIS]
)
async def test_report_reference_collision_navigation_and_search(
    tmp_path: Path, artifact_type: ArtifactType
) -> None:
    wiki = _prepare_project(tmp_path)
    body = f"# Same Report\n\n## Summary\n\nBounded catalog summary.\n\n{_MARKER}\n"
    first = await _file_report(tmp_path, artifact_type, body)
    first_reference = wiki / "analyses" / first.name
    occupied = first_reference.with_stem(f"{first.stem}-2")
    _ = occupied.write_text("Unrelated existing wiki page.\n", encoding="utf-8")
    # Canonical suffix -2 must not be inferred from the independent wiki suffix -3.
    second = await _file_report(tmp_path, artifact_type, body)
    second_reference = first_reference.with_stem(f"{first.stem}-3")
    assert second.stem.endswith("-2")
    assert second_reference.name != second.name
    _assert_navigation(tmp_path, wiki, first_reference, first)
    _assert_navigation(tmp_path, wiki, second_reference, second)
    assert occupied.read_text(encoding="utf-8") == "Unrelated existing wiki page.\n"
    _assert_body_search(tmp_path, {first, second})
    recent = build_recent_artifacts_markdown(tmp_path)
    assert recent is not None
    assert all(
        f"../{path.parent.name}/{path.name}" in recent for path in (first, second)
    )
    deep = await build_l3(tmp_path, _MARKER)
    assert set(deep.sources) == {
        path.relative_to(tmp_path).as_posix() for path in (first, second)
    }
    assert _MARKER in deep.content


def _assert_body_search(root: Path, canonical: set[Path]) -> None:
    results = MemoryBankSearcher(root).search(_MARKER)
    assert {result.source for result in results} == {
        path.relative_to(root).as_posix() for path in canonical
    }
    assert all(_MARKER in result.text for result in results)
