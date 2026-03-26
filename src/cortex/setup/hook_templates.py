from __future__ import annotations

from cortex.services.language_quality_router import LanguageQualityRouter


class HookTemplates:
    @classmethod
    def get_post_edit_hook(cls, language: str) -> str | None:
        return LanguageQualityRouter.get_post_edit_hook_command(language)
