from __future__ import annotations

from pathlib import Path

from cortex.services.framework_adapters.detection import detect_language_at_path
from cortex.setup.hook_templates import HookTemplates


def detect_post_edit_hook_language(project_root: Path) -> str:
    """Detect a hook template language key for the given project root.

    Returns a language key supported by HookTemplates, or "unknown" when
    no supported language can be detected.
    """
    detected = detect_language_at_path(project_root)
    if detected is None:
        return "unknown"
    info, _ = detected
    language = info.language.strip().lower()
    return (
        language
        if HookTemplates.get_post_edit_hook(language) is not None
        else "unknown"
    )
