"""Language detection for pre-commit checks.

Extracted from pre_commit_helpers to keep modules under 400 lines.
"""

import json
from pathlib import Path

from cortex.core.models import OperationStatus
from cortex.core.path_resolver import has_memory_bank
from cortex.managers.initialization import get_project_root
from cortex.services.framework_adapters.detection import detect_language_at_path
from cortex.services.language_detector import LanguageInfo

_MAX_ANCESTOR_WALK = 20


def _create_error_result(msg: str, error_type: str = "ValueError") -> str:
    """Create error response JSON for language detection failures."""
    return json.dumps(
        {"status": OperationStatus.ERROR.value, "error": msg, "error_type": error_type},
        indent=2,
    )


def _detect_language_in_cortex_subdirs(
    candidate: Path,
) -> tuple[LanguageInfo, Path] | None:
    """Try detecting language in subdirs of a Cortex root (1–2 levels)."""
    try:
        for sub in candidate.iterdir():
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            if not has_memory_bank(sub):
                for sub2 in sub.iterdir():
                    if (
                        not sub2.is_dir()
                        or sub2.name.startswith(".")
                        or not has_memory_bank(sub2)
                    ):
                        continue
                    result = detect_language_at_path(sub2)
                    if result is not None:
                        return result
                continue
            result = detect_language_at_path(sub)
            if result is not None:
                return result
    except OSError:
        pass
    return None


def _detect_language_at_cortex_root(
    start_path: Path,
) -> tuple[LanguageInfo, Path] | None:
    """If start_path or an ancestor is a Cortex root, detect language there."""
    for candidate in [start_path, *list(start_path.parents)[:_MAX_ANCESTOR_WALK]]:
        if candidate == candidate.parent:
            continue
        if not has_memory_bank(candidate):
            continue
        result = detect_language_at_path(candidate)
        if result is not None:
            return result
        result = _detect_language_in_cortex_subdirs(candidate)
        if result is not None:
            return result
    return None


def _detect_language_from_ancestors(
    start_path: Path,
) -> tuple[LanguageInfo, Path] | None:
    """Walk up from start_path and run language detection until a language is found."""
    ancestors = [start_path, *list(start_path.parents)[:_MAX_ANCESTOR_WALK]]
    for candidate in ancestors:
        if candidate == candidate.parent:
            continue
        result = detect_language_at_path(candidate)
        if result is not None:
            return result
    return None


def _resolve_language_at_root(root_path: Path) -> tuple[LanguageInfo, str] | str:
    """Detect language at root or ancestors or Cortex root; return (info, root) or error str."""
    result = detect_language_at_path(root_path)
    if result is not None:
        info, path = result
        return (info, str(path))
    resolved = _detect_language_from_ancestors(root_path)
    if resolved is not None:
        info, path = resolved
        return (info, str(path))
    resolved = _detect_language_at_cortex_root(root_path)
    if resolved is not None:
        info, path = resolved
        return (info, str(path))
    msg = (
        "Could not detect project language. Pass language (e.g. 'python') "
        + "to execute_pre_commit_checks when invoking the tool."
    )
    return _create_error_result(msg)


def detect_or_use_language(
    language: str | None, root_str: str
) -> tuple[LanguageInfo, str] | str:
    """Detect language or use provided language.

    Returns (LanguageInfo, root_to_use) so the adapter runs in the correct
    project. Returns error JSON str on failure.
    Empty string is treated as auto-detect (same as None).
    """
    if language is None or language == "":
        return _resolve_language_at_root(Path(root_str).resolve())
    detected_language = language.lower()
    info = LanguageInfo(
        language=detected_language,
        test_framework=None,
        formatter=None,
        linter=None,
        type_checker=None,
        build_tool=None,
        confidence=0.5,
    )
    return (info, root_str)


def get_project_root_str(project_root: str | None) -> str:
    """Get project root as string."""
    root = get_project_root(project_root)
    return str(root)
