from __future__ import annotations

import logging
from pathlib import Path

from cortex.setup.claude_settings import (
    ensure_post_edit_hook_in_project_claude_settings,
)
from cortex.setup.hook_templates import HookTemplates
from cortex.setup.post_edit_hook_detection import detect_post_edit_hook_language

logger = logging.getLogger(__name__)


def apply_project_post_edit_hook(project_root: Path) -> tuple[str, bool]:
    """Detect language and apply project post-edit hook when supported."""
    detected_language = detect_post_edit_hook_language(project_root)
    hook_spec = HookTemplates.get_post_edit_hook(detected_language)

    if hook_spec is None:
        logger.warning(
            "No post-edit hook template for %s. Add one to .claude/settings.json manually.",
            detected_language,
        )
        return (detected_language, False)
    command, condition = hook_spec

    changed = ensure_post_edit_hook_in_project_claude_settings(
        project_root, command=command, condition=condition
    )
    return (detected_language, changed)
