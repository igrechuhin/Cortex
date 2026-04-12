"""Tests for wiki_status on session_start and wiki session helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.tools.models import SessionStartResult
from cortex.tools.session.models import WikiStatusSummary
from cortex.tools.session.wiki_status import (
    append_session_wiki_init_hint,
    compute_wiki_status,
    project_has_wiki_seed_docs,
)
from cortex.wiki.layout import ensure_default_wiki_layout
from tests.tools.session_start_fixtures import (
    managers_for_phase54_session_start,
    run_session_start_patched_mcp_healthy,
)


def test_project_has_wiki_seed_docs_readme(tmp_path: Path) -> None:
    _ = (tmp_path / "README.md").write_text("# Hi\n")
    assert project_has_wiki_seed_docs(tmp_path) is True


def test_project_has_wiki_seed_docs_docs_dir(tmp_path: Path) -> None:
    d = tmp_path / "docs"
    d.mkdir()
    _ = (d / "guide.md").write_text("# Guide\n")
    assert project_has_wiki_seed_docs(tmp_path) is True


def test_project_has_wiki_seed_docs_negative(tmp_path: Path) -> None:
    assert project_has_wiki_seed_docs(tmp_path) is False


def test_compute_wiki_status_no_cortex(tmp_path: Path) -> None:
    st = compute_wiki_status(tmp_path)
    assert st == WikiStatusSummary()


def test_append_session_wiki_init_hint(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir()
    _ = (tmp_path / "README.md").write_text("# Hi\n")
    wiki = WikiStatusSummary(
        wiki_enabled=False, wiki_page_count=0, wiki_path=".cortex/wiki"
    )
    out: list[str] = []
    append_session_wiki_init_hint(out, wiki, tmp_path)
    assert len(out) == 1 and "init-wiki" in out[0]


def test_compute_wiki_status_with_wiki(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir()
    _ = ensure_default_wiki_layout(tmp_path)
    st = compute_wiki_status(tmp_path)
    assert st.wiki_enabled is True
    assert st.wiki_path == ".cortex/wiki"
    assert st.wiki_page_count >= 2


@pytest.mark.asyncio
async def test_session_start_brief_includes_wiki_status(tmp_path: Path) -> None:
    managers = await managers_for_phase54_session_start(tmp_path)
    result = await run_session_start_patched_mcp_healthy(tmp_path, managers)
    assert isinstance(result, SessionStartResult)
    ws = result.brief.wiki_status
    assert ws.wiki_path is None or ws.wiki_path == ".cortex/wiki"
    assert isinstance(ws.wiki_page_count, int)
    assert ws.wiki_page_count >= 0
