"""
Text similarity and content utilities for consolidation detection.

Extracted from consolidation_detector.py for file size compliance.
"""

import hashlib
import re
from difflib import SequenceMatcher


def compute_content_hash(content: str) -> str:
    """
    Compute fast hash of content for quick equality checks.

    Performance: O(n) where n is content length.
    Uses SHA-256 for collision resistance.

    Args:
        content: Text content to hash

    Returns:
        Hex digest of content hash
    """
    return hashlib.sha256(content.encode()).hexdigest()


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts."""
    return SequenceMatcher(None, text1, text2).ratio()


def extract_common_content(text1: str, text2: str) -> str:
    """Extract common content from two texts."""
    matcher = SequenceMatcher(None, text1, text2)
    common_parts: list[str] = []

    for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if tag == "equal":
            common_parts.append(text1[i1:i2])

    return "".join(common_parts)


def extract_common_content_multi(texts: list[str]) -> str:
    """Extract common content from multiple texts."""
    if not texts:
        return ""

    common = texts[0]
    for text in texts[1:]:
        common = extract_common_content(common, text)

    return common


def get_differences(text1: str, text2: str) -> list[str]:
    """Get list of differences between two texts."""
    matcher = SequenceMatcher(None, text1, text2)
    differences: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            differences.append(f"{tag}: '{text1[i1:i2]}' vs '{text2[j1:j2]}'")

    return differences[:5]  # Limit to first 5 differences


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def find_common_prefix(strings: list[str]) -> str:
    """Find common prefix in list of strings."""
    if not strings:
        return ""

    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix) and prefix:
            prefix = prefix[:-1]

    return prefix
