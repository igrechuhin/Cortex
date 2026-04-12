"""Tests for default wiki directory layout."""

import json
from pathlib import Path
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.wiki.layout import (
    bootstrap_wiki_if_cortex_present,
    ensure_default_wiki_layout,
    expected_wiki_category_dirs,
    wiki_has_content,
    wiki_scaffold_present,
    wiki_schema_document_path,
)
from cortex.wiki.wiki_root_files import WikiRootDocument


class TestWikiPaths:
    """Path helpers for wiki files."""

    def test_wiki_schema_document_path(self, tmp_path: Path) -> None:
        """Normative schema lives under `.cortex/wiki/schema.md`."""
        got = wiki_schema_document_path(tmp_path)
        assert got == tmp_path / ".cortex" / "wiki" / WikiRootDocument.SCHEMA.value


class TestBootstrapWikiIfCortexPresent:
    """MCP-style attach: only bootstrap when ``.cortex`` exists."""

    def test_returns_none_without_dot_cortex(self, tmp_path: Path) -> None:
        assert bootstrap_wiki_if_cortex_present(tmp_path) is None

    def test_creates_when_dot_cortex_present(self, tmp_path: Path) -> None:
        _ = (tmp_path / ".cortex").mkdir()
        result = bootstrap_wiki_if_cortex_present(tmp_path)
        assert result is not None
        schema = tmp_path / ".cortex" / "wiki" / WikiRootDocument.SCHEMA.value
        assert schema.is_file()


class TestEnsureDefaultWikiLayout:
    """Bootstrap idempotency and structure."""

    def test_creates_layout_and_index_readable(self, tmp_path: Path) -> None:
        """First run creates dirs, gitkeeps, index, and schema.md."""
        cortex = tmp_path / ".cortex"
        cortex.mkdir(parents=True)

        result = ensure_default_wiki_layout(tmp_path)

        wiki = get_cortex_path(tmp_path, CortexResourceType.WIKI)
        assert result.wiki_root == wiki.as_posix()
        assert wiki.is_dir()
        for name in expected_wiki_category_dirs():
            sub = wiki / name
            assert sub.is_dir()
            assert (sub / ".gitkeep").is_file()

        index = wiki / WikiRootDocument.INDEX.value
        assert index.is_file()
        text = index.read_text(encoding="utf-8")
        assert "Wiki index" in text
        assert "| Page |" in text

        normative = wiki / WikiRootDocument.SCHEMA.value
        assert normative.is_file()
        assert "Cortex project wiki schema" in normative.read_text(encoding="utf-8")

        assert result.created
        assert any(WikiRootDocument.INDEX.value in entry for entry in result.created)

    def test_second_run_skips_existing_paths(self, tmp_path: Path) -> None:
        """Second call reports skips and does not duplicate work."""
        cortex = tmp_path / ".cortex"
        cortex.mkdir(parents=True)
        first = ensure_default_wiki_layout(tmp_path)
        second = ensure_default_wiki_layout(tmp_path)

        assert first.created
        assert not second.created
        assert second.skipped


class TestWikiScaffoldAndContent:
    """``wiki_scaffold_present`` / ``wiki_has_content`` gate ``/cortex/init-wiki`` registration."""

    def test_wiki_scaffold_false_without_schema(self, tmp_path: Path) -> None:
        assert wiki_scaffold_present(tmp_path) is False

    def test_wiki_scaffold_true_with_schema_file(self, tmp_path: Path) -> None:
        wiki = tmp_path / ".cortex" / "wiki"
        wiki.mkdir(parents=True)
        _ = (wiki / WikiRootDocument.SCHEMA.value).write_text("s", encoding="utf-8")
        assert wiki_scaffold_present(tmp_path) is True

    def test_wiki_has_content_false_after_bootstrap_only(self, tmp_path: Path) -> None:
        cortex = tmp_path / ".cortex"
        cortex.mkdir(parents=True)
        _ = ensure_default_wiki_layout(tmp_path)
        assert wiki_has_content(tmp_path) is False

    def test_wiki_has_content_true_when_concepts_has_md(self, tmp_path: Path) -> None:
        cortex = tmp_path / ".cortex"
        cortex.mkdir(parents=True)
        _ = ensure_default_wiki_layout(tmp_path)
        wiki = get_cortex_path(tmp_path, CortexResourceType.WIKI)
        _ = (wiki / "concepts" / "topic.md").write_text("# Topic\n", encoding="utf-8")
        assert wiki_has_content(tmp_path) is True

    def test_sources_only_does_not_count_as_wiki_pages(self, tmp_path: Path) -> None:
        cortex = tmp_path / ".cortex"
        cortex.mkdir(parents=True)
        _ = ensure_default_wiki_layout(tmp_path)
        wiki = get_cortex_path(tmp_path, CortexResourceType.WIKI)
        _ = (wiki / "sources" / "snap.md").write_text("# Snap\n", encoding="utf-8")
        assert wiki_has_content(tmp_path) is False


class TestInitWikiSynapsePrompt:
    """`/cortex/init-wiki` workflow is registered next to other Synapse prompts."""

    def test_init_wiki_prompt_exists_and_manifest_lists_it(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        prompts_dir = repo / ".cortex" / "synapse" / "prompts"
        prompt_path = prompts_dir / "init-wiki.md"
        manifest_path = prompts_dir / "prompts-manifest.json"

        assert prompt_path.is_file()
        raw: object = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        categories = cast(dict[str, object], raw).get("categories")
        assert isinstance(categories, dict)
        general = cast(dict[str, object], categories).get("general")
        assert isinstance(general, dict)
        prompts_val = cast(dict[str, object], general).get("prompts")
        assert isinstance(prompts_val, list)
        files = [
            str(cast(dict[str, object], p).get("file", ""))
            for p in cast(list[object], prompts_val)
            if isinstance(p, dict)
        ]
        assert "init-wiki.md" in files
        assert "# Init Wiki" in prompt_path.read_text(encoding="utf-8")


class TestAskSynapsePrompt:
    """`/cortex/ask` workflow is registered next to other Synapse prompts."""

    def test_ask_prompt_exists_and_manifest_lists_it(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        prompts_dir = repo / ".cortex" / "synapse" / "prompts"
        prompt_path = prompts_dir / "ask.md"
        manifest_path = prompts_dir / "prompts-manifest.json"

        assert prompt_path.is_file()
        raw: object = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        categories = cast(dict[str, object], raw).get("categories")
        assert isinstance(categories, dict)
        general = cast(dict[str, object], categories).get("general")
        assert isinstance(general, dict)
        prompts_val = cast(dict[str, object], general).get("prompts")
        assert isinstance(prompts_val, list)
        files = [
            str(cast(dict[str, object], p).get("file", ""))
            for p in cast(list[object], prompts_val)
            if isinstance(p, dict)
        ]
        assert "ask.md" in files
        assert "# Ask" in prompt_path.read_text(encoding="utf-8")
