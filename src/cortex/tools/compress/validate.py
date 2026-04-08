"""Structural validation for compressed Cortex text files."""

from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, Field

HEADING_PATTERN = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)
FENCED_CODE_PATTERN = re.compile(r"```[^\n]*\n[\s\S]*?```")
URL_PATTERN = re.compile(r"https?://\S+")
FILE_PATH_PATTERN = re.compile(r"(?:\.cortex|src)/[^\s]+")
LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+", re.MULTILINE)


class ValidationResult(BaseModel):
    """Result of compressed-content structural validation."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    token_ratio: float


def _extract_fenced_code_blocks(text: str) -> list[str]:
    return FENCED_CODE_PATTERN.findall(text)


def _collect_structure_errors(original: str, compressed: str) -> list[str]:
    errors: list[str] = []
    original_headings = HEADING_PATTERN.findall(original)
    compressed_headings = HEADING_PATTERN.findall(compressed)
    if original_headings != compressed_headings:
        errors.append("Heading count/order mismatch.")

    original_blocks = _extract_fenced_code_blocks(original)
    compressed_blocks_counter = Counter(_extract_fenced_code_blocks(compressed))
    # AI: Multiset comparison catches both missing and duplicated fenced blocks.
    for block in original_blocks:
        if compressed_blocks_counter[block] == 0:
            errors.append("Missing fenced code block from original content.")
            break
        compressed_blocks_counter[block] -= 1

    return errors


def _collect_reference_errors(original: str, compressed: str) -> list[str]:
    errors: list[str] = []
    original_urls = set(URL_PATTERN.findall(original))
    compressed_urls = set(URL_PATTERN.findall(compressed))
    if original_urls != compressed_urls:
        errors.append("URL set mismatch.")

    original_paths = set(FILE_PATH_PATTERN.findall(original))
    compressed_paths = set(FILE_PATH_PATTERN.findall(compressed))
    if original_paths != compressed_paths:
        errors.append("File path set mismatch.")

    return errors


def _validate_list_counts(
    original: str, compressed: str
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    original_list_count = len(LIST_ITEM_PATTERN.findall(original))
    compressed_list_count = len(LIST_ITEM_PATTERN.findall(compressed))
    if original_list_count > 0:
        min_allowed = original_list_count * 0.85
        max_allowed = original_list_count * 1.15
        if not (min_allowed <= compressed_list_count <= max_allowed):
            errors.append("Bullet/numbered list item count outside +/-15% tolerance.")
    elif compressed_list_count > 0:
        warnings.append(
            "Compressed content introduced list items where original had none."
        )

    return errors, warnings


def _compute_token_ratio(
    original: str, compressed: str
) -> tuple[float, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    original_tokens = len(original.split())
    compressed_tokens = len(compressed.split())
    if original_tokens == 0:
        token_ratio = 1.0
        warnings.append(
            "Original content has zero tokens; token reduction check skipped."
        )
    else:
        token_ratio = compressed_tokens / original_tokens
        if compressed_tokens >= original_tokens:
            errors.append("Compressed token count must be lower than original.")

    return token_ratio, errors, warnings


def validate_compressed(original: str, compressed: str) -> ValidationResult:
    """Validate compressed content against required structural invariants."""

    errors = _collect_structure_errors(original, compressed)
    errors.extend(_collect_reference_errors(original, compressed))
    list_errors, warnings = _validate_list_counts(original, compressed)
    errors.extend(list_errors)
    token_ratio, token_errors, token_warnings = _compute_token_ratio(
        original, compressed
    )
    errors.extend(token_errors)
    warnings.extend(token_warnings)

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        token_ratio=token_ratio,
    )
