from __future__ import annotations

from pathlib import Path


def detect_languages_for_migration(project_root: Path) -> list[str]:
    """Detect migration scaffold languages using marker-based priority.

    Priority is aligned with the migration roadmap:
    swift -> typescript/javascript -> java -> rust -> go -> python.
    Multiple languages can be returned when multiple markers are present.
    """

    detected: list[str] = []

    if (project_root / "Package.swift").exists():
        detected.append("swift")

    has_package_json = (project_root / "package.json").exists()
    has_tsconfig = (project_root / "tsconfig.json").exists()
    if has_package_json or has_tsconfig:
        if has_tsconfig:
            detected.append("typescript")
        elif has_package_json:
            detected.append("javascript")

    if (project_root / "pom.xml").exists() or (project_root / "build.gradle").exists():
        detected.append("java")

    if (project_root / "Cargo.toml").exists():
        detected.append("rust")

    if (project_root / "go.mod").exists():
        detected.append("go")

    if _has_python_sources(project_root):
        detected.append("python")

    return detected


def _has_python_sources(project_root: Path) -> bool:
    return (
        (project_root / "pyproject.toml").exists()
        or (project_root / "setup.py").exists()
        or bool(list(project_root.glob("*.py")))
    )
