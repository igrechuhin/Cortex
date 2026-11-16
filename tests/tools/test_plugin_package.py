"""Fresh assembly must not modify a user's install or canonical sources."""

import shlex
from pathlib import Path
from zipfile import ZipFile

import pytest

from cortex.setup import uv_launch
from cortex.setup.plugin_package import WORKFLOWS, assemble, main
from cortex.setup.uv_launch import UvLaunchDirectories, launch_directories
from tests.helpers.plugin_launch_models import read_plugin_launch


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


def test_generated_do_skill_fails_closed_on_opaque_agent_handles(
    tmp_path: Path,
) -> None:
    synapse, wheel, docs = _sources(tmp_path)
    canonical = (
        Path(__file__).parents[2] / ".cortex" / "synapse" / "prompts" / WORKFLOWS["do"]
    ).read_text(encoding="utf-8")
    _ = (synapse / "prompts" / WORKFLOWS["do"]).write_text(canonical, encoding="utf-8")
    output = tmp_path / "packages"

    assemble(synapse, wheel, output, docs)

    for host in ("claude", "codex"):
        skill = (output / host / "plugins/cortex/skills/do/SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "const result = await agent(instruction, options)" in skill
        assert "await handle.wait(600)" in skill
        assert "opaque handles can serialize as\n`{}`" in skill
        assert "SUBAGENT_HANDLE_INVALID" in skill
        assert "SUBAGENT_HANDLE_UNRECOVERABLE" in skill
        assert "wait([" not in skill


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


def test_uv_launch_defaults_preserve_existing_commands(tmp_path: Path) -> None:
    synapse, wheel, docs = _sources(tmp_path)
    output = tmp_path / "legacy"
    assemble(synapse, wheel, output, docs)
    assert launch_directories(None, None) is None
    for host in ("claude", "codex"):
        server, hook = read_plugin_launch(output / host / "plugins/cortex")
        assert server.command == "uv"
        assert server.env == {"CORTEX_NATIVE_WORKFLOWS": "1"}
        assert hook.command.startswith("uv tool run --from ")
        assert hook.timeout == 15


def test_explicit_uv_paths_match_mcp_and_quoted_startup(tmp_path: Path) -> None:
    synapse, wheel, docs = _sources(tmp_path)
    output = tmp_path / "new plugin ; $(literal)"
    selected = UvLaunchDirectories(
        cache_dir=tmp_path / "cache space ; $(literal) 'quote'",
        tool_dir=tmp_path / "tools space & `literal`",
    )
    assemble(synapse, wheel, output, docs, uv_directories=selected)
    for host in ("claude", "codex"):
        server, hook = read_plugin_launch(output / host / "plugins/cortex")
        tokens = shlex.split(hook.command)
        assert tokens[:3] == [
            "env",
            *[f"{key}={value}" for key, value in selected.environment().items()],
        ]
        assert tokens[3:6] == ["uv", "tool", "run"]
        for key, value in selected.environment().items():
            assert server.env[key] == value
        macro = "${CLAUDE_PLUGIN_ROOT}" if host == "claude" else "${PLUGIN_ROOT}"
        assert f'"{macro}/dist/{wheel.name}"' in hook.command
    assert not selected.cache_dir.exists() and not selected.tool_dir.exists()


@pytest.mark.parametrize(
    "invalid",
    ["relative/path", "/", "/tmp/../escape", "/tmp/new\nline", "/tmp/null\0byte"],
)
def test_invalid_uv_paths_fail_without_output(tmp_path: Path, invalid: str) -> None:
    output = tmp_path / "not-created"
    with pytest.raises(ValueError):
        directories = UvLaunchDirectories.model_validate(
            {"cache_dir": invalid, "tool_dir": tmp_path / "tools"}
        )
        synapse, wheel, docs = _sources(tmp_path)
        assemble(synapse, wheel, output, docs, uv_directories=directories)
    assert not output.exists()


@pytest.mark.parametrize(
    "cache,tools",
    [
        (None, "/tmp/tools"),
        ("/tmp/cache", None),
        ("/tmp/state", "/tmp/state"),
        ("/tmp/state", "/tmp/state/tools"),
    ],
)
def test_incomplete_or_overlapping_uv_directories_rejected(
    cache: str | None, tools: str | None
) -> None:
    with pytest.raises(ValueError):
        _ = launch_directories(
            Path(cache) if cache else None, Path(tools) if tools else None
        )


def test_opt_in_posix_contract_rejects_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(uv_launch, "POSIX_LAUNCH_SUPPORTED", False)
    with pytest.raises(ValueError, match="POSIX"):
        _ = UvLaunchDirectories(
            cache_dir=tmp_path / "cache", tool_dir=tmp_path / "tools"
        )


def test_partial_cli_uv_pair_creates_no_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synapse, wheel, docs = _sources(tmp_path)
    output = tmp_path / "not-created"
    monkeypatch.setattr(
        "sys.argv",
        [
            "plugin_package",
            "--synapse",
            str(synapse),
            "--wheel",
            str(wheel),
            "--docs",
            str(docs),
            "--output",
            str(output),
            "--uv-cache-dir",
            str(tmp_path / "cache"),
        ],
    )
    with pytest.raises(ValueError, match="both"):
        main()
    assert not output.exists()
