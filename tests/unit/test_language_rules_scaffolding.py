from pathlib import Path

from cortex.structure.language_rules_scaffolding import (
    scaffold_language_rules_from_templates,
)


def test_scaffold_language_rules_from_templates_copies_missing_rules(
    tmp_path: Path,
) -> None:
    templates_dir = tmp_path / ".cortex" / "synapse" / "rules" / "_templates" / "swift"
    templates_dir.mkdir(parents=True, exist_ok=True)
    template_rule = templates_dir / "swift-style.mdc"
    _ = template_rule.write_text("# style", encoding="utf-8")

    scaffolded = scaffold_language_rules_from_templates(tmp_path, ["swift"])

    scaffolded_rule = (
        tmp_path / ".cortex" / "synapse" / "rules" / "swift" / "swift-style.mdc"
    )
    assert scaffolded_rule.exists()
    assert scaffolded_rule.read_text(encoding="utf-8") == "# style"
    assert scaffolded == [str(scaffolded_rule)]


def test_scaffold_language_rules_from_templates_skips_existing_rule(
    tmp_path: Path,
) -> None:
    templates_dir = tmp_path / ".cortex" / "synapse" / "rules" / "_templates" / "swift"
    templates_dir.mkdir(parents=True, exist_ok=True)
    _ = (templates_dir / "swift-style.mdc").write_text("# template", encoding="utf-8")

    destination_dir = tmp_path / ".cortex" / "synapse" / "rules" / "swift"
    destination_dir.mkdir(parents=True, exist_ok=True)
    existing_rule = destination_dir / "swift-style.mdc"
    _ = existing_rule.write_text("# existing", encoding="utf-8")

    scaffolded = scaffold_language_rules_from_templates(tmp_path, ["swift"])

    assert scaffolded == []
    assert existing_rule.read_text(encoding="utf-8") == "# existing"


def test_scaffold_language_rules_from_templates_supports_multiple_languages(
    tmp_path: Path,
) -> None:
    ts_templates_dir = (
        tmp_path / ".cortex" / "synapse" / "rules" / "_templates" / "typescript"
    )
    ts_templates_dir.mkdir(parents=True, exist_ok=True)
    _ = (ts_templates_dir / "typescript-coding-standards.mdc").write_text(
        "# ts", encoding="utf-8"
    )
    go_templates_dir = tmp_path / ".cortex" / "synapse" / "rules" / "_templates" / "go"
    go_templates_dir.mkdir(parents=True, exist_ok=True)
    _ = (go_templates_dir / "go-coding-standards.mdc").write_text(
        "# go", encoding="utf-8"
    )

    scaffolded = scaffold_language_rules_from_templates(tmp_path, ["typescript", "go"])

    ts_rule = (
        tmp_path
        / ".cortex"
        / "synapse"
        / "rules"
        / "typescript"
        / "typescript-coding-standards.mdc"
    )
    go_rule = (
        tmp_path / ".cortex" / "synapse" / "rules" / "go" / "go-coding-standards.mdc"
    )
    assert ts_rule.exists()
    assert go_rule.exists()
    assert ts_rule.read_text(encoding="utf-8") == "# ts"
    assert go_rule.read_text(encoding="utf-8") == "# go"
    assert scaffolded == [str(ts_rule), str(go_rule)]
