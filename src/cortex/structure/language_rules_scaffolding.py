from __future__ import annotations

from pathlib import Path


def scaffold_language_rules_from_templates(
    project_root: Path, languages: list[str]
) -> list[str]:
    """Copy language rule templates into project rule folders when missing."""
    scaffolded: list[str] = []

    for language in languages:
        templates_dir = (
            project_root / ".cortex" / "synapse" / "rules" / "_templates" / language
        )
        if not templates_dir.exists():
            continue

        destination_dir = project_root / ".cortex" / "synapse" / "rules" / language
        destination_dir.mkdir(parents=True, exist_ok=True)

        for template_file in sorted(templates_dir.glob("*.mdc")):
            destination_file = destination_dir / template_file.name
            if destination_file.exists():
                continue
            content = template_file.read_text(encoding="utf-8")
            _ = destination_file.write_text(content, encoding="utf-8")
            scaffolded.append(str(destination_file))

    return scaffolded
