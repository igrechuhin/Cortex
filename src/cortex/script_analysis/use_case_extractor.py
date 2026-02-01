"""Extract use cases from captured session scripts."""

import re

from cortex.script_analysis.models import UseCaseExtraction
from cortex.script_detection.models import ScriptCaptureRecord

# Keywords that map to common use-case labels (lowercase).
_USE_CASE_KEYWORDS: dict[str, str] = {
    "format": "format code",
    "lint": "lint code",
    "type_check": "type check",
    "type check": "type check",
    "test": "run tests",
    "pytest": "run tests",
    "validate": "validate",
    "analyze": "analyze",
    "migrate": "migrate",
    "fix": "fix",
    "check": "check",
    "build": "build",
    "shell": "shell utility",
    "script": "utility script",
}


def _normalize(s: str) -> str:
    """Lowercase and collapse whitespace."""
    return " ".join(re.split(r"\s+", s.strip().lower()))


def _keywords_from_text(text: str) -> list[str]:
    """Extract keywords from text (lowercase tokens, no punctuation)."""
    if not text:
        return []
    normalized = _normalize(text)
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return list(dict.fromkeys(tokens))[:20]


def _infer_label_from_keywords(keywords: list[str]) -> str:
    """Infer a short use-case label from keywords."""
    for kw in keywords:
        for pattern, label in _USE_CASE_KEYWORDS.items():
            if pattern in kw or kw in pattern:
                return label
    return "custom utility" if keywords else "session script"


def extract_use_case(record: ScriptCaptureRecord) -> UseCaseExtraction:
    """Extract use case label and keywords from a capture record.

    Uses task_description, usage_context, purpose, script_path, and
    a sample of script_content to infer a short label and keyword list.

    Args:
        record: Captured script record.

    Returns:
        UseCaseExtraction with use_case_label and keywords.
    """
    parts: list[str] = []
    if record.task_description:
        parts.append(record.task_description)
    if record.usage_context:
        parts.append(record.usage_context)
    if record.purpose:
        parts.append(record.purpose)
    if record.script_path:
        parts.append(record.script_path)

    combined = " ".join(parts)
    content_sample = (record.script_content or "")[:2000]
    full_text = combined + " " + content_sample

    keywords = _keywords_from_text(full_text)
    label = _infer_label_from_keywords(keywords)
    if not keywords and combined.strip():
        label = _normalize(combined)[:60] or "session script"

    return UseCaseExtraction(use_case_label=label, keywords=keywords)
