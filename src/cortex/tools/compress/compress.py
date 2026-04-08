"""Single-file compression pipeline with validation and retries."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from .detect import detect_file_type
from .prompts import build_compress_prompt, build_fix_prompt
from .validate import ValidationResult, validate_compressed

_MAX_RETRIES = 2


class CompressResult(BaseModel):
    """Result for one file compression attempt."""

    success: bool
    token_ratio: float | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    backup_path: Path | None = None
    skipped_reason: str | None = None


def _run_claude_print(prompt: str) -> str:
    completed = subprocess.run(
        ["claude", "--print"],
        input=prompt,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(f"claude --print failed: {stderr or 'unknown error'}")
    output = completed.stdout.strip()
    if not output:
        raise RuntimeError("claude --print produced empty output")
    return output


def _compress_with_retries(original: str) -> tuple[str, ValidationResult]:
    compressed = _run_claude_print(build_compress_prompt(original))
    validation_result = validate_compressed(original, compressed)

    retries = 0
    # AI: Retry only on structural validation failures; subprocess failures should fail fast.
    while not validation_result.is_valid and retries < _MAX_RETRIES:
        compressed = _run_claude_print(
            build_fix_prompt(original, compressed, validation_result.errors)
        )
        validation_result = validate_compressed(original, compressed)
        retries += 1
    return compressed, validation_result


def _handle_success(
    *,
    path: Path,
    compressed: str,
    backup_path: Path,
    validation_result: ValidationResult,
    dry_run: bool,
) -> CompressResult:
    saved_backup: Path | None = None
    if not dry_run:
        _ = path.write_text(compressed, encoding="utf-8")
        saved_backup = backup_path
    return CompressResult(
        success=True,
        token_ratio=validation_result.token_ratio,
        warnings=validation_result.warnings,
        backup_path=saved_backup,
    )


def _handle_failure(
    *,
    path: Path,
    backup_path: Path,
    validation_result: ValidationResult,
    dry_run: bool,
) -> CompressResult:
    saved_backup: Path | None = None
    if not dry_run:
        restored = backup_path.read_text(encoding="utf-8")
        _ = path.write_text(restored, encoding="utf-8")
        saved_backup = backup_path
    return CompressResult(
        success=False,
        token_ratio=validation_result.token_ratio,
        errors=validation_result.errors,
        warnings=validation_result.warnings,
        backup_path=saved_backup,
    )


def compress_file(path: Path, *, dry_run: bool = False) -> CompressResult:
    """Compress one file, validate structure, and apply on success."""

    file_type = detect_file_type(path)
    if file_type != "natural_language":
        return CompressResult(
            success=False, skipped_reason=f"unsupported_file_type:{file_type}"
        )

    original = path.read_text(encoding="utf-8")
    backup_path = path.with_suffix(f"{path.suffix}.original")
    if not dry_run:
        _ = backup_path.write_text(original, encoding="utf-8")

    compressed, validation_result = _compress_with_retries(original)
    if validation_result.is_valid:
        return _handle_success(
            path=path,
            compressed=compressed,
            backup_path=backup_path,
            validation_result=validation_result,
            dry_run=dry_run,
        )
    return _handle_failure(
        path=path,
        backup_path=backup_path,
        validation_result=validation_result,
        dry_run=dry_run,
    )
