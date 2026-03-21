"""Unit tests for internal markdown link validation (docs + policy files)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.tools.files.markdown_link_validation import (
    BrokenLink,
    collect_markdown_files_for_link_check,
    find_broken_links,
    format_broken_links_report,
    is_doc_placeholder_link,
    resolve_exists,
    run_cli,
    should_skip_target,
    strip_inline_link_title,
)


def test_valid_relative_link(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    target = tmp_path / "docs" / "other.md"
    _ = target.write_text("# Other\n", encoding="utf-8")
    src = tmp_path / "docs" / "a.md"
    _ = src.write_text("See [o](other.md).\n", encoding="utf-8")
    assert find_broken_links(tmp_path) == []


def test_broken_relative_link(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    src = tmp_path / "docs" / "a.md"
    _ = src.write_text("See [x](missing.md).\n", encoding="utf-8")
    got = find_broken_links(tmp_path)
    assert len(got) == 1
    assert got[0] == BrokenLink(source_file="docs/a.md", line=1, target="missing.md")


def test_anchor_only_skipped(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    src = tmp_path / "docs" / "a.md"
    _ = src.write_text("Jump to [#section](#section).\n", encoding="utf-8")
    assert find_broken_links(tmp_path) == []


def test_http_skipped(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    src = tmp_path / "docs" / "a.md"
    _ = src.write_text("[e](https://example.com/foo).\n", encoding="utf-8")
    assert find_broken_links(tmp_path) == []


def test_cortex_scheme_skipped(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    src = tmp_path / "docs" / "a.md"
    _ = src.write_text("[r](cortex://rules).\n", encoding="utf-8")
    assert find_broken_links(tmp_path) == []


def test_link_inside_fenced_block_ignored(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    src = tmp_path / "docs" / "a.md"
    _ = src.write_text(
        "```\n[bad](nope.md)\n```\n[good](ok.md)\n",
        encoding="utf-8",
    )
    ok = tmp_path / "docs" / "ok.md"
    _ = ok.write_text("# OK\n", encoding="utf-8")
    assert find_broken_links(tmp_path) == []


def test_fragment_requires_existing_file(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    tgt = tmp_path / "docs" / "t.md"
    _ = tgt.write_text("# T\n", encoding="utf-8")
    src = tmp_path / "docs" / "a.md"
    _ = src.write_text("[x](t.md#section)\n", encoding="utf-8")
    assert find_broken_links(tmp_path) == []


def test_directory_target_ok(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    _ = (tmp_path / "docs" / "sub").mkdir()
    src = tmp_path / "docs" / "a.md"
    _ = src.write_text("[d](sub/)\n", encoding="utf-8")
    assert find_broken_links(tmp_path) == []


def test_placeholder_pattern_skipped(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    src = tmp_path / "docs" / "a.md"
    _ = src.write_text("Example [text](target.md#section).\n", encoding="utf-8")
    assert find_broken_links(tmp_path) == []


def test_placeholder_with_inline_title_skipped(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    src = tmp_path / "docs" / "a.md"
    _ = src.write_text('Doc [text](target "title").\n', encoding="utf-8")
    assert find_broken_links(tmp_path) == []


def test_link_escaping_outside_project_reported_broken(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    src = tmp_path / "docs" / "a.md"
    _ = src.write_text("[x](../../../nope.md)\n", encoding="utf-8")
    assert len(find_broken_links(tmp_path)) == 1


def test_read_text_oserror_skips_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = (tmp_path / "docs").mkdir()
    good = tmp_path / "docs" / "ok.md"
    bad = tmp_path / "docs" / "bad.md"
    _ = good.write_text("[l](peer.md)\n", encoding="utf-8")
    _ = bad.write_text("x\n", encoding="utf-8")
    peer = tmp_path / "docs" / "peer.md"
    _ = peer.write_text("# p\n", encoding="utf-8")
    orig = Path.read_text

    def _read_text(
        self: Path,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> str:
        if self.resolve() == bad.resolve():
            raise OSError("denied")
        return orig(self, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "read_text", _read_text)
    assert find_broken_links(tmp_path) == []


def test_strip_inline_link_title() -> None:
    assert strip_inline_link_title('foo.md "Title"') == "foo.md"
    assert strip_inline_link_title("foo.md") == "foo.md"


def test_should_skip_target() -> None:
    assert should_skip_target("#only")
    assert should_skip_target("https://a.b")
    assert should_skip_target("//cdn.example/lib.js")
    assert not should_skip_target("./x.md")


def test_is_doc_placeholder_link() -> None:
    assert is_doc_placeholder_link("text", "target.md")
    assert not is_doc_placeholder_link("See", "target.md")


def test_resolve_exists_accepts_empty_path_part(tmp_path: Path) -> None:
    src = tmp_path / "docs" / "a.md"
    assert resolve_exists(tmp_path, src, "") is True


def test_collect_skips_non_file_md_entries(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    link = tmp_path / "docs" / "ghost.md"
    link.symlink_to("nonexistent-target.md")
    assert collect_markdown_files_for_link_check(tmp_path) == []


def test_collect_includes_readme_at_root(tmp_path: Path) -> None:
    _ = (tmp_path / "docs").mkdir()
    _ = (tmp_path / "README.md").write_text("# R\n", encoding="utf-8")
    paths = collect_markdown_files_for_link_check(tmp_path)
    rels = {str(p.relative_to(tmp_path)) for p in paths}
    assert "README.md" in rels


def test_format_broken_links_report() -> None:
    b = [BrokenLink(source_file="a.md", line=2, target="z.md")]
    assert "a.md:2" in format_broken_links_report(b)
    assert "z.md" in format_broken_links_report(b)


def test_run_cli_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ = (tmp_path / "docs").mkdir()
    _ = (tmp_path / "docs" / "a.md").write_text("x\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert run_cli([]) == 0


def test_run_cli_reports_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = (tmp_path / "docs").mkdir()
    _ = (tmp_path / "docs" / "a.md").write_text("[b](gone.md)\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert run_cli([]) == 1
