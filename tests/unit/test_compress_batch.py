"""Unit tests for batch compression orchestration."""

from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from cortex.tools.compress.batch import (
    compress_cortex_internal_files,
    compress_directory,
    run_and_verify_cortex_compression,
    summarize_compression_results,
    verify_compression_success_criteria,
)
from cortex.tools.compress.compress import CompressResult


def _create_cortex_target_tree(tmp_path: Path) -> None:
    prompts = tmp_path / ".cortex" / "synapse" / "prompts"
    agents = tmp_path / ".cortex" / "synapse" / "cursor-agents"
    _ = prompts.mkdir(parents=True)
    _ = agents.mkdir(parents=True)
    _ = (prompts / "plan.md").write_text("# Prompt\n", encoding="utf-8")
    _ = (agents / "implement-code.md").write_text("# Agent\n", encoding="utf-8")
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
    assert results[0].path == normal


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
    assert results[0].path == first
    assert results[1].path == second
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


def test_compress_directory_continues_after_exception(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    _ = first.write_text("# One\n", encoding="utf-8")
    _ = second.write_text("# Two\n", encoding="utf-8")
    info_logs, error_logs = _patch_batch_logger(monkeypatch)

    def fake_compress_file(path: Path, *, dry_run: bool = False) -> CompressResult:
        if path.name == "a.md":
            raise RuntimeError("transient claude failure")
        return CompressResult(success=True, token_ratio=0.4)

    monkeypatch.setattr("cortex.tools.compress.batch.compress_file", fake_compress_file)

    # Act
    results = compress_directory(tmp_path, dry_run=True)

    # Assert
    assert len(results) == 2
    assert results[0].success is False
    assert results[0].path == first
    assert results[0].errors == ["exception:RuntimeError:transient claude failure"]
    assert results[1].success is True
    assert results[1].path == second
    assert any("compress failure" in message for message in error_logs)
    assert any("compress success" in message for message in info_logs)


def test_compress_cortex_internal_files_targets_expected_locations(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    _create_cortex_target_tree(tmp_path)

    file_calls: list[tuple[Path, bool]] = []

    def fake_compress_file(path: Path, *, dry_run: bool = False) -> CompressResult:
        file_calls.append((path, dry_run))
        return CompressResult(success=True, path=path, token_ratio=0.6)

    monkeypatch.setattr("cortex.tools.compress.batch.compress_file", fake_compress_file)

    # Act
    results = compress_cortex_internal_files(tmp_path, dry_run=True)

    # Assert
    assert len(results) == 4
    assert (
        sum(
            result.skipped_reason == "protected_target:prompt_integrity_policy"
            for result in results
        )
        == 2
    )
    assert file_calls == [
        (tmp_path / ".cortex" / "memory-bank" / "activeContext.md", True),
        (tmp_path / ".cortex" / "memory-bank" / "progress.md", True),
    ]
    assert all(result.path is not None for result in results)


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
    assert len(results) == 4
    assert all(result.success is False for result in results)
    assert all(result.skipped_reason is not None for result in results)
    assert all(
        (reason is not None and reason.startswith("missing_target:"))
        for reason in (result.skipped_reason for result in results)
    )
    assert {result.path for result in results} == {
        tmp_path / ".cortex" / "synapse" / "prompts",
        tmp_path / ".cortex" / "synapse" / "cursor-agents",
        tmp_path / ".cortex" / "memory-bank" / "activeContext.md",
        tmp_path / ".cortex" / "memory-bank" / "progress.md",
    }
    assert called == []


def test_summarize_compression_results_counts_missing_targets_as_skipped() -> None:
    # Arrange
    results = [
        CompressResult(success=False, skipped_reason="missing_target:prompts_root"),
        CompressResult(success=False, skipped_reason="missing_target:progress.md"),
        CompressResult(success=True, token_ratio=0.6),
    ]

    # Act
    summary = summarize_compression_results(results, target_reduction=0.35)

    # Assert
    assert summary.total_files == 3
    assert summary.successful_files == 1
    assert summary.skipped_files == 2
    assert summary.failed_files == 0


def test_summarize_compression_results_computes_counts_and_target_hits() -> None:
    # Arrange
    results = [
        CompressResult(success=True, token_ratio=0.60),
        CompressResult(success=True, token_ratio=0.80),
        CompressResult(success=False, errors=["validation failure"]),
        CompressResult(success=False, skipped_reason="unsupported_file_type:code"),
    ]

    # Act
    summary = summarize_compression_results(results, target_reduction=0.35)

    # Assert
    assert summary.total_files == 4
    assert summary.successful_files == 2
    assert summary.failed_files == 1
    assert summary.skipped_files == 1
    assert summary.files_meeting_target == 1
    assert summary.average_token_ratio == 0.7


def test_summarize_compression_results_rejects_invalid_target() -> None:
    # Arrange
    results = [CompressResult(success=True, token_ratio=0.60)]

    # Act / Assert
    try:
        _ = summarize_compression_results(results, target_reduction=1.0)
    except ValueError as error:
        assert "target_reduction" in str(error)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError for invalid target_reduction")


def test_verify_compression_success_criteria_passes_when_thresholds_met() -> None:
    # Arrange
    summary = summarize_compression_results(
        [
            CompressResult(success=True, token_ratio=0.60),
            CompressResult(success=True, token_ratio=0.62),
            CompressResult(success=True, token_ratio=0.64),
            CompressResult(success=True, token_ratio=0.80),
            CompressResult(success=True, token_ratio=0.90),
        ],
        target_reduction=0.35,
    )

    # Act
    result = verify_compression_success_criteria(summary)

    # Assert
    assert result.passed is True
    assert result.errors == []
    assert result.successful_files == 5
    assert result.failed_files == 0
    assert result.files_meeting_target == 3


def test_verify_compression_success_criteria_fails_with_insufficient_successes() -> (
    None
):
    # Arrange
    summary = summarize_compression_results(
        [
            CompressResult(success=True, token_ratio=0.60),
            CompressResult(success=True, token_ratio=0.70),
            CompressResult(success=False, errors=["failed"]),
        ],
        target_reduction=0.35,
    )

    # Act
    result = verify_compression_success_criteria(summary)

    # Assert
    assert result.passed is False
    assert "insufficient_successful_files:2<5" in result.errors
    assert "too_many_failed_files:1>0" in result.errors


def test_verify_compression_success_criteria_fails_when_failed_files_exceed_limit() -> (
    None
):
    # Arrange
    summary = summarize_compression_results(
        [
            CompressResult(success=True, token_ratio=0.60),
            CompressResult(success=True, token_ratio=0.62),
            CompressResult(success=True, token_ratio=0.64),
            CompressResult(success=True, token_ratio=0.66),
            CompressResult(success=True, token_ratio=0.68),
            CompressResult(success=False, errors=["runtime failure"]),
        ],
        target_reduction=0.35,
    )

    # Act
    result = verify_compression_success_criteria(summary)

    # Assert
    assert result.passed is False
    assert "too_many_failed_files:1>0" in result.errors


def test_verify_compression_success_criteria_allows_configured_failure_budget() -> None:
    # Arrange
    summary = summarize_compression_results(
        [
            CompressResult(success=True, token_ratio=0.60),
            CompressResult(success=True, token_ratio=0.62),
            CompressResult(success=True, token_ratio=0.64),
            CompressResult(success=True, token_ratio=0.66),
            CompressResult(success=True, token_ratio=0.68),
            CompressResult(success=False, errors=["runtime failure"]),
        ],
        target_reduction=0.35,
    )

    # Act
    result = verify_compression_success_criteria(summary, allowed_failed_files=1)

    # Assert
    assert result.passed is True
    assert result.failed_files == 1


def test_verify_compression_success_criteria_validates_configuration() -> None:
    # Arrange
    summary = summarize_compression_results([], target_reduction=0.35)

    # Act / Assert
    try:
        _ = verify_compression_success_criteria(
            summary,
            required_sample_size=2,
            minimum_target_hits=3,
        )
    except ValueError as error:
        assert "minimum_target_hits" in str(error)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError for invalid verification thresholds")

    try:
        _ = verify_compression_success_criteria(summary, allowed_failed_files=-1)
    except ValueError as error:
        assert "allowed_failed_files" in str(error)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError for negative allowed_failed_files")


def test_run_and_verify_cortex_compression_returns_integrated_report(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    mocked_results = [
        CompressResult(success=True, token_ratio=0.60),
        CompressResult(success=True, token_ratio=0.62),
        CompressResult(success=True, token_ratio=0.64),
        CompressResult(success=True, token_ratio=0.80),
        CompressResult(success=True, token_ratio=0.90),
    ]

    def fake_compress_internal(
        repo_root: Path, *, dry_run: bool = True
    ) -> list[CompressResult]:
        assert repo_root == tmp_path
        assert dry_run is True
        return mocked_results

    monkeypatch.setattr(
        "cortex.tools.compress.batch.compress_cortex_internal_files",
        fake_compress_internal,
    )

    # Act
    report = run_and_verify_cortex_compression(tmp_path, dry_run=True)

    # Assert
    assert report.results == mocked_results
    assert report.summary.total_files == 5
    assert report.summary.files_meeting_target == 3
    assert report.verification.passed is True
    assert report.verification.errors == []


def test_run_and_verify_cortex_compression_applies_custom_thresholds(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    mocked_results = [
        CompressResult(success=True, token_ratio=0.60),
        CompressResult(success=True, token_ratio=0.70),
        CompressResult(success=True, token_ratio=0.80),
        CompressResult(success=False, errors=["runtime failure"]),
    ]

    def fake_compress_internal(
        repo_root: Path, *, dry_run: bool = True
    ) -> list[CompressResult]:
        return mocked_results

    monkeypatch.setattr(
        "cortex.tools.compress.batch.compress_cortex_internal_files",
        fake_compress_internal,
    )
    report = run_and_verify_cortex_compression(
        tmp_path,
        dry_run=False,
        target_reduction=0.20,
        required_sample_size=3,
        minimum_target_hits=2,
        allowed_failed_files=1,
    )
    assert report.summary.target_reduction == 0.20
    assert report.summary.total_files == 4
    assert report.summary.failed_files == 1
    assert report.summary.files_meeting_target == 3
    assert report.verification.passed is True


def test_run_and_verify_cortex_compression_relaxes_target_hits_in_protected_mode(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    mocked_results = [
        CompressResult(
            success=False,
            skipped_reason="protected_target:prompt_integrity_policy",
        ),
        CompressResult(
            success=False, skipped_reason="protected_target:prompt_integrity_policy"
        ),
        CompressResult(success=True, token_ratio=0.95),
        CompressResult(success=True, token_ratio=0.92),
    ]

    def fake_compress_internal(
        repo_root: Path, *, dry_run: bool = True
    ) -> list[CompressResult]:
        return mocked_results

    monkeypatch.setattr(
        "cortex.tools.compress.batch.compress_cortex_internal_files",
        fake_compress_internal,
    )

    report = run_and_verify_cortex_compression(tmp_path, dry_run=False)

    assert report.verification.required_sample_size == 2
    assert report.verification.minimum_target_hits == 0
    assert report.verification.passed is True


def test_run_and_verify_cortex_compression_fails_when_zero_success_in_protected_mode(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    mocked_results = [
        CompressResult(
            success=False,
            skipped_reason="protected_target:prompt_integrity_policy",
        ),
        CompressResult(
            success=False, skipped_reason="protected_target:prompt_integrity_policy"
        ),
        CompressResult(
            success=False,
            errors=["Compressed token count must be lower than original."],
        ),
    ]

    def fake_compress_internal(
        repo_root: Path, *, dry_run: bool = True
    ) -> list[CompressResult]:
        return mocked_results

    monkeypatch.setattr(
        "cortex.tools.compress.batch.compress_cortex_internal_files",
        fake_compress_internal,
    )

    report = run_and_verify_cortex_compression(tmp_path, dry_run=False)

    assert report.verification.passed is False
    assert report.verification.successful_files == 0
    assert any(
        e.startswith("insufficient_successful_files")
        for e in report.verification.errors
    )
