from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cortex.core.constants import LANGUAGE_POST_EDIT_HOOK_COMMANDS
from cortex.services.framework_adapters.base import FrameworkAdapter
from cortex.services.framework_adapters.csharp_adapter import CSharpAdapter
from cortex.services.framework_adapters.go_adapter import GoAdapter
from cortex.services.framework_adapters.java_adapter import JavaAdapter
from cortex.services.framework_adapters.javascript_adapter import JavaScriptAdapter
from cortex.services.framework_adapters.kotlin_adapter import KotlinAdapter
from cortex.services.framework_adapters.php_adapter import PhpAdapter
from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.framework_adapters.rust_adapter import RustAdapter
from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.services.framework_adapters.typescript_adapter import TypeScriptAdapter

AdapterFactory = Callable[[str | None], FrameworkAdapter]


@dataclass(frozen=True)
class LanguageQualityRoute:
    adapter_factory: AdapterFactory
    post_edit_hook_command: str | None


class LanguageQualityRouter:
    """Map detected language → framework adapter for pre-commit / quality gate.

    Used by inline checks, the detached ``pre_commit_worker`` (``run_quality_gate``),
    and post-edit hook template resolution.
    """

    _ROUTES: dict[str, LanguageQualityRoute] = {
        "python": LanguageQualityRoute(
            adapter_factory=lambda root: PythonAdapter(root),
            post_edit_hook_command=LANGUAGE_POST_EDIT_HOOK_COMMANDS.get("python"),
        ),
        "typescript": LanguageQualityRoute(
            adapter_factory=lambda root: TypeScriptAdapter(root),
            post_edit_hook_command=LANGUAGE_POST_EDIT_HOOK_COMMANDS.get("typescript"),
        ),
        "javascript": LanguageQualityRoute(
            adapter_factory=lambda root: JavaScriptAdapter(root),
            post_edit_hook_command=LANGUAGE_POST_EDIT_HOOK_COMMANDS.get("javascript"),
        ),
        "rust": LanguageQualityRoute(
            adapter_factory=lambda root: RustAdapter(root),
            post_edit_hook_command=LANGUAGE_POST_EDIT_HOOK_COMMANDS.get("rust"),
        ),
        "go": LanguageQualityRoute(
            adapter_factory=lambda root: GoAdapter(root),
            post_edit_hook_command=LANGUAGE_POST_EDIT_HOOK_COMMANDS.get("go"),
        ),
        "java": LanguageQualityRoute(
            adapter_factory=lambda root: JavaAdapter(root),
            post_edit_hook_command=LANGUAGE_POST_EDIT_HOOK_COMMANDS.get("java"),
        ),
        "swift": LanguageQualityRoute(
            adapter_factory=lambda root: SwiftAdapter(root),
            post_edit_hook_command=LANGUAGE_POST_EDIT_HOOK_COMMANDS.get("swift"),
        ),
        "kotlin": LanguageQualityRoute(
            adapter_factory=lambda root: KotlinAdapter(root),
            post_edit_hook_command=LANGUAGE_POST_EDIT_HOOK_COMMANDS.get("kotlin"),
        ),
        "php": LanguageQualityRoute(
            adapter_factory=lambda root: PhpAdapter(root),
            post_edit_hook_command=LANGUAGE_POST_EDIT_HOOK_COMMANDS.get("php"),
        ),
        "csharp": LanguageQualityRoute(
            adapter_factory=lambda root: CSharpAdapter(root),
            post_edit_hook_command=LANGUAGE_POST_EDIT_HOOK_COMMANDS.get("csharp"),
        ),
    }

    @classmethod
    def _normalize_language(cls, language: str) -> str:
        return language.strip().lower()

    @classmethod
    def adapter_registry(cls) -> dict[str, AdapterFactory]:
        return {
            language: route.adapter_factory for language, route in cls._ROUTES.items()
        }

    @classmethod
    def supported_languages(cls) -> tuple[str, ...]:
        return tuple(cls._ROUTES.keys())

    @classmethod
    def get_adapter(
        cls, language: str, project_root: str | None
    ) -> FrameworkAdapter | None:
        route = cls._ROUTES.get(cls._normalize_language(language))
        if route is None:
            return None
        return route.adapter_factory(project_root)

    @classmethod
    def get_post_edit_hook_command(cls, language: str) -> str | None:
        route = cls._ROUTES.get(cls._normalize_language(language))
        if route is None:
            return None
        return route.post_edit_hook_command
