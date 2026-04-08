"""Tests for ingest MCP tool and ingest helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.tools.ingest.ingest_handler import ingest
from cortex.tools.ingest.slug import allocate_unique_source_path, slugify_title
from cortex.tools.ingest.source_types import IngestSource, SourceType


def test_slugify_title_basic() -> None:
    assert slugify_title("Hello World") == "hello-world"
    assert slugify_title("  Foo / Bar!!!  ") == "foo-bar"
    assert slugify_title("___") == "untitled"


def test_allocate_unique_source_path_increments(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    _ = sources.mkdir()
    _ = (sources / "foo.md").write_text("a", encoding="utf-8")
    slug, path = allocate_unique_source_path(sources, "foo")
    assert slug == "foo-2"
    assert path == sources / "foo-2.md"


def test_ingest_source_model() -> None:
    m = IngestSource(
        type=SourceType.TEXT,
        content="body",
        title="T",
        tags=["a"],
    )
    assert m.type == SourceType.TEXT


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_ingest_writes_source_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.ingest import ingest_handler as module

    mb = tmp_path / ".cortex" / "memory-bank"
    _ = mb.mkdir(parents=True)

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    result = await ingest(
        source_type="text",
        content="# Hello\n",
        title="Test Doc",
    )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["slug"] == "test-doc"
    assert data["title"] == "Test Doc"
    written = mb / "sources" / "test-doc.md"
    assert written.read_text(encoding="utf-8") == "# Hello\n"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_ingest_collision_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.ingest import ingest_handler as module

    mb = tmp_path / ".cortex" / "memory-bank" / "sources"
    _ = mb.mkdir(parents=True)
    _ = (mb / "same-title.md").write_text("old", encoding="utf-8")

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    result = await ingest(
        source_type="text",
        content="new",
        title="Same Title",
    )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["slug"] == "same-title-2"
    assert (mb / "same-title-2.md").read_text(encoding="utf-8") == "new"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_ingest_rejects_bad_source_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cortex.tools.ingest import ingest_handler as module

    mb = tmp_path / ".cortex" / "memory-bank"
    _ = mb.mkdir(parents=True)

    async def _fake_root(_: object) -> Path:
        return tmp_path

    monkeypatch.setattr(module, "get_or_resolve_project_root", _fake_root)

    result = await ingest(
        source_type="not_a_type",
        content="x",
        title="T",
    )
    data = json.loads(result)
    assert data["status"] == "error"
    assert "invalid_source_type" in data.get("error_code", "")
