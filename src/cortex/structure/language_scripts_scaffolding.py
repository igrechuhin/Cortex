from __future__ import annotations

from pathlib import Path

# Languages that have pre-built scripts in Synapse (no stubs needed).
_LANGUAGES_WITH_NATIVE_SCRIPTS: frozenset[str] = frozenset({"python", "swift"})


def scaffold_language_scripts(project_root: Path, languages: list[str]) -> list[str]:
    """Create script stubs for languages that have no native Synapse scripts.

    Python and Swift already ship full script packs in Synapse and are skipped.
    All other detected languages receive a ``README.md`` and a ``run_quality_check.sh``
    stub under ``.cortex/synapse/scripts/<lang>/`` so the native toolchain can be wired
    in without manual directory setup.
    """
    scaffolded: list[str] = []
    for language in languages:
        if language in _LANGUAGES_WITH_NATIVE_SCRIPTS:
            continue
        scripts_dir = project_root / ".cortex" / "synapse" / "scripts" / language
        scripts_dir.mkdir(parents=True, exist_ok=True)
        scaffolded.extend(
            _write_text_if_missing(scripts_dir / "README.md", _readme(language))
        )
        scaffolded.extend(
            _write_executable_if_missing(
                scripts_dir / "run_quality_check.sh", _quality_script(language)
            )
        )
    return scaffolded


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
        path.chmod(path.stat().st_mode | 0o111)
    except OSError:
        pass
    return created


# ---------------------------------------------------------------------------
# Per-language README templates
# ---------------------------------------------------------------------------

_LANGUAGE_HINTS: dict[str, str] = {
    "java": (
        "Replace the stub command with your build/test invocation, e.g.:\n"
        "  ./gradlew build test   # Gradle\n"
        "  ./mvnw verify          # Maven"
    ),
    "go": (
        "Replace the stub command with your build/test invocation, e.g.:\n"
        "  go build ./...\n"
        "  go test ./..."
    ),
    "rust": (
        "Replace the stub command with your build/test invocation, e.g.:\n"
        "  cargo build\n"
        "  cargo test"
    ),
    "typescript": (
        "Replace the stub command with your build/test invocation, e.g.:\n"
        "  npm run build\n"
        "  npm test"
    ),
    "javascript": (
        "Replace the stub command with your build/test invocation, e.g.:\n"
        "  npm run build\n"
        "  npm test"
    ),
}

_DEFAULT_HINT = "Replace the stub command with your project's quality-check invocation."


def _readme(language: str) -> str:
    hint = _LANGUAGE_HINTS.get(language, _DEFAULT_HINT)
    return "\n".join(
        [
            f"# {language.capitalize()} scripts (project-local)",
            "",
            f"This folder contains {language}-native quality scripts used by Cortex.",
            "",
            f"- `run_quality_check.sh`: stub script for {language} quality checks.",
            f"  {hint}",
            "",
        ]
    )


# ---------------------------------------------------------------------------
# Per-language quality-check script stubs
# ---------------------------------------------------------------------------

_LANGUAGE_QUALITY_COMMANDS: dict[str, list[str]] = {
    "java": [
        "# Replace with your build + test command",
        "# Examples: ./gradlew build test | ./mvnw verify",
    ],
    "go": ["go build ./...", "go test ./..."],
    "rust": ["cargo build", "cargo test"],
    "typescript": ["npm run build", "npm test"],
    "javascript": ["npm run build", "npm test"],
}

_DEFAULT_QUALITY_COMMANDS = [
    "# Add your project's quality-check command here",
]


def _quality_script(language: str) -> str:
    commands = _LANGUAGE_QUALITY_COMMANDS.get(language, _DEFAULT_QUALITY_COMMANDS)
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""] + commands + [""]
    return "\n".join(lines)
