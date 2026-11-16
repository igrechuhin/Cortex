"""Assemble local host plugins from a built wheel and canonical Synapse sources."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

from cortex.setup.uv_launch import UvLaunchDirectories, launch_directories

WORKFLOWS = {
    "plan": "plan.md",
    "do": "do-loop.md",
    "review": "review.md",
    "commit": "commit.md",
}


def _json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _wheel_version(wheel: Path) -> str:
    with ZipFile(wheel) as archive:
        names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
        if len(names) != 1 or not names[0].startswith("cortex-"):
            raise ValueError("Expected a built Cortex wheel")
        metadata = archive.read(names[0]).decode("utf-8")
    return next(
        line.removeprefix("Version: ")
        for line in metadata.splitlines()
        if line.startswith("Version: ")
    )


def _skills(root: Path, synapse: Path) -> None:
    for name, filename in WORKFLOWS.items():
        source = (synapse / "prompts" / filename).read_text(encoding="utf-8")
        target = root / "skills" / name / "SKILL.md"
        target.parent.mkdir(parents=True)
        header = (
            f"---\nname: {name}\ndescription: Explicit Cortex {name} workflow\n"
            "disable-model-invocation: true\n---\n\n"
            "For read-only canonical prompt/rule/script references beginning "
            ".cortex/synapse/, resolve ../../synapse/ relative to this SKILL.md; "
            "resolve docs/ references under ../../docs/. This applies recursively "
            "when reading packaged prompts. Never write or run Git in the package. "
            "Project Git/state paths remain in the workspace; submodule steps apply "
            "only to an actual project-owned Synapse Git submodule. "
            "Use canonical Markdown when host-specific Workflow tools are unavailable. "
            "Discovery is not authorization: commit and push each require explicit "
            "user authorization for that action, even if the procedure says otherwise.\n\n"
        )
        _ = target.write_text(header + source, encoding="utf-8")


def _precompact_hook(host: str) -> dict[str, object]:
    server = "plugin:cortex:cortex" if host == "claude" else "cortex"
    payload: dict[str, object] = {
        "host": host,
        "event": "PreCompact",
        "cwd": "${cwd}",
        "session_id": "${session_id}",
        "trigger": "${trigger}",
        "transcript_path": "${transcript_path}",
    }
    if host == "codex":
        payload["turn_id"] = "${turn_id}"
    return {
        "type": "mcp_tool",
        "server": server,
        "tool": "session",
        "input": {"operation": "hook", "hook_event": payload},
        "timeout": 15,
    }


def _wheel_requirement(root: Path, host: str, wheel: Path) -> str:
    installed = root.resolve() / "dist" / wheel.name
    # Codex MCP does not expand plugin-root variables. A local file URI also
    # prevents uv from treating a path's semicolon as a requirement marker.
    if host == "codex" or any(char in str(installed) for char in ";%#?"):
        return installed.as_uri()
    return f"${{CLAUDE_PLUGIN_ROOT}}/dist/{wheel.name}"


def _hooks(
    root: Path, host: str, wheel: Path, uv_directories: UvLaunchDirectories | None
) -> dict[str, object]:
    wheel_requirement = _wheel_requirement(root, host, wheel)
    startup = {
        "type": "command",
        "command": (uv_directories.hook_prefix() if uv_directories else "")
        + f'uv tool run --from "{wheel_requirement}" python -m cortex.setup.plugin_start {host}',
        "timeout": 15,
    }
    return {
        "hooks": {
            "SessionStart": [{"matcher": "startup|resume", "hooks": [startup]}],
            "PreCompact": [
                {"matcher": "manual|auto", "hooks": [_precompact_hook(host)]}
            ],
        }
    }


def _mcp_server(
    root: Path, host: str, wheel: Path, uv_directories: UvLaunchDirectories | None
) -> dict[str, object]:
    wheel_requirement = _wheel_requirement(root, host, wheel)
    return {
        "command": "uv",
        "args": [
            "tool",
            "run",
            "--from",
            wheel_requirement,
            "python",
            "-m",
            "cortex.setup.plugin_server",
        ],
        "env": {
            "CORTEX_NATIVE_WORKFLOWS": "1",
            **(uv_directories.environment() if uv_directories else {}),
        },
    }


def _manifest(
    root: Path,
    host: str,
    wheel: Path,
    version: str,
    uv_directories: UvLaunchDirectories | None,
) -> None:
    identity: dict[str, object] = {
        "name": "cortex",
        "version": version,
        "description": "Canonical Cortex workflows and bounded session handoffs",
        "author": {"name": "Cortex"},
    }
    if host == "claude":
        _json(root / ".claude-plugin/plugin.json", identity)
    else:
        identity.update(
            {
                "skills": "./skills/",
                "hooks": "./hooks/hooks.json",
                "mcpServers": "./.mcp.json",
            }
        )
        _json(root / ".codex-plugin/plugin.json", identity)
    _json(
        root / ".mcp.json",
        {"mcpServers": {"cortex": _mcp_server(root, host, wheel, uv_directories)}},
    )
    _json(root / "hooks/hooks.json", _hooks(root, host, wheel, uv_directories))


def _marketplace(output: Path, host: str) -> None:
    entry: dict[str, object] = {"name": "cortex", "source": "./plugins/cortex"}
    if host == "codex":
        entry.update(
            {
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Productivity",
            }
        )
    directory = ".claude-plugin" if host == "claude" else ".agents/plugins"
    catalog: dict[str, object] = {"name": "cortex-local", "plugins": [entry]}
    if host == "claude":
        catalog["owner"] = {"name": "Cortex"}
    _json(output / directory / "marketplace.json", catalog)


def _assembly_report_template(synapse: Path, docs: Path, output: Path) -> Path:
    for filename in WORKFLOWS.values():
        if not (synapse / "prompts" / filename).is_file():
            raise ValueError(f"Missing canonical prompt: {filename}")
    report_template = docs / "guides/synapse-final-report-templates.md"
    if not report_template.is_file():
        raise ValueError("Missing canonical final-report template in --docs")
    if output.exists():
        raise FileExistsError(f"Build into a new directory: {output}")
    return report_template


def assemble(
    synapse: Path,
    wheel: Path,
    output: Path,
    docs: Path,
    *,
    uv_directories: UvLaunchDirectories | None = None,
) -> None:
    """Create a fresh distribution; never merge into user settings or existing assets."""
    synapse, wheel, output = synapse.resolve(), wheel.resolve(), output.absolute()
    if uv_directories is not None:
        uv_directories = UvLaunchDirectories.model_validate(uv_directories)
    version = _wheel_version(wheel)
    report_template = _assembly_report_template(synapse, docs, output)
    for host in ("claude", "codex"):
        root = output / host / "plugins/cortex"
        (root / "dist").mkdir(parents=True)
        _ = shutil.copy2(wheel, root / "dist" / wheel.name)
        _ = shutil.copytree(
            synapse,
            root / "synapse",
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"),
        )
        (root / "docs/guides").mkdir(parents=True)
        _ = shutil.copy2(report_template, root / "docs/guides" / report_template.name)
        _skills(root, synapse)
        _manifest(root, host, wheel, version, uv_directories)
        _marketplace(output / host, host)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--synapse", type=Path, required=True)
    _ = parser.add_argument("--wheel", type=Path, required=True)
    _ = parser.add_argument("--output", type=Path, required=True)
    _ = parser.add_argument("--docs", type=Path, required=True)
    _ = parser.add_argument("--uv-cache-dir", type=Path)
    _ = parser.add_argument("--uv-tool-dir", type=Path)
    args = parser.parse_args()
    directories = launch_directories(args.uv_cache_dir, args.uv_tool_dir)
    assemble(
        args.synapse, args.wheel, args.output, args.docs, uv_directories=directories
    )


if __name__ == "__main__":
    main()
