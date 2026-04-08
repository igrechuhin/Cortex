"""Single-file compression pipeline with validation and retries."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from .detect import detect_file_type
from .prompts import build_compress_prompt, build_fix_prompt
from .validate import ValidationResult, validate_compressed

_MAX_RETRIES = 2
# AI: Fallback runs only when `claude --print` is unavailable. Keep phrase-level
# removals only; do not strip function words or truncate lines (that broke meaning).
_SAFE_FILLER_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bplease note that\b", ""),
    (r"\bit is important to\b", ""),
    (r"\bin order to\b", "to"),
    (r"\bmake sure to\b", ""),
)


class CompressResult(BaseModel):
    """Result for one file compression attempt."""

    success: bool
    path: Path | None = None
    token_ratio: float | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    backup_path: Path | None = None
    skipped_reason: str | None = None


def _compress_plain_line(line: str) -> str:
    if (
        "http://" in line
        or "https://" in line
        or ".cortex/" in line
        or "src/" in line
        or "`" in line
    ):
        return re.sub(r"\s+", " ", line).strip() or line.strip()
    compact = line
    for pattern, replacement in _SAFE_FILLER_PATTERNS:
        compact = re.sub(pattern, replacement, compact, flags=re.IGNORECASE)
    compact = re.sub(r"\s+", " ", compact).strip()
    return compact or line.strip()


def _fallback_compress_markdown(original: str) -> str:
    output_lines: list[str] = []
    in_fence = False
    for raw_line in original.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            output_lines.append(line)
            continue
        if in_fence or not stripped:
            output_lines.append(line)
            continue
        if stripped.startswith("#"):
            output_lines.append(line)
            continue
        if stripped.startswith("- "):
            output_lines.append(f"- {_compress_plain_line(stripped[2:])}")
            continue
        if stripped.startswith("* "):
            output_lines.append(f"* {_compress_plain_line(stripped[2:])}")
            continue
        numbered_match = re.match(r"^(\d+\.\s+)(.*)$", stripped)
        if numbered_match is not None:
            marker, body = numbered_match.groups()
            output_lines.append(f"{marker}{_compress_plain_line(body)}")
            continue
        output_lines.append(_compress_plain_line(line))
    return "\n".join(output_lines).strip()


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
    try:
        compressed = _run_claude_print(build_compress_prompt(original))
    except RuntimeError:
        # AI: Local fallback keeps one-time compression operable when external CLI is unavailable.
        compressed = _fallback_compress_markdown(original)
    validation_result = validate_compressed(original, compressed)

    retries = 0
    # AI: Retry only on structural validation failures; subprocess failures should fail fast.
    while not validation_result.is_valid and retries < _MAX_RETRIES:
        try:
            compressed = _run_claude_print(
                build_fix_prompt(original, compressed, validation_result.errors)
            )
        except RuntimeError:
            compressed = _fallback_compress_markdown(original)
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
    normalized_compressed = compressed.rstrip("\n") + "\n"
    if not dry_run:
        _ = path.write_text(normalized_compressed, encoding="utf-8")
        saved_backup = backup_path
    return CompressResult(
        success=True,
        path=path,
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
        restored = backup_path.read_text(encoding="utf-8").rstrip("\n") + "\n"
        _ = path.write_text(restored, encoding="utf-8")
        saved_backup = backup_path
    return CompressResult(
        success=False,
        path=path,
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
            success=False,
            path=path,
            skipped_reason=f"unsupported_file_type:{file_type}",
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
