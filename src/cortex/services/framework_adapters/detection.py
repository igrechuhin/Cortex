"""Language detection via framework adapters.

Reuses adapters for detection so "what is a Python/TypeScript/... project"
lives with each adapter; pre-commit logic stays language-agnostic.
"""

from pathlib import Path

from cortex.services.language_detector import LanguageInfo

from .base import FrameworkAdapter
from .csharp_adapter import CSharpAdapter
from .go_adapter import GoAdapter
from .java_adapter import JavaAdapter
from .javascript_adapter import JavaScriptAdapter
from .kotlin_adapter import KotlinAdapter
from .python_adapter import PythonAdapter
from .rust_adapter import RustAdapter
from .swift_adapter import SwiftAdapter
from .typescript_adapter import TypeScriptAdapter

# Adapters that support detect(); order can affect which language wins when multiple match.
_DETECTOR_ADAPTERS: tuple[type[FrameworkAdapter], ...] = (
    PythonAdapter,
    TypeScriptAdapter,
    JavaScriptAdapter,
    RustAdapter,
    GoAdapter,
    JavaAdapter,
    SwiftAdapter,
    KotlinAdapter,
    CSharpAdapter,
)


def detect_language_at_path(path: Path) -> tuple[LanguageInfo, Path] | None:
    """Detect language at the given path using framework adapters.

    Tries each adapter's detect(path); returns (LanguageInfo, path) for the
    first that recognizes the project. Reuses LanguageDetector inside adapters
    so marker logic stays in one place.

    Args:
        path: Candidate project root path.

    Returns:
        (LanguageInfo, path) if an adapter recognizes the project, None otherwise.
    """
    for adapter_cls in _DETECTOR_ADAPTERS:
        info = adapter_cls.detect(path)
        if info is not None:
            return (info, path)
    return None
