from __future__ import annotations

from pathlib import Path


def scaffold_language_scripts(project_root: Path, languages: list[str]) -> list[str]:
    scaffolded: list[str] = []

    for language in languages:
        if language == "swift":
            scaffolded.extend(_scaffold_swift_scripts(project_root))

    return scaffolded


def _scaffold_swift_scripts(project_root: Path) -> list[str]:
    swift_dir = project_root / ".cortex" / "synapse" / "scripts" / "swift"
    swift_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    created.extend(_write_text_if_missing(swift_dir / "README.md", _swift_readme()))
    created.extend(
        _write_executable_if_missing(
            swift_dir / "run_quality_check.sh", _swift_quality_script()
        )
    )
    return created


def _write_text_if_missing(path: Path, content: str) -> list[str]:
    if path.exists():
        return []
    _ = path.write_text(content, encoding="utf-8")
    return [str(path)]


def _write_executable_if_missing(path: Path, content: str) -> list[str]:
    created = _write_text_if_missing(path, content)
    if not created:
        return []

    try:
        current_mode = path.stat().st_mode
        path.chmod(current_mode | 0o111)
    except OSError:
        pass

    return created


def _swift_readme() -> str:
    return "\n".join(
        [
            "# Swift scripts (project-local)",
            "",
            "This folder contains Swift-native quality scripts used by Cortex.",
            "",
            "- `run_quality_check.sh`: a stub that runs `swift build` + `swift test`.",
            "  Customize it for your toolchain (SwiftPM, Xcodebuild, CI flags, etc.).",
            "",
        ]
    )


def _swift_quality_script() -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "",
            "swift build",
            "swift test",
            "",
        ]
    )
