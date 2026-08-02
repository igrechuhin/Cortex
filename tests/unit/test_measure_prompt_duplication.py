"""Tests for scripts/measure_prompt_duplication.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "measure_prompt_duplication.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "measure_prompt_duplication", SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        msg = f"Cannot load {SCRIPT_PATH}"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    # AI: dataclass field resolution reads sys.modules[cls.__module__]; register
    # before exec so @dataclass does not fail on a missing module entry.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_mod = _load_module()

SHARED_BLOCK = "## Orientation\nCall session() first.\nThen read cortex://rules.\n"


def _write_prompts(root: Path, files: dict[str, str]) -> Path:
    """Create a prompts directory populated with the given files."""
    root.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        _ = (root / name).write_text(body, encoding="utf-8")
    return root


class TestEstimateTokens:
    """Tests for estimate_tokens."""

    def test_empty_string_is_zero(self) -> None:
        """Arrange empty text; act; assert zero tokens."""
        assert _mod.estimate_tokens("") == 0

    def test_rounds_up_to_whole_tokens(self) -> None:
        """Five characters occupy two 4-char tokens."""
        assert _mod.estimate_tokens("abcde") == 2


class TestLoadPrompts:
    """Tests for load_prompts."""

    def test_loads_all_markdown_files(self, tmp_path: Path) -> None:
        """Arrange two prompts plus a non-markdown file; act; assert count."""
        prompts = _write_prompts(
            tmp_path / "prompts", {"a.md": "alpha\n", "b.md": "beta\n"}
        )
        _ = (prompts / "manifest.json").write_text("{}", encoding="utf-8")

        loaded = _mod.load_prompts(prompts)

        assert [p.path.name for p in loaded] == ["a.md", "b.md"]

    def test_reports_tokens_and_strips_trailing_whitespace(
        self, tmp_path: Path
    ) -> None:
        """Trailing spaces are normalized away in the line view."""
        prompts = _write_prompts(tmp_path / "prompts", {"a.md": "alpha   \nbeta\n"})

        loaded = _mod.load_prompts(prompts)

        assert loaded[0].lines == ("alpha", "beta")
        assert loaded[0].tokens > 0

    def test_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        """Arrange an empty directory; act; assert no prompts."""
        prompts = _write_prompts(tmp_path / "prompts", {})

        assert _mod.load_prompts(prompts) == []


class TestFindDuplicateBlocks:
    """Tests for find_duplicate_blocks."""

    def test_finds_block_shared_by_enough_files(self, tmp_path: Path) -> None:
        """A 3-line block in 3 files is reported once with 3 occurrences."""
        body = {name: f"# {name}\n{SHARED_BLOCK}" for name in ("a.md", "b.md", "c.md")}
        prompts = _mod.load_prompts(_write_prompts(tmp_path / "prompts", body))

        blocks = _mod.find_duplicate_blocks(prompts, min_block=3, min_files=3)

        assert blocks
        assert blocks[0].file_count == 3
        assert set(blocks[0].occurrences) == {"a.md", "b.md", "c.md"}

    def test_ignores_block_below_file_threshold(self, tmp_path: Path) -> None:
        """A block present in only 2 files is excluded when min_files is 3."""
        body = {
            "a.md": SHARED_BLOCK,
            "b.md": SHARED_BLOCK,
            "c.md": "# unrelated\nnothing shared here\nat all whatsoever\n",
        }
        prompts = _mod.load_prompts(_write_prompts(tmp_path / "prompts", body))

        blocks = _mod.find_duplicate_blocks(prompts, min_block=3, min_files=3)

        assert blocks == []

    def test_skips_insignificant_blank_blocks(self, tmp_path: Path) -> None:
        """Blocks of blank or trivial lines are not reported as duplicates."""
        body = {name: "\n\n\n\n" for name in ("a.md", "b.md", "c.md")}
        prompts = _mod.load_prompts(_write_prompts(tmp_path / "prompts", body))

        blocks = _mod.find_duplicate_blocks(prompts, min_block=3, min_files=3)

        assert blocks == []

    def test_redundant_tokens_exclude_the_retained_copy(self, tmp_path: Path) -> None:
        """Savings count N-1 copies, since one canonical copy is kept."""
        body = {name: SHARED_BLOCK for name in ("a.md", "b.md", "c.md")}
        prompts = _mod.load_prompts(_write_prompts(tmp_path / "prompts", body))

        block = _mod.find_duplicate_blocks(prompts, min_block=3, min_files=3)[0]

        assert block.redundant_tokens == block.tokens * 2


class TestBuildReport:
    """Tests for build_report."""

    def test_report_contains_baseline_and_extractable_share(
        self, tmp_path: Path
    ) -> None:
        """Arrange duplicated prompts; act; assert a non-zero extractable share."""
        body = {name: SHARED_BLOCK for name in ("a.md", "b.md", "c.md")}
        prompts = _mod.load_prompts(_write_prompts(tmp_path / "prompts", body))
        blocks = _mod.find_duplicate_blocks(prompts, min_block=3, min_files=3)

        report = _mod.build_report(prompts, blocks)

        assert report["file_count"] == 3
        assert report["baseline_total_tokens"] > 0
        assert report["extractable_pct"] > 0

    def test_zero_baseline_yields_zero_pct(self, tmp_path: Path) -> None:
        """Empty prompt files must not cause a division-by-zero."""
        prompts = _mod.load_prompts(
            _write_prompts(tmp_path / "prompts", {"a.md": "", "b.md": ""})
        )

        report = _mod.build_report(prompts, [])

        assert report["extractable_pct"] == 0.0


class TestMain:
    """Tests for the CLI entry point."""

    def test_emits_json_report(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Arrange a prompts dir; act via main; assert parseable JSON on stdout."""
        prompts = _write_prompts(
            tmp_path / "prompts", {name: SHARED_BLOCK for name in ("a.md", "b.md")}
        )

        code = _mod.main(["--prompts-dir", str(prompts), "--min-files", "2"])

        assert code == 0
        assert json.loads(capsys.readouterr().out)["file_count"] == 2

    def test_missing_prompts_returns_error_code(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An empty prompts directory is an explicit failure, not a silent pass."""
        empty = _write_prompts(tmp_path / "prompts", {})

        code = _mod.main(["--prompts-dir", str(empty)])

        assert code == 1
        assert "No prompts found" in capsys.readouterr().err


class TestRealPromptsBaseline:
    """Regression guard on the repository's own prompt corpus."""

    def test_extractable_share_below_plan_threshold(self) -> None:
        """The shared-layer plan aborts below 15%; assert the measured finding."""
        prompts = _mod.load_prompts(REPO_ROOT / ".cortex" / "synapse" / "prompts")
        blocks = _mod.find_duplicate_blocks(prompts, min_block=3, min_files=3)

        report = _mod.build_report(prompts, blocks)

        assert report["extractable_pct"] < 15.0

    def test_refactoring_notes_are_not_prompts(self) -> None:
        """The relocated development notes must no longer sit in prompts/."""
        prompts = _mod.load_prompts(REPO_ROOT / ".cortex" / "synapse" / "prompts")

        names = {p.path.name for p in prompts}

        assert "REFACTORING_GUIDE.md" not in names
        assert "REFACTORING_SUMMARY.md" not in names
