from __future__ import annotations

from cortex.services.language_quality_router import LanguageQualityRouter
from cortex.setup.hook_models import HookCondition


class HookTemplates:
    @classmethod
    def get_post_edit_hook(cls, language: str) -> tuple[str, HookCondition] | None:
        command = LanguageQualityRouter.get_post_edit_hook_command(language)
        if command is None:
            return None
        return (command, cls._default_condition(language))

    @classmethod
    def _default_condition(cls, language: str) -> HookCondition:
        normalized_language = language.strip().lower()
        if normalized_language == "python":
            return HookCondition(tool="Edit", pattern="**/*.py")
        if normalized_language == "typescript":
            return HookCondition(tool="Edit", pattern="**/*.ts")
        return HookCondition(tool="Edit")
