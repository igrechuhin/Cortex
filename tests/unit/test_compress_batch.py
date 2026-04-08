"""Unit tests for batch compression orchestration."""

from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from cortex.tools.compress.batch import (
    compress_cortex_internal_files,
    compress_directory,
)
from cortex.tools.compress.compress import CompressResult


def _create_cortex_target_tree(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex" / "synapse" / "prompts").mkdir(parents=True)
    _ = (tmp_path / ".cortex" / "synapse" / "cursor-agents").mkdir(parents=True)
    memory_bank = tmp_path / ".cortex" / "memory-bank"
    _ = memory_bank.mkdir(parents=True)
    _ = (memory_bank / "activeContext.md").write_text("# Active\n", encoding="utf-8")
    _ = (memory_bank / "progress.md").write_text("# Progress\n", encoding="utf-8")
    _ = (memory_bank / "roadmap.md").write_text("# Roadmap\n", encoding="utf-8")


def _patch_batch_logger(
    monkeypatch: MonkeyPatch,
) -> tuple[list[str], list[str]]:
    info_logs: list[str] = []
    error_logs: list[str] = []

    def fake_info(message: str, *args: object) -> None:
        info_logs.append(message % args)

    def fake_error(message: str, *args: object) -> None:
        error_logs.append(message % args)

    monkeypatch.setattr("cortex.tools.compress.batch.logger.info", fake_info)
    monkeypatch.setattr("cortex.tools.compress.batch.logger.error", fake_error)
    return info_logs, error_logs


def test_compress_directory_skips_backup_files(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    normal = tmp_path / "a.md"
    backup = tmp_path / "a.original.md"
    _ = normal.write_text("# Normal\n", encoding="utf-8")
    _ = backup.write_text("# Backup\n", encoding="utf-8")
    called_paths: list[Path] = []

    def fake_compress_file(path: Path, *, dry_run: bool = False) -> CompressResult:
        called_paths.append(path)
        return CompressResult(success=True, token_ratio=0.5)

    monkeypatch.setattr("cortex.tools.compress.batch.compress_file", fake_compress_file)

    # Act
    results = compress_directory(tmp_path)

    # Assert
    assert len(results) == 1
    assert called_paths == [normal]


def test_compress_directory_collects_results_for_all_selected_files(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    _ = first.write_text("# One\n", encoding="utf-8")
    _ = second.write_text("# Two\n", encoding="utf-8")

    def fake_compress_file(path: Path, *, dry_run: bool = False) -> CompressResult:
        success = path.name == "first.md"
        return CompressResult(
            success=success,
            token_ratio=0.6 if success else 0.9,
            skipped_reason=None if success else "unsupported_file_type:code",
        )

    monkeypatch.setattr("cortex.tools.compress.batch.compress_file", fake_compress_file)

    # Act
    results = compress_directory(tmp_path, dry_run=True)

    # Assert
    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is False
    assert results[1].skipped_reason == "unsupported_file_type:code"


def test_compress_directory_logs_per_file_outcome(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    success_file = tmp_path / "success.md"
    skipped_file = tmp_path / "skipped.md"
    failure_file = tmp_path / "failure.md"
    _ = success_file.write_text("# One\n", encoding="utf-8")
    _ = skipped_file.write_text("# Two\n", encoding="utf-8")
    _ = failure_file.write_text("# Three\n", encoding="utf-8")

    def fake_compress_file(path: Path, *, dry_run: bool = False) -> CompressResult:
        if path.name == "success.md":
            return CompressResult(success=True, token_ratio=0.5)
        if path.name == "skipped.md":
            return CompressResult(
                success=False,
                token_ratio=0.95,
                skipped_reason="unsupported_file_type:code",
            )
        return CompressResult(success=False, token_ratio=1.0, errors=["missing URL"])

    monkeypatch.setattr("cortex.tools.compress.batch.compress_file", fake_compress_file)
    info_logs, error_logs = _patch_batch_logger(monkeypatch)

    # Act
    _ = compress_directory(tmp_path, dry_run=True)

    # Assert
    assert any("compress success" in message for message in info_logs)
    assert any("compress skip" in message for message in info_logs)
    assert any("compress failure" in message for message in error_logs)


def test_compress_cortex_internal_files_targets_expected_locations(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    _create_cortex_target_tree(tmp_path)

    directory_calls: list[tuple[Path, str, bool]] = []
    file_calls: list[tuple[Path, bool]] = []

    def fake_compress_directory(
        root: Path, *, glob: str = "**/*.md", dry_run: bool = False
    ) -> list[CompressResult]:
        directory_calls.append((root, glob, dry_run))
        return [CompressResult(success=True, token_ratio=0.5)]

    def fake_compress_file(path: Path, *, dry_run: bool = False) -> CompressResult:
        file_calls.append((path, dry_run))
        return CompressResult(success=True, token_ratio=0.6)

    monkeypatch.setattr(
        "cortex.tools.compress.batch.compress_directory", fake_compress_directory
    )
    monkeypatch.setattr("cortex.tools.compress.batch.compress_file", fake_compress_file)

    # Act
    results = compress_cortex_internal_files(tmp_path, dry_run=True)

    # Assert
    assert len(results) == 4
    assert directory_calls == [
        (tmp_path / ".cortex" / "synapse" / "prompts", "**/*.md", True),
        (tmp_path / ".cortex" / "synapse" / "cursor-agents", "**/*.md", True),
    ]
    assert file_calls == [
        (tmp_path / ".cortex" / "memory-bank" / "activeContext.md", True),
        (tmp_path / ".cortex" / "memory-bank" / "progress.md", True),
    ]


def test_compress_cortex_internal_files_skips_missing_paths(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    called: list[Path] = []

    def fake_compress_file(path: Path, *, dry_run: bool = False) -> CompressResult:
        called.append(path)
        return CompressResult(success=True, token_ratio=0.7)

    monkeypatch.setattr("cortex.tools.compress.batch.compress_file", fake_compress_file)

    # Act
    results = compress_cortex_internal_files(tmp_path)

    # Assert
    assert results == []
    assert called == []
