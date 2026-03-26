from __future__ import annotations

from pathlib import Path

from cortex.services.language_detector import LanguageDetector
from cortex.setup.hook_templates import HookTemplates


def detect_post_edit_hook_language(project_root: Path) -> str:
    """Detect a hook template language key for the given project root.

    Returns a language key supported by HookTemplates, or "unknown" when
    no supported language can be detected.
    """
    detected = LanguageDetector(str(project_root)).detect_language()
    if detected is None:
        return "unknown"

    language = detected.language.strip().lower()
    return (
        language
        if HookTemplates.get_post_edit_hook(language) is not None
        else "unknown"
    )
