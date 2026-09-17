"""Fresh assembly must not modify a user's install or canonical sources."""

from pathlib import Path
from zipfile import ZipFile

import pytest

from cortex.setup.plugin_package import WORKFLOWS, assemble, main


def _sources(tmp_path: Path) -> tuple[Path, Path, Path]:
    synapse = tmp_path / "canonical synapse"
    (synapse / "prompts").mkdir(parents=True)
    for filename in WORKFLOWS.values():
        _ = (synapse / "prompts" / filename).write_text(
            f"# Canonical {filename}\nDo not invent workflow steps.\n"
        )
    docs = tmp_path / "docs"
    (docs / "guides").mkdir(parents=True)
    _ = (docs / "guides/synapse-final-report-templates.md").write_text("# Reports\n")
    wheel = tmp_path / "cortex-0.2.0-py3-none-any.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr(
            "cortex-0.2.0.dist-info/METADATA", "Name: cortex\nVersion: 0.2.0\n"
        )
    return synapse, wheel, docs


def test_assembly_preserves_existing_settings_and_state(tmp_path: Path) -> None:
    synapse, wheel, docs = _sources(tmp_path)
    install = tmp_path / "user config"
    install.mkdir()
    settings = install / "settings.json"
    _ = settings.write_text('{"unrelated": true}')
    state = install / "session.json"
    _ = state.write_text('{"history": [1]}')

    with pytest.raises(FileExistsError):
        assemble(synapse, wheel, install, docs)

    assert settings.read_text() == '{"unrelated": true}'
    assert state.read_text() == '{"history": [1]}'
    assert not (install / "claude").exists()


def test_packages_retain_canonical_procedure_and_referenced_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    synapse, wheel, docs = _sources(tmp_path)
    output = tmp_path / "fresh packages"

    options = {"synapse": synapse, "wheel": wheel, "docs": docs, "output": output}
    argv = ["plugin_package"]
    for key, value in options.items():
        argv.extend([f"--{key}", str(value)])
    monkeypatch.setattr("sys.argv", argv)
    main()

    for host in ("claude", "codex"):
        root = output / host / "plugins/cortex"
        for name, filename in WORKFLOWS.items():
            assert (
                (root / "skills" / name / "SKILL.md")
                .read_text()
                .endswith((synapse / "prompts" / filename).read_text())
            )
        assert (root / "dist" / wheel.name).read_bytes() == wheel.read_bytes()
        assert (
            root / "docs/guides/synapse-final-report-templates.md"
        ).read_bytes() == (
            docs / "guides/synapse-final-report-templates.md"
        ).read_bytes()


@pytest.mark.parametrize("missing", ["wheel_metadata", "prompt", "report_template"])
def test_incomplete_inputs_leave_no_partial_package(
    tmp_path: Path, missing: str
) -> None:
    synapse, wheel, docs = _sources(tmp_path)
    output = tmp_path / "not-created"
    if missing == "wheel_metadata":
        with ZipFile(wheel, "w") as archive:
            archive.writestr("foreign-1.dist-info/METADATA", "Version: 1\n")
    elif missing == "prompt":
        (synapse / "prompts/plan.md").unlink()
    else:
        (docs / "guides/synapse-final-report-templates.md").unlink()

    with pytest.raises(ValueError):
        assemble(synapse, wheel, output, docs)

    assert not output.exists()
