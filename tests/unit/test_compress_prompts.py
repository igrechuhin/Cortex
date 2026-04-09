"""Unit tests for compression prompt builders."""

from cortex.tools.compress.prompts import build_compress_prompt, build_fix_prompt


def test_build_compress_prompt_includes_required_rules() -> None:
    # Arrange
    original = "# Title\nBody text.\n"

    # Act
    prompt = build_compress_prompt(original)

    # Assert
    assert "Compress the following Markdown technical documentation." in prompt
    assert "Drop articles, filler phrases, hedging, pleasantries" in prompt
    assert "Keep verbatim (byte-for-byte)" in prompt
    assert "Target at least 35% token reduction" in prompt
    assert "Output compressed document only" in prompt
    assert "Original content:\n# Title\nBody text.\n" in prompt


def test_build_fix_prompt_lists_errors_and_payloads() -> None:
    # Arrange
    original = "# Original\n"
    compressed = "# Compressed\n"
    errors = ["Heading count/order mismatch.", "URL set mismatch."]

    # Act
    prompt = build_fix_prompt(original, compressed, errors)

    # Assert
    assert "The previous compression failed validation." in prompt
    assert "Meaning and completeness take priority over token reduction" in prompt
    assert "Keep verbatim (byte-for-byte)" in prompt
    assert "- Heading count/order mismatch." in prompt
    assert "- URL set mismatch." in prompt
    assert "Original content:\n# Original\n" in prompt
    assert "Current compressed content:\n# Compressed\n" in prompt


def test_fix_prompt_prioritizes_meaning() -> None:
    # Arrange
    original = "# Doc\nSome prose.\n"
    compressed = "# Doc\n"
    errors = ["Compressed token count must be lower than original."]

    # Act
    prompt = build_fix_prompt(original, compressed, errors)

    # Assert
    assert "Meaning and completeness take priority over token reduction" in prompt
    assert "restore any content that was removed to achieve compression" in prompt
